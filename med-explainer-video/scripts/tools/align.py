"""逐字时刻：已知台词原文 + 录音 wav → 每个字的起止秒。
默认用 whisper 词级时间（tools/asr.py，不需要额外安装）：识别结果按拼音和原文逐字配对，配不上的字在前后已知时刻之间按字数插值。
装了 torch + torchaudio 时自动改用 MMS_FA 强制对齐（中文转无调拼音逐字对齐，精度约 20 ms）；KEPU_ALIGN=whisper 强制用前者。
whisper 中文词级时间只作参考：timeline.py 还会把字幕块起点吸附到波形开口点（snap_onsets）。"""
import os, re, difflib, functools
from pypinyin import lazy_pinyin

DIG = dict(zip('0123456789', ['ling', 'yi', 'er', 'san', 'si', 'wu', 'liu', 'qi', 'ba', 'jiu']))
ASCII = {'a': 'ei', 'b': 'bi', 'c': 'xi', 'd': 'di', 'e': 'yi', 'g': 'ji', 'i': 'ai', 't': 'ti', 'u': 'you', 'r': 'a', 'x': 'aikesi'}
def units(text):
    """把原文拆成可对齐单元：[(原文下标, 罗马化拼音)]；标点不参与对齐。"""
    out = []
    for i, ch in enumerate(text):
        if '一' <= ch <= '鿿': out.append((i, lazy_pinyin(ch)[0].replace('ü', 'v').replace('v', 'u')))
        elif ch.isdigit(): out.append((i, DIG[ch]))
        elif ch == '.' and 0 < i < len(text) - 1 and text[i - 1].isdigit() and text[i + 1].isdigit(): out.append((i, 'dian'))
        elif ch.isascii() and ch.isalpha(): out.append((i, ASCII.get(ch.lower(), ch.lower())))
    return out

def _finish(text, st, en, total):
    """st / en：{原文下标: 秒} → 长度 = len(text) 的两个列表；标点取下一个字的起点"""
    n = len(text); starts = [None] * n; ends = [None] * n; nxt = None
    for i in range(n - 1, -1, -1):
        if i in st: nxt = (st[i], en[i])
        starts[i] = st.get(i, nxt[0] if nxt else total); ends[i] = en.get(i, starts[i])
    return starts, ends

@functools.lru_cache(1)
def _mms():
    import torchaudio
    b = torchaudio.pipelines.MMS_FA
    return b, b.get_model(with_star=False).eval(), b.get_tokenizer(), b.get_aligner()

def align_mms(text, wav):
    import torch, torchaudio, soundfile as sf
    b, model, tok, aligner = _mms()
    a, sr = sf.read(str(wav)); a = a if a.ndim == 1 else a.mean(1)
    x = torchaudio.functional.resample(torch.tensor(a, dtype=torch.float32)[None], sr, b.sample_rate)
    u = units(text); words = [w for _, w in u]
    with torch.inference_mode():
        em, _ = model(x)
        spans = aligner(em[0], tok(words))
    ratio = x.shape[1] / em.shape[1] / b.sample_rate
    st = {i: s[0].start * ratio for (i, _), s in zip(u, spans)}; en = {i: s[-1].end * ratio for (i, _), s in zip(u, spans)}
    return _finish(text, st, en, len(a) / sr)

def align_whisper(text, wav, asr_result=None, prompt=None):
    import soundfile as sf
    total = sf.info(str(wav)).duration
    if asr_result is None or not any(s.get('words') for s in asr_result.get('segments', [])):
        from asr import transcribe
        asr_result = transcribe(wav, initial_prompt=prompt, word_timestamps=True)
    hyp = []   # [(拼音, 起, 止)]：一个词里的几个字平分这个词的时长
    for s in asr_result['segments']:
        for w in s.get('words') or []:
            chars = [c for c in w['word'] if '一' <= c <= '鿿' or c.isalnum()]
            if not chars: continue
            d = (w['end'] - w['start']) / len(chars)
            for k, c in enumerate(chars):
                p = DIG.get(c) or (lazy_pinyin(c)[0].replace('ü', 'u').replace('v', 'u') if '一' <= c <= '鿿' else ASCII.get(c.lower(), c.lower()))
                hyp.append((p, w['start'] + k * d, w['start'] + (k + 1) * d))
    u = units(text); st, en = {}, {}
    sm = difflib.SequenceMatcher(None, [p for _, p in u], [p for p, _, _ in hyp], autojunk=False)
    for a, b, n in sm.get_matching_blocks():
        for k in range(n): i = u[a + k][0]; st[i], en[i] = hyp[b + k][1], hyp[b + k][2]
    # 配不上的字：在前后已知时刻之间按字数线性插值
    idx = [i for i, _ in u]; known = [i for i in idx if i in st]
    if not known:   # 一个字都没认出来：按字数均分整段
        step = total / max(1, len(idx))
        for k, i in enumerate(idx): st[i], en[i] = k * step, (k + 1) * step
        return _finish(text, st, en, total)
    for k, i in enumerate(idx):
        if i in st: continue
        prev = next((j for j in reversed(idx[:k]) if j in st), None); nxt = next((j for j in idx[k + 1:] if j in st), None)
        t0 = en[prev] if prev is not None else 0.0; t1 = st[nxt] if nxt is not None else total
        gap = [j for j in idx if (prev is None or j > prev) and (nxt is None or j < nxt)]; m = gap.index(i); d = max(0.0, t1 - t0) / len(gap)
        st[i], en[i] = t0 + m * d, t0 + (m + 1) * d
    return _finish(text, st, en, total)

def snap_phrases(text, starts, ends, wav):
    """whisper 词级时间整体偏早（实测约 0.1–0.15 s）、句中停顿处也不准：用波形校正。
    在录音里找停顿（低于峰值 5% 的静音 ≥ 60 ms，与 subcheck 同一判据）；原文每个标点处、whisper 估计时刻 ±0.6 s 内最近的停顿当分界，
    分界把整句切成短语：短语起点 = 停顿后第一个出声点，终点 = 下一个停顿开始；短语内各字按 whisper 的相对时长重新铺进去。"""
    import numpy as np, soundfile as sf
    a, sr = sf.read(str(wav)); a = a if a.ndim == 1 else a.mean(1); hop = int(0.005 * sr)
    rms = np.sqrt(np.convolve(a ** 2, np.ones(hop * 2) / (hop * 2), 'same')[::hop]); thr = rms.max() * 0.05; on = rms > thr
    idx = np.where(on)[0]
    if not len(idx): return starts, ends
    f0, f1 = idx[0], idx[-1] + 1; pauses = []; i = f0
    while i < f1:
        if not on[i]:
            j = i
            while j < f1 and not on[j]: j += 1
            if j - i >= 12: pauses.append((i * 0.005, j * 0.005))
            i = j
        else: i += 1
    u = [i for i, ch in enumerate(text) if '一' <= ch <= '鿿' or ch.isalnum()]
    if not u: return starts, ends
    cuts, used = [], set()   # [(短语最后一个字的下标, 停顿起, 停顿止)]
    for k in range(len(u) - 1):
        a_, b_ = u[k], u[k + 1]
        if b_ - a_ == 1: continue   # 两字之间没有标点
        tb = (ends[a_] + starts[b_]) / 2
        cand = [(max(0.0, p0 - tb, tb - p1), n) for n, (p0, p1) in enumerate(pauses) if n not in used and (not cuts or p0 >= cuts[-1][2])]
        if not cand: continue
        d, n = min(cand)
        if d <= 0.6: used.add(n); cuts.append((a_, pauses[n][0], pauses[n][1]))
    S, E = list(starts), list(ends)
    bounds = [(-1, None, f0 * 0.005)] + cuts + [(u[-1], f1 * 0.005, None)]
    for (pa, _, t0), (la, t1, _) in zip(bounds[:-1], bounds[1:]):
        chars = [i for i in u if pa < i <= la]
        if not chars or t1 is None or t0 is None or t1 <= t0: continue
        w0, w1 = starts[chars[0]], ends[chars[-1]]; span = max(1e-3, w1 - w0)
        for i in chars:
            S[i] = t0 + (starts[i] - w0) / span * (t1 - t0); E[i] = t0 + (ends[i] - w0) / span * (t1 - t0)
    nxt = None   # 标点取下一个字的起点
    for i in range(len(text) - 1, -1, -1):
        if i in u: nxt = S[i]
        else: S[i] = E[i] = nxt if nxt is not None else E[i]
    return S, E

def align(text, wav, asr_result=None, prompt=None):
    """返回 (starts, ends)：长度 = len(text)"""
    if os.environ.get('KEPU_ALIGN', '').lower() != 'whisper':
        try:
            import torch, torchaudio  # noqa: F401
            return align_mms(text, wav)
        except Exception:
            pass
    s, e = align_whisper(text, wav, asr_result, prompt)
    return snap_phrases(text, s, e, wav)

if __name__ == '__main__':
    import sys
    t = sys.argv[1]; w = sys.argv[2]; s, e = align(t, w)
    print([(ch, round(a, 2)) for ch, a in zip(t, s)])

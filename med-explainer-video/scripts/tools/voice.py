#!/usr/bin/env python3
"""用户自己配音：台词本 → 录音导入 → audio/lines/{scene}_{i}.wav + lines.json（timeline.py 直接用）。

  python tools/voice.py script              出 audio/台词本.md / .docx（按角色分组：每句的文件名、台词、读音提示、语气、参考时长）
  python tools/voice.py draft [--all]       草稿配音：还没录音的句子先用合成声顶上（audio/draft/<句>.mp3），只为预演对节奏；正式成片不许用（render final 会拒绝）
        用微软 Edge 在线朗读（pip 包 edge-tts，要联网，台词文本会发给这个在线服务——先问过用户）。voices[who].draft_voice 可指定音色。
  python tools/voice.py import [s03_2 …] [--reimport]
        读 audio/recordings/ 里的录音（wav / m4a / mp3 / aac / flac / ogg 都行），四种放法任选，同一句以前面的为准：
          s03_2.m4a          一句一个文件（文件名 = 场景_句号）
          s03_laozhang.m4a   某场某角色的全部台词，按顺序读，句间停 1.5 秒以上
          s03.m4a            某场的全部台词（所有角色），按顺序读，句间停 1.5 秒以上
          laozhang.m4a       某角色全片的全部台词，按台词本顺序读，句间停 1.5 秒以上
        → 转 48 kHz 单声道、轻度降噪、切掉首尾静音、句中长停顿压短、停顿处压底噪、响度统一 −16 LUFS
        → whisper 回读和台词逐字比（拼音相似度、长度比、关键词、多出来的语气词）→ 逐字时刻
        录音不齐：已有的照常处理并缓存，缺的列出来，退出码 6（不写 lines.json，timeline 用不了）。
        某句没有录音、但 audio/draft/ 里有草稿配音：用草稿顶上（lines.json 里 engine = draft）；录音补上后重新导入就自动换成录音。
storyboard 里与配音相关的字段：voices[who].actor（谁来配）/ desc（嗓音要求）；tts.asr_prompt（回读提示词，只写领域）；tts.must（必须读对的关键词拼音）；
tts.min_pinyin（拼音相似度门限，默认 0.92）；tts.ear_confirmed（回读没过、但人耳听过没问题的句子）；design.say_overrides / lines[].say（读音提示）。"""
import json, re, sys, subprocess, difflib, hashlib
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import ROOT, load_sb, asr_prompt, emo_notes
from pypinyin import lazy_pinyin, pinyin, Style

SB = load_sb()
REC = ROOT / 'audio/recordings'; DRAFT = ROOT / 'audio/draft'; OUT = ROOT / 'audio/lines'; WORK = OUT / 'work'
EXTS = ('.wav', '.m4a', '.mp3', '.aac', '.flac', '.ogg', '.opus', '.wma', '.amr', '.mp4', '.mov')
TTS = SB.get('tts') or {}; MUST = TTS.get('must') or {}; MIN_PY = float(TTS.get('min_pinyin', 0.92))
SAY = (SB.get('design') or {}).get('say_overrides') or {}
EMO = emo_notes(SB); V = SB.get('voices') or {}; CH = SB.get('characters') or {}
LINES = [(sc['id'], i, ln) for sc in SB['scenes'] for i, ln in enumerate(sc['lines'])]
POLY = set('长重发行处血尿膀脉泌便量刺系解薄削传调应好差数中结塞弹泡卡扎晕曲没得着还觉都为乐和间')   # 常读错的多音字：台词本里给出本句的读音

def kid(sid, i): return f'{sid}_{i}'
def name_of(who): return (CH.get(who) or {}).get('name') or who
def say_text(ln):
    t = ln.get('say', ln['text'])
    for a, b in SAY.items(): t = t.replace(a, b)
    return t

# ---------------- 台词本 ----------------
def pron_hints(ln):
    text, say = ln['text'], say_text(ln); hints = []
    if say != text and len(say) == len(text):
        for k, (a, b) in enumerate(zip(text, say)):
            if a != b and '一' <= a <= '鿿': hints.append(f"{a} 读 {pinyin(say[max(0, k - 1):k + 2], style=Style.TONE)[min(1, k)][0]}")
    elif say != text: hints.append(f'照这样读：{say}')
    py = pinyin(say if len(say) == len(text) else text, style=Style.TONE)
    for k, ch in enumerate(text):
        if ch in POLY and not any(h.startswith(ch + ' ') for h in hints) and k < len(py): hints.append(f'{ch} {py[k][0]}')
    return '；'.join(dict.fromkeys(hints))
def han(s): return re.sub(r'[^一-鿿A-Za-z0-9]', '', s)

def cmd_script():
    title = SB.get('title', SB['project']); rows = {}
    for sid, i, ln in LINES: rows.setdefault(ln['who'], []).append((sid, i, ln))
    L = [f'# {title} · 台词本（录音用）', '',
         '## 怎么录', '',
         '- 安静的房间，手机或电脑录音都行；嘴离话筒一拳远，别对着话筒吹气；先录 10 秒试听，没有电流声、回声再正式录。',
         '- 语速放慢：大约每秒 4.5 个字（下表“参考时长”），老年观众也听得清；宁慢勿快。',
         '- 按“读音提示”读；没把握的字先查。',
         '- 文件放进 `audio/recordings/`，格式随意（m4a、mp3、wav 都行）。三种放法任选：',
         '  1. **一句一个文件**：文件名用下表第一列，例如 `s01_0.m4a`。重录某一句也用这种。',
         '  2. **一个角色一个文件**：按本台词本该角色的顺序一口气读完，**句与句之间停 1.5 秒以上**，文件名用角色代号，例如 `narrator.m4a`。',
         '  3. **一场一个文件**：`s03.m4a`（这一场全部台词按顺序）或 `s03_laozhang.m4a`（这一场某个角色的台词）。',
         '- 读错了就停 2 秒，从这一句开头重读；导入时会逐句回读核对，对不上的句子会列出来，单独重录那几句即可（一句一个文件会覆盖整段文件里的那一句）。', '']
    for who, items in rows.items():
        v = V.get(who) or {}; secs = sum(len(han(ln['text'])) for _, _, ln in items) / 4.5
        L += [f"## {name_of(who)}（文件名代号 `{who}`）", '',
              f"配音：{v.get('actor') or '（待定）'}　嗓音：{v.get('desc') or (CH.get(who) or {}).get('desc') or '—'}　共 {len(items)} 句，约 {secs:.0f} 秒", '',
              '| 文件名 | 台词 | 读音提示 | 语气 | 参考时长 |', '|---|---|---|---|---|']
        for sid, i, ln in items:
            tone = (EMO.get(ln.get('emo')) or '') + (ln.get('tts_note') or '')
            L.append(f"| `{kid(sid, i)}` | {ln['text']} | {pron_hints(ln) or ''} | {tone} | {len(han(ln['text'])) / 4.5:.1f} 秒 |")
        L.append('')
    (ROOT / 'audio').mkdir(exist_ok=True); REC.mkdir(parents=True, exist_ok=True)
    f = ROOT / 'audio/台词本.md'; f.write_text('\n'.join(L) + '\n'); print(f'台词本：{f.relative_to(ROOT).as_posix()}（{len(LINES)} 句，{len(rows)} 个角色）')
    try:
        from md2docx import convert
        if convert(f): print('        audio/台词本.docx（发给配音的人用）')
    except Exception as e: print(f'  （台词本 docx 没出成：{e}）')

# ---------------- 音频处理 ----------------
def ff(args): subprocess.run(['ffmpeg', '-v', 'error', '-y', *map(str, args)], check=True)
def lufs(f):
    r = subprocess.run(['ffmpeg', '-hide_banner', '-i', str(f), '-af', 'ebur128', '-f', 'null', '-'], capture_output=True, text=True, encoding='utf-8', errors='ignore').stderr
    return float(re.findall(r'I:\s+(-?[\d.]+) LUFS', r)[-1])
def decode(src, dst):   # 任意格式 → 48 kHz 单声道 wav；去 70 Hz 以下低频；轻度频域降噪（跟踪底噪）
    ff(['-i', src, '-vn', '-af', 'highpass=f=70,afftdn=nr=10:nf=-45:tn=1', '-ar', '48000', '-ac', '1', '-c:a', 'pcm_s16le', dst])

def frames_db(a, sr, hop_s=0.01):
    import numpy as np
    hop = int(hop_s * sr); n = max(1, len(a) // hop)
    e = np.sqrt(np.add.reduceat(a[:n * hop] ** 2, np.arange(0, n * hop, hop)) / hop) if n * hop else np.zeros(1)
    return 20 * np.log10(e + 1e-9), hop
def voiced_mask(db):
    """语音帧：高于底噪（第 10 百分位）+ 12 dB，且不低于峰值 −45 dB"""
    import numpy as np
    floor = np.percentile(db, 10); return db > max(floor + 12, db.max() - 45)

def split_by_pauses(wav, k):
    """一个文件里按顺序读了 k 句 → 取最长的 k−1 个停顿做分界 → [(起, 止)] 秒。停顿短于 0.5 s 的分界会提示"""
    import numpy as np, soundfile as sf
    a, sr = sf.read(str(wav)); db, hop = frames_db(a, sr); v = voiced_mask(db)
    idx = np.where(v)[0]
    if not len(idx): return None, '整段没有声音'
    first, last = idx[0], idx[-1]; runs = []; i = first
    while i <= last:
        if not v[i]:
            j = i
            while j <= last and not v[j]: j += 1
            runs.append((j - i, i, j)); i = j
        else: i += 1
    if len(runs) < k - 1: return None, f'只找到 {len(runs) + 1} 段话，台词有 {k} 句（句间停顿要 1.5 秒以上）'
    cuts = sorted(sorted(runs, reverse=True)[:k - 1], key=lambda r: r[1])
    warn = [f'第 {n + 1}、{n + 2} 句之间只停了 {r[0] * hop / sr:.2f} 秒' for n, r in enumerate(cuts) if r[0] * hop / sr < 0.5]
    bounds = [first] + [(r[1] + r[2]) // 2 for r in cuts] + [last + 1]
    segs = [(bounds[n] * hop / sr, bounds[n + 1] * hop / sr) for n in range(k)]
    return segs, '；'.join(warn)

def tidy(src, dst, who):
    """切首尾静音（留 80 ms）、句中长停顿压到 0.4 s（旁白）/ 0.35 s（角色）、停顿处压底噪 −24 dB"""
    import numpy as np, soundfile as sf
    a, sr = sf.read(str(src)); db, hop = frames_db(a, sr); v = voiced_mask(db)
    idx = np.where(v)[0]
    if not len(idx): raise RuntimeError('没有声音')
    pad = int(0.08 * sr / hop); i0, i1 = max(0, idx[0] - pad), min(len(v), idx[-1] + 1 + pad)
    keep = np.zeros(len(v), bool); keep[i0:i1] = True
    cap = int((0.4 if who == 'narrator' else 0.35) * sr / hop); i = i0
    while i < i1:   # 压短长停顿：只保留开头 cap/2 和结尾 cap/2 帧
        if not v[i]:
            j = i
            while j < i1 and not v[j]: j += 1
            if j - i > cap: keep[i + cap // 2: j - cap // 2] = False
            i = j
        else: i += 1
    k6 = 6; vd = np.array([v[max(0, n - k6):n + k6 + 1].any() for n in range(len(v))])   # 语音帧前后各护 60 ms
    g = np.repeat(np.where(vd, 1.0, 10 ** (-24 / 20)), hop)[:len(a)]; g = np.pad(g, (0, len(a) - len(g)), constant_values=g[-1] if len(g) else 1.0)
    w = int(0.015 * sr); g = np.convolve(g, np.ones(w) / w, 'same'); y = a * g
    m = np.repeat(keep, hop)[:len(y)]; m = np.pad(m, (0, len(y) - len(m)), constant_values=False)
    sf.write(str(dst), y[m], sr)

def finalize(src, dst):
    """响度统一 −16 LUFS、限幅、首尾淡入淡出并各留 40 ms 空白（防“咔哒”）"""
    g = -16 - lufs(src)
    ff(['-i', src, '-af', f'volume={g:.2f}dB,alimiter=limit=0.89:level=false,afade=t=in:d=0.012,areverse,afade=t=in:d=0.025,areverse,adelay=40,apad=pad_dur=0.04', '-ar', '48000', '-ac', '1', '-c:a', 'pcm_s16le', dst])

# ---------------- 回读核对 ----------------
CN = '零一二三四五六七八九'
def num2cn(m):
    s = m.group(0)
    if '.' in s: a, b = s.split('.'); return num2cn(re.match(r'\d+', a)) + '点' + ''.join(CN[int(c)] for c in b)
    n = int(s)
    if n < 10: return CN[n]
    out, units, ds = '', ['', '十', '百', '千'], [int(c) for c in str(n)]
    for k, d in enumerate(ds):
        u = units[len(ds) - 1 - k]
        if d: out += CN[d] + u
        elif out and not out.endswith('零'): out += '零'
    out = out.rstrip('零'); return out[1:] if n < 20 and out.startswith('一十') else out
def norm(s): s = re.sub(r'(\d+(?:\.\d+)?)\s*[%％]', r'百分之\1', s); s = re.sub(r'\d+(\.\d+)?', num2cn, s).replace('℃', '摄氏度'); return ''.join(ch for ch in s if '一' <= ch <= '鿿')
def py(s, tone=False): return lazy_pinyin(norm(s), style=Style.TONE3, neutral_tone_with_five=True) if tone else lazy_pinyin(norm(s))
def sim(a, b): return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()
def judge(ln, k, wav, res):
    import soundfile as sf
    text = ln['text']; hyp = res['text']; d = sf.info(str(wav)).duration
    ratio = len(norm(hyp)) / max(1, len(norm(text))); s0 = sim(py(text), py(hyp)); st = sim(py(text, True), py(hyp, True)); hz = sim(norm(text), norm(hyp))
    pyt = lambda s: ' '.join(py(s, True))
    must_ok = all(pyt(hyp).count(m) >= max(1, pyt(text).count(m)) for m in MUST.get(k, []))
    extra = [ch for ch in '啊呀哎唉哦嗯嘿哇噢诶呃' if ch in hyp and ch not in text]
    ok = 0.88 <= ratio <= 1.15 and s0 >= MIN_PY and must_ok
    cps = len(norm(text)) / max(0.1, d - 0.08)
    note = []
    if not 0.88 <= ratio <= 1.15: note.append('多读或漏读' if ratio > 1 else '漏读或没读完')
    if s0 < MIN_PY: note.append('和台词对不上')
    if not must_ok: note.append('关键词没读对：' + '、'.join(MUST.get(k, [])))
    if extra: note.append('多了语气词 ' + ''.join(extra) + '（不一定错，听一下）')
    if cps > 5.6: note.append(f'语速偏快（{cps:.1f} 字/秒）')
    return dict(ok=ok, asr=hyp, hz=round(hz, 3), ratio=round(ratio, 2), py=round(s0, 3), tone=round(st, 3), seconds=round(d, 3), cps=round(cps, 2), must_ok=must_ok, extra=extra, note='；'.join(note))

# ---------------- 导入 ----------------
def find_sources():
    files = {f.stem: f for f in sorted(REC.iterdir()) if f.is_file() and f.suffix.lower() in EXTS} if REC.is_dir() else {}
    plan, groups = {}, {}
    order = {}
    for sid, i, ln in LINES:
        k = kid(sid, i)
        for key, members in ((k, None), (f"{sid}_{ln['who']}", lambda s, w, x=sid, y=ln['who']: s == x and w == y), (sid, lambda s, w, x=sid: s == x), (ln['who'], lambda s, w, y=ln['who']: w == y)):
            if key in files:
                if members is None: plan[k] = (files[key], None)
                else:
                    grp = groups.setdefault(key, [kid(s, j) for s, j, l in LINES if members(s, l['who'])])
                    plan[k] = (files[key], grp.index(k), len(grp))
                break
        if k not in plan:   # 这句没有录音：有草稿配音就先用草稿
            for ext in ('.mp3', '.wav'):
                if (DRAFT / (k + ext)).exists(): plan[k] = (DRAFT / (k + ext), None); break
    return plan, files

def sig(f, extra=''): st = f.stat(); return f'{f.name}:{st.st_size}:{int(st.st_mtime)}:{extra}'

def cmd_import(argv):
    import soundfile as sf
    from align import align
    only = {a for a in argv if not a.startswith('--')}; force = '--reimport' in argv
    OUT.mkdir(parents=True, exist_ok=True); WORK.mkdir(parents=True, exist_ok=True)
    cache_f = OUT / 'import_cache.json'; cache = json.loads(cache_f.read_text()) if cache_f.exists() else {}
    plan, files = find_sources(); missing = [kid(s, i) for s, i, _ in LINES if kid(s, i) not in plan]
    used = {p[0].stem for p in plan.values() if p[0].parent != DRAFT}; unknown = [n for n in files if n not in used]
    if unknown: print(f'  !! audio/recordings/ 里这些文件对不上任何台词，没用：{unknown}（文件名用台词本第一列、场景号、或角色代号）')
    split_cache = {}; rows = []; EAR = set(TTS.get('ear_confirmed') or [])
    prompt = asr_prompt(SB)
    for sid, i, ln in LINES:
        k = kid(sid, i)
        if k not in plan: continue
        src = plan[k]; f = src[0]
        key = hashlib.sha1(f"{sig(f, '' if src[1] is None else f'{src[1]}/{src[2]}')}|{ln['text']}|{ln['who']}".encode()).hexdigest()[:16]
        wav = OUT / f'{k}.wav'
        if not force and k not in only and cache.get(k, {}).get('key') == key and wav.exists():
            rows.append(cache[k]['row']); print(f'  {k} 沿用（录音没变）'); continue
        dec = WORK / f'{f.stem}.dec.wav'
        if f.stem not in split_cache:
            decode(f, dec); split_cache[f.stem] = None
            if src[1] is not None:
                segs, warn = split_by_pauses(dec, src[2]); split_cache[f.stem] = segs
                if segs is None: print(f'  !! {f.name}：切不开（{warn}）——改成一句一个文件，或句间多停一会儿再录'); continue
                if warn: print(f'  !! {f.name}：{warn}（分句可能不准，看回读结果）')
        piece = WORK / f'{k}.raw.wav'
        if src[1] is None: piece = dec
        else:
            segs = split_cache[f.stem]
            if segs is None: continue
            a, sr = sf.read(str(dec)); t0, t1 = segs[src[1]]; sf.write(str(piece), a[int(t0 * sr):int(t1 * sr)], sr)
        tid = WORK / f'{k}.tidy.wav'
        try: tidy(piece, tid, ln['who'])
        except RuntimeError as e: print(f'  !! {k}：{e}（{f.name}）'); continue
        finalize(tid, wav)
        from asr import transcribe
        res = transcribe(wav, initial_prompt=prompt, word_timestamps=True)
        j = judge(ln, k, wav, res); ct, ce = align(ln['text'], wav, asr_result=res, prompt=prompt)
        row = {'scene': sid, 'i': i, 'who': ln['who'], 'emo': ln.get('emo'), 'engine': 'draft' if f.parent == DRAFT else 'recording', 'voice': (V.get(ln['who']) or {}).get('actor') or ln['who'], 'text': ln['text'], 'say': say_text(ln),
               'file': wav.relative_to(ROOT).as_posix(), 'source': f.name + ('' if src[1] is None else f' 第 {src[1] + 1}/{src[2]} 段'), 'seconds': j['seconds'], 'tempo': 1.0, 'seed': None,
               'passed': j['ok'], 'asr': j['asr'], 'hanzi_match': j['hz'], 'len_ratio': j['ratio'], 'pinyin_match': j['py'], 'tone_match': j['tone'], 'cps': j['cps'], 'note': j['note'], 'f0': None,
               'ct': [round(x, 3) for x in ct], 'ce': [round(x, 3) for x in ce]}
        cache[k] = {'key': key, 'row': row}; rows.append(row)
        for p in (tid,) + ((piece,) if piece != dec else ()): p.unlink(missing_ok=True)
        print(f"  {k} {ln['who']:10s} {'OK ' if j['ok'] else 'xx '} 拼音 {j['py']} 长度比 {j['ratio']} {j['cps']} 字/秒 {j['seconds']} s | {j['asr']}" + (f"  ← {j['note']}" if j['note'] else ''), flush=True)
    cache_f.write_text(json.dumps(cache, ensure_ascii=False, indent=1))
    for p in WORK.glob('*.dec.wav'): p.unlink(missing_ok=True)
    for r in rows: r['ear_ok'] = f"{r['scene']}_{r['i']}" in EAR
    done = {f"{r['scene']}_{r['i']}" for r in rows}; lack = [kid(s, i) for s, i, _ in LINES if kid(s, i) not in done]
    if lack:
        (OUT / 'lines.partial.json').write_text(json.dumps(rows, ensure_ascii=False, indent=1))
        print(f"\n录音还缺 {len(lack)} 句：{'、'.join(lack[:40])}{' …' if len(lack) > 40 else ''}\n  照 audio/台词本.md 录好放进 audio/recordings/ 再导入（已处理的 {len(rows)} 句已缓存）")
        sys.exit(6)
    (OUT / 'lines.partial.json').unlink(missing_ok=True)
    (OUT / 'lines.json').write_text(json.dumps(rows, ensure_ascii=False, indent=1))
    bad = [f"{r['scene']}_{r['i']}" for r in rows if not r['passed'] and not r['ear_ok'] and r['engine'] != 'draft']
    tot = sum(r['seconds'] for r in rows); chars = sum(len(norm(r['text'])) for r in rows)
    print(f'\n配音 {len(rows)} 句，总长 {tot:.1f} s，平均 {chars / max(1, tot):.1f} 字/秒；回读没过且未人耳确认：{bad or "无"}')
    nd = sum(r['engine'] == 'draft' for r in rows)
    if nd: print(f'  其中 {nd} 句是草稿配音（合成声）：只能出预演；正式成片前照 audio/台词本.md 录好这些句子再导入')

# ---------------- 草稿配音 ----------------
DRAFT_VOICES = {'narrator': 'zh-CN-XiaoxiaoNeural'}; DRAFT_POOL = ['zh-CN-YunxiNeural', 'zh-CN-XiaoyiNeural', 'zh-CN-YunjianNeural', 'zh-CN-YunyangNeural']
def draft_voice(who):
    v = (V.get(who) or {}).get('draft_voice')
    if v: return v
    if who in DRAFT_VOICES: return DRAFT_VOICES[who]
    others = [w for w in dict.fromkeys(ln['who'] for _, _, ln in LINES) if w not in DRAFT_VOICES and not (V.get(w) or {}).get('draft_voice')]
    return DRAFT_POOL[others.index(who) % len(DRAFT_POOL)]
def cmd_draft(argv):
    try: import edge_tts   # noqa: F401
    except ImportError: sys.exit('草稿配音要装 edge-tts：python -m pip install edge-tts（要联网；台词文本会发给微软的在线朗读服务）。不想用就直接录音。')
    plan, _ = find_sources(); DRAFT.mkdir(parents=True, exist_ok=True)
    meta_f = DRAFT / 'draft.json'; meta = json.loads(meta_f.read_text()) if meta_f.exists() else {}
    n = fail = 0
    for sid, i, ln in LINES:
        k = kid(sid, i); out = DRAFT / f'{k}.mp3'; voice = draft_voice(ln['who']); want = f"{voice}|{say_text(ln)}"
        real = k in plan and plan[k][0].parent != DRAFT
        if real and '--all' not in argv:   # 已有真录音：不出草稿，旧草稿删掉
            out.unlink(missing_ok=True); meta.pop(k, None); continue
        if out.exists() and meta.get(k) == want: continue
        for attempt in range(3):   # 在线服务偶尔断一下：重试两次
            r = subprocess.run([sys.executable, '-m', 'edge_tts', '--voice', voice, '--rate=-8%', '--text', say_text(ln), '--write-media', str(out)], capture_output=True, text=True)
            if r.returncode == 0 and out.exists() and out.stat().st_size >= 800: break
            import time; time.sleep(2 + 3 * attempt)
        if r.returncode or not out.exists() or out.stat().st_size < 800:
            fail += 1; out.unlink(missing_ok=True); print(f"  !! {k} 草稿配音没出成：{(r.stderr or '').strip().splitlines()[-1][:160] if (r.stderr or '').strip() else '没有声音返回'}"); continue
        meta[k] = want; n += 1; print(f'  {k} {ln["who"]:10s} 草稿 {voice}', flush=True)
    meta_f.write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    print(f'草稿配音：新出 {n} 句' + (f'，{fail} 句失败（多半是没联网，过会儿再跑）' if fail else '') + '。接着跑 voice（导入）。草稿只用于预演，正式成片必须换成真人录音。')
    if fail: sys.exit(2)

if __name__ == '__main__':
    a = sys.argv[1:]
    if not a or a[0] not in ('script', 'import', 'draft'): sys.exit(__doc__)
    {'script': lambda: cmd_script(), 'import': lambda: cmd_import(a[1:]), 'draft': lambda: cmd_draft(a[1:])}[a[0]]()

#!/usr/bin/env python3
"""storyboard + audio/lines/lines.json → render/timeline.json（ORIENT=land：render/land/timeline.json，画幅/字幕块字数/字卡格数按 layout_land.json，封面用 cover.hold_land，片尾追加参考文献页 sref）
场景/台词绝对时间；字幕块与标签、cue 都按强制对齐的字级时间戳定位（tools/align.py，MMS_FA）。
--estimate：无音频时按 5 字/秒估算（先调画面用）。运行：python tools/timeline.py [--estimate]
可调参数全部来自 storyboard.timing（场首/场尾留白、片尾时长、句间停顿）、storyboard.subtitle_numbers（字幕里的数字写法）、layout.json（字幕每块最多字数、字卡默认张数）。"""
import json, sys, re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import ROOT, load_sb, load_layout, card_stays, ORIENT, LAND, render_dir
SB = load_sb(); LAYOUT = load_layout()
EST = '--estimate' in sys.argv
LINES = {} if EST else {(r['scene'], r['i']): r for r in json.loads((ROOT / 'audio/lines/lines.json').read_text())}
TM = SB.get('timing', {})
LEAD, TAIL, OUTRO = TM.get('lead', 0.26), TM.get('tail', 0.36), TM.get('outro', 5.0)          # 场首留白、场尾留白、片尾卡
GAP_SAME, GAP_SWITCH = TM.get('gap_same', 0.12), TM.get('gap_switch', 0.28)                   # 同一角色连说 / 换人说话 的句间停顿
EST_RATE = TM.get('est_chars_per_s', 5.0)
PAUSE = '，。；：！？、…—“”'
MAXC = int((LAYOUT.get('subtitle') or {}).get('max_chars', 11))   # 单行字幕最多字数：floor(字幕最大宽 / 字号)，由 layout.json 决定
SUBL = LAYOUT.get('subtitle') or {}
def maxc_for(who):
    """角色台词（带名牌的行）按名牌宽度折算：(max_width − 名牌宽) / 字号，且至少比 MAXC 少 1；旁白 / 无名牌角色用 MAXC"""
    ch = (SB.get('characters') or {}).get(who) or {}
    if who == 'narrator' or ch.get('no_badge'): return MAXC
    name = ch.get('name') or who; badge = SUBL.get('name_size', 36) * len(name) + 34 + 18
    return max(4, min(MAXC - 1, int((SUBL.get('max_width', 840) - badge) // SUBL.get('size', 74))))
MAXL = int((LAYOUT.get('labels') or {}).get('max_default', 2))    # 字卡默认同屏张数
LBC = LAYOUT.get('labels') or {}
MOS = int(LBC.get('max_on_screen') or 0)                            # 同屏上限（方案二：3；0 = 不限）
MIN_STAY, MIN_STAY_ALERT = float(LBC.get('min_stay', 2.5)), float(LBC.get('min_stay_alert', 3.5))   # 字卡停留下限（普通 / 危险信号）
MAX_EXT = float(TM.get('max_extend', 2.0))                          # 场景结束导致停留不足时，每场最多延长的秒数（无旁白、配乐继续）
EXTRA = int(LBC.get('extra_rows') or 0)                             # 横屏要点板：同屏格数再加 extra_rows（竖屏 0）
BIG_SLOT = LBC.get('style') != 'board'                              # 竖屏标签卡 big 占第 0 格；横屏要点板 big 是板头、不占格
CARD_STAYS, WARN = [], []
def norm(s): return re.sub(r'[^一-鿿A-Za-z0-9.]', '', s)

def char_times(text, wav, dur, row):
    if EST:
        w = [0.0 if (ch in PAUSE or not norm(ch)) else 1.0 for ch in text]; tot = sum(w) or 1; acc = 0; st = []
        for x in w: st.append(dur * acc / tot); acc += x
        return st, [min(dur, x + dur / tot) for x in st]
    return row['ct'], row['ce']

def make_chunks(text, st, en, br=(), maxc=None):
    maxc = maxc or MAXC
    """字幕分块：按标点断句 → 超长句在 jieba 词边界处均衡切分 → 过短的块与相邻块合并。每块带发声起止。"""
    import jieba; jieba.setLogLevel(60)
    forced = set()
    for b in br:
        k = text.find(b); assert k >= 0, f'字幕断点找不到：{b} in {text}'; forced.add(k + len(b))
    phrases, cur = [], []
    for i, ch in enumerate(text):
        if i in forced and cur: phrases.append(cur); cur = []
        if ch in PAUSE:
            if cur: phrases.append(cur); cur = []
        else: cur.append(i)
    if cur: phrases.append(cur)
    pieces = []
    for ph in phrases:
        s0 = ''.join(text[i] for i in ph)
        if len(ph) <= maxc: pieces.append(ph); continue
        k = -(-len(ph) // maxc); target = len(ph) / k
        bounds, pos = [], 0
        for w in jieba.cut(s0): pos += len(w); bounds.append(pos)
        cuts, last = [], 0
        for j in range(1, k):
            want = target * j; c = min((b for b in bounds if last < b < len(ph)), key=lambda b: abs(b - want)); cuts.append(c); last = c
        for x, y in zip([0] + cuts, cuts + [len(ph)]): pieces.append(ph[x:y])
    merged = []
    for pc in pieces:
        between = text[merged[-1][-1] + 1:pc[0]] if merged else ''
        if merged and pc[0] not in forced and not any(f in forced for f in range(merged[-1][-1] + 1, pc[0] + 1)) and (len(merged[-1]) <= 4 or len(pc) <= 3) and len(merged[-1]) + len(pc) + 1 <= maxc and st[pc[0]] - en[merged[-1][-1]] < 0.5 and not any(q in between for q in '。；！？'):
            merged[-1] = merged[-1] + pc
        else: merged.append(pc)
    out = []
    for pc in merged:
        raw = text[pc[0]:pc[-1] + 1]
        disp = re.sub(r'[，、；：]', ' ', raw).replace('“', '').replace('”', '').replace('——', ' ').replace('……', ' ').replace('…', ' ').strip()
        disp = re.sub(r'\s+', ' ', disp)
        nxt = text[pc[-1] + 1:pc[-1] + 3]
        if nxt[:1] in '？！' : disp += nxt[:1]
        elif nxt[:1] == '”' and nxt[1:2] in '？！': disp += nxt[1:2]
        out.append({'text': disp, 'start': round(st[pc[0]], 3), 'end': round(en[pc[-1]], 3), 'k0': pc[0], 'k1': pc[-1]})
    return out

SNAP = str(TM.get('snap_onsets') or 'v2').lower()   # 'legacy' = 10-24 前的吸附（只给要逐位复现旧时间轴的专题用）
def snap_onsets(chs, wav):
    """停顿后的字幕块：起点吸附到波形上的真实开口点，避免对齐模型给出的起点偏晚。
    v2（10-24）：从对齐起点往回找“含这一点的那段声音”的起头——段内短于 40 ms 的低谷（塞音闭塞）不算断开；往回最多 300 ms、不越过上一块末字的对齐终点；
      起头前面必须是静音（真开口），否则不动。旧版（storyboard.timing.snap_onsets: "legacy"）取对齐起点前 300 ms 窗口里的第一个上升沿：
      上一块末字的开口、句中换气声落在窗口里就被吸过去，字幕早出 0.1–0.3 s（10-24 普查：nocturia 10 块、foam 15、psa 3、bph_on_template 22）。"""
    import numpy as np, soundfile as sf
    a, sr = sf.read(str(wav)); hop = int(0.005 * sr)
    rms = np.sqrt(np.convolve(a ** 2, np.ones(hop * 2) / (hop * 2), 'same')[::hop]); thr = rms.max() * 0.05
    first = next((q for q in range(len(rms)) if rms[q] > thr), 0) * 0.005
    chs[0]['start'] = round(min(chs[0]['start'], first), 3)          # 首块：从第一个出声点开始（叹词常被对齐模型判晚）
    for k, ch in enumerate(chs):
        i = int(ch['start'] / 0.005); pre = rms[max(0, i - 40):max(1, i - 6)]
        if k == 0 or len(pre) < 10 or pre.mean() > thr: continue
        if SNAP == 'legacy':
            j0 = max(0, i - 60); seg = rms[j0:i + 30]
            on = next((q for q in range(1, len(seg)) if seg[q] > thr and seg[q - 1] <= thr), None)
            if on is not None: ch['start'] = round(min(ch['start'], (j0 + on) * 0.005), 3)
            continue
        lb = max(0, i - 60, int(chs[k - 1]['end'] / 0.005)); q, quiet, on = min(i + 1, len(rms)), 0, None   # 从对齐起点所在的那一帧查起；此时 chs[k-1]['end'] 还是对齐终点（块尾在下面才延长）
        while q > lb:
            q -= 1
            if rms[q] > thr: on, quiet = q, 0
            else:
                quiet += 1
                if quiet >= 8: break
        if on is not None and on > 0 and rms[on - 1] <= thr: ch['start'] = round(min(ch['start'], on * 0.005), 3)
    # 块尾：跟到这一段声音真正结束（拖长音、句尾喊声），但不越过下一块开口
    for k, ch in enumerate(chs):
        cap = chs[k + 1]['start'] - 0.05 if k + 1 < len(chs) else len(rms) * 0.005
        j = int(ch['end'] / 0.005); quiet = 0
        while j < len(rms) and j * 0.005 < cap:
            quiet = quiet + 1 if rms[j] <= thr else 0
            if quiet >= 12: break
            j += 1
        ch['end'] = round(max(ch['end'], min(cap, (j - quiet) * 0.005)), 3)
    return chs

STOP = '。！？；'
def merge_short(chs, text, maxc=None):
    """一闪而过的块（显示 <0.8 s 或 ≤2 字）并入相邻块：优先并入下一块，放不下再并入上一块；不跨句末标点，合并后不超过 maxc 字。"""
    maxc = maxc or MAXC
    n = lambda c: len(re.sub(r'\s', '', c['text']))
    def shown(k): return (chs[k + 1]['start'] if k + 1 < len(chs) else chs[k]['end'] + 0.3) - chs[k]['start']
    k = 0
    while k < len(chs):
        if len(chs) > 1 and (shown(k) < 0.8 or n(chs[k]) <= 2):
            for j in [q for q in (k + 1, k - 1) if 0 <= q < len(chs)]:
                a, b = (k, j) if j > k else (j, k)
                if n(chs[a]) + n(chs[b]) <= maxc and not any(q in text[chs[a]['k1'] + 1:chs[b]['k0']] for q in STOP):
                    chs[a] = {**chs[a], 'text': chs[a]['text'] + ' ' + chs[b]['text'], 'end': chs[b]['end'], 'k1': chs[b]['k1']}; del chs[b]; k = max(0, a - 1); break
            else: k += 1
        else: k += 1
    return chs

# 字幕里的计量数字用阿拉伯数字（与字卡一致）；口语说法（四五趟、一半、八成）保留汉字。表在 storyboard.subtitle_numbers：[["六十岁","60岁"], ...]
NUMS = [tuple(x) for x in SB.get('subtitle_numbers', [])]
def disp_num(t):
    for a, b in NUMS: t = t.replace(a, b)
    return t

def mouth_track(text, cts, ces, wav):
    """口型轨道：每个字按拼音韵母定嘴型（M 闭 / A 啊 / E 诶 / I 衣 / O 哦 / U 乌），b/p/m 声母开口前先闭一下；
    开合幅度用这句配音的音量包络（25 ms 一个点，0..1）。只给出镜角色用。"""
    import numpy as np, soundfile as sf
    from pypinyin import pinyin, Style
    vis = []
    for ch in text:
        if not ('一' <= ch <= '鿿'): vis.append(None); continue
        fin = pinyin(ch, style=Style.FINALS, strict=False)[0][0] or 'a'; ini = pinyin(ch, style=Style.INITIALS, strict=False)[0][0]
        f0 = fin[0] if fin[0] not in 'iuv' or len(fin) == 1 else fin[1] if fin[1] in 'aoe' else fin[0]
        shape = {'a': 'A', 'o': 'O', 'e': 'E', 'i': 'I', 'u': 'U', 'v': 'U'}.get(f0, 'E')
        if fin in ('ong', 'iong', 'ou', 'iu', 'uo'): shape = 'O'
        vis.append(shape + ('m' if ini in ('b', 'p', 'm') else ''))
    a, sr = sf.read(str(wav)); hop = int(0.025 * sr)
    env = np.array([np.sqrt(np.mean(a[i:i + hop] ** 2)) for i in range(0, len(a), hop)]); env = np.clip(env / (np.percentile(env, 95) + 1e-9), 0, 1)
    return {'vis': vis, 'ce': [round(x, 3) for x in ces], 'env': [round(float(x), 2) for x in env]}

CV = SB.get('cover') or {}
COVER = float(CV.get('hold_land', 3.0) if LAND else CV.get('hold', 0.0)) if CV else 0.0   # 片头封面（s00）：成片第一帧即封面，之后全片顺延；横屏 cover.hold_land 默认 3.0 s（AI 标识 ≥ 2 s + 退场动画 0.9 s）
t = COVER; scenes = [{'id': 's00', 'chapter': None, 'start': 0.0, 'end': round(COVER, 3), 'lines': [], 'labels': [], 'cues': {}}] if COVER else []
chap_of = {sid: ch for ch in SB['chapters'] for sid in ch['scenes']}
for sc in SB['scenes']:
    ch = chap_of.get(sc['id'])
    if ch is None: sys.exit(f"场景 {sc['id']} 不属于任何章节（storyboard.chapters[].scenes）")
    st = t; cur = st + sc.get('lead', LEAD); lines = []; prev = None; ct_all = []
    for i, ln in enumerate(sc['lines']):
        row = None
        if EST: dur = len(norm(ln['text'])) / EST_RATE; wav = None
        else:
            if (sc['id'], i) not in LINES: sys.exit(f"audio/lines/lines.json 缺 {sc['id']}_{i}：先跑 tts")
            row = LINES[(sc['id'], i)]; assert row['text'] == ln['text'], f"配音与稿子不一致：{sc['id']}_{i}（改了台词要重跑 tts）"; dur = row['seconds']; wav = ROOT / row['file']
        if prev is not None: cur += GAP_SWITCH if prev != ln['who'] else GAP_SAME
        cts, ces = char_times(ln['text'], wav, dur, row); ct_all.append(cts)
        mc = maxc_for(ln['who']); chs = make_chunks(ln['text'], cts, ces, ln.get('br', ()), mc)
        if not EST: chs = snap_onsets(chs, wav)
        chs = merge_short(chs, ln['text'], mc)
        assert re.sub(r'\s', '', ''.join(c_['text'] for c_ in chs)).replace('？', '').replace('！', '') == re.sub(r'[，。；：！？、…—“”\s]', '', ln['text']), f"字幕丢字/多字：{sc['id']}_{i}"
        for c_ in chs: c_['text'] = disp_num(c_['text'])
        lines.append({'i': i, 'who': ln['who'], 'text': ln['text'], 'emo': ln.get('emo'), 'start': round(cur - st, 3), 'end': round(cur - st + dur, 3),
                      'file': None if EST else row['file'], 'abs': round(cur, 3), 'ct': [round(x, 3) for x in cts], 'chunks': chs,
                      **({} if EST or ln['who'] == 'narrator' else {'mouth': mouth_track(ln['text'], cts, ces, wav)})})
        cur += dur + ln.get('hold', 0); prev = ln['who']
    labels = []
    for lb in sc.get('labels', []):
        li, sub = lb['at']; k = sc['lines'][li]['text'].find(sub)
        if k < 0: sys.exit(f"label anchor not found: {sc['id']} {lb}")
        labels.append({**lb, 't': round(lines[li]['start'] + ct_all[li][k] - 0.05, 3)})
    cues = {}
    for name, (li, sub) in sc.get('cues', {}).items():
        k = sc['lines'][li]['text'].find(sub)
        if k < 0: sys.exit(f"cue not found: {sc['id']} {name}")
        cues[name] = round(lines[li]['start'] + ct_all[li][k], 3)
    end = cur + TAIL + sc.get('tail', 0)
    # 字卡停留：按叠字层同一套格位规则算每张卡在屏时长；场景结束导致不足的，把场尾延长到补足（每场最多 MAX_EXT 秒）；被挤走的只警告
    shown = min(sc.get('max_labels', MAXL), MOS) if MOS else sc.get('max_labels', MAXL)   # 写进 timeline 的 max_labels（竖屏按同屏上限截）
    maxN_eff = shown + EXTRA
    need = lambda r: MIN_STAY_ALERT if r['alert'] else MIN_STAY
    stays = card_stays(labels, end - st, maxN_eff, BIG_SLOT); ext = 0.0
    deficit = max([need(r) - r['stay'] for r in stays if r['reason'] == 'scene_end'] + [0.0])
    if deficit > 1e-6:
        ext = round(min(MAX_EXT, deficit) + 0.001, 3); end += ext
        if deficit > MAX_EXT: WARN.append(f"{sc['id']}：结尾已延长 {MAX_EXT} s，字卡停留仍不足（还差 {deficit - MAX_EXT:.2f} s）→ 减卡 / 把卡提前 / 加台词")
        stays = card_stays(labels, end - st, maxN_eff, BIG_SLOT)
    for r in stays:
        r['scene'] = sc['id']; r['min'] = need(r); r['ok'] = r['stay'] + 1e-6 >= r['min']
        if not r['ok'] and r['reason'] != 'scene_end': WARN.append(f"{sc['id']}：字卡“{r['text']}”只停 {r['stay']:.1f} s（<{r['min']}，{r['reason']}）→ 调 cue 错开 / 本场 max_labels 提到 {MOS or '上限'} / 合并卡")
    CARD_STAYS.extend(stays)
    scenes.append({'id': sc['id'], 'chapter': ch['id'], 'start': round(st, 3), 'end': round(end, 3), 'lines': lines, 'labels': labels, 'cues': cues, 'max_labels': shown, 'extended': ext}); t = end
scenes.append({'id': 's99', 'chapter': SB['chapters'][-1]['id'], 'start': round(t, 3), 'end': round(t + OUTRO, 3), 'lines': [], 'labels': [], 'cues': {}}); t += OUTRO
# 参考文献页（sref）：storyboard.references 非空且横屏（或 submit.refs_in_portrait）时追加在片尾之后；页数 references_pages（没写按条数 / layout.refs.per_page_default 自动分页），每页 references_page_seconds 秒
REFS = SB.get('references') or []; RFL = LAYOUT.get('refs') or {}
REFS_ON = bool(REFS) and (LAND or bool((SB.get('submit') or {}).get('refs_in_portrait')))
REFS_INFO = {'on': REFS_ON, 'count': len(REFS), 'pages': 0, 'page_seconds': 0.0}
if REFS_ON:
    import math
    RP = int(SB.get('references_pages') or max(1, math.ceil(len(REFS) / int(RFL.get('per_page_default') or 10)))); RS = float(SB.get('references_page_seconds') or RFL.get('page_seconds_default') or 5.0)
    REFS_INFO.update({'pages': RP, 'page_seconds': RS}); RD = RP * RS
    scenes.append({'id': 'sref', 'chapter': SB['chapters'][-1]['id'], 'start': round(t, 3), 'end': round(t + RD, 3), 'lines': [], 'labels': [], 'cues': {}}); t += RD
chapters = [{'id': c['id'], 'node': c['node'], 'start': min(x['start'] for x in scenes if x['chapter'] == c['id']), 'end': max(x['end'] for x in scenes if x['chapter'] == c['id'])} for c in SB['chapters']]
out = {'project': SB['project'], 'fps': SB['fps'], 'width': int(LAYOUT.get('width') or SB['width']), 'height': int(LAYOUT.get('height') or SB['height']), 'orient': ORIENT, 'duration': round(t, 3), 'estimate': EST, 'cover': round(COVER, 3), 'scenes': scenes, 'chapters': chapters,
       'subtitle_max_chars': MAXC, 'layout_version': LAYOUT.get('version'), 'refs': REFS_INFO, 'card_stays': CARD_STAYS, 'card_stay_rules': {'max_on_screen': MOS, 'extra_rows': EXTRA, 'big_takes_slot': BIG_SLOT, 'min_stay': MIN_STAY, 'min_stay_alert': MIN_STAY_ALERT, 'max_extend': MAX_EXT}}
(render_dir() / 'timeline.json').write_text(json.dumps(out, ensure_ascii=False, indent=1))
short = [r for r in CARD_STAYS if not r['ok']]; exts = [(x['id'], x['extended']) for x in scenes if x.get('extended')]
print('duration', round(t, 1), 's', 'estimate' if EST else '', f'| {ORIENT} {out["width"]}x{out["height"]} | chunks ≤ {MAXC} 字, labels default {MAXL}, 同屏上限 {MOS or "不限"}{f" +{EXTRA} 格（要点板）" if EXTRA else ""}' + (f' | 参考文献页 {REFS_INFO["pages"]} 页 × {REFS_INFO["page_seconds"]} s（{len(REFS)} 条）' if REFS_ON else '') + (f' | 封面 {COVER} s' if COVER else ''))
print(f"字卡 {len(CARD_STAYS)} 张：停留不足 {len(short)} 张（被挤 {sum(1 for r in short if r['reason'] != 'scene_end')} / 场末 {sum(1 for r in short if r['reason'] == 'scene_end')}），最短 {min((r['stay'] for r in CARD_STAYS), default=0):.2f} s；场尾延长 {len(exts)} 场 共 {sum(e for _, e in exts):.2f} s {exts}")
for w in WARN: print('!!', w)

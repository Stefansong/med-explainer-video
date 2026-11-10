#!/usr/bin/env python3
"""从 timeline.json 导出字幕（投稿须知：字幕文本以补充材料形式上传）：
  submit/{project}_字幕.srt      与成片字幕块同步：块在首字开口前 lead 秒出现，同句下一块开口时切换，停顿 >0.6 s 则末字后 tail 秒隐去（与 overlay.js OV.subtitle 同一规则）；角色台词前加名牌
  submit/{project}_字幕文本.txt   台词全文，按场分段、带角色名（旁白不加）
运行：python3 tools/export_subs.py [--out submit]   （ORIENT=land 读 render/land/timeline.json）"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import ROOT, load_sb, load_tl, load_layout
SB = load_sb(); TL = load_tl(); LAYOUT = load_layout(); Sb = LAYOUT.get('subtitle') or {}
LEAD, TAIL = float(Sb.get('lead', 0.06)), float(Sb.get('tail', 0.3))
out_dir = ROOT / (sys.argv[sys.argv.index('--out') + 1] if '--out' in sys.argv else 'submit'); out_dir.mkdir(parents=True, exist_ok=True)
P = SB['project']; CH = SB.get('characters') or {}
def name_of(who):
    ch = CH.get(who) or {}
    return None if who == 'narrator' or ch.get('no_badge') else (ch.get('name') or who)
def ts(t):
    t = max(0.0, t); h = int(t // 3600); m = int(t % 3600 // 60); s = t % 60
    return f'{h:02d}:{m:02d}:{s:06.3f}'.replace('.', ',')
srt = []; n = 0
for sc in TL['scenes']:
    for ln in sc['lines']:
        cs = ln.get('chunks') or []
        for k, ch in enumerate(cs):
            a = sc['start'] + ln['start'] + ch['start'] - LEAD
            nxt = sc['start'] + ln['start'] + cs[k + 1]['start'] - LEAD if k + 1 < len(cs) else None
            end_ = sc['start'] + ln['start'] + ch['end']
            b = min(nxt, end_ + TAIL) if nxt is not None and nxt - end_ <= 0.6 else (end_ + TAIL if nxt is None else min(nxt, end_ + TAIL))
            who = name_of(ln['who']); text = ch['text'].rstrip('。')
            n += 1; srt.append(f"{n}\n{ts(a)} --> {ts(max(a + 0.2, b))}\n{(who + '：') if who else ''}{text}\n")
(out_dir / f'{P}_字幕.srt').write_text('\n'.join(srt), encoding='utf-8')
chap = {sid: c for c in SB.get('chapters', []) for sid in c.get('scenes', [])}
txt = [SB.get('title') or ''.join((SB.get('cover') or {}).get('title_lines') or []), '']
last_ch = None
for sc in SB['scenes']:
    c = chap.get(sc['id'])
    if c and c is not last_ch: txt.append(f"【{c.get('node', '')}】"); last_ch = c
    for ln in sc['lines']:
        who = name_of(ln['who']); txt.append(f"{(who + '：') if who else ''}{ln['text']}")
    txt.append('')
(out_dir / f'{P}_字幕文本.txt').write_text('\n'.join(txt).rstrip('\n') + '\n', encoding='utf-8')
print(f"→ {out_dir / (P + '_字幕.srt')}（{n} 条）  {out_dir / (P + '_字幕文本.txt')}（{sum(len(s['lines']) for s in SB['scenes'])} 句）")

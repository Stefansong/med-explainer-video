#!/usr/bin/env python3
"""台词时长变了（换 take、旁白改速）之后，把 storyboard 里的视频片段（3D 人物 pix 片段等 media）对到新时间轴上。
  旧 → 新时间映射：每句台词内按比例伸缩，句间空隙、场首留白、场尾不变。
  说话的片段（gen.lines 非空）：保持“台词开口在片段里的位置”不变（口型不能错位），起播点 = 新开口 − 原偏移；dur 随叙事终点伸缩、不短于原值。
  不说话的片段：起播点、结束点都按映射走；--tmap 给超过 --tmap-min 秒的无声长镜头写分段对时表 tmap（片段里的事件仍对准原来那句话，
  如肾结石 3D 内镜：激光对准“钬激光”、硬骨头开口对准它那句），否则按原速播放（待机类片段窗口变长要配 loop / loop_s，否则会定格或回退代码画面）。
  锚在 cue 上的保持锚点名，只改偏移。改完 → pipeline.py frames 抽帧 → 正式渲染后 `scan.py warp` 与旧成片逐帧比。
运行：cd <专题> && cp render/timeline.json /tmp/timeline_old.json && （改配音 → pipeline.py timeline）&& python3 tools/retime_media.py /tmp/timeline_old.json [--tmap] [--tmap-min 6] [--dry-run]"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import ROOT, load_sb, save_sb, load_tl
a = sys.argv[1:]
if not a or a[0].startswith('--'): sys.exit(__doc__)
OLD = {s['id']: s for s in json.load(open(a[0]))['scenes']}; NEW = {s['id']: s for s in load_tl()['scenes']}
TMAP = '--tmap' in a; TMIN = float(a[a.index('--tmap-min') + 1]) if '--tmap-min' in a else 6.0; DRY = '--dry-run' in a

def warp(o, n, t):   # 旧场内时间 → 新场内时间
    ol, nl = o['lines'], n['lines']
    if not ol or t <= ol[0]['start']: return t
    for i, (x, y) in enumerate(zip(ol, nl)):
        if x['start'] <= t <= x['end']: return y['start'] + (t - x['start']) * (y['end'] - y['start']) / max(1e-6, x['end'] - x['start'])
        nxt = ol[i + 1]['start'] if i + 1 < len(ol) else 1e9
        if x['end'] < t < nxt: return min(y['end'] + (t - x['end']), nl[i + 1]['start'] if i + 1 < len(nl) else 1e9)
    return t
def inv(o, n, t): return warp(n, o, t)   # 新 → 旧（映射对称）
def t0_of(sc, at):   # at[0]：cue 名，或 l<i> = 第 i 句台词开口
    import re; ln = re.match(r'l(\d+)$', at[0])
    return (sc.get('cues', {})[at[0]] if at[0] in sc.get('cues', {}) else sc['lines'][int(ln.group(1))]['start'] if ln else 0) + (at[1] or 0)

SB = load_sb(); changed = 0
for sc in SB['scenes']:
    sid = sc['id']
    if sid not in OLD or sid not in NEW: continue
    o, n = OLD[sid], NEW[sid]
    if len(o['lines']) != len(n['lines']): sys.exit(f'{sid}: 新旧台词句数不同，不能映射')
    for m in sc.get('media', []):
        talk = (m.get('gen') or {}).get('lines') or []; at, dur = m['at'], m.get('dur'); ot0 = t0_of(o, at)
        nt0 = n['lines'][talk[0]]['start'] - (o['lines'][talk[0]]['start'] - ot0) if talk else warp(o, n, ot0)
        base = t0_of(n, [at[0], 0]); nat = [at[0], round(nt0 - base, 3)]
        nd = None if dur is None else round(max(dur, warp(o, n, ot0 + dur) - nt0), 2)
        note = ''
        if TMAP and not talk and dur and nd and nd > TMIN and abs(nd - dur) > 0.2:
            ks = sorted({0.0, round(nd, 3)} | {round(x - nt0, 3) for l in n['lines'] for x in (l['start'], l['end']) if 0 < x - nt0 < nd})
            m['tmap'] = [[k, round(inv(o, n, nt0 + k) - ot0, 3)] for k in ks]; note = f'  tmap {len(ks)} 段'
        if nat != at or nd != dur:
            print(f"{m['id']:14s} {sid} {'说话' if talk else '无声'}  at {at} → {nat}  dur {dur} → {nd}{note}"); changed += 1
            if not DRY: m['at'] = nat; m['dur'] = nd if nd is not None else m.get('dur')
print(f'{changed} 条要改' + ('（--dry-run，未写入）' if DRY else '，已写入 storyboard'))
if not DRY and changed: save_sb(SB)

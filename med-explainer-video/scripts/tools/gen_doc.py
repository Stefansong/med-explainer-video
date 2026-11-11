#!/usr/bin/env python3
"""storyboard（唯一真源）+ 可选的手写 design/s0_summary_v{ver}.md（先说结论）/ design/review_head_v{ver}.md（修改说明）→ design/{project}_修订稿_v{ver}.md / .docx
修订稿正文、口径表、节拍表都从 storyboard 生成；结论和修改说明是手写的（文件不存在就跳过）。S0 检查点给用户看的就是这份文档。
运行：python tools/gen_doc.py   （docx 由 tools/md2docx.py 出，需要 python-docx；没装就只出 md）"""
import json, re, subprocess, shutil, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import ROOT, load_sb
D = ROOT / 'design'; d = load_sb()
ver = d['version']; name = d.get('doc_name') or f"{d['project']}_修订稿"
who = {k: v['name'] for k, v in d['characters'].items()}
chap = {c['id']: c['node'] for c in d['chapters']}
chap_of = {s: c['id'] for c in d['chapters'] for s in c['scenes']}
e = d.get('est') or {}
mmss = lambda s: f"{int(s // 60)} 分 {int(round(s % 60))} 秒"
st = d.get('status'); st_txt = st if isinstance(st, str) else '；'.join(f"{k.upper()} {'已确认' if (v or {}).get('confirmed') else '待确认'}" for k, v in (st or {}).items() if not k.startswith('_'))
o = [f"# {d['title']}", '',
     f"**修订稿 v{ver}（动画脚本版）**　竖屏 {d['width']}×{d['height']}" + (f" · 台词 {e['narration_chars']} 字 · 估算成片约 {mmss(e['est_total_seconds'])}" if e else ''), '',
     f"> 状态：{st_txt}", '',
     '本文件包含：先说结论；一、修订稿（即配音和字幕的脚本）；二、修改说明；三、口径表；四、节拍表（每场画面设计）。', '']
f = D / f's0_summary_v{ver}.md'
if f.exists(): o.append(f.read_text().rstrip())
o += ['', '## 一、修订稿', '', '> 角色：' + '；'.join(f"**{c['name']}**（{c['desc']}）" for c in d['characters'].values()), '']
cur = None
for s in d['scenes']:
    c = chap_of.get(s['id'], '?')
    if c != cur: o += [f"### {chap.get(c, c)}", '']; cur = c
    o += [f"**【{s['id']}】{s['beat']}**", '']
    for l in s['lines']: o.append(f"**{who.get(l['who'], l['who'])}**：{l['text']}" + '  ')
    o += ['', '*【画面字卡】' + ' ｜ '.join(lb['text'] for lb in s.get('labels', [])) + '*', '']
o += ['（完）', '']
f = D / f'review_head_v{ver}.md'
if f.exists(): o += [f.read_text().rstrip()]
else: o += ['## 二、修改说明', '', '（手写 design/review_head_v{ver}.md 后自动并入）', '']
o += ['', '## 三、口径表', '', '片中每一处医学表述都以下表为准；画面字卡和台词只能比它更简略，不能更绝对。', '', '| 编号 | 口径 | 出处 | 来源原句 |', '|---|---|---|---|']
o += [f"| {c['id']} | {c['text']} | {c.get('src', '')} | {c.get('quote', '')} |" for c in d['claims']]
o += ['', '**危险信号（全部进画面）：** ' + '；'.join(d.get('red_flags', [])) + f"。{d.get('red_flags_action', '')}。{d.get('red_flags_special', '')}".rstrip('。') + '。', '', '**文献：**', '']
o += [f"- **{k}**：{v}" for k, v in d.get('sources', {}).items() if not k.startswith('_')]
import re as _re
nosrc = [c['id'] for c in d['claims'] if not [x for x in _re.split(r'[,，、;；\s]+', str(c.get('src') or '')) if x] or any(x not in d.get('sources', {}) for x in _re.split(r'[,，、;；\s]+', str(c.get('src') or '')) if x)]
if nosrc: o += ['', f"**⚠ 来源没登记全的口径：{'、'.join(nosrc)}**"]
o += ['', '## 四、节拍表', '', '| 场 | 章 | 节拍 | 抓人点 | 画面 | 口径 | 字数 | 估时 s |', '|---|---|---|---|---|---|---|---|']
for s in d['scenes']: o.append(f"| {s['id']} | {chap.get(chap_of.get(s['id']), '?')} | {s['beat']} | {s.get('hook', '')} | {s['visual']} | {', '.join(s.get('claims', []))} | {s.get('chars', '')} | {s.get('est_seconds', '')} |")
if e: o += ['', f"台词共 {e['narration_chars']} 字。{e.get('rate_note', '')} 估算成片约 {mmss(e['est_total_seconds'])}。"]
o += ['', '**解剖核对（出图和动画都要过）：**', ''] + [f"- {a}" for a in d.get('anatomy_checks', [])]
md = D / f'{name}_v{ver}.md'; md.write_text('\n'.join(o) + '\n')
from md2docx import convert as _docx
if _docx(md): print('ok', md.name, md.with_suffix('.docx').name)
elif shutil.which('pandoc'): subprocess.run(['pandoc', str(md), '-o', str(md.with_suffix('.docx')), '--from', 'markdown+raw_html'], check=True); print('ok', md.name, md.with_suffix('.docx').name)
else: print('ok', md.name, '（没装 python-docx，未出 docx：python -m pip install python-docx）')

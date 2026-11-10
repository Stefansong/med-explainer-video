#!/usr/bin/env python3
"""字体字形覆盖检查（投稿须知：只用开源免费商用字体；10-21 用户：竖屏横屏都不要苹方后备，缺字在 QA 门报出）。
把所有会上屏的文字（章节名、片名、字卡、字幕块、片尾、参考文献、署名、封面、AI 标识、名牌；_common.overlay_texts）按字体角色归到 layout.fonts.{sub,label,title,ref}，
用 fontTools 查 layout.fonts.files 里该角色各字体文件的 cmap（按 family 顺序，任一含该字即可）：列出缺字（字、U+ 码、角色、该用的字体文件、出现位置）——缺字时浏览器会回退系统字体，不允许；
并报告 fonts.* 里声明了但不在 files 里的字体族（系统回退声明，也不允许）。箭头“→”是线条画的，不查；空白不查；其它符号照查。
运行：python3 tools/check_fonts.py [--json]   （ORIENT=land 查 layout_land.json；fontTools 在 tts/.venv 和系统 python 里都有）"""
import json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import ROOT, load_sb, load_layout, load_tl, overlay_texts
JS = '--json' in sys.argv
SB = load_sb(); LAYOUT = load_layout()
try: TL = load_tl()
except Exception: TL = None
F = LAYOUT.get('fonts') or {}; FILES = F.get('files') or {}
SKIP = set('→')   # 画出来的符号
def families(spec):
    return [m[0] or m[1] for m in re.findall(r'"([^"]+)"|([A-Za-z][A-Za-z0-9 \-]*)', spec or '') if (m[0] or m[1]).strip()]
cmaps = {}
def cmap_of(name):
    if name in cmaps: return cmaps[name]
    f = FILES.get(name)
    if not f: cmaps[name] = None; return None
    try:
        from fontTools.ttLib import TTFont
        cmaps[name] = set(TTFont(str(ROOT / f['src']), lazy=True).getBestCmap().keys())
    except Exception as e:
        cmaps[name] = None; print('!! 读不了字体', name, f, e, file=sys.stderr)
    return cmaps[name]
texts = overlay_texts(SB, LAYOUT, TL, where=True)
roles = {}; sysdecl = []; missing = []
for role in ('sub', 'label', 'title', 'ref'):
    spec = (F.get(role) or {}).get('family', ''); fams = families(spec); fb = [x for x in fams if x in FILES]; nf = [x for x in fams if x not in FILES]
    if nf: sysdecl.append({'role': role, 'declared': nf})
    if not fb: sysdecl.append({'role': role, 'declared': fams or ['（空）'], 'note': '没有任何 files 里的字体'})
    locs = {}
    for r, t, w in texts:
        if r != role: continue
        for ch in t:
            if ch.isspace() or ch in SKIP: continue
            locs.setdefault(ch, []).append(f'{w}「{t[:24]}」')
    files = [FILES[x]['src'] for x in fb]
    miss = sorted(ch for ch in locs if not any((cm := cmap_of(x)) and ord(ch) in cm for x in fb))
    for ch in miss: missing.append({'char': ch, 'code': f'U+{ord(ch):04X}', 'role': role, 'fonts': [Path(f).name for f in files], 'where': sorted(set(locs[ch]))[:6], 'count': len(locs[ch])})
    roles[role] = {'families': fams, 'files': files, 'chars': len(locs), 'missing': miss}
res = {'layout': LAYOUT.get('version'), 'texts': len(texts), 'roles': roles, 'missing_total': len(missing), 'missing': missing, 'missing_sample': [(m['role'], m['char']) for m in missing[:10]], 'system_fallback_declared': sysdecl}
for role, r in roles.items(): print(f"{role:5s} {r['families']} → {[Path(f).name for f in r['files']]}：{r['chars']} 个不同字，缺 {len(r['missing'])}" + (f"：{''.join(r['missing'][:40])}" if r['missing'] else ''))
for m in missing: print(f"  缺字 “{m['char']}” {m['code']}  角色 {m['role']}  应在 {m['fonts']}  出现 {m['count']} 处：{'；'.join(m['where'][:3])}")
if sysdecl: print('!! layout.fonts 声明了不在 files 里的字体族（会回退系统字体）：', sysdecl)
print('字形覆盖', 'OK' if not missing and not sysdecl else f'缺 {len(missing)} 字 / 系统回退声明 {len(sysdecl)}')
if JS: print(json.dumps(res, ensure_ascii=False))

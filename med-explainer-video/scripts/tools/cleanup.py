#!/usr/bin/env python3
"""成片通过审核后的清理（生成过程中的其他版本和过期文件清掉，只保留最新 2 版）

用法（专题目录下，或 pipeline.py clean）：
  python3 tools/cleanup.py              只列清单，不动文件（默认）
  python3 tools/cleanup.py --apply      先归拢到 <工作目录>/清理_<专题>_<时刻>/（保持相对路径），再整个移进回收站 / 废纸篓；清单写 render/cleanup_<时刻>.json
  --keep N   每类版本保留几版（默认 2）
  -v         清单逐项全列（默认每类只列 12 项）
  --force    成片审核没过也列清单（--apply 仍要求 audit_post pass + 交付清单在）
  ORIENT=land（pipeline.py clean --orient land 会设）：只做横屏的专题，清 render/land/（门：audit_post_master pass + deliver_master.json）；竖屏 render/ 不碰（hydro 11-01 加）
不是永久删除：清空废纸篓由用户自己决定。

清理的类（每类“版本”按版本号排，保留最新 N 版）：
  预演      render/{p}_preview_vN.*、render/preview_vN_frames/                         保留最新 N 版
  渲染分段  render/seg/*（成片已合成，分段只是 render.js 的缓存，重渲会重出）            全清
  开发抽帧  render/check/、render/check_sheet.png（frames 阶段会重出）                  全清
  审核材料  render/audit/pre_vN/ 保留最新 N 版；render/recheck/ 下只留现行审核报告（最新 N 份 audit_pre + audit_post_*）里引用到的
  旧成片    render/archive/{p}_final_*（连同 qa / overlay / 审核报告）                   按归档版本保留最新 N−1 版（加上现行成片 = N 版）
  原集遗留  别的专题名开头的 preview / final / cover 文件、*.orig_copy、render/archive/orig_*（副本建出来时带过来的，原集目录里都还在）  全清
  3D 片段   assets/pix3d/<场>/<片段>/ 没被 storyboard / 场景代码引用的（服务器 ~/kepu/pix/<p>/ 还有）  全清
  GPT 原图  render/pix3d_gpt/<id>/：被 storyboard（定妆 art3d / art、assets、gen.image）/ 场景代码 / 出图清单引用的永远留；_vN 旧版保留最新 N 版（不带后缀的现行版算一版）；
            _cN 是候选不是版本（S3 选定的 c1 不因有 c2/c3 被当旧版），没人引用的才清；rejected/ 同一镜头只留最新 1 张
  文稿      design/ 下带版本号的 *_vX[.Y].md/.docx（审核报告、差异稿、修订稿、summary、review…）同名族保留最新 N 版
永远不动：assets/lib/**（定稿素材，带 APPROVED.md）、storyboard 引用的素材与片段帧、交付清单 deliver_*.json 里的文件、现行成片与封面、
  timeline / mix / stems、audio/**、design/storyboard_*、src/ tools/ docs/ layout*.json、pix3d/*.json；只认上面列的类，其他文件一律不碰。
"""
import json, os, re, shutil, subprocess, sys, time
from pathlib import Path

ROOT = Path.cwd()
if not (ROOT / 'design').is_dir(): sys.exit('在专题目录下跑（要有 design/）')
SBP = next(iter(sorted(f for f in (ROOT / 'design').glob('storyboard_*.json'))), None)
if not SBP: sys.exit('找不到 design/storyboard_*.json')
SB = json.loads(SBP.read_text()); PROJ = SB.get('project') or SBP.stem.replace('storyboard_', '')
A = sys.argv[1:]; APPLY = '--apply' in A; FORCE = '--force' in A; VERB = '-v' in A
KEEP = int(A[A.index('--keep') + 1]) if '--keep' in A else 2
LAND = os.environ.get('ORIENT') == 'land' or ('--orient' in A and A[A.index('--orient') + 1:A.index('--orient') + 2] == ['land'])
RD = ROOT / 'render' / 'land' if LAND else ROOT / 'render'   # 横屏投稿版（只做横屏的专题，如 hydro）：产物全在 render/land/、tag master；竖屏 render/、tag final
TAG = 'master' if LAND else 'final'
def rel(p): return str(Path(p).relative_to(ROOT))
def size(p):
    p = Path(p)
    if p.is_symlink() or p.is_file(): return p.lstat().st_size
    return sum(f.lstat().st_size for f in p.rglob('*') if f.is_file() and not f.is_symlink())
def vkey(s): return tuple(int(x) for x in re.findall(r'\d+', s))

# ---------- 门：成片审核过了才清 ----------
def post_ok():
    r = subprocess.run([sys.executable, '-X', 'utf8', str(Path(__file__).resolve().parent / 'audit.py'), 'check', 'post', '--tag', TAG], cwd=ROOT, capture_output=True, text=True, env={**os.environ, 'ORIENT': 'land' if LAND else 'port'})
    return r.returncode == 0 and (RD / f'deliver_{TAG}.json').exists(), (r.stdout + r.stderr).strip().splitlines()[-1:] or ['']
ok, why = post_ok()
if not ok and not FORCE: sys.exit(f'成片审核未过或还没交付（{why[0]}）：清理只在 audit_post pass + deliver 之后做；只想看清单加 --force')
if APPLY and not ok: sys.exit(f'--apply 要求成片审核 pass 且有 {rel(RD / f"deliver_{TAG}.json")}')

# ---------- 受保护的路径 ----------
SBTXT = SBP.read_text()
CODETXT = '\n'.join(f.read_text(errors='ignore') for f in sorted((ROOT / 'src').glob('*.js'))) if (ROOT / 'src').is_dir() else ''
IMGJSON = '\n'.join(f.read_text(errors='ignore') for f in sorted((ROOT / 'pix3d').glob('images*.json'))) if (ROOT / 'pix3d').is_dir() else ''
PROT = {ROOT / 'assets/lib', ROOT / 'audio', ROOT / 'src', ROOT / 'tools', ROOT / 'docs', SBP, RD / 'timeline.json', RD / 'mix.wav',
        RD / f'{PROJ}_{TAG}.mp4', RD / f'{PROJ}_{TAG}.qa.json', RD / f'{PROJ}_{TAG}.overlay.json', RD / f'{PROJ}_cover_9x16.png', RD / f'audit_post_{TAG}.md'}
if LAND: PROT |= {RD / f'{PROJ}_submit.mp4', RD / f'{PROJ}_submit.qa.json', RD / f'{PROJ}_submit.overlay.json', RD / f'{PROJ}_cover_16x9.png', ROOT / 'submit'}
for d in RD.glob('deliver_*.json'):
    PROT.add(d)
    for r in json.loads(d.read_text()).get('files', []): PROT.add(ROOT / r['path'])
for a in (SB.get('assets') or {}).values():
    if isinstance(a, dict) and a.get('src'): PROT.add(ROOT / a['src'])
for ap in ROOT.rglob('APPROVED.md'): PROT.add(ap.parent)
def protected(p):
    p = Path(p)
    return any(p == q or q in p.parents or p in q.parents for q in PROT)

C = {}   # 类 → [路径]
def add(cls, p):
    if Path(p).exists() and not protected(p): C.setdefault(cls, []).append(Path(p))

# 预演
pv = {}
for f in RD.glob(f'{PROJ}_preview_v*'):
    m = re.match(rf'{re.escape(PROJ)}_preview_v(\d+)', f.name)
    if m: pv.setdefault(int(m.group(1)), []).append(f)
for f in RD.glob('preview_v*_frames'):
    m = re.match(r'preview_v(\d+)_frames$', f.name)
    if m: pv.setdefault(int(m.group(1)), []).append(f)
for v in sorted(pv)[:-KEEP]:
    for f in pv[v]: add('预演（旧版）', f)
# 渲染分段、开发抽帧
for f in sorted((RD / 'seg').glob('*')) if (RD / 'seg').is_dir() else []: add('渲染分段缓存', f)
add('开发抽帧', RD / 'check'); add('开发抽帧', RD / 'check_sheet.png')
# 审核材料
packs = sorted((d for d in (RD / 'audit').glob('pre_v*') if re.match(r'pre_v\d+$', d.name)), key=lambda d: vkey(d.name)) if (RD / 'audit').is_dir() else []
for d in packs[:-KEEP]: add('审核材料包（旧版）', d)
reps = sorted((ROOT / 'design').glob('audit_pre_v*.md'), key=lambda f: vkey(f.name))[-KEEP:] + sorted(RD.glob('audit_post_*.md')) + sorted((RD / 'archive').glob('audit_post_*.md'))   # 留下的那版归档成片，它的审核证据也留
REPTXT = '\n'.join(f.read_text(errors='ignore') for f in reps)
if (RD / 'recheck').is_dir():
    for f in sorted((RD / 'recheck').iterdir()):
        if f'recheck/{f.name}' not in REPTXT: add('审核证据（现行报告没引用）', f)
# 旧成片
if (RD / 'archive').is_dir():
    arc = {}
    for f in sorted((RD / 'archive').iterdir()):
        if f.name.startswith('orig_'): add('原集遗留', f); continue
        m = re.match(rf'({re.escape(PROJ)}_{TAG}|audit_post_{TAG})_(.+?)(\.qa|\.overlay)?\.(mp4|json|md)$', f.name)
        if m: arc.setdefault(m.group(2), []).append(f)
    for tag in sorted(arc, key=lambda t: max(x.stat().st_mtime for x in arc[t]))[:-(KEEP - 1) or None]:
        for f in arc[tag]: add('旧成片（归档）', f)
# 原集遗留（副本建立时带过来的别的专题前缀文件）
pat = re.compile(r'^([a-z0-9_]+?)_(preview_v\d+|final|master|submit|cover_9x16|cover_16x9)\b')
for f in RD.iterdir():
    m = pat.match(f.name)
    if m and m.group(1) != PROJ and not f.name.startswith(PROJ + '_') and (ROOT.parent / m.group(1) / 'design').is_dir(): add('原集遗留', f)   # 前缀得是 Kepu 下真有的另一个专题（原集），别把 run_until_s6a_final.log 之类误判
for f in ROOT.rglob('*.orig_copy'): add('原集遗留', f)
for f in (ROOT / 'design').iterdir():
    m = re.match(r'^([a-z0-9_]+)_修订稿_v', f.name)
    if m and m.group(1) != PROJ and (ROOT.parent / m.group(1) / 'design').is_dir(): add('原集遗留', f)
# 3D 片段帧
ap = ROOT / 'assets/pix3d'
if ap.is_dir():
    for d in sorted(x for s in ap.iterdir() if s.is_dir() for x in s.iterdir() if x.is_dir()):
        r = rel(d)
        if r + '/' not in SBTXT and r + '/' not in CODETXT: add('3D 片段帧（storyboard 已不用）', d)
# GPT 原图
gp = ROOT / 'render/pix3d_gpt'   # GPT 原图横竖屏共用，总在 render/ 下
if gp.is_dir():
    # <id>/ 是 <id>.png 的 GPT 原图：名字出现在 storyboard（characters.*.art3d / art、assets、places、媒体 gen.image）、场景代码、出图清单 images*.json（out / id）里 → 永远留，不管带什么后缀
    # _cN 是同一批的候选（c1/c2/c3，S3 用户选一张定稿），不是版本号，互相不比新旧（11-07 bph_3d：定稿 drsong_3d_gpt_c1 被当旧版列进清单，落选的 c2/c3 反倒留着）
    # 只有 _vN 是版本号：图标 / 立绘重出时旧的改名 _vN、现行的不带后缀（算最新一版）
    def gref(n): return n in SBTXT or n in CODETXT or n in IMGJSON
    fam = {}
    for d in sorted(x for x in gp.iterdir() if x.is_dir() and x.name != 'rejected'):
        m = re.match(r'(.+)_v(\d+)$', d.name)
        if m: fam.setdefault(m.group(1), []).append((int(m.group(2)), d))
        elif gref(d.name): fam.setdefault(d.name, []).append((10 ** 6, d))
        else: add('GPT 原图（没人引用）', d)
    for k, vs in fam.items():
        for _, d in sorted(vs)[:-KEEP]:
            if not gref(d.name): add('GPT 原图（旧版）', d)
    rj = gp / 'rejected'
    if rj.is_dir():
        rf = {}
        for f in rj.iterdir():
            m = re.match(r'(.+?)(_gpt_c\d+|_v\d+)', f.stem); rf.setdefault(m.group(1) if m else f.stem, []).append(f)
        for k, fs in rf.items():
            for f in sorted(fs, key=lambda x: x.stat().st_mtime)[:-1]: add('GPT 落选图（旧版）', f)
# 文稿：带版本号的同名族
fam = {}
for f in (ROOT / 'design').iterdir():
    m = re.match(r'^(.+?)_v(\d+(?:\.\d+)*)\.(md|docx)$', f.name)
    if m: fam.setdefault((m.group(1), m.group(3)), []).append((vkey(m.group(2)), f))
for k, vs in fam.items():
    for _, f in sorted(vs)[:-KEEP]: add('文稿 / 审核报告（旧版）', f)

# ---------- 输出 ----------
seen = set(); tot = 0; rows = []
for cls, ps in C.items():
    ps = [p for p in ps if p not in seen and not any(q in p.parents for q in seen)]; seen.update(ps)
    if not ps: continue
    sz = sum(size(p) for p in ps); tot += sz
    print(f'\n## {cls}：{len(ps)} 项，{sz / 1e6:.1f} MB')
    for p in ps[:None if VERB else 12]: print(f'  {rel(p)}{"/" if p.is_dir() else ""}')
    if len(ps) > 12 and not VERB: print(f'  …另 {len(ps) - 12} 项')
    rows += [{'class': cls, 'path': rel(p), 'bytes': size(p)} for p in ps]
print(f'\n合计 {len(rows)} 项，{tot / 1e9:.2f} GB（保留每类最新 {KEEP} 版；{"成片审核 pass" if ok else "成片审核未过，只列清单"}）')
if not APPLY: print('只列了清单；确认后加 --apply 移到废纸篓'); sys.exit(0)
if not rows: sys.exit(0)
ts = time.strftime('%Y%m%d_%H%M%S'); T = ROOT.parent / f'清理_{PROJ}_{ts}'   # 先归拢到这个文件夹，最后整个移进回收站（一次就能放回）
for r in rows:
    src = ROOT / r['path']; dst = T / r['path']; dst.parent.mkdir(parents=True, exist_ok=True)
    try: os.rename(src, dst)
    except OSError: shutil.move(str(src), str(dst))
    r['trash'] = str(dst)
man = RD / f'cleanup_{ts}.json'
man.write_text(json.dumps({'project': PROJ, 'at': ts, 'keep': KEEP, 'trash': str(T), 'bytes': tot, 'items': rows}, ensure_ascii=False, indent=1))
try:
    from send2trash import send2trash
    send2trash(str(T)); print(f'→ 已移进回收站 / 废纸篓：{T.name}（放回：从回收站还原这个文件夹，再按 {rel(man)} 里的 path 移回原处）')
except Exception as e:
    print(f'→ 已归拢到 {T}（没能移进回收站：{e}；确认不要了自己删这个文件夹）')

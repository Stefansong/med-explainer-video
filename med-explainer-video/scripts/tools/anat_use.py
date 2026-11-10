#!/usr/bin/env python3
"""系列解剖库 → 本集 src/anat.js（2026-10-31）。
母版在工作目录的 anatomy/<名>_v<n>/（anat.js + APPROVED.md + palette_*.json，只读、永不覆盖；新画的母版也先进这里，用户批准后冻结）。
storyboard 写 "anatomy_masters": ["kidney_tract_v1", "prostate_v2"]，本工具把它们各自包成一个 AN 子集、合并成全局 AN 写进 src/anat.js：
  - 逐个核对 anat.js 的 md5 与 APPROVED.md 表格一致（母版被改过就拒绝）；
  - 函数名（AN.xxx）在两个母版里撞了就拒绝（同一母版的两个版本只能选一个）；
  - 列出本集 style.palette 缺的色键；--palette 只补缺的键（已有的值不改，值不同只提示）。
用法（专题目录下）：python3 tools/anat_use.py [--palette] [--lib <解剖库目录>]
本集自己新画、还没进库的结构：先在 anatomy/<名>_v1/ 起候选（APPROVED.md 写“候选，未批准”），同样列进 anatomy_masters；用户在 S3 / S6a 批准后补 md5 表、设只读。"""
import sys, re, json, hashlib
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import ROOT, find_storyboard, load_sb, save_sb

def md5(p): return hashlib.md5(Path(p).read_bytes()).hexdigest()
def main(argv):
    lib = Path(argv[argv.index('--lib') + 1]).resolve() if '--lib' in argv else ROOT.parent / 'anatomy'
    SB = load_sb(); names = SB.get('anatomy_masters') or []
    if not lib.is_dir(): sys.exit(f'没有解剖库目录 {lib}：在工作目录下建 anatomy/<名>_v1/anat.js（见 references/anatomy.md），或用 --lib 指定')
    if not names: sys.exit('storyboard 没写 anatomy_masters（例：["kidney_tract_v1", "prostate_v2"]）；可选：' + ' '.join(sorted(p.name for p in lib.iterdir() if (p / 'anat.js').exists())))
    parts, owner, pal_need = [], {}, {}
    for n in names:
        d = lib / n; a = d / 'anat.js'
        if not a.exists(): sys.exit(f'解剖库里没有 {n}（{d}）')
        ap = (d / 'APPROVED.md').read_text() if (d / 'APPROVED.md').exists() else ''
        m = re.search(r'`anat\.js`\s*\|\s*`([0-9a-f]{32})`', ap)
        if m and m.group(1) != md5(a): sys.exit(f'{n}/anat.js 的 md5 {md5(a)} ≠ APPROVED.md 记的 {m.group(1)}：母版被改过，拒绝生成（改画法要升版本）')
        cand = not m
        code = a.read_text()
        for fn in re.findall(r'^\s*AN\.([A-Za-z_]\w*)\s*=', code, re.M):
            if fn in owner and owner[fn] != n: sys.exit(f'AN.{fn} 在 {owner[fn]} 和 {n} 里都有：两个母版只能选一个（同一结构的两个版本不能同时用）')
            owner[fn] = n
        body = re.sub(r"^if \(typeof module !== 'undefined'\) module\.exports = AN; else window\.AN = AN;\s*$", '', code, flags=re.M).rstrip()
        parts.append(f"// ---------- {n}{'（候选，未批准）' if cand else ''}  md5 {md5(a)} ----------\nANL[{json.dumps(n)}] = (() => {{\n{body}\nreturn AN;\n}})();")
        for pf in sorted(d.glob('palette_*.json')):
            pj = json.loads(pf.read_text()); pj = pj['palette'] if isinstance(pj.get('palette'), dict) else pj   # testis_v1/v2 是 {_note, palette: {...}}
            pal_need.update({k: v for k, v in pj.items() if v is not None and not k.startswith('_')})
    out = ROOT / 'src/anat.js'
    out.write_text('// 本文件由 tools/anat_use.py 从系列解剖库生成，不要手改（改画法去 anatomy/ 升版本，再重新生成）。\n'
                   f'// 母版：{", ".join(names)}\n// 本集的箭头、高亮、标注叠在 scenes.js 里画，不改母版。\n'
                   "const ANL = {};\n" + '\n'.join(parts) + '\n'
                   f"const AN = Object.assign({{}}, {', '.join(f'ANL[{json.dumps(n)}]' for n in names)});\n"
                   "if (typeof module !== 'undefined') module.exports = AN; else window.AN = AN;\n")
    print(f'→ src/anat.js：{len(names)} 个母版、{len(owner)} 个 AN 函数')
    pal = (SB.setdefault('style', {})).setdefault('palette', {})
    miss = {k: v for k, v in pal_need.items() if k not in pal}; diff = {k: (pal[k], v) for k, v in pal_need.items() if k in pal and pal[k] != v}
    if diff: print('  色键值与母版不同（保留本集的值；要和母版一致就手改）：' + '、'.join(f'{k} {a}≠{b}' for k, (a, b) in diff.items()))
    if miss:
        if '--palette' in argv: pal.update(miss); save_sb(SB); print(f'  已把 {len(miss)} 个缺的色键补进 storyboard.style.palette')
        else: print(f'  本集 style.palette 缺 {len(miss)} 个色键：{" ".join(miss)}（加 --palette 补上）')
    return 0

if __name__ == '__main__': sys.exit(main(sys.argv[1:]))

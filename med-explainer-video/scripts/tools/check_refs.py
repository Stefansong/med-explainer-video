#!/usr/bin/env python3
"""参考文献检查（只报告，不改 storyboard）：
① 编号是否按影片首次出现顺序（GB/T 7714—2015 顺序编码制；投稿须知要求片尾按出现先后标出）。出现顺序的依据，任选其一写在 storyboard：
   - references_keys：与 references 平行的 sources 键列表（如 ["WK9", "EAU2026", …]），各场 claims[].src 里引用这些键（"WK9; BERRY1984"）；
   - scenes[].refs：该场引用的文献编号列表（1 起）。
   两个都没有就只查格式，order_checked=false。
② 每条著录的基本格式：文献类型标识 [J]/[M]/[EB/OL]/[C]/[D]/[S]…、年份；[J] 要有 卷(期): 页；[M] 要有 出版地: 出版社, 年；[EB/OL] 要有网址和引用日期 [YYYY-MM-DD]；末尾句点。
运行：python3 tools/check_refs.py [--json]"""
import json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import load_sb
JS = '--json' in sys.argv
SB = load_sb(); REFS = SB.get('references') or []
res = {'count': len(REFS), 'order_checked': False, 'order_ok': None, 'order_problems': [], 'uncited': [], 'format_problems': [], 'types': {}}
# ---------- 出现顺序 ----------
keys = SB.get('references_keys'); claims = {c['id']: c for c in SB.get('claims', [])}
order = []
if keys:
    if len(keys) != len(REFS): res['order_problems'].append(f'references_keys {len(keys)} 个 ≠ references {len(REFS)} 条')
    for sc in SB.get('scenes', []):
        for cid in sc.get('claims', []):
            for k in re.split(r'[;,，；\s]+', (claims.get(cid) or {}).get('src', '') or ''):
                if k and k in keys and k not in order: order.append(k)
        for k in sc.get('refs_keys', []) or []:
            if k in keys and k not in order: order.append(k)
    res['order_checked'] = True
    pos = [keys.index(k) + 1 for k in order]
    for i, (k, p) in enumerate(zip(order, pos)):
        if p != i + 1: res['order_problems'].append({'key': k, 'number': p, 'first_appears_as': i + 1})
    res['uncited'] = [keys[i] for i in range(len(keys)) if keys[i] not in order]
    res['first_appearance'] = order
elif any(sc.get('refs') for sc in SB.get('scenes', [])):
    for sc in SB.get('scenes', []):
        for n in sc.get('refs', []) or []:
            if n not in order: order.append(n)
    res['order_checked'] = True
    for i, n in enumerate(order):
        if n != i + 1: res['order_problems'].append({'number': n, 'first_appears_as': i + 1})
    res['uncited'] = [n for n in range(1, len(REFS) + 1) if n not in order]
    res['first_appearance'] = order
res['order_ok'] = (not res['order_problems']) if res['order_checked'] else None
# ---------- 著录格式 ----------
TYPE = r'\[(J|M|C|D|R|S|P|N|G|DB|CP|EB|A|Z)(/OL)?\]'
for i, r in enumerate(REFS, 1):
    probs = []; m = re.search(TYPE, r); typ = (m.group(1) + (m.group(2) or '')) if m else None
    res['types'][typ or '无'] = res['types'].get(typ or '无', 0) + 1
    if not m: probs.append('缺文献类型标识 [J]/[M]/[EB/OL]…')
    if not re.search(r'(19|20)\d{2}', r): probs.append('缺年份')
    if typ == 'J' and not (re.search(r'(19|20)\d{2}\s*[,，]\s*\d+\s*(\([^)]*\))?\s*[:：]\s*[A-Za-z]?\d+', r) or re.search(r'(19|20)\d{2}\s*\([^)]*\)\s*[:：]\s*[A-Za-z]*\d+', r)): probs.append('[J] 缺 年, 卷(期): 页')   # 无卷号的（Cochrane 等）：年(期): 页 也算
    if typ == 'M' and not re.search(r'[:：]\s*[^,，:：]+[,，]\s*(19|20)\d{2}', r): probs.append('[M] 缺 出版地: 出版社, 年')
    if typ and typ.endswith('/OL'):
        if not re.search(r'https?://|www\.', r): probs.append('联机文献缺网址')
        if not re.search(r'\[\d{4}-\d{2}-\d{2}\]', r): probs.append('联机文献缺引用日期 [YYYY-MM-DD]')
    if not r.rstrip().endswith(('.', '。')): probs.append('末尾缺句点')
    if re.search(r'\s{2,}', r): probs.append('有连续空格')
    if probs: res['format_problems'].append({'n': i, 'problems': probs, 'ref': r[:80]})
print(f"参考文献 {len(REFS)} 条，类型 {res['types']}；出现顺序 " + ('未核（storyboard 没有 references_keys / scenes[].refs）' if not res['order_checked'] else ('OK' if res['order_ok'] else f"有问题 {res['order_problems'][:5]}")) + (f"；未被引用 {res['uncited']}" if res['uncited'] else ''))
for fp in res['format_problems']: print(f"  [{fp['n']}] {'; '.join(fp['problems'])}  ← {fp['ref']}")
print('著录格式', 'OK' if not res['format_problems'] else f"{len(res['format_problems'])} 条有疑点（只报告，请人工核对）")
if JS: print(json.dumps(res, ensure_ascii=False))

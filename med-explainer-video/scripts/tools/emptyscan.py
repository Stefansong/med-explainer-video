#!/usr/bin/env python3
"""空画面检查：看抽帧里每一场的舞台上到底有没有画出东西（frames 阶段自动跑）。
做法：把每张抽帧的舞台区域和它自己的模糊版相减，数“有细节的像素”占多少。只有底色和色块的画面约 2–4%，有人物 / 道具 / 解剖图的画面 ≥ 9%。
  一场里一半以上的抽帧低于 6% → 错误（这一场基本是空的，退出码 1）；四分之一以上 → 提醒。
  确实要留白的场：storyboard 的 scenes[] 里写 "allow_empty": true。
  python tools/emptyscan.py <抽帧目录>      结果另存 <抽帧目录>/empty_scan.json"""
import sys, json, glob, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import load_sb, load_layout
import numpy as np
from PIL import Image, ImageFilter
EMPTY = 6.0

def stage_box(W, H, st):
    """舞台在画面里的位置（去掉上面 18%：第一场的片名会盖在那里）"""
    if W > H and st.get('h'):   # 横屏：舞台是左边一列
        h = st['h']; w = h * st.get('design_width', 1080) / max(1, st.get('design_bottom', 1236) - st.get('design_top', 236)); x, y = st.get('x', 0), st.get('y', 0)
        return (int(x), int(y + 0.18 * h), int(min(W, x + w)), int(y + h))
    return (0, int(H * 420 / 1920), W, int(H * 1236 / 1920))
def ink(f, st):
    im = Image.open(f).convert('RGB'); box = stage_box(*im.size, st); s = im.crop(box); k = 270 / max(1, s.size[0])
    s = s.resize((270, max(8, int(s.size[1] * k))), Image.BILINEAR)
    a = np.asarray(s).astype(np.float32); b = np.asarray(s.filter(ImageFilter.GaussianBlur(8))).astype(np.float32)
    return float((np.abs(a - b).max(-1) > 14).mean() * 100)

def main(d):
    SB = load_sb(); st = (load_layout() or {}).get('stage') or {}
    allow = {s['id'] for s in SB.get('scenes', []) if s.get('allow_empty')}; ids = [s['id'] for s in SB.get('scenes', [])]
    by = {}
    for f in sorted(glob.glob(f'{d}/*.png')):
        sid = os.path.basename(f).split('_')[0]
        if sid in ids: by.setdefault(sid, []).append((os.path.basename(f)[:-4], round(ink(f, st), 1)))
    errs, warns, out = [], [], {}
    for sid in ids:
        v = by.get(sid) or []; n = len(v); e = [name for name, x in v if x < EMPTY]; out[sid] = {'frames': n, 'empty': len(e), 'ink': [x for _, x in v]}
        if n < 3 or sid in allow or not e: continue
        msg = f"{sid}：{n} 张抽帧里有 {len(e)} 张舞台上几乎没有东西（只有底色）"
        if len(e) * 2 >= n: errs.append(msg + '。这一场等于没画：检查镜头函数的尺寸参数是不是写成了很小的数（SH.SP 的高度、SH.IC / SH.steps 的 size 都是像素，几百），东西是不是画到了画面外，或者全都挂在很晚才发生的 cue 上。确实要留白就在这一场写 "allow_empty": true')
        elif len(e) * 4 >= n: warns.append(msg + f"（{'、'.join(e[:4])}…）：这几处画面是空的，补上主体或让上一个东西多留一会儿")
    Path(d, 'empty_scan.json').write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
    for m in errs: print('✗ ' + m)
    for m in warns: print('! ' + m)
    print(f"空画面检查：{len(errs)} 场是空的，{len(warns)} 条提醒" if errs or warns else '空画面检查：每一场都有主体')
    return 1 if errs else 0

if __name__ == '__main__':
    if len(sys.argv) < 2: sys.exit(__doc__)
    sys.exit(main(sys.argv[1]))

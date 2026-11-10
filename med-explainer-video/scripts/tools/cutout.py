#!/usr/bin/env python3
"""3D 立绘 / 道具图标抠底：平台生图出的纯色底图片 → 透明底 PNG（裁到主体、四周留 6 px）→ 登记进 storyboard.assets。
不用 AI 抠图模型：从图片四边取背景色，与背景色相近、且和四边连通的像素当背景（主体内部同色的地方不会被挖掉），边缘按色差做半透明过渡并去掉背景色溢色。
出图时背景要纯色、和主体差别大：人物立绘用纯品红 #FF00FF 或纯绿 #00FF00 底；不要渐变、不要地面阴影、不要场景。原图已是透明底的直接裁边。

  python tools/cutout.py <图片> <id> [--kind sprite|icon] [--tol 34] [--no-register]
     sprite（默认）→ assets/lib/characters/sprites/<id>.png，场景代码用 SH.SP(c, A, '<id>', x, 脚底y, 高度)
     icon           → assets/lib/props/<id>.png，场景代码用 SH.IC(c, A, '<id>', x, y, 尺寸)
     id 建议：立绘 sp_<角色>_<动作>，图标 ic_<物品>；默认把 {"src": 路径} 写进 storyboard.assets[id]
  在专题目录下跑（或设 KEPU_PROJECT）。结果顺手出一张棋盘格预览 render/cutout/<id>_check.png，看边缘干不干净。"""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import ROOT, load_sb, save_sb
import numpy as np
from PIL import Image

def main(a):
    pos = [x for i, x in enumerate(a) if not x.startswith('--') and (i == 0 or a[i - 1] not in ('--kind', '--tol'))]
    if len(pos) < 2: sys.exit(__doc__)
    src, iid = Path(pos[0]), pos[1]
    kind = a[a.index('--kind') + 1] if '--kind' in a else ('icon' if iid.startswith('ic_') else 'sprite')
    tol = float(a[a.index('--tol') + 1]) if '--tol' in a else 34.0
    im = Image.open(src).convert('RGBA'); px = np.asarray(im).astype(np.float32); A0 = px[..., 3]
    if (A0 < 10).mean() >= 0.2: alpha = A0   # 已经是透明底
    else:
        from scipy import ndimage
        rgb = px[..., :3]; h, w = A0.shape; b = max(2, int(min(h, w) * 0.02))
        border = np.concatenate([rgb[:b].reshape(-1, 3), rgb[-b:].reshape(-1, 3), rgb[:, :b].reshape(-1, 3), rgb[:, -b:].reshape(-1, 3)])
        bg = np.median(border, 0); d = np.sqrt(((rgb - bg) ** 2).sum(-1))
        if bg.max() - bg.min() > 120:
            # 饱和底色（品红 / 绿 / 蓝…）：色差抠像。键值 = 背景的主通道最小值 − 其余通道最大值；越接近背景的键值越透明。
            # 围住的空洞（杯柄里）和半透明处（热气、玻璃）都按颜色处理，不靠连通性
            D = bg > 128; O = ~D
            key = rgb[..., D].min(-1) - (rgb[..., O].max(-1) if O.any() else 0); bk = bg[D].min() - (bg[O].max() if O.any() else 0)
            a_ = 1 - np.clip(key / max(1.0, bk), 0, 1)   # 混合像素按比例还原（热气 30% 白 + 70% 品红 → alpha 0.3、颜色还原成白）
            alpha = np.where(a_ > 0.75, 1.0, a_) * 255     # 主体上略带底色倾向的颜色（浅粉衣服）不变半透明；主体本身偏品红就改用绿底出图
        else:
            # 中性底色（白 / 灰）：与四边连通、和底色相近的像素当背景（主体里同色的地方不挖）
            near = d < tol; lab, n = ndimage.label(near)
            edge = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
            bgmask = np.isin(lab, list(edge))
            alpha = np.where(bgmask, 0.0, 255.0)
            ring = ndimage.binary_dilation(bgmask, iterations=2) & ~bgmask   # 主体外缘 2 px：按色差做半透明
            alpha[ring] = np.clip((d[ring] - tol) / tol, 0, 1) * 255
        if (alpha < 10).mean() < 0.15: print(f'!! 背景只认出 {(alpha < 10).mean():.0%}：底色不纯或和主体太像，换纯色底重出，或调 --tol')
        k = (alpha > 0) & (alpha < 255)   # 去溢色：半透明像素减掉背景色的成分
        if k.any():
            t = (alpha[k] / 255.0)[:, None]; rgb[k] = np.clip((rgb[k] - (1 - t) * bg) / np.maximum(t, 0.05), 0, 255)
        px[..., :3] = rgb
    alpha = np.asarray(alpha, np.float32).copy(); alpha[:3] = 0; alpha[-3:] = 0; alpha[:, :3] = 0; alpha[:, -3:] = 0   # 生图常在最外圈留一两列杂色（立绘旁边会多一条细线）
    px[..., 3] = np.where(alpha > 245, 255, alpha)
    hb = max(2, int(alpha.shape[0] * 0.02)); wb = max(2, int(alpha.shape[1] * 0.02))
    side = max((alpha[:, :wb] > 24).mean(), (alpha[:, -wb:] > 24).mean()); bottom = (alpha[-hb:] > 24).mean()   # 主体一般碰不到左右边；脚可以碰底边，但占不到一半
    if side > 0.05 or bottom > 0.5: print(f'!! 抠完图左右边还有 {side:.0%}、底边 {bottom:.0%} 不透明：多半是渐变底、地面或阴影没抠掉。出图时写明“纯品红 #FF00FF 纯色背景、无地面、无阴影”重出，或调大 --tol')
    ys, xs = np.where(px[..., 3] > 24)
    if not len(xs): sys.exit('抠完什么都没剩：检查图片或调小 --tol')
    x0, x1, y0, y1 = max(0, xs.min() - 6), min(px.shape[1], xs.max() + 7), max(0, ys.min() - 6), min(px.shape[0], ys.max() + 7)
    out_im = Image.fromarray(px.astype(np.uint8), 'RGBA').crop((x0, y0, x1, y1))
    rel = f"assets/lib/{'props' if kind == 'icon' else 'characters/sprites'}/{iid}.png"; out = ROOT / rel; out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists(): sys.exit(f'{rel} 已存在：定稿素材不覆盖，换个 id（加 _v2）')
    out_im.save(out)
    chk = ROOT / 'render/cutout' / f'{iid}_check.png'; chk.parent.mkdir(parents=True, exist_ok=True)   # 棋盘格预览
    W, H = out_im.size; g = np.indices((H, W)).sum(0) // 16 % 2; board = Image.fromarray(np.where(g[..., None], 205, 245).repeat(3, -1).astype(np.uint8)).convert('RGBA')
    board.alpha_composite(out_im); board.convert('RGB').save(chk)
    print(f'→ {rel}（{W}×{H}，透明 {(np.asarray(out_im)[..., 3] < 10).mean():.0%}）；预览 {chk.relative_to(ROOT).as_posix()}')
    if '--no-register' not in a:
        SB = load_sb(); SB.setdefault('assets', {})[iid] = {'src': rel}; save_sb(SB); print(f'  已登记 storyboard.assets.{iid}')

if __name__ == '__main__': main(sys.argv[1:])

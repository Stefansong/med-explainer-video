#!/usr/bin/env python3
"""成片扫描（审片用，不调任何外部模型；结论由审核员看输出与图来下）。从成片 mp4 直接取帧，不看开发渲染器。
  jumps <mp4> [--thr 12]                 30 fps 灰度 108×192 相邻帧差，> thr 的峰值逐个列出：对照是不是有意的切换（片名砸入、硬切、转场），
                                         查“转场里闪回代码人物 / 片段放完回退 / 漏帧”最可靠（肾结石 v4、v14 都靠它抓到）
  edges <mp4>                            每 0.5 s 一帧，量字卡区、字幕区文字的左右边缘与中心：右缘 ≤ safe.right_x、居中（中心中位数 ≈ labels.center_x）
  top <mp4> [--every 4] [--out PNG]      顶部带（0 – 舞台顶 + 200 px）联系表：看主体有没有钻到进度条 / 章节名 / 片名下面
  warp <old.mp4> <old_timeline.json> <new.mp4> [<new_timeline.json>] [--thr 18]
                                         台词时长变了（换 take、改语速）后，新成片每帧按“逐句线性、句间平移”的时间映射对到旧成片同一叙事点逐帧比，
                                         只比舞台区（避开顶栏和字卡字幕区）；差异中位数 ≈ 3 才算对齐，> thr 的连续段逐个看（3D 片段没撑满窗口、慢放没对时）
运行：cd <专题> && python tools/scan.py jumps render/<project>_final.mp4"""
import sys, json, subprocess
from pathlib import Path
import numpy as np
ROOT = Path.cwd()
def layout():
    p = ROOT / 'layout.json'; return json.loads(p.read_text()) if p.exists() else {}
def gray_frames(v, w=108, h=192, fps=30):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(v), '-vf', f'fps={fps},scale={w}:{h},format=gray', '-f', 'rawvideo', '-'], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, h, w).astype(np.float32)
def opt(a, k, d):
    return type(d)(a[a.index(k) + 1]) if k in a else d

def jumps(a):
    v = a[0]; thr = opt(a, '--thr', 12.0); f = gray_frames(v)
    d = np.abs(np.diff(f, axis=0)).mean(axis=(1, 2))
    print(f'frames {len(f)}  median diff {np.median(d):.2f}  （> {thr} 的峰值，逐个确认是有意的切换）')
    for i in np.where(d > thr)[0]: print(f'  {(i + 1) / 30:8.2f}s  diff {d[i]:5.1f}')

def edges(a):
    from scipy import ndimage
    v = a[0]; L = layout(); W = L.get('width', 1080); right = (L.get('safe') or {}).get('right_x', 900)
    lb = (L.get('labels') or {}).get('band', [1192, 1418]); sb = L.get('subtitle') or {}; sy, ss = sb.get('y', 1560), sb.get('size', 66)
    bands = {'label': (lb[0] - 10, lb[1] + 10), 'sub': (int(sy - ss * 0.75), int(sy + ss * 0.75))}
    y0 = min(b[0] for b in bands.values()) // 2 * 2; y1 = (max(b[1] for b in bands.values()) + 1) // 2 * 2   # yuv420 裁切要偶数
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(v), '-vf', f'fps=2,crop={W}:{y1 - y0}:0:{y0}', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True, check=True).stdout
    fr = np.frombuffer(raw, np.uint8).reshape(-1, y1 - y0, W, 3)
    out = {k: [] for k in bands}; bad = []
    for i, f in enumerate(fr):
        white = f.min(axis=2) > 243; dark = f.max(axis=2) < 90; m = white & ndimage.binary_dilation(dark, iterations=3)   # 白字黑描边 / 白底黑字：两者相邻处就是文字
        for k, (b0, b1) in bands.items():
            cols = np.where(m[b0 - y0:b1 - y0].sum(axis=0) >= 3)[0]
            if len(cols) > 20:
                l, r = int(cols.min()), int(cols.max()); out[k].append((i / 2 + 0.25, l, r, (l + r) / 2))
                if r > right: bad.append((k, i / 2 + 0.25, r))
    cx = (L.get('labels') or {}).get('center_x', W / 2)   # 字卡写了 align: center 才居中；默认模板字卡左对齐，字卡区的“中心”一项只作参考
    for k, xs in out.items():
        if not xs: print(f'{k}: 没测到'); continue
        cs = np.array([x[3] for x in xs]); print(f'{k}: {len(xs)} 帧  左缘最小 {min(x[1] for x in xs)}  右缘最大 {max(x[2] for x in xs)}（限 {right}）  中心中位数 {np.median(cs):.0f}（目标 {cx}）  中心偏左 >20 px 的 {int((cs < cx - 20).sum())} 帧（长文本让出右侧，正常）')
    for k, t, r in bad: print(f'  !! {k} {t:.2f}s 右缘 {r} > {right}')

def top(a):
    from PIL import Image, ImageDraw
    v = a[0]; every = opt(a, '--every', 4.0); L = layout(); W = L.get('width', 1080)
    h = int(((L.get('stage') or {}).get('top', 260)) + 200); import probe; dur = probe.duration(v)
    out = opt(a, '--out', str(ROOT / 'render' / (Path(v).stem + '_top.png'))); ts = np.arange(every / 2, dur, every); tw = 270; th = int(h * tw / W); cols = 8
    sheet = Image.new('RGB', (cols * (tw + 4), -(-len(ts) // cols) * (th + 4)), (255, 0, 255)); dr = ImageDraw.Draw(sheet)
    for k, t in enumerate(ts):
        raw = subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{t:.2f}', '-i', str(v), '-frames:v', '1', '-vf', f'crop={W}:{h}:0:0,scale={tw}:{th}', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True).stdout
        if len(raw) < tw * th * 3: continue
        im = Image.frombytes('RGB', (tw, th), raw[:tw * th * 3]); x, y = (k % cols) * (tw + 4), (k // cols) * (th + 4); sheet.paste(im, (x, y)); dr.rectangle([x, y, x + 52, y + 14], fill=(0, 0, 0)); dr.text((x + 2, y + 1), f'{t:.0f}s', fill=(255, 255, 0))
    sheet.save(out); print(out, sheet.size)

def warp(a):
    ov, otl, nv = a[0], a[1], a[2]; ntl = a[3] if len(a) > 3 and not a[3].startswith('--') else str(ROOT / 'render/timeline.json'); thr = opt(a, '--thr', 18.0)
    O = json.load(open(otl))['scenes']; N = json.load(open(ntl))['scenes']; L = layout(); H = L.get('height', 1920)
    st = L.get('stage') or {}; r0, r1 = int((st.get('top', 230)) / H * 192), int(min(st.get('bottom', 1300), (L.get('labels') or {}).get('band', [1300])[0]) / H * 192)
    A, B = gray_frames(ov), gray_frames(nv)
    def inv(o, n, tn):   # 新场内时间 → 旧场内时间（逐句线性、句间平移）
        ol, nl = o['lines'], n['lines']
        if not nl or tn <= nl[0]['start']: return tn
        for i, (x, y) in enumerate(zip(ol, nl)):
            if y['start'] <= tn <= y['end']: return x['start'] + (tn - y['start']) * (x['end'] - x['start']) / max(1e-6, y['end'] - y['start'])
            nxt = nl[i + 1]['start'] if i + 1 < len(nl) else 1e9
            if y['end'] < tn < nxt: return min(x['end'] + (tn - y['end']), ol[i + 1]['start'] if i + 1 < len(ol) else 1e9)
        return tn
    rows = []
    for o, n in zip(O, N):
        if o['id'] != n['id']: sys.exit(f'场景顺序不同：{o["id"]} vs {n["id"]}')
        for k in range(int(n['start'] * 30) + 6, int(n['end'] * 30) - 6):
            tn = k / 30; j = int(round((o['start'] + inv(o, n, tn - n['start'])) * 30))
            if j < len(A) and k < len(B): rows.append((float(np.abs(A[j][r0:r1] - B[k][r0:r1]).mean()), tn, j / 30, n['id']))
    ds = np.array([r[0] for r in rows]); print(f'frames {len(rows)}  median diff {np.median(ds):.2f}  p99 {np.percentile(ds, 99):.2f}（中位数 ≈ 3 = 对齐）')
    runs = []
    for r in sorted([r for r in rows if r[0] > thr], key=lambda r: r[1]):
        if runs and r[1] - runs[-1][-1][1] < 0.2: runs[-1].append(r)
        else: runs.append([r])
    for g in runs: print(f'  {g[0][3]} 新 {g[0][1]:.2f}–{g[-1][1]:.2f}s（旧 {g[0][2]:.2f}s）最大差 {max(x[0] for x in g):.1f}，{len(g)} 帧')

if __name__ == '__main__':
    if len(sys.argv) < 3 or sys.argv[1] not in ('jumps', 'edges', 'top', 'warp'): sys.exit(__doc__)
    globals()[sys.argv[1]](sys.argv[2:])

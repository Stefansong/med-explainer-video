#!/usr/bin/env python3
"""换镜暗谷扫描（10-24 并进 QA 门，qa.py 调用；也可单独跑）：场内换镜时新旧镜头同时半透明（双向淡化），中间透出画布底色，舞台一下子变灰。
nocturia 正式版 v1 的成片审核员抓到 5 处（亮度掉 7–11%），QA 门、预演都没拦住；本扫描在 v1 上找出 29.2 / 125.7 / 206.9 / 214.2 / 221.0 / 237.7 s 六处（125.7 s 后来也证实是 s06 场首双向淡化），
psa / foam 正式版、nocturia v2 一处都没有。
方法：只取舞台区（竖屏 layout.stage 的 top–bottom 整宽，1080×1070 @ y 230；横屏 layout_land.stage 的矩形，x 60 y 104 的 950×880），按 30 fps 用 ffmpeg signalstats 算平均亮度 YAVG。
  某帧比前 12 帧（0.4 s）的最大值、也比后 12 帧的最大值都低 5% 以上，且是前后 3 帧内的最小值 → 一个暗谷；相隔不到 6 帧的算同一个（取最深的那帧）。
分两类（10-24 补，torsion 201.37 s 的误报）：取谷底前、后 12 帧里各自最亮的那帧比画面相关系数——
  < SHOT_CORR（0.7）= 换镜（前后是两个不同镜头）：透底穿帮，qa 判失败；
  ≥ 0.7 = 镜头内的明暗变化（同一画面）：警示灯一闪一闪、亮的解剖圆窗滑出画面再滑回（torsion）、关灯，多半有意，qa 只警告。
  再加一条（10-24 第三轮，主会话抽帧看过 bph 正式版 3.13 s、381.30 s）：落在引擎场景转场窗口内（场界 ±TD/2，engine.js 的 TD = 0.8 s）的谷只警告——
  转场是不透明水浪（新场画在离屏缓冲里、用裁切路径揭开），结构上不会透底；窗口里的变暗来自内容：s00 封面进 s01 时片名条、章节签淡入（在舞台区里），s12 开场“夜里到天亮”。
  场界前后本来就是两个场景，“前后最亮帧相关”天然 < 0.7，不加这条就会把所有“进入暗开场”的转场判失败。
  已知 20 处（重标后）：真穿帮 12 处（nocturia v1 6、bph 正式版 189.63 / 388.57、bph_on_template 预演 185.1 / 190.77 / 200.63 / 393.1）前后相关 −0.03–0.53、离场界 ≥1.79 s，全判失败；
  否 8 处——场首 3（bph 3.13 / 381.30、预演 385.83，离场界 0.12–0.13 s）、警示灯 4（相关 0.997–0.998）、torsion 滑窗 1（0.85）——全只警告。foam_3d 预演 v16、正式版（InfiniteTalk 3D 片段）零暗谷。
  试过“谷底帧与前、后最亮帧各自比、像其中一边就不算透底”：真穿帮的谷底帧多半就是某一侧镜头被压暗（相关不管亮度缩放），12 处里 9 处会被放过，torsion 滑窗反而判失败，弃用。
白名单（有意的暗场：关灯、闪电、闭眼……）写在 storyboard.qa.dips_ok，每条要写 why：
  {"scene": "s04", "t": 3.2, "why": "关灯"}             场内秒 ± tol（默认 0.4 s）
  {"scene": "s04", "cue": "dark", "dt": 0.1, "why": …}  cue 时刻 + dt ± tol
  {"scene": "s04", "why": …}                            整场
  {"T": 123.4, "why": …}                                成片绝对秒 ± tol（时间轴一变就失效，尽量用前三种）
用法：python3 tools/dipscan.py [<mp4> …] [--json]（不给文件就扫本专题正式版 render[/land]/{project}_final|master.mp4；
      扫别的专题：KEPU_PROJECT=<专题目录> python3 _template/tools/dipscan.py <该专题的 mp4>，只读，不写任何文件）"""
import json, re, subprocess, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
FPS, WIN, LOCAL, MERGE, DROP, TOL, SHOT_CORR = 30, 12, 3, 6, 0.05, 0.4, 0.7
def engine_td():
    """引擎场景转场时长（engine.js `const TD = 0.8`）；读不到按 0.8"""
    try:
        from _common import ROOT
        m = re.search(r'const TD = ([\d.]+)', (ROOT / 'src/engine.js').read_text()); return float(m.group(1)) if m else 0.8
    except Exception: return 0.8

def stage_crop(layout, W, H):
    """舞台区裁切 (w, h, x, y)，都取偶数（yuv420 裁切要偶数）；横屏 stage 有 x/y/h 矩形，竖屏只有 top/bottom"""
    St = (layout or {}).get('stage') or {}; ev = lambda v: int(v) // 2 * 2
    if St.get('x') is not None:
        k = St['h'] / ((St.get('design_bottom') or 1236) - (St.get('design_top') or 236)); w, h, x, y = (St.get('design_width') or 1080) * k, St['h'], St['x'], St['y']
    else: x, y, w, h = 0, St.get('top', 230), W, St.get('bottom', 1300) - St.get('top', 230)
    x, y = ev(x), ev(y); return min(ev(w), W - x), min(ev(h), H - y), x, y

def yavg(mp4, crop, fps=FPS):
    w, h, x, y = crop
    out = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(mp4), '-vf', f'fps={fps},crop={w}:{h}:{x}:{y},scale=108:-2,signalstats,metadata=print:key=lavfi.signalstats.YAVG:file=-', '-f', 'null', '-'],
                         capture_output=True, text=True, check=True).stdout
    return np.array([float(v) for v in re.findall(r'YAVG=([\d.]+)', out)])

def gray_at(mp4, crop, frame, fps=FPS):
    """第 frame 帧（按 fps 计）的舞台区灰度小图（108 宽），与 yavg 同一套裁切缩放"""
    w, h, x, y = crop
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{frame / fps:.4f}', '-i', str(mp4), '-frames:v', '1', '-vf', f'crop={w}:{h}:{x}:{y},scale=108:-2,format=gray', '-f', 'rawvideo', '-'], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).astype(float)

def find_dips(y, win=WIN, local=LOCAL, merge=MERGE, drop=DROP):
    """[(帧号, 掉多少（0–1）, 前侧最亮, 后侧最亮)]：比两侧 win 帧内的最大值都暗 drop 以上、又是 ±local 帧内最小值；相隔 < merge 帧的并成一个、留最深的"""
    hits = []
    for i in range(win, len(y) - win):
        l, r = y[i - win:i].max(), y[i + 1:i + 1 + win].max()
        if y[i] < (1 - drop) * min(l, r) and y[i] == y[max(0, i - local):i + local + 1].min():
            d = (i, 1 - y[i] / min(l, r), float(l), float(r))
            if hits and i - hits[-1][0] < merge:
                if d[1] > hits[-1][1]: hits[-1] = d
            else: hits.append(d)
    return hits

def where(T, TL):
    """成片秒 → (场, 场内秒, 最近的 cue 名, 离 cue 秒数)"""
    sc = next((s for s in (TL or {}).get('scenes', []) if s['start'] <= T < s['end']), None)
    if not sc: return None, None, None, None
    cues = sorted(((n, sc['start'] + t) for n, t in (sc.get('cues') or {}).items()), key=lambda c: abs(c[1] - T))
    return sc['id'], round(T - sc['start'], 2), (cues[0][0] if cues else None), (round(T - cues[0][1], 2) if cues else None)

def allowed_by(T, TL, rules):
    """命中的白名单条目（storyboard.qa.dips_ok），没有就 None"""
    S = {s['id']: s for s in (TL or {}).get('scenes', [])}; sid = where(T, TL)[0]
    for r in rules or []:
        tol = float(r.get('tol', TOL))
        if 'T' in r:
            if abs(float(r['T']) - T) <= tol: return r
            continue
        if r.get('scene') != sid or sid not in S: continue
        st = S[sid]['start']
        if 'cue' in r:
            ct = (S[sid].get('cues') or {}).get(r['cue'])
            if ct is not None and abs(st + ct + float(r.get('dt', 0)) - T) <= tol: return r
        elif 't' in r:
            if abs(st + float(r['t']) - T) <= tol: return r
        else: return r
    return None

def scan(mp4, layout, TL=None, SB=None, fps=FPS):
    """→ {crop, fps, frames, dips: [{T, frame, drop_pct, scene, t_in_scene, near_cue, cue_dt, allowed}]}"""
    import probe; pr = probe.video(mp4)
    crop = stage_crop(layout, pr['width'], pr['height']); y = yavg(mp4, crop, fps); rules = ((SB or {}).get('qa') or {}).get('dips_ok') or []; out = []
    bounds = [s['start'] for s in (TL or {}).get('scenes', [])[1:]]; half = engine_td() / 2 + 0.05   # 场界（含封面 s00→s01）；窗口 ±TD/2，多留一帧多的余量
    for i, d, l, r in find_dips(y):
        T = round(i / fps, 2); sid, tin, cue, cdt = where(T, TL); ok = allowed_by(T, TL, rules)
        ib, ia = i - WIN + int(np.argmax(y[i - WIN:i])), i + 1 + int(np.argmax(y[i + 1:i + 1 + WIN]))   # 谷底前、后最亮的那帧：比它们像不像，判断是不是换镜
        cr = float(np.corrcoef(gray_at(mp4, crop, ib, fps), gray_at(mp4, crop, ia, fps))[0, 1])
        nb = min((abs(T - b) for b in bounds), default=None); in_tr = nb is not None and nb <= half
        kind = '转场窗口内' if in_tr else ('换镜透底' if cr < SHOT_CORR else '镜头内变暗')
        out.append({'T': T, 'frame': i, 'drop_pct': round(d * 100, 1), 'yavg': round(float(y[i]), 1), 'before_max': round(l, 1), 'after_max': round(r, 1), 'scene': sid, 't_in_scene': tin, 'near_cue': cue, 'cue_dt': cdt,
                    'ref_corr': round(cr, 3), 'to_boundary_s': None if nb is None else round(nb, 2), 'shot_change': kind == '换镜透底', 'kind': kind, 'allowed': (ok.get('why') or '白名单（没写 why）') if ok else None})
    return {'crop': 'crop={}:{}:{}:{}'.format(*crop), 'fps': fps, 'frames': int(len(y)), 'seconds': round(len(y) / fps, 2), 'rule': f'比前后各 {WIN} 帧的最大值都暗 ≥{DROP:.0%}、±{LOCAL} 帧内最低、相隔 <{MERGE} 帧算一个；场界 ±{half:.2f} s 内算转场窗口（不透明水浪）；其余前后最亮帧画面相关 <{SHOT_CORR} 算换镜', 'dips': out}

if __name__ == '__main__':
    from _common import load_layout, load_tl, load_sb, render_dir, LAND
    args = [a for a in sys.argv[1:] if not a.startswith('--')]; SB = load_sb(); L = load_layout()
    try: TL = load_tl()
    except FileNotFoundError: TL = None
    files = args or [str(render_dir() / f"{SB['project']}_{'master' if LAND else 'final'}.mp4")]
    res = {f: scan(f, L, TL, SB) for f in files}
    if '--json' in sys.argv: print(json.dumps(res, ensure_ascii=False)); sys.exit()
    for f, r in res.items():
        bad = [d for d in r['dips'] if not d['allowed']]
        print(f"{Path(f).name}  {r['seconds']} s  舞台 {r['crop']}：暗谷 {len(r['dips'])} 处（未列入白名单 {len(bad)}）")
        for d in r['dips']: print(f"  {d['T']:8.2f} s  掉 {d['drop_pct']:4.1f}%  {d['kind']}（前后相关 {d['ref_corr']:.2f}）  {d['scene'] or '?'} 场内 {d['t_in_scene']} s" + (f"（cue {d['near_cue']} {d['cue_dt']:+.2f} s）" if d['near_cue'] else '') + (f"  ← 白名单：{d['allowed']}" if d['allowed'] else ''))

#!/usr/bin/env python3
"""音效库（程序合成，不用外部素材；mix.py 从这里取）。每个音效是无参/带默认参数的函数，返回 48 kHz 单声道 float 数组（峰值约 0.3–0.8，响度由 storyboard.audio.sfx 的 gain 定）。
storyboard.audio.sfx 条目：{"scene", "cue"|"at", "dt", "sfx": kind, "gain", "every", "count"|"until_cue"|"until", "params": {...}}；params 原样传给音效函数（如 snore 的 cycles、flush 的 dur）。
kind 一览（docs/sfx.md 有时长、建议 gain、用途）：
  tap 字卡出现（两声轻点，mix 自动加）| swish 转场气流声（mix 自动加）| pop 啵 | splash 水浪 | thud 落地闷响 | zap 激光/电 | crack 碎裂 | boing 弹簧 | chime 提示铃 | siren 警报 | tick 钟表嗒 | plip 水滴 | hiss 蒸汽/喷雾 | wind 风 | clink 金属碰 | chirp 鸟鸣/电子叫
  flush 马桶冲水 ~2.8 s（起势 → 水流漩涡 → 回落滴水）| snore 老年男性打鼾（吸气带鼾、呼气轻；cycles 次）| gasp 憋气后猛吸一口再喘两下 ~1.5 s（10-22 夜尿集 s08 手机录音）
试听：python3 tools/sfx.py demo [out_dir]  → 每种一个 wav + 新三种连播（默认 render/sfx_demo/）"""
import sys
import numpy as np, scipy.signal as ss
SR = 48000
rng = np.random.default_rng(3)
def env(n, a, d): t = np.arange(n) / SR; return np.minimum(1, t / max(a, 1e-4)) * np.exp(-t / d)
def _bp(x, lo, hi, order=2): return ss.sosfilt(ss.butter(order, [lo, hi], 'bandpass', fs=SR, output='sos'), x)
def _lp(x, fc, order=2): return ss.sosfilt(ss.butter(order, fc, 'lowpass', fs=SR, output='sos'), x)
def _resonate(x, f, r=0.99):
    """时变二阶谐振器（中心频率数组 f，Hz；r 越接近 1 越尖）：漩涡、气道共鸣用"""
    f = np.asarray(f, dtype=float); c = 2 * r * np.cos(2 * np.pi * f / SR); r2 = r * r; g = 1 - r
    y = np.zeros(len(x)); y1 = y2 = 0.0
    for i in range(len(x)):
        y0 = g * x[i] + c[i] * y1 - r2 * y2; y[i] = y0; y2 = y1; y1 = y0
    return y
def _ramp(t, xs, ys): return np.interp(t, xs, ys)
def _norm(x, peak): return x / (np.max(np.abs(x)) + 1e-9) * peak

# ---------- 原有音效（从 mix.py 原样搬来，10-22）----------
def pop():
    n = int(0.12 * SR); tt = np.arange(n) / SR; f = 900 * np.exp(-tt * 18) + 420; ph = 2 * np.pi * np.cumsum(f) / SR
    return np.sin(ph) * env(n, 0.002, 0.04)
def splash():   # 水浪：滤波噪声 + 气泡
    n = int(0.8 * SR); x = rng.standard_normal(n); y = np.zeros(n); a = 0.0
    for i in range(n): cc = 0.03 + 0.2 * np.sin(np.pi * i / n); a += cc * (x[i] - a); y[i] = a
    y *= 0.35 * np.sin(np.pi * np.arange(n) / n) ** 2
    for b in range(6):
        m = int(0.08 * SR); tt = np.arange(m) / SR; f0 = 500 + 500 * rng.random(); add_at = int((0.2 + 0.08 * b) * SR)
        y[add_at:add_at + m] += 0.4 * np.sin(2 * np.pi * (f0 + 2500 * tt) * tt) * env(m, 0.002, 0.02)
    return y
def thud():
    n = int(0.3 * SR); tt = np.arange(n) / SR; return np.sin(2 * np.pi * (140 * np.exp(-tt * 9) + 50) * tt) * env(n, 0.002, 0.08) + 0.3 * rng.standard_normal(n) * env(n, 0.001, 0.015)
def zap():
    n = int(0.5 * SR); tt = np.arange(n) / SR; return 0.5 * np.sign(np.sin(2 * np.pi * (1800 + 600 * np.sin(tt * 60)) * tt)) * env(n, 0.005, 0.15)
def crack():
    n = int(0.6 * SR); x = rng.standard_normal(n) * env(n, 0.001, 0.12); return x + 0.6 * np.sin(2 * np.pi * 90 * np.arange(n) / SR) * env(n, 0.002, 0.1)
def boing(): n = int(0.35 * SR); tt = np.arange(n) / SR; return np.sin(2 * np.pi * (300 + 260 * np.sin(tt * 40) * np.exp(-tt * 6)) * tt) * env(n, 0.003, 0.15)
def chime():
    n = int(1.0 * SR); tt = np.arange(n) / SR
    return sum(a * np.sin(2 * np.pi * f * tt) * np.exp(-tt * d) for f, a, d in [(1046.5, 0.6, 3.5), (1568, 0.35, 4.5), (2093, 0.15, 6)])
def siren(dur=2.4):
    n = int(dur * SR); tt = np.arange(n) / SR; f = 700 + 250 * np.sign(np.sin(2 * np.pi * 1.6 * tt)); ph = 2 * np.pi * np.cumsum(f) / SR
    return 0.5 * np.sin(ph) * np.minimum(1, tt / 0.1) * np.minimum(1, (dur - tt) / 0.4)
def tick(): n = int(0.03 * SR); tt = np.arange(n) / SR; return 0.7 * np.sin(2 * np.pi * 1900 * tt) * env(n, 0.001, 0.005) + 0.4 * np.sin(2 * np.pi * 2700 * tt) * env(n, 0.001, 0.004)   # 木鱼式“嗒”，不用白噪声
def plip(): n = int(0.18 * SR); tt = np.arange(n) / SR; return np.sin(2 * np.pi * (600 + 900 * tt / 0.18) * tt) * env(n, 0.002, 0.05)
def hiss(dur=1.4):
    n = int(dur * SR); x = rng.standard_normal(n); y = np.zeros(n); a = 0.0
    for i in range(n): cc = 0.5 + 0.4 * np.sin(np.pi * i / n); a += cc * (x[i] - a); y[i] = x[i] - a
    return y * np.sin(np.pi * np.arange(n) / n) ** 0.7
def wind(dur=2.5):
    n = int(dur * SR); x = rng.standard_normal(n); y = np.zeros(n); a = 0.0
    for i in range(n): cc = 0.004 + 0.01 * (1 + np.sin(2 * np.pi * i / n * 3)); a += cc * (x[i] - a); y[i] = a
    return y / (np.max(np.abs(y)) + 1e-9) * np.sin(np.pi * np.arange(n) / n)
def clink(): n = int(0.6 * SR); tt = np.arange(n) / SR; return sum(a * np.sin(2 * np.pi * f * tt) * np.exp(-tt * d) for f, a, d in [(2400, 0.5, 9), (3700, 0.3, 12), (5200, 0.15, 15)])
def chirp():
    n = int(0.25 * SR); tt = np.arange(n) / SR; return np.sin(2 * np.pi * (3000 + 1800 * np.sin(tt * 60)) * tt) * env(n, 0.005, 0.06)

# ---------- 10-22 新增：冲水 / 呼噜 / 猛喘（夜尿集 s08 手机录音；泡沫尿、PSA 也要冲水）----------
def flush(dur=3.0, tail=1.4):
    """马桶冲水：拉杆咔哒 + 水闸打开的冲（起势 0–0.5 s）→ 湍流水声 + 漩涡（谐振中心 1500→400 Hz 下扫）+ 低频轰鸣 + 几声咕咚 → 回落：水声收、滴水两三声；之后 tail 秒水箱注水细丝慢慢淡出（Gemini 10-22 听后说收得太急，加了这段尾巴）。总长 dur + tail"""
    T = dur; n = int((dur + tail) * SR); t = np.arange(n) / SR
    click = np.zeros(n); m = int(0.012 * SR); click[:m] = rng.standard_normal(m) * np.exp(-np.arange(m) / (0.002 * SR)) * 0.8
    water = _bp(rng.standard_normal(n), 300, 4500) * _ramp(t, [0, 0.08, 0.5, T * 0.57, T * 0.79, T], [0, 0.6, 1.0, 0.9, 0.3, 0.0]) * (0.75 + 0.25 * np.sin(2 * np.pi * 7 * t + 3 * np.sin(2 * np.pi * 1.3 * t)))
    fc = _ramp(t, [0, T * 0.32, T * 0.36, T * 0.86, T], [1100, 1100, 1000, 380, 340])
    swirl = _resonate(rng.standard_normal(n) * 0.08, fc, 0.982) * _ramp(t, [0, T * 0.32, T * 0.46, T * 0.82, T], [0, 0.0, 1.0, 0.7, 0]) * 1.4   # 谐振放宽（r 0.982）、起点 1100 Hz：Gemini 说 1500 Hz/0.992 像金属啸叫
    rumble = _lp(rng.standard_normal(n), 140) * _ramp(t, [0, 0.2, T * 0.54, T * 0.86, T], [0, 1.0, 0.8, 0.2, 0]) * 2.5
    glug = np.zeros(n)
    for k in range(5):
        i = int((T * 0.46 + k * 0.28 + rng.random() * 0.08) * SR); m = int(0.09 * SR)
        if i + m > n: break
        tt = np.arange(m) / SR; fr = 320 * np.exp(-tt * 12) + 110; glug[i:i + m] += np.sin(2 * np.pi * np.cumsum(fr) / SR) * env(m, 0.004, 0.03) * 0.5
    drips = np.zeros(n)
    for t0 in (T - 0.35, T - 0.18, T - 0.06):
        i = int(t0 * SR); m = int(0.08 * SR)
        if 0 <= i and i + m <= n: tt = np.arange(m) / SR; drips[i:i + m] += np.sin(2 * np.pi * (900 + 1800 * tt / 0.08) * tt) * env(m, 0.001, 0.02) * 0.25
    # 水箱注水：细水流（700–3500 Hz 噪声、22 Hz 抖动）+ 水位上升的空腔音（谐振 250→620 Hz 上扫）；起得比水声收得晚，尾部慢慢淡出（Gemini 两轮听后说缺注水声，调大了）
    env_r = _ramp(t, [0, T * 0.72, T * 0.92, T + tail * 0.55, T + tail], [0, 0, 1.0, 0.8, 0])
    trickle = _bp(rng.standard_normal(n), 700, 3500) * (0.7 + 0.3 * np.sin(2 * np.pi * 22 * t + 2 * np.sin(2 * np.pi * 3 * t))) * 0.9
    column = _resonate(rng.standard_normal(n) * 0.1, _ramp(t, [0, T * 0.9, T + tail], [250, 250, 620]), 0.995) * 2.5
    refill = (trickle + column) * env_r * 0.8
    x = click + water * 0.55 + swirl + rumble + glug + drips + refill
    return _norm(x, 0.7)
def snore(cycles=1, pitch=1.0):
    """老年男性打鼾：每轮 = 吸气带鼾 1.1–1.35 s（悬雍垂扑动脉冲串 24–30 Hz 略升、经 180–2200 Hz 带通和 420 Hz 腔体共鸣）+ 呼气 1.0–1.3 s（轻气流 + 一点哼鸣）+ 停顿 0.5–0.9 s；cycles 轮，每轮速率/时长略有随机"""
    out = []
    for _ in range(max(1, int(cycles))):
        d_in = 1.1 + rng.random() * 0.25; n = int(d_in * SR); t = np.arange(n) / SR
        f0 = (24 + rng.random() * 6) * pitch; ph = np.cumsum(f0 * (1 + 0.12 * t / d_in)) / SR
        pulses = np.zeros(n); m = int(0.006 * SR)
        for i in np.where(np.diff(np.floor(ph)) > 0)[0]:
            if i + m < n: pulses[i:i + m] += rng.standard_normal(m) * np.exp(-np.arange(m) / (0.0012 * SR))
        rattle = _bp(pulses, 180, 1600); rattle = rattle + 0.9 * _resonate(rattle, np.full(n, 420.0), 0.985) + 0.5 * _resonate(rattle, np.full(n, 1000.0), 0.975)   # 咽腔两个共鸣，少点机械摩擦感
        inhale = (rattle * 1.0 + _bp(rng.standard_normal(n), 250, 1200) * 0.16) * _ramp(t, [0, 0.25, 0.7, d_in - 0.1, d_in], [0, 0.8, 1.0, 0.6, 0]) ** 1.2
        d_ex = 1.0 + rng.random() * 0.3; n2 = int(d_ex * SR); t2 = np.arange(n2) / SR
        exh = _lp(rng.standard_normal(n2), 700) * 0.12 * _ramp(t2, [0, 0.15, 0.6, d_ex], [0, 1, 0.5, 0]) + np.sin(2 * np.pi * 95 * pitch * t2) * 0.05 * _ramp(t2, [0, 0.2, 0.7, d_ex], [0, 1, 0.4, 0])
        out += [inhale, exh, np.zeros(int((0.5 + rng.random() * 0.4) * SR))]
    return _norm(np.concatenate(out), 0.6)
def gasp():
    """憋气后猛吸一口（0.38 s：气流噪声过上扫共振 500→2800 Hz + 起点一声短促的 \"呃\" 声带音）→ 再喘两下（呼/吸各 0.22 s，一次比一次轻），共约 1.5 s。憋气的静默由 storyboard 的 cue/dt 安排"""
    def inhale(d, amp, f0, f1):
        n = int(d * SR); t = np.arange(n) / SR
        return (_resonate(rng.standard_normal(n) * 0.15, _ramp(t, [0, d], [f0, f1]), 0.975) * 2.5 + _bp(rng.standard_normal(n), 400, 5000) * 0.25 + _bp(rng.standard_normal(n), 150, 700) * 0.35) * _ramp(t, [0, 0.03, 0.5 * d, d], [0, 1.0, 0.9, 0]) * amp   # 谐振放宽 + 胸腔低频气流：少点呼啸的音效感
    def exhale(d, amp):
        n = int(d * SR); t = np.arange(n) / SR
        return _lp(rng.standard_normal(n), 900) * _ramp(t, [0, 0.05, 0.6 * d, d], [0, 1, 0.6, 0]) * amp
    first = inhale(0.38, 1.0, 500, 2200); m = int(0.05 * SR); tt = np.arange(m) / SR
    first[:m] += sum(np.sin(2 * np.pi * 175 * k * tt) / k for k in range(1, 6)) * env(m, 0.005, 0.02) * 0.25
    x = np.concatenate([first, np.zeros(int(0.12 * SR)), exhale(0.22, 0.5), inhale(0.22, 0.55, 600, 2000), np.zeros(int(0.1 * SR)), exhale(0.22, 0.35), inhale(0.2, 0.35, 600, 1800)])
    return _norm(x, 0.7)

def tap():   # 字卡出现：两声很短的轻点，先低后高（G5 → D6）
    n = int(0.17 * SR); tt = np.arange(n) / SR; d = int(0.055 * SR)
    a = np.sin(2 * np.pi * 784 * tt) * env(n, 0.002, 0.03); b = np.zeros(n); b[d:] = (np.sin(2 * np.pi * 1175 * tt) * env(n, 0.002, 0.035))[:n - d]
    return 0.8 * a + 0.7 * b
def swish(dur=0.55):   # 转场：一道由低到高的气流声（带通噪声，中心频率 500 → 2600 Hz），两头渐入渐出
    n = int(dur * SR); t = np.arange(n) / SR
    y = _resonate(rng.standard_normal(n), 500 * (2600 / 500) ** (t / dur), 0.985) * np.sin(np.pi * t / dur) ** 1.5
    return _norm(y, 0.5)

SFX = {'tap': tap, 'swish': swish, 'pop': pop, 'splash': splash, 'thud': thud, 'zap': zap, 'crack': crack, 'boing': boing, 'chime': chime, 'siren': siren, 'tick': tick, 'plip': plip, 'hiss': hiss, 'wind': wind, 'clink': clink, 'chirp': chirp, 'flush': flush, 'snore': snore, 'gasp': gasp}

def demo(out_dir='render/sfx_demo', level=0.5):
    """每种音效一个 wav（gain=level），再把新三种连播：冲水 → 0.8 s → 呼噜 ×2 → 1.2 s 憋气静默 → 猛喘"""
    import soundfile as sf, os
    os.makedirs(out_dir, exist_ok=True)
    for k, fn in SFX.items():
        x = fn(cycles=3) if k == 'snore' else fn(); sf.write(f'{out_dir}/{k}.wav', (x * level).astype(np.float32), SR)
    gap = lambda s: np.zeros(int(s * SR))
    seq = np.concatenate([flush(), gap(0.8), snore(cycles=2), gap(1.2), gasp(), gap(0.3)])
    sf.write(f'{out_dir}/连播_冲水_呼噜_猛喘.wav', (seq * level).astype(np.float32), SR); print('→', out_dir, sorted(SFX))
if __name__ == '__main__':
    a = sys.argv[1:]
    if a[:1] == ['demo']: demo(*(a[1:2] or []))
    else: print(__doc__)

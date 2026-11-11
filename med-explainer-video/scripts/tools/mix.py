#!/usr/bin/env python3
"""timeline + 逐句配音 → 程序化 BGM（木琴/拨弦/铺底/贝斯，轻快大调；可按 storyboard.audio.bgm 指定小调段、安静段）
+ 音效（字卡 pop、转场水浪 是通用的；其余音效由 storyboard.audio.sfx 按 cue 声明）→ 人声闪避混音 → render/mix.wav / mix.m4a（-16 LUFS）+ 分轨 stem_*.wav（ORIENT=land：render/land/，按横屏 timeline 混）
片头语音标识（GB 45438 ③，只对纯音频作品；默认关）：cover.ai_voice_on 为 true 时把 audio/lines/s00_ai.wav（自己录一句“本视频含人工智能生成内容”）放在 cover.ai_voice_at（默认 0.35 s）。
人声链（bph 10-13/14 定稿）：低通 11.5 kHz 去重采样镜像 → 轻度分频去齿音 → 停顿彻底静音 → 预先 0.3 s 闪避、保持 0.6 s。
storyboard.audio 示例：
  "bgm": {"bpm": 104, "minor": [["s06", "night", "f1"]], "quiet": [["s01", null, null]]}   区间 = [场, 起 cue（null=场首）, 止 cue（null=场尾）]
    quiet 默认只抽掉木琴、拨弦，铺底和贝斯照常；"quiet_gain": 0.2 之类（默认 1.0，旧专题逐位不变）让安静段整段配乐再乘这个增益，进出各 0.3 s 线性渐变，没人说话时的音效才听得清（夜尿集 s08 录音）；
    只压某一段就给那个区间写第 4 个元素：["s08", "deny", "doze", 0.2]（优先于 quiet_gain）。
  "sfx": [{"scene": "s06", "cue": "aur", "dt": 0.0, "sfx": "thud", "gain": 0.25}, {"scene": "s01", "at": 0.1, "sfx": "tick", "gain": 0.08, "every": 1.0, "until_cue": "bath"},
          {"scene": "s08", "cue": "laser", "sfx": "zap", "gain": 0.022, "every": 0.45, "count": 5}]
    sfx 名：pop splash thud zap crack boing chime siren tick plip hiss wind clink chirp flush snore gasp（tools/sfx.py，kind 一览与建议 gain 见 docs/sfx.md）；at = 场内秒（与 cue 二选一）；params: {"cycles": 3} 之类原样传给音效函数；
    重复：every + count（相对 cue 重复 N 次）或 every + until_cue / until（重复到某时刻）。bgm.from_cover 默认 false（配乐从 0 s 起）。
运行：python tools/mix.py"""
import json, subprocess, re, sys, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import ROOT, load_sb, load_tl, log, render_dir
import numpy as np, soundfile as sf, scipy.signal as ss
SR = 48000
SB = load_sb(); TL = load_tl(); N = int(TL['duration'] * SR) + SR; AU = SB.get('audio') or {}; BG = AU.get('bgm') or {}
if TL.get('estimate'): sys.exit('timeline 是 --estimate（无配音），不能混音：先跑 tts 再跑 timeline')
voice = np.zeros(N); bgm = np.zeros(N); sfx = np.zeros(N)
def add(buf, x, t, g=1.0):
    i = int(t * SR); j = min(N, i + len(x))
    if i < 0 or i >= N: return
    buf[i:j] += g * x[:j - i]
for sc in TL['scenes']:
    for ln in sc['lines']:
        a, sr = sf.read(ROOT / ln['file']); assert sr == SR; add(voice, a, sc['start'] + ln['start'])
CV = SB.get('cover') or {}; AIW = ROOT / 'audio/lines/s00_ai.wav'
if CV.get('ai_voice_on'):
    if not AIW.exists(): sys.exit('cover.ai_voice_on 为 true 但没有 audio/lines/s00_ai.wav：自己录一句“本视频由人工智能辅助生成”，处理成 48 kHz 单声道 wav 放这里')
    a, sr = sf.read(AIW); assert sr == SR; add(voice, a, float(CV.get('ai_voice_at', 0.35))); print('片头语音标识 s00_ai.wav @', CV.get('ai_voice_at', 0.35), 's')
S = {s['id']: s for s in TL['scenes']}; LAST = TL['scenes'][-1]['id']
def span(rng_):
    sid, c0, c1 = rng_; s = S[sid]
    return (s['start'] + (s['cues'][c0] if c0 else 0) - 0.3, s['start'] + (s['cues'][c1] if c1 else s['end'] - s['start']) - 0.3)
# ---------- BGM ----------
BPM = BG.get('bpm', 104); beat = 60 / BPM; bar = 4 * beat
def midi(m): return 440 * 2 ** ((m - 69) / 12)
def env(n, a, d): t = np.arange(n) / SR; return np.minimum(1, t / max(a, 1e-4)) * np.exp(-t / d)
def marimba(f, dur=0.8, v=1.0):
    n = int(dur * SR); t = np.arange(n) / SR
    return v * (np.sin(2 * np.pi * f * t) * env(n, 0.004, 0.28) + 0.08 * np.sin(2 * np.pi * f * 3.93 * t) * env(n, 0.004, 0.05))   # 高泛音 0.08、起音 4 ms（停顿里不像沙锤）
def pluck(f, dur=0.5, v=1.0):
    n = int(dur * SR); t = np.arange(n) / SR; x = sum(np.sin(2 * np.pi * f * k * t) / k ** 2 for k in range(1, 4)); return v * x * env(n, 0.006, 0.12)
def pad(freqs, dur, v=1.0):
    n = int(dur * SR); t = np.arange(n) / SR; x = sum(np.sin(2 * np.pi * f * t) + 0.5 * np.sin(2 * np.pi * f * 1.004 * t + 1) for f in freqs)
    e = np.minimum(1, t / 0.5) * np.minimum(1, (dur - t) / 0.5); return v * x * e / len(freqs)
def bass(f, dur=0.5): n = int(dur * SR); t = np.arange(n) / SR; return np.sin(2 * np.pi * f * t) * env(n, 0.005, 0.22) + 0.3 * np.sin(4 * np.pi * f * t) * env(n, 0.005, 0.08)
MAJ = [(48, [60, 64, 67]), (43, [59, 62, 67]), (45, [57, 60, 64]), (41, [57, 60, 65])]      # C G Am F
MIN = [(45, [57, 60, 64]), (41, [57, 60, 65]), (43, [59, 62, 67]), (40, [56, 59, 64])]      # Am F G E
MEL = [0, 2, 1, 2, 0, 1, 2, 1]
minor = [span(r) for r in BG.get('minor', [])]; quiet = [span(r[:3]) for r in BG.get('quiet', [])]
t = TL.get('cover', 0.0) if BG.get('from_cover') else 0.0; k = 0   # bgm.from_cover 默认 false：配乐与小节网格从 0 s 起（封面有音乐，bph 验收版如此）
while t < TL['duration'] - 0.3:
    is_min = any(a <= t < b for a, b in minor); is_q = any(a <= t < b for a, b in quiet)
    root, ch = (MIN if is_min else MAJ)[k % 4]
    add(bgm, pad([midi(m - 12) for m in ch], bar + 0.5, 0.16), t)
    add(bgm, 0.5 * bass(midi(root)), t); add(bgm, 0.35 * bass(midi(root)), t + 2 * beat); add(bgm, 0.25 * bass(midi(root + 7)), t + 3 * beat)
    for q, idx in enumerate(MEL):
        if (is_min or is_q) and q % 2: continue
        if is_q and q % 4: continue
        m = ch[idx] + 12 + (12 if (q == 6 and k % 2 == 0 and not is_min) else 0)
        add(bgm, marimba(midi(m), v=0.30 if q % 2 == 0 else 0.2), t + q * beat / 2)
    if not is_min and not is_q:
        for q in (1, 3): add(bgm, pluck(midi(ch[2] + 12), v=0.10), t + q * beat)   # 拨弦只高一个八度（两八度在停顿里像高频打击乐）；沙锤已去掉
    t += bar; k += 1
bgm = ss.sosfiltfilt(ss.butter(4, 3500, 'lowpass', fs=SR, output='sos'), bgm)   # 配乐整体低通 3.5 kHz，去掉停顿里刺耳的高频成分
fi = int(1.0 * SR); bgm[:fi] *= np.linspace(0, 1, fi); fo = int(3.0 * SR); end = int(TL['duration'] * SR); bgm[end - fo:end] *= np.linspace(1, 0, fo); bgm[end:] = 0
# ---------- SFX 库：tools/sfx.py（pop splash thud zap crack boing chime siren tick plip hiss wind clink chirp + flush snore gasp；kind 一览见 docs/sfx.md）----------
from sfx import SFX, pop, splash, rng   # 同一个 rng（种子 3）、同样的调用顺序 → 旧专题混音逐位不变（bph_on_template 横屏 mix.wav 比对为证）
# 通用：字卡 pop、转场水浪（在下一场第一个字之前收尾）
for sc in TL['scenes']:
    for lb in sc.get('labels', []): add(sfx, pop(), sc['start'] + lb['t'], 0.045)
    if sc['id'] != LAST: add(sfx, splash()[:int(0.6 * SR)] * np.linspace(1, 0, int(0.6 * SR)) ** 0.5, sc['end'] - 0.6, 0.12)   # 最后一场（竖屏 s99 / 横屏 sref）之后没有转场
# 专题声明的音效（事件表写 render/sfx_events.json，方便核对 count/every 改写前后是否等价）
EVENTS = []
for ev in AU.get('sfx', []):
    s = S.get(ev['scene'])
    if not s: print('!! sfx 场景不存在', ev); continue
    fn = SFX.get(ev['sfx'])
    if not fn: print('!! 未知 sfx', ev); continue
    t0 = s['start'] + (s['cues'][ev['cue']] if 'cue' in ev else ev.get('at', 0)) + ev.get('dt', 0)
    t1 = s['start'] + (s['cues'][ev['until_cue']] if ev.get('until_cue') else (ev.get('until', 0) or 0)) if (ev.get('until_cue') or ev.get('until')) else None
    tt = t0; n = 0; cnt = int(ev.get('count') or 0); prm = ev.get('params') or {}   # every + count：相对 cue/at 重复 N 次；every + until_cue/until：重复到某时刻；params 原样传给音效函数（snore cycles、flush dur…）
    while True:
        add(sfx, fn(**prm), tt, ev.get('gain', 0.1)); EVENTS.append([round(tt, 3), ev['sfx'], ev['scene']]); n += 1
        if not ev.get('every') or n > 2000 or (cnt and n >= cnt) or (not cnt and (t1 is None or tt + ev['every'] >= t1)): break
        tt += ev['every']
# ---------- 人声链 ----------
voice = ss.sosfiltfilt(ss.butter(10, 11500, 'lowpass', fs=SR, output='sos'), voice)   # 24 kHz 源升到 48 kHz 的镜像（12 kHz 以上“沙沙”）
DS_THR = -2.0
def deess(x):
    """轻度分频去齿音：3.5 kHz 分高低两部分，只在齿音超标的几十毫秒压高频部分（最多 8 dB），元音和时长不动"""
    lo = ss.sosfiltfilt(ss.butter(4, 3500, 'lowpass', fs=SR, output='sos'), x); hi = x - lo
    h5 = int(0.005 * SR); n5 = len(x) // h5
    fe = lambda y: 20 * np.log10(np.sqrt(np.add.reduceat(y[:n5 * h5] ** 2, np.arange(0, n5 * h5, h5)) / h5) + 1e-12)
    HFd = fe(ss.sosfilt(ss.butter(6, [3500, 11000], 'bandpass', fs=SR, output='sos'), x)); LFd = fe(ss.sosfilt(ss.butter(4, [80, 1000], 'bandpass', fs=SR, output='sos'), x))
    w = 80; ref = np.array([np.percentile(LFd[max(0, i - w):i + w], 95) for i in range(0, n5, 4)]); ref = np.repeat(ref, 4)[:n5]
    over = np.maximum(0, (HFd - ref) - DS_THR) * (HFd > -70); gr = np.maximum(-over * (3 / 4), -8.0)
    sm = np.zeros(n5); cur = 0.0; aa, rr = 1 - np.exp(-0.005 / 0.003), 1 - np.exp(-0.005 / 0.04)
    for i in range(n5): tgt = gr[i]; cur += (tgt - cur) * (aa if tgt < cur else rr); sm[i] = cur
    g = 10 ** (np.interp(np.arange(len(x)), np.arange(n5) * h5 + h5 / 2, sm) / 20)
    return lo + hi * g, float(gr.min()), int((gr < -1).sum())
if os.environ.get('DEESS', '1') != '0': voice, _ds_max, _ds_n = deess(voice); print('去齿音：最大压 %.1f dB，压 >1 dB 的帧 %d（×5 ms）' % (-_ds_max, _ds_n))
# 人声停顿彻底静音：低于全片人声峰值 −50 dB、连续 ≥100 ms 的段置零（两端各留 30 ms、10 ms 渐变）；只改停顿，不改时长
_h = int(0.01 * SR); _n = len(voice) // _h; _e = np.sqrt(np.add.reduceat(voice[:_n * _h] ** 2, np.arange(0, _n * _h, _h)) / _h); _q = 20 * np.log10(_e + 1e-12) < 20 * np.log10(np.max(np.abs(voice)) + 1e-12) - 50
_g = np.ones(len(voice)); _i = 0
while _i < _n:
    if _q[_i]:
        _j = _i
        while _j < _n and _q[_j]: _j += 1
        if _j - _i >= 10:
            s0, s1 = (_i + 3) * _h, (_j - 3) * _h; _g[s0:s1] = 0; _g[s0 - _h:s0] = np.linspace(1, 0, _h); _g[s1:s1 + _h] = np.linspace(0, 1, len(_g[s1:s1 + _h]))
        _i = _j
    else: _i += 1
voice = voice * _g
# ---------- duck + mix ----------
v_env = np.convolve(np.abs(voice), np.ones(int(0.03 * SR)) / int(0.03 * SR), 'same'); act = (v_env > 0.01).astype(float)
la = int(0.3 * SR); act = np.maximum(act, np.concatenate([act[la:], np.zeros(la)]))   # 预先 0.3 s 开始闪避：句首第一个字不被配乐压住
hd = int(0.6 * SR); act = np.maximum(act, np.concatenate([np.zeros(hd), act[:-hd]]))   # 保持 0.6 s：句间短停顿里配乐不回升
g = np.zeros(N); cur = 0.0; au = 1 - np.exp(-1 / (0.08 * SR)); ar = 1 - np.exp(-1 / (0.5 * SR))
for i in range(0, N, 48):
    tgt = act[i]; cur += (tgt - cur) * (1 - (1 - (au if tgt > cur else ar)) ** 48); g[i:i + 48] = cur
duck = 1 - AU.get('duck', 0.80) * g   # 老年观众：说话时背景压低 80%（人声高出背景 ≥ 15 dB）
bgm_n = bgm / (np.max(np.abs(bgm)) + 1e-9)
QG = float(BG.get('quiet_gain', 1.0)); QGS = [float(r[3]) if len(r) > 3 else QG for r in BG.get('quiet', [])]   # 安静段整段配乐增益（默认 1.0 不动）：区间起点后 0.3 s 降到位，终点后 0.3 s 回到 1
if any(q != 1.0 for q in QGS):
    gq = np.ones(N); rp = int(0.3 * SR)
    for (a, b), q in zip(quiet, QGS):
        i, j = int(a * SR), int(b * SR); e = np.concatenate([np.linspace(0, 1, rp), np.ones(max(0, j - i - rp)), np.linspace(1, 0, rp)])
        k0 = max(0, i); e = e[k0 - i:]; k1 = min(N, k0 + len(e)); gq[k0:k1] = np.minimum(gq[k0:k1], 1 - (1 - q) * e[:k1 - k0])
    bgm_n = bgm_n * gq; print('安静段配乐增益：', [round(q, 2) for q in QGS])
sfx_duck = 1 - 0.78 * g
mix = voice + AU.get('bgm_gain', 0.30) * bgm_n * duck + sfx * sfx_duck
mix = mix[:int((TL['duration'] + 0.2) * SR)]
R = render_dir()
sf.write(R / 'stem_bgm.wav', (0.30 * bgm_n * duck)[:len(mix)], SR); sf.write(R / 'stem_sfx.wav', (sfx * sfx_duck)[:len(mix)], SR); sf.write(R / 'stem_voice.wav', voice[:len(mix)], SR)
sf.write(R / 'mix_raw.wav', mix / max(1, np.max(np.abs(mix)) * 1.05), SR)
r = subprocess.run(['ffmpeg', '-hide_banner', '-i', str(R / 'mix_raw.wav'), '-af', 'ebur128', '-f', 'null', '-'], capture_output=True, text=True).stderr
I = float(re.findall(r'I:\s+(-?[\d.]+) LUFS', r)[-1])
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(R / 'mix_raw.wav'), '-af', f'volume={-16 - I:.2f}dB,alimiter=limit=0.84:attack=5:release=80:level=false', '-ar', '48000', '-ac', '2', str(R / 'mix.wav')], check=True)
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(R / 'mix.wav'), '-c:a', 'aac', '-b:a', '192k', str(R / 'mix.m4a')], check=True)
(R / 'sfx_events.json').write_text(json.dumps(sorted(EVENTS), ensure_ascii=False))
log(f'mix ok {round(len(mix) / SR, 1)} s sfx_events={len(EVENTS)}'); print('mix ok', round(len(mix) / SR, 1), 's', 'sfx events', len(EVENTS))

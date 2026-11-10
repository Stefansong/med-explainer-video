"""字幕对齐独立验证（不依赖对齐模型/Whisper）：在每句配音波形上找每个字幕块附近的真实开口点
（从静音到有声的跃变），与字幕块起点比较。只统计前面有停顿的块（开口点在物理上可测）。
10-24：开口点只在上一块声音结束（上一块的 end）之后找——原来 250 ms 窗口里先碰到上一块末字的开口就当成本块开口，块起点放对了反而记成“早”；
  另报 early_onto_previous：块起点与本块首字（对齐 ct）之间隔着 ≥40 ms 静音 = 起点吸到了前面的声音上（10-24 前 snap_onsets 的毛病，字幕早出 0.1–0.3 s），qa 记警告。
运行：python tools/subcheck.py [--json]   （--json 输出机器可读结果，qa.py 用）"""
import json, sys, numpy as np, soundfile as sf
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import ROOT, load_tl
TL = load_tl()
errs = []; early = []
for sc in TL['scenes']:
    for ln in sc['lines']:
        if not ln.get('file'): continue
        a, sr = sf.read(ROOT / ln['file']); hop = int(0.005 * sr)
        rms = np.sqrt(np.convolve(a ** 2, np.ones(hop * 2) / (hop * 2), 'same')[::hop]); thr = rms.max() * 0.05
        for k, ch in enumerate(ln['chunks']):
            t = ch['start']; i = int(t / 0.005)
            pre = rms[max(0, i - 40):max(1, i - 6)]
            if k == 0: errs.append((next((q for q in range(len(rms)) if rms[q] > thr), 0) * 0.005 - t, sc['id'], ch['text'])); continue   # 首块：对比整句第一个出声点
            ct = ln.get('ct') or []; ia = int(ct[ch['k0']] / 0.005) if 'k0' in ch and ch['k0'] < len(ct) else None   # 本块首字的对齐起点
            if ia is not None and ia > i:   # 块起点 → 首字之间最长的静音段 ≥ 40 ms：起点吸到了前面的声音上
                run = best = 0
                for v in rms[i:ia]: run = run + 1 if v <= thr else 0; best = max(best, run)
                if best >= 8: early.append((round((ia - i) * 5), f"{sc['id']}_{ln['i']}", ch['text']))
            if len(pre) < 10 or pre.mean() > thr: continue       # 前面没有明显停顿，跳过
            j0 = max(0, i - 60); seg = rms[j0:i + 60]; lo = max(i - 50, int(ln['chunks'][k - 1]['end'] / 0.005))   # 只在上一块声音结束之后找
            cand = [j0 + q for q in range(1, len(seg)) if seg[q] > thr and seg[q - 1] <= thr and q + j0 > lo][:1]   # ① 上一块之后的第一个上升沿（停顿里的换气 / 咂嘴也会算进来）
            if ia is not None:   # ② 含本块首字的那段声音的起头（短于 40 ms 的低谷不算断开）——取 ①② 里离块起点近的：吸到换气声上的旧时间轴量值不变，放对了的新时间轴也不被误记成“早”
                q = ia
                while q < len(rms) - 1 and q < ia + 60 and rms[q] <= thr: q += 1
                quiet = 0; on2 = q if rms[q] > thr else None
                while on2 is not None and q > lo:
                    q -= 1
                    if rms[q] > thr: on2, quiet = q, 0
                    else:
                        quiet += 1
                        if quiet >= 8: break
                if on2 is not None: cand.append(on2)
            if not cand: continue
            on = min(cand, key=lambda c: abs(c * 0.005 - t))
            errs.append((on * 0.005 - t, sc['id'], ch['text']))
e = np.array([x[0] for x in errs]) if errs else np.zeros(0)
res = {'measurable': int(len(e)), 'within_50ms': float(np.mean(np.abs(e) <= 0.05)) if len(e) else None, 'within_100ms': float(np.mean(np.abs(e) <= 0.1)) if len(e) else None,
       'median_ms': float(np.median(e) * 1000) if len(e) else None, 'max_ms': float(np.abs(e).max() * 1000) if len(e) else None,
       'worst': [(round(x[0] * 1000), x[1], x[2]) for x in sorted(errs, key=lambda x: -abs(x[0]))[:5]],
       'early_onto_previous': len(early), 'early_max_ms': max((x[0] for x in early), default=0), 'early_worst': sorted(early, key=lambda x: -x[0])[:6]}
if '--json' in sys.argv: print(json.dumps(res, ensure_ascii=False)); sys.exit()
if not len(e): print('可测块 0（timeline 是 --estimate 或没有配音）'); sys.exit()
print(f'可测块 {len(e)}：|误差| ≤ 50 ms {np.mean(np.abs(e) <= 0.05):.0%}，≤ 100 ms {np.mean(np.abs(e) <= 0.1):.0%}，中位 {np.median(e) * 1000:+.0f} ms，最大 {np.abs(e).max() * 1000:.0f} ms')
for x in sorted(errs, key=lambda x: -abs(x[0]))[:5]: print(f'  {x[0] * 1000:+.0f} ms {x[1]} {x[2]}')
if early: print(f'起点吸到前面声音上的块 {len(early)}（块起点与首字之间隔着 ≥40 ms 静音）：' + '；'.join(f'{x[1]}“{x[2]}”早 {x[0]} ms' for x in sorted(early, key=lambda x: -x[0])[:8]))

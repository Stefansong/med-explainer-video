#!/usr/bin/env python3
"""成片 QA → render/{project}_{tag}.qa.json，并给出通过/不通过（--gate：不通过时退出码 1，pipeline 用）。
① ASR 回读：从成片音轨逐句截取回读，拼音相似度 vs 台词（整段识别只作参考；10-24 起删掉台词区间外的段和已知幻听句，片尾纯配乐不再幻听成“请不吝点赞…”）
② 字幕：逐字一致（chunks 拼起来 == 台词原文）、波形开口点对齐（subcheck.py）、whisper 词级时间戳（仅参考）
③ 口径/危险信号是否全部上屏（10-24 起逐卡匹配 + 或/且、数字转写走样警告，_common.red_flag_check；storyboard.qa.red_flags_match compat|strict|legacy）；④ 响度、分辨率、帧率、时长；⑤ 叠字层渲染期自检计数（render.js 写的 .overlay.json，阈值见 layout.qa_gate）；⑤′ 字体：上屏文字逐字核字形覆盖（check_fonts.py），缺字 / 系统字体回退声明 / 字体未加载 判失败
⑦ 舞台换镜暗谷（10-24，tools/dipscan.py）：舞台区 30 fps 平均亮度里两侧都亮 5% 以上的窄谷 = 场内换镜双向淡化透出底色；layout.qa_gate.stage_dip（缺省 0）以上判失败，有意的暗场写 storyboard.qa.dips_ok
⑥ 横屏投稿版（ORIENT=land）专项门：画幅 ≥1280×720 横向、AI 标识在右下角且 ≥ 短边 5%/首帧 0/≥2 s、参考文献页存在且条数连续、著录/出现顺序（check_refs.py）、
   字体全部加载 + 逐字字形覆盖 + 不声明系统字体回退（check_fonts.py）、画面文字不含 storyboard.submit.forbidden 字串、tag=submit 时文件 ≤ 50 MB 且字幕文件已导出
运行：python tools/qa.py <tag> [--gate] [--no-asr]（--no-asr：跳过 whisper，只做字幕/技术/叠字检查，预演用）；横屏：ORIENT=land … qa.py master / submit"""
import json, sys, subprocess, difflib, re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import ROOT, load_sb, load_tl, load_layout, asr_prompt, log, render_dir, LAND, overlay_texts, red_flag_check
HERE = Path(__file__).resolve().parent
import numpy as np
from pypinyin import lazy_pinyin
args = [a for a in sys.argv[1:] if not a.startswith('--')]; tag = args[0] if args else 'final'; GATE = '--gate' in sys.argv; NOASR = '--no-asr' in sys.argv
SB = load_sb(); TL = load_tl(); LAYOUT = load_layout(); project = SB['project']; RD = render_dir()
mp4 = RD / f'{project}_{tag}.mp4'
if not mp4.exists(): sys.exit(f'没有 {mp4}')
def han(s): return re.sub(r'[^一-鿿]', '', s)
def py(s): return lazy_pinyin(han(s))
ref = ''.join(l['text'] for s in SB['scenes'] for l in s['lines'])
qa = {'file': str(mp4.relative_to(ROOT)), 'project': project, 'tag': tag, 'orient': TL.get('orient') or ('land' if LAND else 'port'), 'failures': [], 'warnings': []}
def fail(msg): qa['failures'].append(msg)
def warn(msg): qa['warnings'].append(msg)

# ---------- 技术规格 ----------
import probe as _probe; probe = _probe.info(mp4)   # 有 ffprobe 用它，没有就解析 ffmpeg -i
v = next(s for s in probe['streams'] if s['codec_type'] == 'video'); dur = float(probe['format']['duration'])
num, den = v['r_frame_rate'].split('/'); fps = round(int(num) / int(den), 3)
qa.update({'duration_s': round(dur, 2), 'timeline_s': TL['duration'], 'resolution': f"{v['width']}x{v['height']}", 'fps': fps, 'pix_fmt': v.get('pix_fmt'), 'color_space': v.get('color_space'), 'color_range': v.get('color_range')})
if (v['width'], v['height']) != (TL['width'], TL['height']): fail(f"分辨率 {qa['resolution']} ≠ {TL['width']}x{TL['height']}")
if abs(dur - TL['duration']) > 0.5: fail(f"时长 {dur:.2f} 与 timeline {TL['duration']} 差 >0.5 s")
if v.get('pix_fmt') != 'yuv420p': fail(f"pix_fmt {v.get('pix_fmt')} ≠ yuv420p")
if v.get('color_range') not in ('tv', None): warn(f"color_range {v.get('color_range')}（应为 tv/BT.709 电视范围）")
r = subprocess.run(['ffmpeg', '-hide_banner', '-i', str(mp4), '-af', 'ebur128', '-f', 'null', '-'], capture_output=True, text=True).stderr
m = re.findall(r'I:\s+(-?[\d.]+) LUFS', r); lufs = float(m[-1]) if m else None; qa['loudness_LUFS'] = lufs
if lufs is None or lufs <= -60: warn('音轨为静音（未混音：预演/演示可以，正式版不行）'); (fail('正式版音轨为静音') if tag == 'final' else None)
elif not (-17.5 <= lufs <= -14.5): fail(f'响度 {lufs} LUFS 不在 −16±1.5')

# ---------- 字幕逐字一致 ----------
bad = []
for sc in TL['scenes']:
    for ln in sc['lines']:
        joined = re.sub(r'\s', '', ''.join(c['text'] for c in ln['chunks'])).replace('？', '').replace('！', '')
        want = re.sub(r'[，。；：！？、…—“”\s]', '', ln['text'])
        for a, b in [tuple(x) for x in SB.get('subtitle_numbers', [])]: want = want.replace(a, b)
        if joined != want: bad.append(f"{sc['id']}_{ln['i']}")
qa['subtitle_text_identical'] = not bad
if bad: fail(f'字幕与台词不逐字一致：{bad}')

# ---------- 字幕开口点对齐（波形，硬指标）----------
if not TL.get('estimate'):
    sc_out = subprocess.run([sys.executable, str(HERE / 'subcheck.py'), '--json'], capture_output=True, text=True)
    try: sub = json.loads(sc_out.stdout.strip().splitlines()[-1])
    except Exception: sub = {'error': sc_out.stderr[-300:]}
    qa['subtitle_onset_check'] = sub
    if sub.get('measurable') and sub.get('within_100ms', 1) < 0.95: fail(f"字幕开口点对齐：≤100 ms 只有 {sub['within_100ms']:.0%}（要求 ≥95%）")
    if sub.get('early_onto_previous'): warn(f"字幕块起点吸到了前面的声音上（块起点与本块首字之间隔着 ≥40 ms 静音，字幕提前出现）{sub['early_onto_previous']} 块，最多早 {sub['early_max_ms']} ms：{sub['early_worst']}（10-24 前的 timeline.py snap_onsets 的毛病，重跑 timeline 即修）")
else: qa['subtitle_onset_check'] = 'timeline 是 --estimate，无配音，跳过'

# ---------- 口径 / 危险信号上屏（逐卡匹配；字卡可写 rf 显式关联；或/且、数字转写走样只警告。旧规则“前 4 个汉字在全部字卡拼接里”只在 compat 模式兜底）----------
rfc, rf_mode = red_flag_check(SB); rf = {f: r['ok'] for f, r in rfc.items()}
qa['red_flags_on_screen'] = rf; qa['red_flags_count'] = f"{sum(rf.values())}/{len(rf)}"; qa['red_flags_match'] = {'mode': rf_mode, 'detail': rfc}
if not all(rf.values()): fail('危险信号未全部上屏：' + '、'.join(k for k, ok in rf.items() if not ok))
for f, r in rfc.items():
    for x in r['warn']: warn(f'危险信号“{f[:18]}”：{x}')
qa['labels'] = sum(len(s.get('labels', [])) for s in SB['scenes'])

# ---------- 字卡停留（timeline.json card_stays）----------
cs = TL.get('card_stays') or []
if cs:
    lbc = LAYOUT.get('labels') or {}; ms, msa = float(lbc.get('min_stay', 2.5)), float(lbc.get('min_stay_alert', 3.5))
    short_a = [r for r in cs if r.get('alert') and r['stay'] < msa - 1e-6]; short_n = [r for r in cs if not r.get('alert') and r['stay'] < ms - 1e-6]
    qa['card_stays'] = {'cards': len(cs), 'min_stay_s': min(r['stay'] for r in cs), 'alert_short': [(r['scene'], r['text'], r['stay'], r['reason']) for r in short_a], 'normal_short': [(r['scene'], r['text'], r['stay'], r['reason']) for r in short_n],
                        'scenes_extended': [(s['id'], s.get('extended')) for s in TL['scenes'] if s.get('extended')]}
    if short_a: fail(f"危险信号字卡停留不足 {msa} s：{len(short_a)} 张，最短 {min(r['stay'] for r in short_a):.1f} s")
    if short_n: warn(f"字卡停留不足 {ms} s：{len(short_n)} 张，最短 {min(r['stay'] for r in short_n):.1f} s（{'、'.join(r['scene'] + '“' + r['text'][:10] + '”' for r in short_n[:6])}）")
else: warn('timeline.json 没有 card_stays（旧版 timeline.py）')

# ---------- 舞台换镜暗谷（tools/dipscan.py）：场内换镜新旧镜头同时半透明 → 透出底色变灰；nocturia 正式版 v1 五处是成片审核员抓到的，之前的 QA 门查不出 ----------
# 换镜处的暗谷判失败：观众看得见的穿帮，nocturia v1 和第一集 bph 正式版（189.63、388.57 s 两处）都是带着它交付的；psa、foam、nocturia v2、foam_3d 预演零误报，nocturia v1 六处全中。
# 镜头内的明暗变化（前后画面相同：警示灯一闪一闪、亮的解剖圆窗滑出画面再滑回——torsion 201.37 s、关灯）和场景水浪转场窗口里的变暗（不透明转场不会透底：bph 3.13 s 片名淡入、381.30 s 夜到天亮）多半有意，只警告；都可在 storyboard.qa.dips_ok 声明消掉；
# 预演阶段的 qa 不带 --gate，只记进 failures 给渲染前审核员看，早发现早改（正式版重渲 + 复审要 30–60 min）。layout.qa_gate.stage_dip：数字 = 允许处数（缺省 0）、"warn" = 只警告、null = 只记录。
import dipscan
try: ds = dipscan.scan(mp4, LAYOUT, TL, SB)
except Exception as e: ds = {'error': str(e)[-300:]}
qa['stage_dips'] = ds; gate_d = (LAYOUT.get('qa_gate') or {}).get('stage_dip', 0)
if 'error' in ds: warn(f"舞台暗谷扫描出错：{ds['error']}")
else:
    bad_d = [d for d in ds['dips'] if not d['allowed'] and d.get('shot_change', True)]; soft_d = [d for d in ds['dips'] if not d['allowed'] and not d.get('shot_change', True)]
    fmt = lambda ds_: '；'.join(f"{d['T']} s（{d['scene']} 场内 {d['t_in_scene']} s，掉 {d['drop_pct']}%，前后相关 {d.get('ref_corr')}）" for d in ds_[:8])
    msg = f"舞台区换镜暗谷 {len(bad_d)} 处（新旧镜头同时半透明、透出底色变灰）：{fmt(bad_d)} → 场内换镜改成新镜头盖在不透明的旧镜头上只淡入；有意的暗场写进 storyboard.qa.dips_ok（带 why）"
    if bad_d and gate_d == 'warn': warn(msg)
    elif bad_d and gate_d is not None and len(bad_d) > int(gate_d): fail(msg)
    if soft_d and gate_d is not None: warn(f"舞台区镜头内 / 转场窗口内变暗 {len(soft_d)} 处（前后是同一画面：闪烁、亮的东西移出画面、关灯；或落在场景水浪转场窗口里：暗场开头渐亮、片名淡入，多半有意）：{fmt(soft_d)} → 看一眼；有意的写进 storyboard.qa.dips_ok 消掉这条警告")

# ---------- 叠字层渲染期自检 ----------
ovf = RD / f'{project}_{tag}.overlay.json'
if tag == 'submit' and not ovf.exists(): ovf = RD / f'{project}_master.overlay.json'   # 投稿版是母版的转码，叠字层自检沿用母版的
if ovf.exists():
    ov = json.loads(ovf.read_text()); items = ov.get('items', {}); uniq = ov.get('unique') or {k: len(v) for k, v in items.items()}
    qa['overlay_check'] = uniq; qa['overlay_check_frames'] = ov.get('counts', {}); qa['page_errors'] = ov.get('page_errors')
    # 每类的明细：缩字号报“N 张卡缩了，最窄 X px”，其余列出前 20 条（场、文本、帧数）
    detail = {}
    for k, I in items.items():
        rows = sorted(I.values(), key=lambda it: (it.get('min_size', 0), -it.get('frames', 0)))
        if k in ('label_shrunk', 'subtitle_shrunk') and rows:
            detail[k] = {'summary': f"{len(rows)} 张缩了字号，最窄 {min(r['min_size'] for r in rows)} px（原 {rows[0].get('size0')}）", 'worst': [{'scene': r.get('scene'), 'text': r.get('text'), 'min_size': r.get('min_size'), 'frames': r.get('frames')} for r in rows[:20]]}
        else: detail[k] = [{kk: vv for kk, vv in r.items() if kk not in ('kind',)} for r in rows[:20]]
    qa['overlay_detail'] = detail
    gate = LAYOUT.get('qa_gate', {}); verified = bool(LAYOUT.get('safe_area_verified'))
    for k, n in uniq.items():   # 阈值按去重后的张数
        th = gate.get(k, 'warn_until_verified' if k in ('safe_right', 'safe_bottom') else 0)   # 安全区类（右侧图标列、底部留白带）旧 layout 没写阈值也按“真机核对前只警告”
        if th is None: continue
        if th == 'warn_until_verified': th = 0 if verified else None
        if th is None: warn(f'叠字层 {k}: {n} 张（安全区未经真机核对，只警告）')
        elif n > th: fail(f'叠字层 {k}: {n} 张 > {th}')
    for k in ('label_shrunk', 'subtitle_shrunk'):
        if k in detail and isinstance(detail[k], dict): warn(f"叠字层 {k}：{detail[k]['summary']}")
    if ov.get('page_errors'): fail(f"画面代码报错 {ov['page_errors']} 次：" + '；'.join(ov.get('page_error_samples') or ['（看渲染输出里的 PAGEERR / CONSOLE 行）']))
    # AI 生成标识（GB 45438—2025）：实测字高 ≥ 要求字高（短边 5% + 余量）、首帧 = 0、持续 ≥ 2.0 s
    am = ov.get('ai_mark'); amc = (LAYOUT.get('ai_mark') or {})
    if amc.get('text'):
        if not am: fail('AI 生成标识：渲染里没有记录（overlay.json 无 ai_mark）')
        else:
            qa['ai_mark'] = am
            if am.get('ink') is None or am['ink'] < am['need']: fail(f"AI 生成标识字高 {am.get('ink')} px < 要求 {am.get('need')} px（短边 5% + {amc.get('margin_px', 4)}）")
            if am.get('first_frame') != 0: fail(f"AI 生成标识首帧不是第 0 帧（{am.get('first_frame')}）")
            if (am.get('full_seconds') or 0) < 2.0 - 1e-6: fail(f"AI 生成标识完整显示 {am.get('full_seconds')} s < 2.0 s")
else: warn('没有 .overlay.json（render.js 未写出自检），叠字层检查跳过')

# ---------- 字体：只用开源字体、不回退系统字体（竖屏横屏都拦；10-21 用户定）----------
# check_fonts.py 把所有上屏文字按角色逐字查 layout.fonts.files 的 cmap：缺字 > qa_gate.font_fallback（默认 0）判失败，列出字、位置、该用的字体；fonts.* 声明了不在 files 里的字体族也判失败；渲染页字体必须全部 loaded
cf = subprocess.run([sys.executable, str(HERE / 'check_fonts.py'), '--json'], capture_output=True, text=True)
try: fo = json.loads(cf.stdout.strip().splitlines()[-1])
except Exception: fo = {'error': (cf.stderr or cf.stdout)[-400:]}
qa['fonts_check'] = {k: v for k, v in fo.items() if k != 'roles'}; qa['fonts_check']['roles'] = {r: {'families': v['families'], 'files': v['files'], 'chars': v['chars']} for r, v in (fo.get('roles') or {}).items()}
gate_f = (LAYOUT.get('qa_gate') or {}).get('font_fallback', 0)
if 'error' in fo: fail(f"字体检查出错：{fo['error']}")
elif gate_f is not None:
    if fo.get('missing_total', 0) > gate_f: fail(f"字形缺失 {fo['missing_total']} 个字（会回退系统字体）：" + '；'.join(f"“{m['char']}”{m['code']} {m['role']} 应在 {'/'.join(m['fonts'])}，见 {m['where'][0] if m['where'] else '?'}" for m in (fo.get('missing') or [])[:10]))
    if fo.get('system_fallback_declared'): fail(f"layout.fonts 声明了不在 files 里的字体族（系统回退）：{fo['system_fallback_declared']}")
_ovj = json.loads(ovf.read_text()) if ovf.exists() else {}
fl = _ovj.get('fonts')
if fl is not None:
    bad_f = [f for f in fl if f.get('status') != 'loaded']; qa['fonts_loaded'] = {'total': len(fl), 'bad': bad_f}
    if bad_f: fail(f'渲染页字体未全部加载：{bad_f}')
else: warn('overlay.json 没有字体加载状态（旧 render.js？）')

# ---------- 横屏投稿版专项门 ----------
if LAND or TL.get('orient') == 'land':
    SUBC = SB.get('submit') or {}; LS = LAYOUT.get('submit') or {}; land = {}; ovj = json.loads(ovf.read_text()) if ovf.exists() else {}
    if v['width'] < LS.get('min_width', 1280) or v['height'] < LS.get('min_height', 720) or v['width'] <= v['height']: fail(f"横屏分辨率 {qa['resolution']} 不满足 ≥{LS.get('min_width', 1280)}×{LS.get('min_height', 720)} 且横向")
    am = qa.get('ai_mark')
    if am:
        if not (am['x'] > v['width'] / 2 and am['y'] > v['height'] / 2): fail(f"AI 标识不在右下角（x {am['x']}, y {am['y']}）")
        if am['x'] + am['w'] > v['width'] + 1 or am['y'] + am['h'] > v['height'] + 1: fail('AI 标识越出画面')
        ms = float(LS.get('ai_mark_min_seconds', 2.0))
        if (am.get('full_seconds') or 0) < ms - 1e-6: fail(f"AI 标识完整显示 {am.get('full_seconds')} s < {ms} s")
    refs = SB.get('references') or []; sref = next((s for s in TL['scenes'] if s['id'] == 'sref'), None); land['references'] = len(refs)
    if refs and not sref: fail('有 storyboard.references 但 timeline 没有 sref 参考文献页（重跑 timeline）')
    if not refs: warn('storyboard.references 为空：投稿须知要求片尾按出现顺序列参考文献')
    if sref:
        ri = ovj.get('refs') or {}; land['refs_page'] = ri; planned = (TL.get('refs') or {}).get('pages')
        if not ri: warn('overlay.json 没有 refs 信息（渲染没经过 sref 页？抽帧 frames.js 不算）')
        else:
            if ri.get('overflow'): fail(f"参考文献 {ri.get('count')} 条装不进 {ri.get('pages_planned')} 页（最小字号仍放不下）：增大 references_pages")
            if sum(ri.get('pages') or []) != len(refs): fail(f"参考文献页条数 {sum(ri.get('pages') or [])} ≠ references {len(refs)}（编号不连续）")
            if planned and len(ri.get('pages') or []) > planned: fail(f"参考文献实际 {len(ri['pages'])} 页 > timeline 安排的 {planned} 页（最后几页放不出来）")
        cr = subprocess.run([sys.executable, str(HERE / 'check_refs.py'), '--json'], capture_output=True, text=True)
        try: land['check_refs'] = json.loads(cr.stdout.strip().splitlines()[-1])
        except Exception: land['check_refs'] = {'error': cr.stderr[-300:]}
        c_ = land['check_refs']
        if c_.get('order_checked') and not c_.get('order_ok'): fail('参考文献编号不是按影片首次出现顺序：' + json.dumps(c_.get('order_problems'), ensure_ascii=False)[:200])
        elif not c_.get('order_checked') and refs: warn('参考文献出现顺序未核：storyboard 没有 references_keys（与 claims[].src 对应）或 scenes[].refs')
        if c_.get('format_problems'): warn(f"参考文献著录格式疑点 {len(c_['format_problems'])} 条（只报告，见 qa.json land.check_refs）")
    forb = [x for x in (SUBC.get('forbidden') or []) if x]; texts = [t for _, t in overlay_texts(SB, LAYOUT, TL)]
    hits = [(x, t) for x in forb for t in texts if x in t]; land['forbidden'] = {'strings': forb, 'hits': hits[:20]}
    if hits: fail(f"画面文字含禁用字串 {sorted({h[0] for h in hits})}（storyboard.submit.forbidden）")
    if not forb: warn('storyboard.submit.forbidden 为空：没核单位名/作者名是否出现在画面文字里')
    if tag == 'submit' or mp4.name.endswith('_submit.mp4'):
        size = mp4.stat().st_size; mx = float(SUBC.get('max_mb') or LS.get('max_mb') or 50); land['size_mb'] = round(size / 1e6, 2)
        if size > mx * 1e6: fail(f"投稿文件 {size / 1e6:.1f} MB > {mx} MB")
        sd = ROOT / 'submit'; need = [f'{project}_字幕.srt', f'{project}_字幕文本.txt', f'{project}_横屏投稿版.mp4', f'{project}_封面_16x9.png']
        land['submit_files'] = {n: (sd / n).exists() for n in need}; miss = [n for n in need if not (sd / n).exists()]
        if miss: fail(f'投稿包缺文件：{miss}（本技能不出投稿包，这一项只对自己另做的 submit 版生效）')
    qa['land'] = land

# ---------- ASR 回读 ----------
if NOASR or TL.get('estimate'): qa['asr_pinyin_similarity'] = None; qa['asr_note'] = '跳过（--no-asr 或无配音）'
else:
    import soundfile as sf, tempfile
    from asr import transcribe
    WH = dict(language='zh', initial_prompt=asr_prompt(SB))
    wav = Path(tempfile.gettempdir()) / f'qa_{project}_{tag}.wav'; subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(mp4), '-vn', '-ac', '1', '-ar', '16000', str(wav)], check=True)
    au, sr = sf.read(str(wav)); per_line = []
    for sc in TL['scenes']:
        for ln in sc['lines']:
            a0, a1 = sc['start'] + float(ln['start']) - 0.05, sc['start'] + float(ln['end']) + 0.05; tmp = wav.with_suffix('.seg.wav'); sf.write(str(tmp), au[int(max(0, a0) * sr): int(a1 * sr)], sr)
            per_line.append(transcribe(str(tmp), **WH)['text'])
    sim_lines = difflib.SequenceMatcher(None, py(ref), py(''.join(per_line)), autojunk=False).ratio()
    # 整片回读（参考）照旧一次转写（台词区里的结果与 10-24 前相同；试过只送台词区间 clip_timestamps，whisper 切窗一变参考值反而上下乱跳），事后删两类段：
    # ① 与任何台词区间（每句前后 0.5 s）都不重叠的段——片头封面、场间、片尾纯配乐里的幻听（psa 正式版片尾 294.7–296.1 s“请不吝点赞 订阅 转发 打赏支持明镜与点点栏目”）；
    # ② 台词里没有的已知幻听句（storyboard.qa.asr_hallucinations 可增补）
    spans = sorted((sc['start'] + float(ln['start']) - 0.5, sc['start'] + float(ln['end']) + 0.5) for sc in TL['scenes'] for ln in sc['lines'])
    res = transcribe(str(wav), word_timestamps=True, **WH)
    HALLU = re.compile(r'请不吝|点赞|订阅|转发|打赏|明镜|点点栏目|字幕[由制提志]|(?:感谢|谢谢)(?:观看|收看|收听)|下[期次]再见|Amara')
    def hallu(t): return [h for h in [m.group(0) for m in HALLU.finditer(t)] + [x for x in ((SB.get('qa') or {}).get('asr_hallucinations') or []) if x and x in t] if h not in ref]
    def outside(s_): return not any(a < s_['end'] and s_['start'] < b for a, b in spans)
    dropped = [(round(s_['start'], 2), s_['text'], '台词区间外' if outside(s_) else '幻听句') for s_ in res['segments'] if outside(s_) or hallu(s_['text'])]
    if dropped: res['segments'] = [s_ for s_ in res['segments'] if not (outside(s_) or hallu(s_['text']))]; hyp = ''.join(s_['text'] for s_ in res['segments'])
    else: hyp = res['text']
    sim = difflib.SequenceMatcher(None, py(ref), py(hyp), autojunk=False).ratio()   # 整段长音频识别偶尔会跳过几十秒，只作参考
    qa.update({'asr_pinyin_similarity': round(sim_lines, 4), 'asr_full_file_similarity(参考)': round(sim, 4), 'asr_dropped_segments': dropped, 'script_chars': len(han(ref)), 'asr': hyp})
    thr = (SB.get('qa') or {}).get('asr_min', 0.97)
    if sim_lines < thr: fail(f'逐句回读拼音相似度 {sim_lines:.4f} < {thr}')
    # whisper 字级时间戳 vs 字幕块首字（仅参考：whisper 中文词级时间戳不准）
    chars = []
    for seg in res['segments']:
        for w in seg.get('words', []):
            h = han(w['word'])
            for k, ch in enumerate(h): chars.append((lazy_pinyin(ch)[0], w['start'] + (w['end'] - w['start']) * k / max(1, len(h))))
    ref_units = []
    for sc in TL['scenes']:
        for ln in sc['lines']:
            for ch in ln['chunks']:
                for k, c in enumerate(han(ch['text'])): ref_units.append((lazy_pinyin(c)[0], sc['start'] + ln['start'] + ch['start'] if k == 0 else None, ch['text']))
    sm = difflib.SequenceMatcher(None, [u[0] for u in ref_units], [c[0] for c in chars], autojunk=False); offs = []
    for a, b, n in sm.get_matching_blocks():
        for q in range(n):
            u = ref_units[a + q]
            if u[1] is not None: offs.append((chars[b + q][1] - u[1], u[2]))
    e = np.array([o[0] for o in offs]) if offs else np.zeros(0)
    qa['subtitle_vs_whisper_wordtimes(仅参考，whisper 中文词级时间戳不准)'] = {'chunks_matched': int(len(e)), 'within_200ms': round(float(np.mean(np.abs(e) <= 0.20)), 3) if len(e) else None, 'median_ms': round(float(np.median(e)) * 1000) if len(e) else None, 'worst': [(round(o[0] * 1000), o[1]) for o in sorted(offs, key=lambda o: -abs(o[0]))[:5]]}

qa['fonts'] = {r: v['family'] for r, v in (LAYOUT.get('fonts') or {}).items() if isinstance(v, dict) and 'family' in v}; qa['layout_version'] = LAYOUT.get('version'); qa['safe_area_verified'] = bool(LAYOUT.get('safe_area_verified'))
qa['pass'] = not qa['failures']
out = RD / f'{project}_{tag}.qa.json'; out.write_text(json.dumps(qa, ensure_ascii=False, indent=1))
print(json.dumps({k: v for k, v in qa.items() if k not in ('asr', 'overlay_detail')}, ensure_ascii=False, indent=1))
log(f"qa {out.name} pass={qa['pass']} failures={qa['failures']} warnings={len(qa['warnings'])}")
print('QA', 'PASS' if qa['pass'] else 'FAIL', '→', out.name)
if GATE and not qa['pass']: sys.exit(1)

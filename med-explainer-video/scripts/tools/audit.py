#!/usr/bin/env python3
"""两道审核关卡的工具（10-22 多集并行）。审核员是另开的对话或子代理（独立审核员），提示词在 skill 的 references/audit_pre_prompt.md / audit_post_prompt.md；本工具只管材料、哈希、报告校验：
  pack pre                 打包渲染前审核材料 → render[/land]/audit/pre_v{n}/：预演 mp4 每 2 s 一帧（缩图）+ 关键帧原尺寸（封面、每场开头、每张字卡、每个 cue）+ 当前 storyboard/timeline/layout/src 快照 + index.md
  pack post [--tag T]      打包成片审核材料 → render[/land]/audit/post_{T}/：成片每 2 s 一帧、片头片尾原尺寸、音频统计（响度/峰值/静音段）与 6 段回放片段、QA/overlay json、（横屏）投稿包清单 + index.md
  hashes                   打印当前哈希：storyboard_sha / timeline_sha / src_sha（src/*.js + player.html + layout）/ video_sha（成片）/ submit_sha（投稿版）
                           storyboard_sha（10-24 起）只算会进画面 / 声音 / 口径的内容，不算只作记录的字段（AUDIT_SKIP：status、status_text、design.status、design.decisions、
                           tts.ear_confirmed、tts.ear_confirmed_why）——以前是整个文件，确认 S6a 一写 status 就要差异复审（psa 10-22）。check 也认旧报告里的整文件哈希（文件一字未改时）
  stamp <报告.md>           把当前哈希与日期写进报告头部（审核员改完东西、重跑预演、写完报告后的最后一步）；pre 报告顺手把盖章时的状态存成 audit/pre_v{n}/snapshot（没打包的复审补存、打包后又改过的重存），下一轮 diff 以它为基准
  check pre|post [--tag T] 最新报告 result 必须 pass、哈希必须与当前一致 → 退出码 0；否则 1 并说明原因（pipeline 门控用；哈希不符时顺手生成差异稿）
  diff                     当前 storyboard / timeline / src 与最新 audit_pre 快照的差异 → design/audit_diff_v{n}.md（S6a 确认后又改过东西时只复审这个）
报告头部格式（stamp 会补齐/覆盖哈希与日期行）：
  - result: pass | fail
  - tag: preview_v6（pre）| final / master / submit（post）
  - date: …
  - storyboard_sha: … / timeline_sha: … / src_sha: …（pre）；video_sha: … / submit_sha: …（post）"""
import sys, os, re, json, hashlib, shutil, subprocess, datetime, difflib
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import ROOT, LAND, ORIENT, render_dir, render_rel, find_storyboard, layout_path, load_sb, load_tl, log
_SK = Path(__file__).resolve().parent.parent   # skill 的 scripts/
AUD = f'python "{Path(__file__).resolve()}"'; PIPE = f'python "{_SK / "pipeline.py"}"'
REFS = _SK.parent / 'references'
HERE = Path(__file__).resolve().parent
SB_PATH = find_storyboard(); RD = render_dir(); DESIGN = ROOT / 'design'
def sha_bytes(b): return hashlib.sha1(b).hexdigest()[:16]
def sha_file(p): p = Path(p); return sha_bytes(p.read_bytes()) if p.exists() else None
# storyboard 里只作记录、不进画面 / 声音 / 口径的字段：确认 HARD 点时会顺手写（status、拍板记录、人耳确认名单），不该触发复审。其余字段一律算（scenes.js 能读 SB 的任何字段，宁可多复审）
from _common import AUDIT_SKIP, sb_strip   # 定义在 _common（pipeline 各阶段输入哈希也用）
def sb_sha(p):
    p = Path(p); return sha_bytes(json.dumps(sb_strip(json.loads(p.read_text())), ensure_ascii=False, sort_keys=True).encode()) if p.exists() else None
def project(): return load_sb()['project']
def latest_preview():
    ms = sorted(RD.glob(f'{project()}_preview_v*.mp4'), key=lambda f: int(re.search(r'_v(\d+)\.mp4$', f.name).group(1)))
    return ms[-1] if ms else None
def src_files(): return sorted((ROOT / 'src').glob('*.js')) + [ROOT / 'src/player.html', layout_path()]
def hashes(tag=None):
    h = {'orient': ORIENT, 'storyboard_sha': sb_sha(SB_PATH), 'storyboard_file_sha': sha_file(SB_PATH), 'timeline_sha': sha_file(RD / 'timeline.json')}   # storyboard_file_sha：整文件（10-24 前的报告盖的是它）
    hs = hashlib.sha1()
    for f in src_files():
        if f.exists(): hs.update(f.name.encode() + b'\0' + f.read_bytes() + b'\0')
    h['src_sha'] = hs.hexdigest()[:16]
    P = project(); tag = tag or ('master' if LAND else 'final')
    h['tag'] = tag; h['video_sha'] = sha_file(RD / f'{P}_{tag}.mp4')
    if LAND: h['submit_sha'] = sha_file(RD / f'{P}_submit.mp4')
    return h
# ---------- 报告 ----------
KEYS = ('result', 'tag', 'date', 'auditor', 'storyboard_sha', 'timeline_sha', 'src_sha', 'video_sha', 'submit_sha', 'preview')
def parse_report(p):
    d = {}
    for ln in Path(p).read_text().splitlines()[:40]:
        m = re.match(r'^\s*[-*]?\s*(result|tag|date|auditor|storyboard_sha|timeline_sha|src_sha|video_sha|submit_sha|preview)\s*[:：]\s*(\S+)', ln, re.I)
        if m: d[m.group(1).lower()] = m.group(2).strip('`*')
    return d
def pre_reports(): return sorted(DESIGN.glob('audit_pre_v*.md'), key=lambda f: int(re.search(r'_v(\d+)\.md$', f.name).group(1)))
def next_pre_n(): r = pre_reports(); return (int(re.search(r'_v(\d+)\.md$', r[-1].name).group(1)) + 1) if r else 1
def post_report(tag): return RD / f'audit_post_{tag}.md'
def stamp(path):
    p = Path(path); txt = p.read_text(); kind = 'post' if 'audit_post' in p.name else 'pre'
    d = parse_report(p); tag = d.get('tag') or ('master' if LAND else 'final'); h = hashes(tag if kind == 'post' else None)
    want = {'date': datetime.datetime.now().isoformat(timespec='minutes')}
    if kind == 'pre': want.update({k: h[k] for k in ('storyboard_sha', 'timeline_sha', 'src_sha')}); pv = latest_preview(); want['preview'] = render_rel(pv.name) if pv else '?'
    else: want.update({'tag': tag, 'video_sha': h.get('video_sha') or '?'}); want.update({'submit_sha': h['submit_sha']} if h.get('submit_sha') else {})
    lines = txt.splitlines(); out = []; done = set()
    for ln in lines:
        m = re.match(r'^(\s*[-*]?\s*)(' + '|'.join(want) + r')\s*[:：]', ln, re.I)
        if m and m.group(2).lower() not in done: k = m.group(2).lower(); out.append(f'{m.group(1)}{k}: {want[k]}'); done.add(k)
        else: out.append(ln)
    missing = [k for k in want if k not in done]
    if missing:   # 没有的行补在第一行标题后面
        ins = [f'- {k}: {want[k]}' for k in missing]; i = 1 if out and out[0].startswith('#') else 0; out[i:i] = ins
    if 'result' not in parse_report(p): out[1:1] = ['- result: fail']; print('!! 报告没有 result 行，已补 fail，请改成 pass/fail')
    p.write_text('\n'.join(out) + '\n'); print(f'→ {p}：' + ', '.join(f'{k}={v}' for k, v in want.items()))
    m = re.search(r'audit_pre_v(\d+)\.md$', p.name)
    if kind == 'pre' and m:   # 下一轮 diff 的基准 = 盖章这一刻（审核员改完、重跑预演之后）的状态：只审差异的复审没打包 → 补存（psa 10-22 是手工补的）；打包后审核员又改过 → 重存，打包时的留作 snapshot_at_pack
        d0 = RD / f'audit/pre_v{m.group(1)}'; sn = d0 / 'snapshot'; hj = d0 / 'hashes.json'; packed = json.loads(hj.read_text()) if hj.exists() else {}
        if not (sn.exists() and all(packed.get(k) == h.get(k) for k in ('storyboard_sha', 'timeline_sha', 'src_sha'))):
            if sn.exists(): shutil.rmtree(d0 / 'snapshot_at_pack', ignore_errors=True); sn.rename(d0 / 'snapshot_at_pack')
            snapshot(d0); print(f'  快照 {render_rel(f"audit/pre_v{m.group(1)}/snapshot")} = 盖章时的状态（下一轮 diff 的基准）')
def sb_legacy_ok(rp, sha, h):
    """10-24 前的报告盖的是 storyboard 整文件哈希：①文件一字未改 → 一致；②这一版快照里的 storyboard 整文件哈希等于报告哈希（审核后没再改）→ 用快照算新口径的内容哈希再比（只改了 status 等记录字段也算一致）"""
    if sha == h.get('storyboard_file_sha'): return True
    m = re.search(r'_v(\d+)\.md$', Path(rp).name); sn = RD / f'audit/pre_v{m.group(1)}' if m else None
    for f in ([sn / 'snapshot/storyboard.json', sn / 'snapshot_at_pack/storyboard.json'] if sn else []):
        if f.exists() and sha_file(f) == sha: return sb_sha(f) == h.get('storyboard_sha')
    return False
def check(kind, tag=None, quiet=False):
    """返回 (ok, 原因, 报告路径)"""
    say = (lambda *a: None) if quiet else print
    if kind == 'pre':
        rs = pre_reports()
        if not rs: return False, f'没有渲染前审核报告 design/audit_pre_v1.md（先 {AUD} pack pre，再让审核员按 {REFS / "audit_pre_prompt.md"} 审）', None
        rp = rs[-1]; d = parse_report(rp); h = hashes()
        if d.get('result', '').lower() != 'pass': return False, f'{rp.name} result={d.get("result")}（不是 pass：按报告修完、重跑预演、复审后再写 pass 报告）', rp
        bad = [k for k in ('storyboard_sha', 'timeline_sha', 'src_sha') if d.get(k) != h.get(k) and not (k == 'storyboard_sha' and sb_legacy_ok(rp, d.get(k), h))]
        if bad: return False, f'{rp.name} 的哈希与当前不符：{", ".join(f"{k} 报告 {d.get(k)} / 现在 {h.get(k)}" for k in bad)}（审核后改过东西：{AUD} diff 出差异稿，让审核员只复审差异，写 audit_pre_v{next_pre_n()}.md）', rp
        say(f'✓ {rp.name} pass，storyboard/timeline/src 哈希一致'); return True, 'ok', rp
    tag = tag or ('master' if LAND else 'final'); rp = post_report(tag)
    if not rp.exists(): return False, f'没有成片审核报告 {render_rel(rp.name)}（先 {AUD} pack post --tag {tag}，再让审核员按 {REFS / "audit_post_prompt.md"} 审）', None
    d = parse_report(rp); h = hashes(tag)
    if d.get('result', '').lower() != 'pass': return False, f'{rp.name} result={d.get("result")}（不是 pass：修、重渲、复审）', rp
    if d.get('video_sha') != h.get('video_sha'): return False, f'{rp.name} 的 video_sha {d.get("video_sha")} ≠ 当前成片 {h.get("video_sha")}（成片重渲过，要复审）', rp
    if LAND and h.get('submit_sha') and d.get('submit_sha') != h.get('submit_sha'): return False, f'{rp.name} 的 submit_sha {d.get("submit_sha")} ≠ 当前投稿版 {h.get("submit_sha")}（投稿版重压过，要复审）', rp
    say(f'✓ {rp.name} pass，成片哈希一致'); return True, 'ok', rp
# ---------- 打包 ----------
def ff(*a): subprocess.run(['ffmpeg', '-v', 'error', '-y', '-strict', 'unofficial', *map(str, a)], check=True)   # -strict unofficial：本机 ffmpeg 8.1 的 mjpeg 编码器拒绝电视范围 yuv420p 输入（成片是 BT.709 tv 范围）
def duration(f):
    import probe; return probe.duration(f)
def grab_every2s(mp4, d, w):
    """每 2 s 一帧：fps=0.5:round=up 精确取 0、2、4… 秒那一帧（f0001 = 0 s，第 k 张 = 第 2(k−1) 秒）。10-24 前用 fps=0.5（默认 round=near），实测取的是 (2k−1) 秒前一帧，index 却写“≈ 2k−2 秒”，差约 1 s"""
    (d / 'every2s').mkdir(parents=True, exist_ok=True); ff('-i', mp4, '-vf', f'fps=0.5:round=up,scale={w}:-1', '-pix_fmt', 'yuvj420p', '-q:v', '4', d / 'every2s/f%04d.jpg'); return len(list((d / 'every2s').glob('*.jpg')))
def grab_at(mp4, T, out): ff('-ss', f'{max(0, T):.3f}', '-i', mp4, '-frames:v', '1', '-pix_fmt', 'yuvj420p', '-q:v', '2', out)
def snapshot(d):
    """当前 storyboard / timeline / layout / src 存进 d/snapshot（diff 的基准）"""
    snap = Path(d) / 'snapshot'; snap.mkdir(parents=True); shutil.copy(SB_PATH, snap / 'storyboard.json'); shutil.copy(RD / 'timeline.json', snap / 'timeline.json'); shutil.copy(layout_path(), snap / layout_path().name)
    (snap / 'src').mkdir(); [shutil.copy(f, snap / 'src' / f.name) for f in src_files() if f.exists() and f.suffix in ('.js', '.html')]
    return snap
def pack_pre():
    P = project(); pv = latest_preview()
    if not pv: sys.exit(f'没有预演：{render_rel(P + "_preview_vN.mp4")}（先 {PIPE} run "{ROOT}" --until animatic）')
    TL = load_tl(); SB = load_sb(); n = next_pre_n(); d = RD / f'audit/pre_v{n}'
    hj = d / 'hashes.json'
    if hj.exists() and json.loads(hj.read_text()).get('storyboard_sha') == hashes()['storyboard_sha'] and json.loads(hj.read_text()).get('timeline_sha') == hashes()['timeline_sha'] and json.loads(hj.read_text()).get('src_sha') == hashes()['src_sha'] and (d / 'index.md').exists():
        print(f'  （审核材料 {os.path.relpath(d, ROOT)} 已是当前版本，不重新打包）'); return d
    if d.exists(): shutil.rmtree(d)
    d.mkdir(parents=True); W = 640 if LAND else 480; dur = duration(pv)
    if abs(dur - TL['duration']) > 0.5: print(f'!! 预演 {pv.name} 时长 {dur:.1f} s ≠ timeline {TL["duration"]} s：预演比 timeline 旧，先重跑 animatic 再审（超出预演的关键帧会跳过）')
    ne = grab_every2s(pv, d, W)
    # 关键帧：checkset.js 的清单（封面、每句台词 35%/85%、每张字卡 +0.8 s、每个 cue +0.5 s、场末）→ 这里只取封面、每场开头、字卡、cue、场末（台词点用每 2 s 帧覆盖）
    lst = subprocess.run(['node', str(HERE / 'checkset.js'), '--labels', '--cues', '--ends'], capture_output=True, text=True, check=True).stdout.split()
    S = {s['id']: s for s in TL['scenes']}; rows = []; (d / 'key').mkdir()
    for s in TL['scenes']: lst.append(f"{s['id']}+{1.0 if s['id'] != 's00' else 0.5}")
    seen = set()
    for item in sorted(set(lst), key=lambda x: (x.split('+')[0], float(x.split('+')[1]))):
        sid, dt = item.split('+'); sc = S.get(sid)
        if not sc: continue
        T = sc['start'] + float(dt); key = f'{sid}_{float(dt):07.2f}'
        if key in seen: continue
        seen.add(key); fn = d / f'key/{key}.jpg'
        if T > dur - 0.05: rows.append((f'（超出预演时长 {dur:.1f} s，跳过）', round(T, 2), sid, '')); continue
        grab_at(pv, T, fn)
        what = ''
        for lb in sc.get('labels', []):
            if abs(lb['t'] + 0.8 - float(dt)) < 0.02: what = f"字卡「{lb['text']}」" + ('（big）' if lb.get('big') else '') + ('（alert）' if lb.get('alert') else '')
        for name, t in (sc.get('cues') or {}).items():
            if abs(t + 0.5 - float(dt)) < 0.02: what = what or f'cue {name}'
        if not what: what = '封面' if sid == 's00' else ('场末' if abs(sc['end'] - sc['start'] - 0.6 - float(dt)) < 0.02 else '场开头')
        rows.append((fn.name, round(T, 2), sid, what))
    (d / 'keyframes.tsv').write_text('file\tT\tscene\twhat\n' + '\n'.join('\t'.join(map(str, r)) for r in rows) + '\n')
    snap = snapshot(d)
    h = hashes(); (d / 'hashes.json').write_text(json.dumps(h, ensure_ascii=False, indent=1))
    qa = RD / f'{pv.stem}.qa.json'; ov = RD / f'{pv.stem}.overlay.json'
    rel = lambda p: os.path.relpath(p, ROOT)
    idx = f"""# 渲染前审核材料 v{n} — {P}（{ORIENT}）

- 预演：`{rel(pv)}`（{duration(pv):.1f} s，{TL['width']}×{TL['height']}，timeline {TL['fps']} fps）
- 每 2 s 一帧（缩图 {W} px 宽）：`{rel(d)}/every2s/`（{ne} 张；文件 fNNNN 的第 k 张 = 第 2(k−1) 秒，f0001 = 0 s）
- 关键帧（原尺寸）：`{rel(d)}/key/`（{len(rows)} 张；清单 `keyframes.tsv`：文件、绝对秒、场、是什么——封面 / 每场开头 / 每张字卡出现后 0.8 s / 每个 cue 后 0.5 s / 场末）
- storyboard（唯一真源）：`{rel(SB_PATH)}`
- 配音：`audio/lines/lines.json`（每句 text / 回读结果 passed / ear_ok / seconds）+ `audio/lines/{{scene}}_{{i}}.wav`
- 时间轴：`{rel(RD / 'timeline.json')}`（scenes[].lines[].chunks 字幕块、labels[].t 字卡时刻、card_stays 停留）
- 版式：`{rel(layout_path())}`；画面代码：`src/scenes.js`（+ anat.js / props.js / chars.js）
- 预演 QA：`{rel(qa)}`{'' if qa.exists() else '（缺）'}；叠字层自检：`{rel(ov)}`{'' if ov.exists() else '（缺）'}
- 快照（diff 用，别改）：`{rel(snap)}/`；哈希：`{rel(d / 'hashes.json')}` = {json.dumps({k: h[k] for k in ('storyboard_sha', 'timeline_sha', 'src_sha')})}

**不要读**：`design/*修订稿*`、`design/s0_summary*`、`design/review_*`、`design/*.docx`、`docs/`（作者的设计笔记和修订稿，会带偏审核）。

**报告写到**：`design/audit_pre_v{n}.md`（格式见 `{REFS / "audit_pre_prompt.md"}`）；改完东西、重跑预演（`{PIPE} animatic "{ROOT}"`）、写完报告后最后执行
`{AUD} stamp design/audit_pre_v{n}.md`（在专题目录下执行）把哈希盖进报告头部。
"""
    (d / 'index.md').write_text(idx); log(f'audit pack pre v{n}: {rel(d)} every2s={ne} key={len(rows)} {json.dumps({k: h[k] for k in ("storyboard_sha", "timeline_sha", "src_sha")})}')
    print(f'→ {rel(d)}/index.md（每 2 s {ne} 张，关键帧 {len(rows)} 张）；报告写 design/audit_pre_v{n}.md'); return d
def pack_post(tag=None):
    P = project(); tag = tag or ('master' if LAND else 'final'); mp4 = RD / f'{P}_{tag}.mp4'
    if not mp4.exists(): sys.exit(f'没有成片 {render_rel(mp4.name)}')
    TL = load_tl(); d = RD / f'audit/post_{tag}'
    hj = d / 'hashes.json'
    if hj.exists() and json.loads(hj.read_text()).get('video_sha') == hashes(tag).get('video_sha') and json.loads(hj.read_text()).get('submit_sha') == hashes(tag).get('submit_sha') and (d / 'index.md').exists():
        print(f'  （审核材料 {os.path.relpath(d, ROOT)} 已是当前成片，不重新打包）'); return d
    if d.exists(): shutil.rmtree(d)
    d.mkdir(parents=True); W = 640 if LAND else 480; dur = duration(mp4)
    ne = grab_every2s(mp4, d, W); (d / 'full').mkdir()
    pts = [0.04, 1.0, max(0.1, TL.get('cover', 0) - 0.3)] + [dur - x for x in (6, 4, 2, 0.5)]
    for s in TL['scenes']:
        if s['id'] == 'sref':
            sec = (TL.get('refs') or {}).get('page_seconds') or 5; pts += [s['start'] + sec * k + sec / 2 for k in range(int((TL.get('refs') or {}).get('pages') or 1))]
    for T in sorted(set(round(x, 2) for x in pts if 0 <= x < dur)): grab_at(mp4, T, d / f'full/T{T:07.2f}.jpg')
    # 音频：响度 / 峰值 / 静音段；回放片段 6 × 8 s
    r = subprocess.run(['ffmpeg', '-hide_banner', '-i', str(mp4), '-af', 'ebur128=peak=true,astats=measure_overall=Peak_level+RMS_level+Flat_factor:measure_perchannel=0,silencedetect=n=-45dB:d=1.5', '-f', 'null', '-'], capture_output=True, text=True).stderr
    keep = [ln for ln in r.splitlines() if 'TARGET:' not in ln and re.search(r'Summary|I:|LRA:|Peak:|Peak level|RMS level|Flat factor|silence_(start|end)', ln)]   # ebur128 每 0.1 s 一行（含 TARGET:）不要：原来按 keep[-60:] 截，静音段全被它挤掉
    (d / 'audio_stats.txt').write_text('\n'.join(keep) + '\n'); (d / 'clips').mkdir()
    for k in range(6):
        T = dur * (k + 0.5) / 6; ff('-ss', f'{T:.2f}', '-t', '8', '-i', mp4, '-vn', '-c:a', 'aac', '-b:a', '128k', d / f'clips/c{k + 1}_T{T:06.1f}.m4a')
    for f in (RD / f'{P}_{tag}.qa.json', RD / f'{P}_{tag}.overlay.json', RD / f'{P}_submit.qa.json'):
        if f.exists(): shutil.copy(f, d / f.name)
    h = hashes(tag); (d / 'hashes.json').write_text(json.dumps(h, ensure_ascii=False, indent=1)); rel = lambda p: os.path.relpath(p, ROOT)
    pkg = ''
    if LAND:
        sd = ROOT / 'submit'; files = sorted(sd.glob('*')) if sd.exists() else []
        pkg = '\n- 投稿包 `submit/`：' + ('、'.join(f'`{f.name}`（{f.stat().st_size / 1e6:.1f} MB）' if f.suffix == '.mp4' else f'`{f.name}`' for f in files) if files else '（还没生成：pipeline.py submit）') + '；清单 `submit/投稿须知对照与材料清单.md`、实测 `submit/核对结果.json`'
    idx = f"""# 成片审核材料 — {P} {tag}（{ORIENT}）

- 成片：`{rel(mp4)}`（{dur:.1f} s，{TL['width']}×{TL['height']}；sha {h['video_sha']}）{f"；投稿版 sha {h.get('submit_sha')}" if h.get('submit_sha') else ''}
- 每 2 s 一帧（缩图 {W} px 宽）：`{rel(d)}/every2s/`（{ne} 张；文件 fNNNN 的第 k 张 = 第 2(k−1) 秒，f0001 = 0 s）
- 原尺寸：`{rel(d)}/full/`（片头 0.04/1.0 s、封面结束前、片尾最后 6 s、参考文献每页中点）
- 音频统计：`{rel(d)}/audio_stats.txt`（综合响度 I / LRA / 真峰 / RMS / 静音段 ≥1.5 s）；回放片段 6 × 8 s：`{rel(d)}/clips/`（用系统播放器或 ffplay 听：削波、噪音、配乐压人声、停顿里的杂音）
- QA：`{rel(d)}/{P}_{tag}.qa.json`、叠字层自检 `{P}_{tag}.overlay.json`{'、投稿版 QA `' + P + '_submit.qa.json`' if (d / f'{P}_submit.qa.json').exists() else ''}
- storyboard（口径真源）：`{rel(SB_PATH)}`；时间轴 `{rel(RD / 'timeline.json')}`；渲染前审核报告 `design/audit_pre_v*.md`（看上一道关卡留下的问题是否都处理了）{pkg}
- 哈希：`{rel(d / 'hashes.json')}`

**不要读**：`design/*修订稿*`、`design/s0_summary*`、`design/review_*`、`design/*.docx`、`docs/`。

**报告写到**：`{render_rel('audit_post_' + tag + '.md')}`（格式见 `{REFS / "audit_post_prompt.md"}`）；写完最后执行 `{AUD} stamp {render_rel('audit_post_' + tag + '.md')}`（在专题目录下执行）（横屏加 ORIENT=land）。
"""
    (d / 'index.md').write_text(idx); log(f'audit pack post {tag}: {rel(d)} every2s={ne} video_sha={h["video_sha"]}')
    print(f'→ {rel(d)}/index.md（每 2 s {ne} 张）；报告写 {render_rel("audit_post_" + tag + ".md")}'); return d
# ---------- 差异稿 ----------
def jd(o): return json.dumps(o, ensure_ascii=False)[:160]
def diff_storyboard(a, b, out):
    """scenes 以外的全部顶层字段都比（10-24 前只比 18 个，sources / tts / design 不列，复审员只好自己全量比）；只作记录的 AUDIT_SKIP 字段不列（不进哈希）。列表按下标、字典按子键列"""
    a, b = sb_strip(a), sb_strip(b)
    top = ('title', 'title_card', 'claims', 'red_flags', 'red_flags_action', 'chapters', 'cover', 'outro', 'credits', 'references', 'references_pages', 'references_page_seconds', 'submit', 'timing', 'subtitle_numbers', 'characters', 'audio', 'disclaimer')
    def dd(k, x, y, depth):   # 字典往下钻两层（tts.must.s01_0）、列表按下标列，其余整值列
        if x == y: return
        if isinstance(x, dict) and isinstance(y, dict) and depth < 3:
            for kk in sorted(set(x) | set(y), key=str): dd(f'{k}.{kk}', x.get(kk), y.get(kk), depth + 1)
        elif isinstance(x, list) and isinstance(y, list) and depth < 2:
            for i in range(max(len(x), len(y))): dd(f'{k}[{i}]', x[i] if i < len(x) else None, y[i] if i < len(y) else None, 9)
        else: out.append(f'- `{k}`：{jd(x)} → {jd(y)}')
    for k in list(top) + sorted(k for k in set(a) | set(b) if k not in top and k != 'scenes'): dd(k, a.get(k), b.get(k), 1)
    SA = {s['id']: s for s in a.get('scenes', [])}; SB_ = {s['id']: s for s in b.get('scenes', [])}
    for sid in sorted(set(SA) | set(SB_), key=lambda x: (len(x), x)):
        x, y = SA.get(sid), SB_.get(sid)
        if x is None: out.append(f'- 新增场 `{sid}`'); continue
        if y is None: out.append(f'- 删除场 `{sid}`'); continue
        for k in sorted(set(x) | set(y)):
            if x.get(k) == y.get(k): continue
            if k in ('lines', 'labels') and isinstance(x.get(k), list) and isinstance(y.get(k), list):
                for i in range(max(len(x[k]), len(y[k]))):
                    p_, q_ = (x[k][i] if i < len(x[k]) else None), (y[k][i] if i < len(y[k]) else None)
                    if p_ != q_: out.append(f'- `{sid}.{k}[{i}]`：{jd(p_)} → {jd(q_)}')
            else: out.append(f'- `{sid}.{k}`：{jd(x.get(k))} → {jd(y.get(k))}')
def diff_timeline(a, b, out):
    SA = {s['id']: s for s in a.get('scenes', [])}; SB_ = {s['id']: s for s in b.get('scenes', [])}
    if abs(a.get('duration', 0) - b.get('duration', 0)) > 1e-3: out.append(f"- 总时长 {a.get('duration')} → {b.get('duration')} s")
    for sid in sorted(set(SA) | set(SB_), key=lambda x: (len(x), x)):
        x, y = SA.get(sid), SB_.get(sid)
        if not x or not y: out.append(f'- 场 `{sid}` {"新增" if not x else "删除"}'); continue
        ch = []
        if abs(x['start'] - y['start']) > 1e-3 or abs(x['end'] - y['end']) > 1e-3: ch.append(f"{x['start']}–{x['end']} → {y['start']}–{y['end']}")
        if [l['text'] for l in x['lines']] != [l['text'] for l in y['lines']]: ch.append('台词变了')
        elif [[c['text'] for c in l.get('chunks', [])] for l in x['lines']] != [[c['text'] for c in l.get('chunks', [])] for l in y['lines']]: ch.append('字幕分块变了')
        else:   # 文字和分块都没变，再比时刻（10-28：snap_onsets 修正后 s01–s10 字幕起点全变，差异稿只列了分块变了的 s12）
            mv = [(f"{sid}_{i}#{k}", round((ly['start'] + cy['start']) - (lx['start'] + cx['start']), 3), round((ly['start'] + cy['end']) - (lx['start'] + cx['end']), 3))
                  for i, (lx, ly) in enumerate(zip(x['lines'], y['lines'])) for k, (cx, cy) in enumerate(zip(lx.get('chunks', []), ly.get('chunks', [])))]
            mv = [m for m in mv if abs(m[1]) > 1e-3 or abs(m[2]) > 1e-3]
            if mv:
                fm = lambda m: m[0] + ' ' + ' '.join(f'{w}{v:+.3f}' for w, v in (('起', m[1]), ('止', m[2])) if abs(v) > 1e-3)
                big = max(mv, key=lambda m: max(abs(m[1]), abs(m[2])))
                ch.append(f"字幕块时刻变了 {len(mv)} 块，最大 {fm(big)} s：" + '、'.join(fm(m) for m in mv[:4]) + ('…' if len(mv) > 4 else ''))
        if [(l['text'], l['t']) for l in x.get('labels', [])] != [(l['text'], l['t']) for l in y.get('labels', [])]: ch.append('字卡文字/时刻变了')
        if ch: out.append(f'- `{sid}`：' + '；'.join(ch))
def diff():
    rs = pre_reports()
    if not rs: sys.exit('没有 audit_pre 报告，无从比较（先 pack pre + 审核）')
    n = int(re.search(r'_v(\d+)\.md$', rs[-1].name).group(1)); snap = RD / f'audit/pre_v{n}/snapshot'
    d = parse_report(rs[-1]); h = hashes(); out = []; s_out = []; t_out = []; c_out = []
    if not snap.exists():   # 这一版没有快照（10-24 前只审差异的复审不打包）：退到最近一版有快照的报告；都没有才只列哈希
        olds = [int(re.search(r'_v(\d+)\.md$', r.name).group(1)) for r in rs[:-1]]; older = next((RD / f'audit/pre_v{k}/snapshot' for k in reversed(olds) if (RD / f'audit/pre_v{k}/snapshot').exists()), None)
        if older: s_out.append(f'- （audit_pre_v{n} 没有快照，下面以 {render_rel(str(older.relative_to(RD)))} 为基准：其中有些改动 v{n} 已审过）'); snap = older
    if not snap.exists():   # 报告不是从本工具打的包审出来的（没有快照）：只能列哈希变化，复审只好全审
        s_out.append(f'- （没有快照 {render_rel(f"audit/pre_v{n}/snapshot")}，无法逐项比较；storyboard 哈希 {d.get("storyboard_sha")} → {h["storyboard_sha"]}）')
        t_out.append(f'- （没有快照；timeline 哈希 {d.get("timeline_sha")} → {h["timeline_sha"]}）'); c_out.append(f'- （没有快照；src 哈希 {d.get("src_sha")} → {h["src_sha"]}）')
    else:
        sb0 = json.loads((snap / 'storyboard.json').read_text()); sb1 = load_sb(); diff_storyboard(sb0, sb1, s_out)
        tl0 = json.loads((snap / 'timeline.json').read_text()); tl1 = load_tl(); diff_timeline(tl0, tl1, t_out)
    for f in (src_files() if snap.exists() else []):
        g = snap / ('src' if f.suffix in ('.js', '.html') else '.') / f.name
        if not f.exists() or not g.exists(): continue
        A, B = g.read_text().splitlines(), f.read_text().splitlines()
        if A != B:
            ud = list(difflib.unified_diff(A, B, f'快照/{f.name}', f'现在/{f.name}', lineterm='', n=2))
            c_out.append(f'### {f.name}（{sum(1 for l in ud if l.startswith("+") and not l.startswith("+++"))} 行新增 / {sum(1 for l in ud if l.startswith("-") and not l.startswith("---"))} 行删除）\n```diff\n' + '\n'.join(ud[:400]) + ('\n…（截断）' if len(ud) > 400 else '') + '\n```')
    m = n + 1; rp = DESIGN / f'audit_diff_v{n}.md'
    txt = f"""# 渲染前审核差异稿（基于 audit_pre_v{n}，{datetime.datetime.now().isoformat(timespec='minutes')}）

上一次审核 `design/audit_pre_v{n}.md`（{d.get('date', '?')}，result {d.get('result', '?')}）之后改过的东西。复审只看这里列出的部分，写 `design/audit_pre_v{m}.md`（result + stamp）。
哈希：storyboard {d.get('storyboard_sha')} → {h['storyboard_sha']}；timeline {d.get('timeline_sha')} → {h['timeline_sha']}；src {d.get('src_sha')} → {h['src_sha']}

## storyboard 差异（{len(s_out)} 处）
{chr(10).join(s_out) or '- 无'}

## timeline 差异（{len(t_out)} 处）
{chr(10).join(t_out) or '- 无'}

## 画面代码 / 版式差异（{len(c_out)} 个文件）
{chr(10).join(c_out) or '- 无'}
"""
    rp.write_text(txt); log(f'audit diff v{n}: storyboard {len(s_out)} timeline {len(t_out)} src {len(c_out)}')
    print(f'→ {os.path.relpath(rp, ROOT)}：storyboard {len(s_out)} 处、timeline {len(t_out)} 处、代码 {len(c_out)} 个文件'); return rp
if __name__ == '__main__':
    a = sys.argv[1:]; tag = a[a.index('--tag') + 1] if '--tag' in a else next((x.split('=')[1] for x in a if x.startswith('--tag=')), None)
    if not a: sys.exit(__doc__)
    if a[0] == 'pack': (pack_pre() if a[1:2] == ['pre'] else pack_post(tag) if a[1:2] == ['post'] else sys.exit('pack pre|post'))
    elif a[0] == 'hashes': print(json.dumps(hashes(tag), ensure_ascii=False, indent=1))
    elif a[0] == 'stamp': stamp(a[1])
    elif a[0] == 'check':
        ok, why, rp = check(a[1] if a[1:] else 'pre', tag); print(('✓ ' if ok else '✗ ') + why); sys.exit(0 if ok else 1)
    elif a[0] == 'diff': diff()
    else: sys.exit(__doc__)

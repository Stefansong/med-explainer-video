#!/usr/bin/env python3
"""冒烟测试（Windows / macOS / Linux 通用）：setup → 样例专题 → check → 修订稿（md + docx）→ 无录音预演（后台跑 + wait）→ 草稿配音（审核门要拦）→ 合成语音当录音 → 导入 → 时间轴 → 混音 → 预演 → 审核门 → 正式渲染 → QA → 交付。
  python tests/smoke.py [--no-voice]
审核报告和 HARD 点确认在这里由测试脚本代写，只为验证流水线能跑通，不代表真实审核。录音用 edge-tts 合成（需要联网；失败就跳过配音部分并在最后标出）。"""
import json, os, shutil, subprocess, sys, tempfile, time
if not sys.flags.utf8_mode: sys.exit(subprocess.call([sys.executable, '-X', 'utf8', *sys.argv]))   # 控制台不是 UTF-8（英文 / 中文 Windows）时打印中文会报错：用 UTF-8 模式重跑自己
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent; SK = ROOT / 'med-explainer-video'; PIPE = SK / 'scripts/pipeline.py'; TOOLS = SK / 'scripts/tools'
WORK = Path(os.environ.get('SMOKE_DIR') or tempfile.mkdtemp(prefix='kepu_smoke_')); P = WORK / 'demo'
ENV = dict(os.environ, PYTHONUTF8='1', KEPU_ASR_MODEL=os.environ.get('KEPU_ASR_MODEL', 'small'), FPS='30', SUB='1')
steps = []
def run(name, cmd, expect=0, cwd=None):
    t0 = time.time(); r = subprocess.run([str(c) for c in cmd], cwd=cwd, env=ENV, capture_output=True, text=True, encoding='utf-8', errors='replace')
    ok = r.returncode == expect; steps.append((name, ok, r.returncode, round(time.time() - t0, 1)))
    print(f"{'PASS' if ok else 'FAIL'} {name}（退出码 {r.returncode}，期望 {expect}，{time.time() - t0:.0f} s）", flush=True)
    if not ok: print((r.stdout or '')[-3000:]); print((r.stderr or '')[-3000:]); summary(); sys.exit(1)
    return r
def pipe(name, *args, expect=0): return run(name, [sys.executable, '-X', 'utf8', PIPE, *args], expect)
def summary():
    print('\n==== 冒烟测试 ===='); [print(f"  {'✓' if ok else '✗'} {n}  ({s} s)") for n, ok, _, s in steps]
def sb(): return json.loads((P / 'design/storyboard_demo.json').read_text(encoding='utf-8'))
def save(d): (P / 'design/storyboard_demo.json').write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding='utf-8')
def confirm(k): d = sb(); d['status'][k] = {'confirmed': True, 'by': '冒烟测试', 'date': time.strftime('%Y-%m-%d'), 'note': '测试脚本代写，仅验证流程'}; save(d)

print('工作目录', WORK, '| 平台', sys.platform, '| Python', sys.version.split()[0], flush=True)
pipe('setup', 'setup')
pipe('new --example', 'new', 'demo', '--example', '--dir', WORK)
pipe('check（样例没有错误）', 'check', P)
pipe('new --theme indigo', 'new', 'th1', '--example', '--theme', 'indigo', '--dir', WORK)
th = json.loads((WORK / 'th1/layout.json').read_text(encoding='utf-8'))['theme']['name']; pal = json.loads((WORK / 'th1/design/storyboard_th1.json').read_text(encoding='utf-8'))['style']
ok = th == 'indigo' and pal['theme'] == 'indigo' and pal['palette']['paper'] == '#F5F6FC'; steps.append(('建专题时选的主题写进了版式和调色板', ok, 0, 0)); print('PASS 主题 indigo 已写入' if ok else f'FAIL 主题没写对：{th} {pal.get("theme")}', flush=True)
if not ok: summary(); sys.exit(1)
pipe('theme（换成 amber）', 'theme', WORK / 'th1', 'amber')
pipe('theme（不存在的主题要报错）', 'theme', WORK / 'th1', 'nope', expect=4)
pipe('check（换主题后仍通过）', 'check', WORK / 'th1')
pipe('s0（停在 HARD 点）', 's0', P, expect=3)
docx = list((P / 'design').glob('*修订稿*.docx')); steps.append(('修订稿出了 docx', bool(docx), 0, 0)); print('PASS 修订稿 docx' if docx else 'FAIL 修订稿没有 docx', flush=True)
if not docx: summary(); sys.exit(1)
pipe('timeline --estimate', 'timeline', P, '--estimate')
pipe('frames', 'frames', P)
# 后台运行：--bg 立刻返回；再起一个要被拒绝；wait 没等完返回 7，等完返回任务自己的退出码
pipe('animatic --bg（放后台）', 'animatic', P, '--workers=2', '--bg')
pipe('后台任务没结束时不许再起一个', 'frames', P, '--bg', expect=4)
t0 = time.time(); seen7 = False
while True:
    r = subprocess.run([sys.executable, '-X', 'utf8', str(PIPE), 'wait', str(P), '--timeout=8'], env=ENV, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if r.returncode != 7: break
    seen7 = True
    if time.time() - t0 > 1500: break
ok = r.returncode == 0; steps.append(('wait（等后台预演结束）', ok, r.returncode, round(time.time() - t0, 1)))
print(f"{'PASS' if ok else 'FAIL'} wait（退出码 {r.returncode}，期望 0，{time.time() - t0:.0f} s，中途返回过 7：{seen7}）", flush=True)
if not ok: print((r.stdout or '')[-3000:]); print((r.stderr or '')[-2000:]); summary(); sys.exit(1)
assert list((P / 'render').glob('demo_preview_v1.mp4')), '没有预演 mp4'
run('cutout（品红底抠图）', [sys.executable, '-X', 'utf8', '-c', "from PIL import Image, ImageDraw; im = Image.new('RGB', (400, 600), (255, 0, 255)); ImageDraw.Draw(im).ellipse((100, 100, 300, 500), fill=(80, 140, 220)); im.save('t_magenta.png')"], cwd=P)
run('cutout', [sys.executable, '-X', 'utf8', TOOLS / 'cutout.py', 't_magenta.png', 'ic_test', '--no-register'], cwd=P)

voice = '--no-voice' not in sys.argv
if voice:
    confirm('s0'); confirm('s3')
    pipe('voice（缺录音停下）', 'voice', P, expect=6)
    has_docx = (P / 'audio/台词本.docx').exists(); steps.append(('台词本出了 docx', has_docx, 0, 0)); print('PASS 台词本 docx' if has_docx else 'FAIL 台词本没有 docx', flush=True)
    if not has_docx: summary(); sys.exit(1)
    # 草稿配音：能导入、lines.json 标成 draft；预演审核门要拦（退出码 6）。合成要联网，失败就跳过这一段
    r = subprocess.run([sys.executable, '-X', 'utf8', str(PIPE), 'voice', str(P), '--draft'], env=ENV, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if r.returncode == 0:
        rows = json.loads((P / 'audio/lines/lines.json').read_text(encoding='utf-8')); nd = sum(x['engine'] == 'draft' for x in rows)
        ok = nd == len(rows) > 0; steps.append(('voice --draft（全部是草稿声）', ok, 0, 0)); print(f"{'PASS' if ok else 'FAIL'} voice --draft：{nd}/{len(rows)} 句草稿", flush=True)
        if not ok: summary(); sys.exit(1)
        pipe('草稿配音时审核门要拦（等录音）', 'audit_pre', P, expect=6)
    else: print('SKIP 草稿配音（合成失败，多半是网络）：', (r.stdout or '')[-300:].strip()); steps.append(('草稿配音（跳过：合成失败）', True, 0, 0))
    rec = P / 'audio/recordings'; lines = [(s['id'], i, l) for s in sb()['scenes'] for i, l in enumerate(s['lines'])]
    try:
        for sid, i, l in lines:
            v = 'zh-CN-YunxiNeural' if l['who'] != 'narrator' else 'zh-CN-XiaoxiaoNeural'
            for k in range(3):
                r = subprocess.run([sys.executable, '-m', 'edge_tts', '--voice', v, '--rate=-10%', '--text', l['text'], '--write-media', str(rec / f'{sid}_{i}.mp3')], capture_output=True, text=True)
                if r.returncode == 0 and (rec / f'{sid}_{i}.mp3').stat().st_size > 2000: break
                time.sleep(3)
            else: raise RuntimeError(r.stderr[-300:])
        print('PASS 合成测试录音', len(lines), '句', flush=True)
    except Exception as e:
        print('SKIP 配音部分：合成测试录音失败（网络？）', e); voice = False; steps.append(('配音部分（跳过：合成不了测试录音）', True, 0, 0))
if voice:
    d = sb(); d.setdefault('qa', {})['asr_min'] = 0.9; d['tts']['min_pinyin'] = 0.85; save(d)   # 测试用小模型回读，门限放宽
    pipe('voice（导入录音 + 回读）', 'voice', P)
    rows = json.loads((P / 'audio/lines/lines.json').read_text(encoding='utf-8')); bad = [f"{r['scene']}_{r['i']}" for r in rows if not r['passed']]
    assert all(r['engine'] == 'recording' for r in rows), '导入录音后还有草稿声没被替换'
    print('  回读没过的句子：', bad or '无')
    pipe('run --until s6a（停在审核门）', 'run', P, '--until', 's6a', '--workers=2', expect=5)
    (P / 'design/audit_pre_v1.md').write_text('# 渲染前审核 v1（冒烟测试代写）\n\n- result: pass\n- auditor: smoke\n', encoding='utf-8')
    run('audit stamp pre', [sys.executable, '-X', 'utf8', TOOLS / 'audit.py', 'stamp', 'design/audit_pre_v1.md'], cwd=P)
    pipe('run --until s6a（停在 HARD S6a）', 'run', P, '--until', 's6a', expect=3)
    confirm('s6a')
    pipe('run --until qa（正式渲染 + QA）', 'run', P, '--until', 'qa', '--workers=2')
    qa = json.loads((P / 'render/demo_final.qa.json').read_text(encoding='utf-8')); print('  QA pass =', qa['pass'], '| 回读相似度', qa.get('asr_pinyin_similarity'), '|', qa.get('resolution'), qa.get('fps'), 'fps', qa.get('duration_s'), 's')
    pipe('run --until deliver（停在成片审核门）', 'run', P, '--until', 'deliver', expect=5)
    (P / 'render/audit_post_final.md').write_text('# 成片审核（冒烟测试代写）\n\n- result: pass\n- auditor: smoke\n', encoding='utf-8')
    run('audit stamp post', [sys.executable, '-X', 'utf8', TOOLS / 'audit.py', 'stamp', 'render/audit_post_final.md'], cwd=P)
    pipe('deliver', 'run', P, '--until', 'deliver')
    pipe('export_subs', 'export_subs', P)
    pipe('clean（只列清单）', 'clean', P)
    pipe('status', 'status', P)
summary(); print('全部通过' + ('' if voice else '（配音部分未测）'))

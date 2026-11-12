#!/usr/bin/env python3
"""错误提示测试：故意把分镜和场景代码写错，确认流水线会拦下来，并且提示里说清了是什么错（不是一屏报错栈）。
  python tests/test_errors.py     需要先跑过 pipeline.py setup"""
import json, os, re, subprocess, sys, tempfile, shutil
if not sys.flags.utf8_mode: sys.exit(subprocess.call([sys.executable, '-X', 'utf8', *sys.argv]))   # 控制台不是 UTF-8（英文 / 中文 Windows）时打印中文会报错：用 UTF-8 模式重跑自己
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent; PIPE = ROOT / 'med-explainer-video/scripts/pipeline.py'
WORK = Path(os.environ.get('SMOKE_DIR') or tempfile.mkdtemp(prefix='kepu_err_')) / 'errs'; shutil.rmtree(WORK, ignore_errors=True); WORK.mkdir(parents=True)
ENV = dict(os.environ, PYTHONUTF8='1')
def pipe(*a): r = subprocess.run([sys.executable, '-X', 'utf8', str(PIPE), *map(str, a)], env=ENV, capture_output=True, text=True, encoding='utf-8', errors='replace'); return r.returncode, (r.stdout or '') + (r.stderr or '')
assert pipe('new', 'e1', '--example', '--dir', WORK)[0] == 0
P = WORK / 'e1'; SBF = P / 'design/storyboard_e1.json'; SCF = P / 'src/scenes.js'; SB0 = SBF.read_text(encoding='utf-8'); SC0 = SCF.read_text(encoding='utf-8')
assert pipe('timeline', P, '--estimate')[0] == 0
fails = []
def case(name, cmd, must, sb=None, sc=None, expect_fail=True):
    """sb：对分镜做的修改（函数或原始文本）；sc：对 scenes.js 的替换 (旧, 新)；must：输出里必须出现的词（正则）"""
    if callable(sb): d = json.loads(SB0); sb(d); SBF.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding='utf-8')
    elif isinstance(sb, str): SBF.write_text(sb, encoding='utf-8')
    else: SBF.write_text(SB0, encoding='utf-8')
    if sc: assert sc[0] in SC0, sc[0]; SCF.write_text(SC0.replace(sc[0], sc[1], 1), encoding='utf-8')
    else: SCF.write_text(SC0, encoding='utf-8')
    code, out = pipe(*cmd, P)
    ok = (code != 0) == expect_fail and all(re.search(m, out) for m in must) and 'Traceback' not in out
    print(('PASS ' if ok else 'FAIL ') + name + f'（退出码 {code}）')
    if not ok: fails.append(name); print('    期望包含：', must, '\n    实际输出（末尾）：\n' + '\n'.join('      ' + l for l in out.strip().splitlines()[-12:]))

case('样例本身检查通过', ['check'], ['检查通过'], expect_fail=False)
case('JSON 写坏', ['check'], ['不是合法的 JSON', r'第 \d+ 行'], sb=SB0[:-40])
case('字卡锚词不在台词里', ['s0'], ['锚的词“不存在的词”不在第 0 句', '林阿姨买菜回来'], sb=lambda d: d['scenes'][0]['labels'][0].__setitem__('at', [0, '不存在的词']))
case('cue 锚词不在台词里', ['check'], ['cue "shock" 锚的词“肚子”'], sb=lambda d: d['scenes'][0]['cues'].__setitem__('shock', [2, '肚子']))
case('台词角色没登记', ['s0'], ['角色 "linayi" 没在 characters 里登记', 'narrator'], sb=lambda d: d['scenes'][0]['lines'][1].__setitem__('who', 'linayi'))
case('句号越界', ['timeline', '--estimate'], ['锚在第 7 句', '只有 3 句'], sb=lambda d: d['scenes'][0]['labels'][0].__setitem__('at', [7, '顾不上']))
case('场景不在章节里', ['check'], ['场景 s01 不在任何章节里'], sb=lambda d: d['chapters'][0].__setitem__('scenes', []))
case('危险信号没上字卡', ['s0'], ['危险信号“血压很高伴持续胸背剧痛或喘不上气、不能平卧”没有上字卡'], sb=lambda d: d['scenes'][3]['labels'].pop(1))
case('素材文件不存在', ['check'], ['素材 ic_bpmonitor 登记的文件不存在'], sb=lambda d: d['assets'].__setitem__('ic_bpmonitor', {'src': 'assets/lib/props/nope.png'}))
case('场景代码语法错误', ['frames'], ['语法错误', r'第 \d+ 行'], sc=('home(c, t);', 'home(c, t;'))
case('调用不存在的函数', ['frames'], ['SH.actor 不存在'], sc=("SP(c, A, 'sp_lin_worry', spX(A, 'sp_lin_worry', 500, 740) + jolt", "SH.actor(c, A, 'sp_lin_worry', 500 + jolt"))
case('解构了不存在的函数', ['check'], ['取了不存在的 "actor"'], sc=('const { W, P, paper,', 'const { W, P, actor, paper,'))
case('图的名字写错', ['check'], ["用了图 'sp_lin_happy'", 'sp_lin_point'], sc=("'sp_lin_point', spX(A, 'sp_lin_point', 790, 540)", "'sp_lin_happy', spX(A, 'sp_lin_happy', 790, 540)"))
case('用了随机数', ['frames'], ['Math.random'], sc=("const t = A.t, shock = A.cue('shock');", "const t = A.t, shock = A.cue('shock'), rnd = Math.random();"))
case('cue 没声明', ['check'], [r"A\.cue\('ouch'\) 在分镜的 s01 里没有声明", 'shock'], sc=("shock = A.cue('shock');", "shock = A.cue('ouch');"))
case('画面里写字', ['check'], ['写了字'], sc=('home(c, t);', "home(c, t); c.fillText('多喝水', 100, 100);"))
case('运行时出错（语法对、逻辑错）', ['frames'], ['场景 s02 运行出错', r'scenes\.js 第 \d+ 行'], sc=("IC(c, A, 'ic_bpmonitor', 300, 970, 440,", "const boom = A.nothing.here; IC(c, A, 'ic_bpmonitor', 300, 970, 440,"))
case('尺寸写成了倍数', ['frames'], ['尺寸写成了 1', '像素'], sc=("1190, 740, { pop: (t - shock) / 0.4 }", "1190, 1, { pop: (t - shock) / 0.4 }"))
case('整场是空画面', ['frames'], ['s04：', '几乎没有东西'], sc=("    flags(c, t, [f1, f2], 520);\n    paperFloor(c, 1130);\n    SP(c, A, 'sp_lin_worry', spX(A, 'sp_lin_worry', 540, 440), 1130, 440, { pop: t / 0.45 });\n", ""))
case('没写片尾也能出片', ['frames'], ['frames'], sc=("SC.s99 = (c, A) => { paper(c, A.t, 47); SP(c, A, 'sp_lin_point', 540, 880, 520, { pop: A.t / 0.45 }); };", ''), expect_fail=False)
SBF.write_text(SB0, encoding='utf-8'); SCF.write_text(SC0, encoding='utf-8')
print(f'\n错误提示测试：{len(fails)} 项没过' + (f'：{fails}' if fails else '，全部通过')); sys.exit(1 if fails else 0)

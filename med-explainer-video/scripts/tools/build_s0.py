#!/usr/bin/env python3
"""S0：把修订稿（场景、台词、字卡、cue、口径、危险信号、出处、解剖核对）一次写进 storyboard（唯一真源）。
这是一个**写作骨架**：新专题复制后在 S 里按场填内容（bph 的完整例子见 bph/tools/build_s0.py，281 行）。
S0 确认后不再运行本脚本，直接改 JSON（否则会把人工改动冲掉）。运行：python3 tools/build_s0.py"""
import json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import find_storyboard, validate_storyboard, load_layout
SBP = find_storyboard(); d = json.loads(SBP.read_text())
st = d.get('status');
if isinstance(st, dict) and st.get('s0', {}).get('confirmed'): sys.exit('S0 已确认：不再用 build_s0.py 整体重写，直接改 storyboard JSON')

def L(who, text, emo='warm', **kw): return dict(who=who, text=text, emo=emo, **kw)          # 台词行：who / text / emo，可带 hold（句后停顿秒）、say（配音用同音写法）、br（字幕强制断点）、tts_note
def lab(i, anchor, text, **kw): return dict(at=[i, anchor], text=text, **kw)             # 字卡：锚在第 i 句的 anchor 词开口时刻；big=True 红底大卡，alert=True 红色强调
def cue(i, anchor): return [i, anchor]                                                   # 画面事件锚点：A.cue(name) 在 scenes.js 里取到

S = []
# ---- 每场一个 dict。visual 写给动画师（和未来的自己）看：画面要素、顺序、不画什么；check_frames 给 anatset.js 抽帧核对 ----
S.append(dict(id='s01', chapter='c0',
  beat='（节拍：这一场讲什么、用什么钩子）',
  hook='（抓人点）',
  claims=['P1'],
  visual='（画面设计：要素、顺序、转场；画面零文字）',
  lines=[
    L('narrator', '（第一句台词。）', 'intrigued'),
  ],
  labels=[lab(0, '第一句', '（字卡：锚在“第一句”开口）')],
  cues={'start': cue(0, '第一句')},
  check_frames=['cue:start+0.5', 'end-1.0'],
  lead=0.4))

def nchar(t): return len(re.sub(r'[^一-鿿0-9A-Za-z]', '', t))
for s in S:
    s['chars'] = sum(nchar(l['text']) for l in s['lines'])
    s['est_seconds'] = round(s['chars'] / (d.get('timing') or {}).get('est_chars_per_s', 5.0) + 0.4 * len(s['lines']) + 0.6, 1)
d['scenes'] = S
d['est'] = {'narration_chars': sum(s['chars'] for s in S), 'rate_chars_per_s': (d.get('timing') or {}).get('est_chars_per_s', 5.0), 'est_total_seconds': round(sum(s['est_seconds'] for s in S) + 5, 1)}
# 校验：每场属于一个章节、每条 claim 存在、危险信号都在某张字卡里
chap = {sid for c in d['chapters'] for sid in c['scenes']}
for s in S:
    assert s['id'] in chap, f"{s['id']} 不在 chapters 里"
    for c in s['claims']: assert any(x['id'] == c for x in d['claims']), f"{s['id']} 引用了不存在的口径 {c}"
for wmsg in validate_storyboard(d, load_layout()): print('!!', wmsg)   # >8 张卡未声明 max_labels / 单卡 >14 字 / 解剖场缺 check_frames / 危险信号未上卡
SBP.write_text(json.dumps(d, ensure_ascii=False, indent=1) + '\n')
print('written', SBP.name, len(S), 'scenes', d['est'])

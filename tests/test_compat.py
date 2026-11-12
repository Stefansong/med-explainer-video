#!/usr/bin/env python3
"""旧版 Python 兼容性检查：技能声明支持 Python 3.9 及以上，但开发和 CI 用的是 3.12。
在 3.12 上跑也能查出两类只有新版才认的写法：
  1. 3.10+ 的语法（match 语句、带括号的多个 with 项等）：ast.parse(feature_version=(3, 9))
  2. 3.12 才允许的 f-string 写法：花括号里用了和外层相同的引号、或带反斜杠（旧版直接 SyntaxError）
  python tests/test_compat.py"""
import ast, glob, io, sys, tokenize
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
FILES = [ROOT / 'med-explainer-video/scripts/pipeline.py', ROOT / 'med-explainer-video/scripts/setup_env.py'] + sorted((ROOT / 'med-explainer-video/scripts/tools').glob('*.py')) + sorted((ROOT / 'tests').glob('*.py'))
def delim(s):   # 字符串记号的引号部分：' " \'\'\' """
    q = s.lstrip('rRbBfFuU'); return q[:3] if q[:3] in ("'''", '"""') else q[:1]
def fstring_issues(src):
    out = []; stack = []
    if not hasattr(tokenize, 'FSTRING_START'): return out   # 3.11 及以下：能 import 这个文件本身就说明语法没问题，下面的 compile 会查
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type == tokenize.FSTRING_START:
            if any(d in tok.string for d in stack): out.append((tok.start[0], '嵌套的 f-string 用了和外层相同的引号'))
            stack.append(delim(tok.string))
        elif tok.type == tokenize.FSTRING_END: stack.pop()
        elif stack and tok.type != tokenize.FSTRING_MIDDLE:
            if tok.type == tokenize.STRING and any(d in tok.string for d in stack): out.append((tok.start[0], 'f-string 的花括号里用了和外层相同的引号'))
            if '\\' in tok.string: out.append((tok.start[0], 'f-string 的花括号里有反斜杠'))
    return out
bad = 0
for f in FILES:
    src = f.read_text(encoding='utf-8')
    try: ast.parse(src, filename=str(f), feature_version=(3, 9)); compile(src, str(f), 'exec')
    except SyntaxError as e: bad += 1; print(f'FAIL {f.relative_to(ROOT)} 第 {e.lineno} 行：{e.msg}'); continue
    for ln, why in fstring_issues(src): bad += 1; print(f'FAIL {f.relative_to(ROOT)} 第 {ln} 行：{why}（Python 3.12 以前会报语法错误）')
print(f'旧版 Python 兼容性检查：{len(FILES)} 个文件，' + (f'{bad} 处问题' if bad else '全部通过')); sys.exit(1 if bad else 0)

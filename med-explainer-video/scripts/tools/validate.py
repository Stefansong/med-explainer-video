#!/usr/bin/env python3
"""分镜（storyboard）校验：把写错的地方用人话指出来，说明在哪、为什么、怎么改。pipeline 的 s0 / timeline / check 会调用。
  python tools/validate.py [--json]        在专题目录下跑（或设 KEPU_PROJECT）；有错误退出码 1，只有提醒退出码 0
错误（必须改，不改后面的阶段会失败或出错片）：JSON 语法、缺字段、场景号重复 / 不在章节里、台词的角色没登记、字卡 / cue 锚的词不在那句台词里、
  句号越界、引用了不存在的口径、素材文件不在、危险信号没上字卡、check_frames 写法不对。
提醒（建议改）：模板占位没换、口径没登记来源、字卡太长、某句台词没有任何画面事件、估算片长超出目标、语气词不认识、角色没定配音。"""
import json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

def load_json_friendly(path):
    """读 JSON；语法错了给出行号、那一行的内容和常见原因"""
    txt = Path(path).read_text(encoding='utf-8')
    try: return json.loads(txt), None
    except json.JSONDecodeError as e:
        lines = txt.splitlines(); ln = e.lineno; ctx = lines[ln - 1].strip()[:120] if 0 < ln <= len(lines) else ''
        prev = lines[ln - 2].strip()[:120] if ln >= 2 else ''
        hint = '常见原因：上一行末尾少了逗号；最后一项后面多了逗号；用了中文引号 “ ” 或中文逗号；字符串里的英文双引号没写成 \\"；括号没配对'
        return None, f'{Path(path).name} 不是合法的 JSON：第 {ln} 行第 {e.colno} 列附近（{e.msg}）。\n    上一行：{prev}\n    这一行：{ctx}\n    {hint}'

def han(s): return re.sub(r'[^一-鿿A-Za-z0-9]', '', s or '')

def check(root):
    """→ (errors, warnings, storyboard 或 None)"""
    from _common import find_storyboard, validate_storyboard, red_flag_check, emo_notes, load_layout
    E, W = [], []
    try: sbp = find_storyboard(root)
    except SystemExit as e: return [str(e)], [], None
    SB, err = load_json_friendly(sbp)
    if err: return [err], [], None
    name = sbp.name
    for k in ('project', 'title', 'characters', 'claims', 'red_flags', 'chapters', 'scenes', 'style'):
        if k not in SB: E.append(f'{name} 缺少字段 "{k}"（对照样例专题的 storyboard 补上）')
    if E: return E, W, SB
    chars = SB['characters']; scenes = SB['scenes']
    if not isinstance(scenes, list) or not scenes: return [f'{name} 的 scenes 是空的：至少要有一场'], W, SB
    # ---- 场景号、章节 ----
    ids = [s.get('id') for s in scenes]
    for i in sorted({x for x in ids if ids.count(x) > 1}, key=str): E.append(f'场景号重复：{i}（每场的 id 要不同，按 s01、s02… 编）')
    for i in ids:
        if not isinstance(i, str) or not re.match(r'^s\d{2,}$', i) or i in ('s00', 's99'): E.append(f'场景号 "{i}" 不合规：用 s01、s02…（s00 是封面、s99 是片尾，由系统生成，不要自己用）')
    chap = {}
    for c in SB['chapters']:
        for sid in c.get('scenes', []):
            if sid not in ids: E.append(f'章节 "{c.get("node", c.get("id"))}" 里列了不存在的场景 {sid}')
            if sid in chap: E.append(f'场景 {sid} 同时出现在两个章节里（{chap[sid]}、{c.get("node")}）：只能属于一个')
            chap[sid] = c.get('node')
    for i in ids:
        if i not in chap: E.append(f'场景 {i} 不在任何章节里：把它加进 chapters[].scenes')
    # ---- 逐场 ----
    claim_ids = {c.get('id') for c in SB['claims']}; emos = set(emo_notes(SB)); places = SB.get('places') or {}
    total_chars = 0
    for s in scenes:
        sid = s.get('id'); lines = s.get('lines')
        if not isinstance(lines, list) or not lines: E.append(f'{sid} 没有台词（lines 为空）：每场至少一句'); continue
        for k in ('beat', 'visual'):
            if not s.get(k): W.append(f'{sid} 没写 {k}（{"这场讲什么" if k == "beat" else "画面要素与出场顺序"}）')
        for i, l in enumerate(lines):
            who = l.get('who'); text = l.get('text') or ''
            if who not in chars: E.append(f'{sid} 第 {i} 句的角色 "{who}" 没在 characters 里登记（现有：{"、".join(chars)}）。要么改成现有的角色代号，要么在 characters 里加上它')
            if not han(text): E.append(f'{sid} 第 {i} 句没有台词文字')
            if l.get('emo') and l['emo'] not in emos: W.append(f'{sid} 第 {i} 句的语气 "{l["emo"]}" 不在内置表里（台词本里不会有语气提示）。可用：{"、".join(sorted(emos))}；或在 tts.emo_notes 里自己加')
            total_chars += len(han(text))
        def anchor(kind, at, what):
            if not (isinstance(at, list) and len(at) == 2 and isinstance(at[0], int) and isinstance(at[1], str)):
                E.append(f'{sid} 的{kind} {what} 的位置写法不对：应该是 [第几句（从 0 数）, "那句台词里的一个词"]，现在是 {json.dumps(at, ensure_ascii=False)}'); return None
            li, word = at
            if not 0 <= li < len(lines):
                E.append(f'{sid} 的{kind} {what} 锚在第 {li} 句，但这场只有 {len(lines)} 句（句号从 0 数，最大 {len(lines) - 1}）'); return None
            if word not in (lines[li].get('text') or ''):
                E.append(f'{sid} 的{kind} {what} 锚的词“{word}”不在第 {li} 句里。第 {li} 句是：“{lines[li].get("text")}”。改成这句话里原样出现的词（标点、空格都要一致）'); return None
            return li
        hit = set()
        for k, lb in enumerate(s.get('labels') or []):
            if not (lb.get('text') or '').strip(): E.append(f'{sid} 第 {k} 张字卡没有文字')
            li = anchor('字卡', lb.get('at'), f'“{lb.get("text")}”')
            if li is not None: hit.add(li)
        for cname, at in (s.get('cues') or {}).items():
            if not re.match(r'^[A-Za-z_]\w*$', cname): E.append(f'{sid} 的 cue 名字 "{cname}" 不合规：只用英文字母、数字、下划线，字母开头（场景代码里用 A.cue(\'{cname}\') 取）')
            li = anchor('cue', at, f'"{cname}"')
            if li is not None: hit.add(li)
        if len(lines) >= 2 or s.get('labels') or s.get('cues'):
            for i, l in enumerate(lines):
                if i not in hit and len(han(l.get('text'))) >= 12: W.append(f'{sid} 第 {i} 句（“{(l.get("text") or "")[:18]}…”）没有任何字卡或 cue 锚在这句上：这句话讲的内容画面上要有对应的变化，给它加一个 cue 并在场景代码里用上')
        for c in s.get('claims') or []:
            if c not in claim_ids: E.append(f'{sid} 引用了口径 {c}，但口径表（claims）里没有这个编号')
        if s.get('place') and s['place'] not in places: W.append(f'{sid} 的地点 "{s["place"]}" 没在 places 里登记')
        for spec in s.get('check_frames') or []:
            if isinstance(spec, (int, float)): continue
            m = re.match(r'^(?:cue:(\w+)|label:(\d+)|line:(\d+)@.+?|end)([+-][\d.]+)?$', str(spec))
            if not m: E.append(f'{sid} 的 check_frames "{spec}" 写法不对：可以写 "cue:名字+0.6"、"label:2+0.8"、"line:1@某词+1.2"、"end-1.0" 或一个数字（场内秒）')
            elif m.group(1) and m.group(1) not in (s.get('cues') or {}): E.append(f'{sid} 的 check_frames "{spec}" 用了没声明的 cue "{m.group(1)}"')
            elif m.group(2) and int(m.group(2)) >= len(s.get('labels') or []): E.append(f'{sid} 的 check_frames "{spec}"：这场没有第 {m.group(2)} 张字卡')
    # ---- 口径与来源 ----
    seen = set()
    for c in SB['claims']:
        cid = c.get('id')
        if not cid or not c.get('text'): E.append(f'口径表里有一条缺 id 或 text：{json.dumps(c, ensure_ascii=False)[:80]}'); continue
        if cid in seen: E.append(f'口径编号重复：{cid}')
        seen.add(cid)
        srcs = [x for x in re.split(r'[,，、;；\s]+', str(c.get('src') or '')) if x]
        lost = [x for x in srcs if x not in (SB.get('sources') or {})]
        if not srcs: W.append(f'口径 {cid} 没写来源（src）：按 references/sources.md 查到来源后登记；查不到就在 S0 明确告诉用户“待核”')
        elif lost: W.append(f'口径 {cid} 的来源 {"、".join(lost)} 没在 sources 里登记')
    used = {c for s in scenes for c in (s.get('claims') or [])}
    for cid in sorted(seen - used): W.append(f'口径 {cid} 没有任何一场引用（scenes[].claims）：没用到就删掉，用到了就在那一场写上')
    # ---- 危险信号 ----
    try:
        rf, _ = red_flag_check(SB)
        for f, r in rf.items():
            if not r['ok']: E.append(f'危险信号“{f}”没有上字卡：在讲它的那一场加一张字卡，文字以这条危险信号的前几个字开头，并写 "alert": true 和 "rf": {SB["red_flags"].index(f)}')
            elif r.get('alert') is False: W.append(f'危险信号“{f}”的字卡没写 "alert": true（不会显示成红色警示卡）')
            for x in r.get('warn') or []: W.append(f'危险信号“{f}”：{x}')
    except Exception as e: W.append(f'危险信号检查没跑成：{e}')
    # ---- 素材 ----
    for k, v in (SB.get('assets') or {}).items():
        if k.startswith('_'): continue
        src = v.get('src') if isinstance(v, dict) else v
        if not src or not (Path(root) / src).exists(): E.append(f'素材 {k} 登记的文件不存在：{src}（补上文件，或从 assets 里删掉这条）')
    # ---- 配音分工、占位、片长 ----
    whos = {l.get('who') for s in scenes for l in (s.get('lines') or [])}
    for w in sorted(x for x in whos if x in chars and x not in (SB.get('voices') or {})): W.append(f'角色 {w} 有台词，但 voices 里没写由谁来配')
    for w in sorted(x for x in chars if x not in whos and x != 'narrator'): W.append(f'角色 {w} 在 characters 里，但全片没有一句台词：是模板占位就删掉（voices 里对应的也删）')
    ph = lambda v: isinstance(v, str) and re.match(r'^（.*）$', v.strip())
    for path, v in [('title', SB.get('title')), ('片尾口号 outro.slogan', (SB.get('outro') or {}).get('slogan')), ('画风 style.art', (SB.get('style') or {}).get('art'))] + [(f'角色 {k} 的名字', (c or {}).get('name')) for k, c in chars.items()] + [(f'口径 {c.get("id")}', c.get('text')) for c in SB['claims']] + [(f'来源 {k}', v) for k, v in (SB.get('sources') or {}).items() if not k.startswith('_')] + [(f'署名 credits[{i}]', c if isinstance(c, str) else (c or {}).get('text')) for i, c in enumerate(SB.get('credits') or [])]:
        if ph(v) or (isinstance(v, str) and '（你的署名' in v): W.append(f'{path} 还是模板占位：{v}')
    if not (SB.get('style') or {}).get('art') and (SB.get('assets') or any((c or {}).get('art3d') for c in chars.values())): W.append('style.art 没写画风：出图前先和用户定画风，写成一段话，每张图的提示词都以它开头（references/characters_3d.md 第 0 节）')
    tgt = SB.get('target_seconds')
    if tgt:
        est = total_chars / 4.5 + len(scenes) * 1.2 + 6   # 台词 + 场间停顿 + 片尾
        if est > tgt * 1.15: W.append(f'按台词字数估算成片约 {est:.0f} 秒，超过目标 {tgt} 秒：删减台词（现在 {total_chars} 字，约 {int(tgt * 4.5 * 0.8)} 字合适），或改 target_seconds')
    try:
        for w in validate_storyboard(SB, load_layout(Path(root))):
            if '危险信号' not in w: W.append(w)
    except Exception: pass
    return E, list(dict.fromkeys(W)), SB

def report(E, W, out=sys.stdout):
    for e in E: print('✗', e, file=out)
    for w in W: print('!', w, file=out)
    print(f'分镜校验：{len(E)} 个错误，{len(W)} 条提醒' + ('' if E else '（没有错误）'), file=out)

if __name__ == '__main__':
    from _common import ROOT
    E, W, _ = check(ROOT)
    if '--json' in sys.argv: print(json.dumps({'errors': E, 'warnings': W}, ensure_ascii=False, indent=1))
    else: report(E, W)
    sys.exit(1 if E else 0)

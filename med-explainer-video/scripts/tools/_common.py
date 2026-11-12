"""工具共用（Python 侧）：项目根、画幅（ORIENT）、产物目录、storyboard 定位、layout 读取、TTS venv 解释器、whisper 回读提示词、日志。专题常量一律不写在这里。
画幅：环境变量 ORIENT=port（默认，竖屏 1080×1920，产物在 render/）或 ORIENT=land（横屏 1920×1080，版式 layout_land.json，产物全部在 render/land/，竖屏产物不受影响）。"""
import json, os, sys, datetime, locale
from pathlib import Path
# 工具被单独运行（不经 pipeline.py）且系统默认编码不是 UTF-8（中文 Windows 是 GBK）：用 UTF-8 模式重跑本脚本，免得读写中文 JSON 报错
if not sys.flags.utf8_mode and (locale.getpreferredencoding(False) or '').lower().replace('-', '') != 'utf8' and sys.argv and sys.argv[0].endswith('.py') and os.environ.get('_KEPU_UTF8') != '1':
    import subprocess
    os.environ['PYTHONUTF8'] = '1'; os.environ['_KEPU_UTF8'] = '1'
    sys.exit(subprocess.call([sys.executable, '-X', 'utf8', *sys.argv]))
# 专题目录：$KEPU_PROJECT（pipeline 会设）→ 当前目录（在专题目录下直接跑工具时）。工具本身在 skill 的 scripts/tools/，不在专题里
ROOT = Path(os.environ['KEPU_PROJECT']).resolve() if os.environ.get('KEPU_PROJECT') else (Path.cwd() if (Path.cwd() / 'design').is_dir() else Path(__file__).resolve().parent.parent)
ORIENT = 'land' if (os.environ.get('ORIENT') or 'port').lower() in ('land', 'landscape', 'h', '横屏') else 'port'
LAND = ORIENT == 'land'
def render_dir(root=ROOT):
    """产物目录：竖屏 render/，横屏 render/land/（timeline、mix、check、预演、母版、qa、overlay 全在这里）"""
    d = root / ('render/land' if LAND else 'render'); d.mkdir(parents=True, exist_ok=True); return d
def render_rel(name=''):
    """相对项目根的产物路径字符串（给 node 工具 / 日志用）：'render/x' 或 'render/land/x'"""
    base = 'render/land' if LAND else 'render'; return f'{base}/{name}' if name else base

def find_storyboard(root=ROOT):
    """$STORYBOARD → design/storyboard.json → design/storyboard_<目录名>.json → design/storyboard_*.json 唯一一个（排除 archive / 带版本号的旧档）"""
    if os.environ.get('STORYBOARD'): return (root / os.environ['STORYBOARD']).resolve()
    d = root / 'design'
    for cand in ('storyboard.json', f'storyboard_{root.name}.json'):
        if (d / cand).exists(): return d / cand
    import re
    all_ = sorted(f for f in d.glob('storyboard*.json') if not re.search(r'archive|_v\d', f.name)) if d.exists() else []
    if len(all_) == 1: return all_[0]
    raise SystemExit(f'design/ 里有多个 storyboard：{[f.name for f in all_]}，请用 STORYBOARD=design/xxx.json 指定' if all_ else f'找不到 storyboard（design/storyboard*.json）：{root}')

def load_sb(root=ROOT):
    f = find_storyboard(root)
    try: return json.loads(f.read_text())
    except json.JSONDecodeError as e:   # JSON 写坏了：说清第几行（完整提示见 tools/validate.py）
        ls = f.read_text().splitlines(); ctx = ls[e.lineno - 1].strip()[:120] if 0 < e.lineno <= len(ls) else ''
        raise SystemExit(f'{f.name} 不是合法的 JSON：第 {e.lineno} 行第 {e.colno} 列附近（{e.msg}）。这一行：{ctx}。常见原因：少逗号 / 多逗号 / 中文引号 / 括号没配对')
def save_sb(d, root=ROOT): find_storyboard(root).write_text(json.dumps(d, ensure_ascii=False, indent=1) + '\n')
# storyboard 里只作记录、不进画面 / 声音 / 口径的字段：确认 HARD 点时会顺手写（status、拍板记录、人耳确认名单），不该触发复审，也不该让流水线重跑。
# 其余字段一律算（scenes.js 能读 SB 的任何字段，宁可多复审）。audit.py 的哈希和 pipeline.py 各阶段的输入哈希共用这一份（10-26：aur_3d 交付后补人耳确认，tts 输入变了连锁重渲）
AUDIT_SKIP = ('status', 'status_text', 'design.status', 'design.decisions', 'tts.ear_confirmed', 'tts.ear_confirmed_why')
def sb_strip(d):
    d = json.loads(json.dumps(d))
    for k in AUDIT_SKIP:
        a, _, b = k.partition('.')
        if not b: d.pop(a, None)
        elif isinstance(d.get(a), dict): d[a].pop(b, None)
    return d
def credits_for(SB, orient=None):
    """本画幅显示的署名：条目可写 {text, orient: 'port'|'land'}，只在该画幅上屏（与 overlay.js OV.credits 同规则）"""
    o = orient or ('land' if LAND else 'port')
    return [cr for cr in (SB.get('credits') or []) if not (isinstance(cr, dict) and cr.get('orient')) or cr.get('orient') == o]
def layout_path(root=ROOT):
    """版式文件：$LAYOUT → 横屏 layout_land.json / 竖屏 layout.json（横屏缺 layout_land.json 时报错，不回退竖屏版式）"""
    if os.environ.get('LAYOUT'): return (root / os.environ['LAYOUT']).resolve()
    p = (root / ('layout_land.json' if LAND else 'layout.json')).resolve()
    if LAND and not p.exists(): raise SystemExit(f'横屏需要 {p.name}（从 skill 的 scripts/ 复制后按需改数值）')
    return p
def load_layout(root=ROOT):
    p = layout_path(root)
    return json.loads(p.read_text()) if p.exists() else {}
def load_tl(root=ROOT): return json.loads((render_dir(root) / 'timeline.json').read_text())
def asr_prompt(SB):
    """whisper 回读的 initial_prompt。只给领域提示，**不能写目标词**（写了会把读对的字硬改成提示词，bph 试音已证）。storyboard.tts.asr_prompt 可覆盖。"""
    return (SB.get('tts') or {}).get('asr_prompt') or '医学科普。'
def python_bin(root=ROOT):
    """跑各工具的 Python：$KEPU_PY → 当前解释器"""
    return os.environ.get('KEPU_PY') or sys.executable
def log(line, root=ROOT):
    f = render_dir(root) / 'pipeline.log'; f.parent.mkdir(parents=True, exist_ok=True)
    with f.open('a') as h: h.write(f'{datetime.datetime.now().isoformat(timespec="seconds")} {line}\n')
def emo_notes(SB):
    """情绪词 → 给配音模型的表演指令。模板给一套通用默认（bph + kidney_stone 的并集），storyboard.tts.emo_notes 可覆盖/增补。
    10-24 embarrassed 从“支支吾吾”改成“吐字清楚、不加呃嗯”：foam s03_2 照“支支吾吾”演，句首多出“呃 / 嗯”，judge 的语气词门判不过（foam 用 emo_notes 覆盖成“吐字清楚、不支吾”才过）。"""
    base = {'calm': '语气平稳亲切。', 'warm': '亲切、带着笑意。', 'explain': '耐心讲解，清楚明快。', 'firm': '语气认真、郑重。', 'intrigued': '带着悬念，设问的语气。',
            'lively': '轻快活泼，有感染力。', 'light': '轻松俏皮。', 'tense': '语气紧张，越说越重。', 'urgent': '严肃紧迫，郑重提醒，语速稍慢。',
            'annoyed': '又气又无奈，嗓门拔高。', 'sigh': '叹着气，有点认命，慢悠悠的。', 'cheerful': '开朗地打招呼，憨憨的。', 'pout': '委屈巴巴地嘟囔。',
            'embarrassed': '又尴尬又难为情，声音放低、带点不好意思，但吐字清楚，不要加“呃、嗯”。', 'worried': '担心、心里没底。', 'regret': '后悔不已，哼哼唧唧。', 'surprised': '吃了一惊。',
            'hot': '被烫得直跳脚，夸张搞笑地喊。', 'happy': '心情舒畅，乐呵呵的。', 'pain': '疼得龇牙咧嘴，大声喊出来，夸张搞笑。', 'cheeky': '得意地坏笑。',
            'shocked': '大吃一惊，难以置信地尖叫。', 'whine': '气急败坏又不甘心，夸张地喊。', 'arrogant': '傲慢、嚣张、得意洋洋。'}
    base.update((SB.get('tts') or {}).get('emo_notes') or {})
    return base

ANAT_WORDS = ('剖面', '解剖', '矢状', '冠状', '剖视')
def validate_storyboard(SB, layout=None):
    """S0 期可机器查的东西，返回警告列表（不阻断）：某场字卡 >8 张且未声明 max_labels；单张字卡 >14 字；解剖场没有 check_frames；危险信号未上字卡。"""
    w = []; layout = layout or {}
    maxlen = int(((layout.get('labels') or {}).get('max_text_chars') or 14))
    import re as _re
    for s in SB.get('scenes', []):
        labs = s.get('labels', [])
        mos = int((layout.get('labels') or {}).get('max_on_screen') or 0)
        if mos and (s.get('max_labels') or 0) > mos: w.append(f"{s['id']}：max_labels {s['max_labels']} > 同屏上限 max_on_screen {mos}，渲染按 {mos} 算")
        if len(labs) > 8 and not s.get('max_labels'): w.append(f"{s['id']}：字卡 {len(labs)} 张但未声明 max_labels（默认同屏 {int((layout.get('labels') or {}).get('max_default', 2))} 张轮换会很快；考虑 max_labels: 3/4 或拆场）")
        for lb in labs:
            n = len(_re.sub(r'\s', '', lb['text']))
            if n > maxlen: w.append(f"{s['id']}：字卡 {n} 字 > {maxlen}，渲染会缩字号：“{lb['text']}”")
        if (s.get('anatomy') or any(k in (s.get('visual') or '') for k in ANAT_WORDS)) and not s.get('check_frames'): w.append(f"{s['id']}：解剖场没有 check_frames（anatset.js 抽不到帧核对解剖）")
    no_topic = [s['id'] for s in SB.get('scenes', []) if not s.get('topic')]   # 横屏投稿版要点板板头用 scenes[].topic；torsion S3 才发现 S0 生成器没写（只在打算出投稿版——有 submit / references——时提示）
    if no_topic and (SB.get('submit') or SB.get('references')): w.append(f"{len(no_topic)} 场没有 topic（横屏投稿版要点板板头会空白）：{'、'.join(no_topic[:12])}")
    rf, mode = red_flag_check(SB)   # 与 qa.py 同一套判定（逐卡匹配，见 red_flag_check）
    miss = [f for f, r in rf.items() if not r['ok']]
    if miss: w.append('危险信号未上字卡：' + '、'.join(miss))
    for f, r in rf.items():
        for x in r['warn']: w.append(f'危险信号“{f}”：{x}')
    places = SB.get('places') or {}
    for s in SB.get('scenes', []):   # 场景定妆图：scenes[].place 必须在 places 里登记；用了 3D 人物片段的场最好声明 place
        pl = s.get('place')
        if pl and pl not in places: w.append(f"{s['id']}：place “{pl}” 没在 storyboard.places 里登记")
        elif not pl and places and any(m.get('pix') for m in s.get('media', [])): w.append(f"{s['id']}：有 3D 人物片段但没声明 place（姿势图拿不到场景定妆图当参考，房间会跨镜头漂移）")
    return w

# ---------- 危险信号上屏判定（qa.py 的门与 validate_storyboard 共用；10-24 起）----------
# 旧规则（10-16–10-23）：每条前 4 个汉字出现在“全部字卡拼成的一串字”里就算上屏——跨卡拼接也能凑上；卡上多插一个“或 / +”又对不上（psa 改急诊卡措辞只好连 red_flags 一起改）。
# 新规则：逐张卡比。危险信号去掉括号注释和连接词（或 / 伴 / 且…），取前 4 个字（汉字 / 数字 / 字母），在同一张卡里按顺序出现、整段跨度 ≤ 4 + 2 = 这张卡承载了它。
#   字卡写了 rf（危险信号下标，0 起；可写列表）就只认这些卡（显式关联最可靠）：关联卡头 4 字对不上时，卡上字有一半以上出自这条危险信号也算。
#   顺带查转写走样（只警告，foam S0 审稿的头号问题）：卡上“A+B / A且B / A伴B”而原文 A、B 之间是“或”；卡上“A或B”而原文是“伴 / 且”；卡上的数字不在原文里。
# 模式 storyboard.qa.red_flags_match：compat（缺省）= 新规则不过、旧规则过 → 只警告（已过门的旧专题不翻成失败）；strict = 只认新规则（模板骨架默认）；legacy = 只用旧规则。
import re as _re2, difflib as _dl
def rf_core(s): return _re2.sub(r'[^一-鿿0-9A-Za-z]', '', _re2.sub(r'（[^）]*）|\([^)]*\)', '', s or ''))
def rf_key(s): return _re2.sub('[或伴且和及与并]', '', rf_core(s))   # 比“头 4 个字”时去掉连接词：卡上多一个或少一个“或 / 伴”都不影响认卡，走样另由 _rf_warn 报
def _rf_find(head, s, slack=2):
    """head 的字按顺序出现在 s 里、整段跨度 ≤ len(head) + slack → True"""
    for st in range(len(s)):
        if s[st] != head[0]: continue
        j, k = st, 0
        while j < len(s) and k < len(head) and j - st < len(head) + slack:
            if s[j] == head[k]: k += 1
            j += 1
        if k == len(head): return True
    return False
def _rf_share(a, b):
    """b 里有多少比例的字按顺序出自 a（最长公共子序列近似）"""
    if not b: return 0.0
    return sum(m.size for m in _dl.SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks()) / len(b)
def _rf_warn(flag, card):
    c = rf_core(flag); w = []
    toks = _re2.split(r'(\+|＋|或|且|伴)', _re2.sub(r'\s', '', _re2.split(r'→|：|:', card)[0]))   # 只看卡的描述段（“→急诊”“：尽快就医”之前）
    for k in range(1, len(toks) - 1, 2):
        A, B, conn = rf_core(toks[k - 1].split('、')[-1]), rf_core(toks[k + 1].split('、')[0]), toks[k]
        if len(A) < 2 or len(B) < 2: continue
        ia = c.find(A); ib = c.find(B, ia + len(A)) if ia >= 0 else -1
        if ia < 0 or ib < 0: continue
        between = c[ia + len(A):ib]
        if conn in '+＋且伴' and '或' in between and not _re2.search('[伴且和并]', between): w.append(f'卡上写“{A}{conn}{B}”，原文两者之间是“或”（“或”写成了“且”？）')
        if conn == '或' and '或' not in between and _re2.search('[伴且和并]', between): w.append(f'卡上写“{A}或{B}”，原文两者之间是“{between}”（“且 / 伴”写成了“或”？）')
    nf = _re2.findall(r'\d+(?:\.\d+)?', flag); bad = [n for n in _re2.findall(r'\d+(?:\.\d+)?', card) if n not in nf]
    if bad: w.append(f'卡上的数字 {bad} 不在危险信号原文里')
    return w
def red_flag_check(SB, mode=None):
    """→ ({危险信号: {ok, how, scene, card, alert, share, legacy_ok, warn: [...]}}, 模式)。how：rf 显式关联 / 逐卡 / 旧规则（compat 兜底）/ 未找到"""
    mode = (mode or ((SB.get('qa') or {}).get('red_flags_match')) or 'compat').lower()
    labs = [(s['id'], lb) for s in SB.get('scenes', []) for lb in s.get('labels', [])]
    han = lambda s: _re2.sub(r'[^一-鿿]', '', s); on = han(' '.join(lb['text'] for _, lb in labs)); out = {}
    for i, f in enumerate(SB.get('red_flags', [])):
        c = rf_core(f); head = rf_key(f)[:4]; legacy = bool(han(f)[:4]) and han(f)[:4] in on
        rfs = lambda lb: ([lb['rf']] if isinstance(lb.get('rf'), int) else list(lb.get('rf') or []))
        linked = [(sid, lb) for sid, lb in labs if i in rfs(lb)]
        hits = [(sid, lb) for sid, lb in (linked or labs) if head and (_rf_find(head, rf_key(lb['text'])) or (linked and _rf_share(c, rf_core(lb['text'])) >= 0.5))]
        best = max(hits, key=lambda h: (bool(h[1].get('alert')), _rf_share(c, rf_core(h[1]['text'])))) if hits else None
        new_ok = bool(best); warn = _rf_warn(f, best[1]['text']) if best else []
        if mode == 'legacy': ok = legacy
        elif mode == 'strict': ok = new_ok
        else:
            ok = new_ok or legacy
            if legacy and not new_ok: warn.append('旧规则（前 4 个汉字、全部字卡拼起来找）找得到，逐卡找不到：给承载它的卡写 rf（危险信号下标），或改卡措辞；strict 模式下判失败')
        if linked and not new_ok: warn.append(f"写了 rf 的卡（{'、'.join(s + '“' + lb['text'] + '”' for s, lb in linked)}）对不上这条危险信号")
        out[f] = {'ok': ok, 'how': ('rf 显式关联' if linked else '逐卡') if new_ok else ('旧规则' if ok else '未找到'), 'scene': best[0] if best else None, 'card': best[1]['text'] if best else None,
                  'alert': bool(best[1].get('alert')) if best else None, 'share': round(_rf_share(c, rf_core(best[1]['text'])), 2) if best else None, 'legacy_ok': legacy, 'warn': warn}
    return out, mode

def card_stays(labels, scene_len, maxN, big_takes_slot=True):
    """按叠字层 OV.labels 同一套格位规则算每张字卡的在屏时长。labels: [{t, text, big?, alert?}]（场内秒）；scene_len 场长；maxN 同屏格数（已含 max_on_screen 上限）。
    规则（竖屏标签卡，big_takes_slot=True）：big 常驻第 0 格（后一张 big 替换前一张）；普通卡占其余 cap = maxN − (有 big ? 1 : 0) 格，满了再进一张就挤掉最老的；big 第一次出现时若普通卡占满 maxN 格也挤掉最老的一张。
    横屏要点板（big_takes_slot=False）：big 是板头、不占条目格，普通卡占满 maxN 格后再进一张挤掉最老的。
    返回 [{text, t, big, alert, stay, reason}]，reason ∈ squeezed（被后来的卡挤走）/ squeezed_by_big / replaced（big 被后一张 big 换掉）/ scene_end。"""
    labs = sorted(labels, key=lambda l: l['t']); bigs = [l for l in labs if l.get('big')]; out = []
    for i, b in enumerate(bigs):
        end = bigs[i + 1]['t'] if i + 1 < len(bigs) else scene_len
        out.append({'text': b['text'], 't': b['t'], 'big': True, 'alert': bool(b.get('alert')), 'stay': round(end - b['t'], 3), 'reason': 'replaced' if i + 1 < len(bigs) else 'scene_end'})
    events = sorted([(l['t'], 0 if l.get('big') else 1, l) for l in labs], key=lambda e: (e[0], e[1]))   # 同一时刻 big 先于普通卡
    on, big_seen = [], False
    for t, kind, l in events:
        if kind == 0:
            if not big_seen:
                big_seen = True
                if big_takes_slot:
                    while len(on) > maxN - 1: old = on.pop(0); out.append({'text': old['text'], 't': old['t'], 'big': False, 'alert': bool(old.get('alert')), 'stay': round(t - old['t'], 3), 'reason': 'squeezed_by_big'})
            continue
        cap = maxN - (1 if big_seen and big_takes_slot else 0)
        while len(on) >= cap and on: old = on.pop(0); out.append({'text': old['text'], 't': old['t'], 'big': False, 'alert': bool(old.get('alert')), 'stay': round(t - old['t'], 3), 'reason': 'squeezed'})
        on.append(l)
    for l in on: out.append({'text': l['text'], 't': l['t'], 'big': False, 'alert': bool(l.get('alert')), 'stay': round(scene_len - l['t'], 3), 'reason': 'scene_end'})
    return sorted(out, key=lambda r: r['t'])

def overlay_texts(SB, layout=None, TL=None, where=False):
    """所有会上屏的文字，按字体角色归类：[(role, text)]（where=True 时 [(role, text, 位置)]）。
    role ∈ sub（字幕块、名牌）/ label（章节名、普通字卡、免责声明、AI 说明、AI 标识、封面小字）/ title（片名、口号、big 卡、本场主题、封面片名、文献页标题）/ ref（参考文献、署名、片尾短清单）。
    与叠字层画法一致：big 卡 / 要点板板头把“·”换成“•”再画；箭头“→”是线条画的，不算字。给 check_fonts.py（字形覆盖）和 qa.py（禁用字串）用。"""
    layout = layout or {}; out = []
    add = lambda role, text, loc: out.append((role, text, loc)) if text else None
    for c in SB.get('chapters', []): add('label', c.get('node', ''), f"章节 {c.get('id', '')}")
    tc = SB.get('title_card') or {}; add('title', tc.get('main') or '', '片名'); add('title', tc.get('sub') or '', '副标题'); add('title', SB.get('title') or '', 'title')
    for s in SB.get('scenes', []):
        sid = s['id']; add('title', s.get('topic') or '', f'{sid} 主题')
        for k, lb in enumerate(s.get('labels', [])):
            t = lb.get('text', '')
            if lb.get('big'): add('title', t.replace('·', '•'), f'{sid} big 字卡 {k}')
            else: add('label', t, f'{sid} 字卡 {k}')
        for i, ln in enumerate(s.get('lines', [])): add('sub', ln.get('text', ''), f'{sid} 台词 {i}')
    if TL:
        for s in TL.get('scenes', []):
            for ln in s.get('lines', []):
                for k, ch in enumerate(ln.get('chunks', [])): add('sub', ch.get('text', ''), f"{s['id']} 字幕块 {ln.get('i')}.{k}")
    for who, ch in (SB.get('characters') or {}).items(): add('sub', ch.get('name') or who, f'名牌 {who}')
    ou = SB.get('outro') or {}
    add('title', ou.get('slogan') or '', '片尾 口号'); add('label', ou.get('ai_note') or '', '片尾 AI 说明'); add('label', SB.get('disclaimer') or '', '片尾 免责声明')
    for i, r in enumerate(ou.get('references') or []): add('ref', r, f'片尾 参考 {i}')
    for i, r in enumerate(SB.get('references') or [], 1): add('ref', r, f'文献 [{i}]')
    for i, cr in enumerate(credits_for(SB)): add('ref', cr if isinstance(cr, str) else cr.get('text', ''), f'署名 {i}')
    cv = SB.get('cover') or {}
    for i, t in enumerate(cv.get('title_lines') or []): add('title', t, f'封面 片名 {i}')
    add('sub', cv.get('hook') or '', '封面 痛点句'); add('label', cv.get('tagline') or '', '封面 小字')
    add('label', ((layout.get('ai_mark') or {}).get('text')) or '', 'AI 标识')
    add('title', '参考文献（0123456789/）', '文献页标题')
    return out if where else [(r, t) for r, t, _ in out]

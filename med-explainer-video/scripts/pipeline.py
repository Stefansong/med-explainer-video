#!/usr/bin/env python3
"""医学科普动画短片流水线（med-explainer-video）统一入口。Windows / macOS 通用，不需要服务器，配音由用户自己录。

  python pipeline.py setup [--check]                                        检查 / 安装运行环境（Python 包、Node 包、ffmpeg、浏览器、字体）
  python pipeline.py new <project> [--title "片名"] [--dir 工作目录]          新专题：在工作目录（默认当前目录）下建 <project>/
  python pipeline.py new <project> --example                                 建一份样例专题（45 秒，素材和代码齐全）；接着 timeline --estimate → animatic 就能看到预演
  python pipeline.py new <project> … --theme mint|indigo|amber              建专题时选配色（默认 mint 薄荷）；之后想换：python pipeline.py theme <project> <主题名>
  python pipeline.py run <project> [--until s6a|render|qa|deliver] [--force]  从头跑到 --until（默认 qa）；碰到未确认的 HARD 点停下（退出码 3）、缺录音停下（退出码 6）
  python pipeline.py <stage> <project> [--force] [阶段参数]                    单跑一个阶段：s0 s3 voice timeline mix frames animatic audit_pre render qa audit_post deliver
  python pipeline.py check <project>                                        只检查不渲染（1–2 秒）：分镜和场景代码哪里写错了、怎么改。改完任何东西先跑它
  python pipeline.py <任何命令> … --bg                                       放后台跑，立刻返回（预演、渲染、导入录音这类要跑几分钟以上的都加）
  python pipeline.py wait <project> [--timeout=90]                          等后台任务：最多等 90 秒，打印进度；退出码 7 = 还在跑（再 wait），否则是任务自己的退出码
  python pipeline.py status <project>                                       各阶段状态 + 两道审核关卡 + 后台任务
  python pipeline.py clean <project> [--apply]                              交付后清理：每类只留最新 2 版，其余移进回收站 / 废纸篓（不加 --apply 只列清单）
  --orient land（或环境变量 ORIENT=land）：横屏版，版式 layout_land.json，产物全在 render/land/。

阶段与产物（输入哈希变了才重跑；产物在、哈希没变就跳过；失败的从失败处重跑）：
  s0         gen_doc.py → design/{project}_修订稿_v{ver}.md + .docx                      【HARD S0】status.s0.confirmed
  s3         核对角色 3D 定妆图 / 场景定妆图 / 素材登记、谁来配哪个角色              【HARD S3】status.s3.confirmed
  voice      voice.py script → audio/台词本.md / .docx（录音用）；用户录好放进 audio/recordings/ → voice.py import：
             转码、降噪、去首尾静音、响度 −16 LUFS → whisper 回读核对台词 → 逐字时刻 → audio/lines/{scene}_{i}.wav + lines.json
             录音不齐就停下，退出码 6（等用户录音）。voice --draft：没录音的句子先用合成声顶上，只够出预演（审核和正式版会拦）
  timeline   timeline.py → render/timeline.json（--estimate：没录音先按字数估时长调画面）
  mix        mix.py → render/mix.wav（程序化配乐 + 音效 + 人声闪避）
  frames     checkset.js + anatset.js → frames.js → sheet.py → render/check/、render/check_sheet.png（叠字层自检硬错、画面代码出错、某场是空画面 → 失败）
  animatic   render.js preview_vN（低帧率、无运动模糊）+ 联系表 + qa --no-asr
  audit_pre  渲染前审核关卡：tools/audit.py pack pre 打包材料 → 要有 design/audit_pre_v{n}.md 且 result pass、哈希一致，否则退出码 5 等审核
             （审核员 = 另开一个对话 / 子代理，提示词 references/audit_pre_prompt.md）；通过后才到【HARD S6a】status.s6a.confirmed
  render     render.js final + 封面。画质：standard（默认，30 帧 + 2 子帧运动模糊）/ --quality=high（60 帧 + 4 子帧，实测慢约 1.6 倍）。门：audit_pre pass 且哈希一致（S6a 后改过东西 → audit.py diff，只复审差异）
  qa         qa.py final --gate → render/{project}_final.qa.json，不通过退出码 2
  audit_post 成片审核关卡：audit.py pack post → render/audit_post_{tag}.md pass 且成片哈希一致，否则退出码 5
  deliver    交付检查：audit_post pass + QA pass → render/deliver_{tag}.json 清单（文件、大小、sha1）
退出码：0 完成；2 阶段失败 / QA 不通过 / check 有错误；3 停在 HARD 点等用户；4 参数错；5 等审核；6 等用户录音；7 后台任务还在跑（wait）。
两道审核门只看报告文件和哈希，不替用户确认任何 HARD 点。
"""
import sys, os, subprocess
# Windows 中文系统默认 GBK：整条流水线（含子进程）一律 UTF-8 模式，免得读写中文 JSON 报错
if not sys.flags.utf8_mode:
    os.environ['PYTHONUTF8'] = '1'
    sys.exit(subprocess.call([sys.executable, '-X', 'utf8', *sys.argv]))
import json, re, time, hashlib, shutil, importlib.util, datetime
from pathlib import Path
HERE = Path(__file__).resolve().parent          # skill 的 scripts/ 目录：tools/ src/ layout*.json 都从这里取
TOOLS = HERE / 'tools'

def _boot_env():
    """setup 写的 bin/env.json（ffmpeg / 浏览器路径、HuggingFace 镜像）→ 环境变量；bin/ 放进 PATH；node_modules 放进 NODE_PATH"""
    os.environ['PYTHONUTF8'] = '1'
    binp = HERE / 'bin'
    os.environ['PATH'] = str(binp) + os.pathsep + os.environ.get('PATH', '')
    nm = HERE / 'node_modules'
    if nm.is_dir(): os.environ['NODE_PATH'] = os.pathsep.join([str(nm)] + ([os.environ['NODE_PATH']] if os.environ.get('NODE_PATH') else []))
    envf = binp / 'env.json'
    if envf.exists():
        try: cfg = json.loads(envf.read_text(encoding='utf-8'))
        except ValueError: cfg = {}
        for k in ('CHROME_PATH', 'HF_ENDPOINT', 'KEPU_ASR_MODEL'):
            if cfg.get(k) and not os.environ.get(k): os.environ[k] = str(cfg[k])
        if cfg.get('NODE') and Path(cfg['NODE']).exists(): os.environ['PATH'] = str(Path(cfg['NODE']).parent) + os.pathsep + os.environ['PATH']   # setup 找到的 node 不在 PATH 上时
_boot_env()

STAGES = ['s0', 's3', 'voice', 'timeline', 'mix', 'frames', 'animatic', 'audit_pre', 'render', 'qa', 'audit_post', 'deliver']
HARD_AFTER = {'s0': 's0', 's3': 's3', 'audit_pre': 's6a'}   # 阶段跑完后要过的 HARD 点（S6a 放在渲染前审核之后：用户看到的是审核员改过的版本）
HARD_BEFORE = {'render': 's6a', 'deliver': 's6a'}           # 单跑这些阶段前也要过的 HARD 点
class AuditPending(Exception): pass    # 审核关卡没过 → 退出码 5
class WaitRecording(Exception): pass   # 录音不齐 → 退出码 6
HARD_WHAT = {'s0': '口径表 + 节拍表（design/{doc}）：逐条口径与出处、危险信号是否齐全、每场节拍与画面设计。确认后把 storyboard.status.s0 改成 {"confirmed": true, "by": "...", "date": "YYYY-MM-DD", "note": "原话"}',
             's3': '角色 3D 定妆图（assets/lib/characters/）与场景定妆图（assets/lib/scenes/）、样帧风格、每个角色由谁来配音。选定后写各自 APPROVED.md，再把 storyboard.status.s3 改成 {"confirmed": true, ...}；定稿图永不覆盖，改动升版本',
             's6a': '动画预演（render/{project}_preview_vN.mp4 + 联系表 _sheet.png；已过渲染前审核 design/audit_pre_v*.md）：节奏、画面、解剖、口径上屏、字幕，以及审核员交给你的口径类问题。确认后把 storyboard.status.s6a 改成 {"confirmed": true, ...} 再跑 render'}

# ---------------- 工具 ----------------
def die(msg, code=4): print('!!', msg, file=sys.stderr); sys.exit(code)
def now(): return datetime.datetime.now().isoformat(timespec='seconds')
def sha(parts):
    h = hashlib.sha1()
    for p in parts: h.update(p if isinstance(p, bytes) else str(p).encode()); h.update(b'\0')
    return h.hexdigest()[:16]
def fbytes(p): p = Path(p); return p.read_bytes() if p.exists() else b'<missing>'
def fsha(p):
    p = Path(p)
    if not p.exists(): return b'<missing>'
    h = hashlib.sha1()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
    return h.hexdigest().encode()
def jdump(o): return json.dumps(o, ensure_ascii=False, sort_keys=True).encode()
def default_workers(): return max(2, min(8, (os.cpu_count() or 4) // 2))   # 每个渲染页面是一个无头浏览器：普通笔记本别开太多

def tool_mod(name):
    spec = importlib.util.spec_from_file_location(name, TOOLS / f'{name}.py'); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
def check_sb(P, warn=True):
    """分镜校验（tools/validate.py）：错误逐条打印并中止；提醒只打印"""
    E, W, _ = tool_mod('validate').check(P.root)
    for e in E: print('  ✗', e)
    if warn:
        for w in W: print('  !', w)
    if E: raise RuntimeError(f'分镜（{P.sb_path.name}）有 {len(E)} 个错误，上面每条都写了在哪、怎么改；改完再跑')
    return W
def lint_scenes(P):
    """场景代码检查（tools/lint_scenes.js，不渲染）：语法、不存在的函数、没登记的图、没声明的 cue、随机数"""
    r = subprocess.run(['node', str(P.tools / 'lint_scenes.js')], cwd=P.root, env=P.env(), capture_output=True, text=True, encoding='utf-8', errors='replace')
    out = (r.stdout or '') + (r.stderr or '')
    for ln in out.strip().splitlines(): print('  ' + ln)
    if r.returncode: raise RuntimeError('场景代码（src/scenes.js）有错误，上面每条都写了第几行、怎么改；改完再跑')

class Project:
    def __init__(self, path, orient=None):
        self.root = Path(path).resolve()
        if not (self.root / 'design').is_dir(): die(f'{self.root} 不是专题目录（没有 design/）；新建用 pipeline.py new <project>')
        self.tools = TOOLS
        os.environ['ORIENT'] = orient or os.environ.get('ORIENT') or 'port'   # _common 在 import 时读 ORIENT
        os.environ['KEPU_PROJECT'] = str(self.root)
        spec = importlib.util.spec_from_file_location('_common', self.tools / '_common.py'); C = importlib.util.module_from_spec(spec); spec.loader.exec_module(C); self.C = C
        self.orient, self.land = C.ORIENT, C.LAND; os.environ['ORIENT'] = self.orient
        self.sb_path = C.find_storyboard(self.root); self.py = sys.executable
        self.rdir = C.render_dir(self.root); self.rrel = C.render_rel
        self.status_file = self.rdir / 'stage_status.json'
        self.status = json.loads(self.status_file.read_text()) if self.status_file.exists() else {}
    @property
    def SB(self):
        try: return json.loads(self.sb_path.read_text())
        except json.JSONDecodeError:
            _, err = tool_mod('validate').load_json_friendly(self.sb_path); die(err, 2)
    @property
    def layout_file(self): return self.C.layout_path(self.root)
    @property
    def layout(self): return self.C.load_layout(self.root)
    @property
    def project(self): return self.SB['project']
    @property
    def final_tag(self): return 'master' if self.land else 'final'
    def env(self):
        e = dict(os.environ); e['KEPU_PROJECT'] = str(self.root); e['STORYBOARD'] = str(self.sb_path.relative_to(self.root)); e['ORIENT'] = self.orient; return e
    def log(self, line):
        with (self.rdir / 'pipeline.log').open('a') as h: h.write(f'{now()} {line}\n')
    def save_status(self): self.status_file.write_text(json.dumps(self.status, ensure_ascii=False, indent=1))
    def sh(self, cmd, env_extra=None, capture=False):
        env = self.env(); env.update(env_extra or {}); self.log('  $ ' + ' '.join(map(str, cmd)) + (' ' + ' '.join(f'{k}={v}' for k, v in (env_extra or {}).items()) if env_extra else ''))
        r = subprocess.run([str(c) for c in cmd], cwd=self.root, env=env, text=True, capture_output=capture)
        if r.returncode: raise RuntimeError(f'命令失败（退出码 {r.returncode}）：{" ".join(map(str, cmd))}' + (('\n' + (r.stderr or '')[-800:]) if capture else ''))
        return r
    def node(self, script, *args, env_extra=None, capture=False): return self.sh(['node', self.tools / script, *args], env_extra, capture)
    def pyt(self, script, *args, env_extra=None, capture=False): return self.sh([self.py, '-X', 'utf8', '-W', 'ignore', self.tools / script, *args], env_extra, capture)
    # ---- HARD 点 ----
    def confirmed(self, key):
        st = self.SB.get('status')
        return bool(((st or {}).get(key) or {}).get('confirmed')) if isinstance(st, dict) else False
    def hard_stop(self, key):
        SB = self.SB; doc = f"{SB.get('doc_name') or SB['project'] + '_修订稿'}_v{SB.get('version')}.md"
        msg = f"HARD {key.upper()} 未确认，停下等用户确认：" + HARD_WHAT[key].replace('{doc}', doc).replace('{project}', SB['project'])
        print('\n■', msg); self.log(f'WAIT {key}'); return 3
    # ---- 审核关卡 / 资源锁 ----
    def audit_check(self, kind, tag=None):
        """tools/audit.py check pre|post → (通过?, 原因)"""
        r = subprocess.run([sys.executable, '-X', 'utf8', '-W', 'ignore', self.tools / 'audit.py', 'check', kind, *(['--tag', tag] if tag else [])], cwd=self.root, env=self.env(), text=True, capture_output=True)
        out = (r.stdout + r.stderr).strip().splitlines(); msg = (out[-1] if out else '').lstrip('✓✗ ')
        return r.returncode == 0, msg
    def audit(self, *args): self.sh([sys.executable, '-X', 'utf8', '-W', 'ignore', self.tools / 'audit.py', *args])
    def lock(self, pool, stage):
        """同一台电脑上同时做几集时排队：渲染同时只跑 1 个、抽帧最多 2 个（tools/locks.py，跨平台文件锁）"""
        spec = importlib.util.spec_from_file_location('locks', self.tools / 'locks.py'); L = importlib.util.module_from_spec(spec); spec.loader.exec_module(L)
        return L.Slot(pool, self.project, stage)

# ---------------- 阶段定义：inputs() 决定是否要重跑；outputs() 必须存在；run() 做事 ----------------
def sb_sub(SB, keys): return jdump({k: SB.get(k) for k in keys})
def lines_sig(SB): return jdump([[s['id'], i, l['who'], l['text'], l.get('say'), l.get('emo'), l.get('tts_note'), l.get('hold')] for s in SB['scenes'] for i, l in enumerate(s['lines'])])
def scenes_sig(SB): return jdump([[s['id'], s.get('lead'), s.get('tail'), s.get('max_labels'), s.get('labels'), s.get('cues'), [[l['who'], l['text'], l.get('br'), l.get('hold')] for l in s['lines']]] for s in SB['scenes']])
RENDER_SB_KEYS = ['disclaimer', 'title_card', 'outro', 'credits', 'characters', 'chapters', 'references', 'references_pages', 'references_page_seconds', 'outro_media', 'intro_media', 'style', 'assets', 'scenes']
def src_sig(P): return [fbytes(f) for f in sorted((P.root / 'src').glob('*.js'))] + [fbytes(P.root / 'src/player.html'), fbytes(P.tools / '_common.js'), sb_sub(P.SB, RENDER_SB_KEYS)]
def tool_sig(P, *names): return [fbytes(P.tools / n) for n in names] + [fbytes(P.tools / '_common.py')]
def rec_sig(P):   # 录音文件夹：文件名 + 大小 + 修改时间（换了录音就重新导入）
    return jdump([[d, f.name, f.stat().st_size, int(f.stat().st_mtime)] for d in ('recordings', 'draft') if (P.root / 'audio' / d).is_dir() for f in sorted((P.root / 'audio' / d).iterdir()) if f.is_file() and f.suffix != '.json'])
def draft_lines(P):   # 现在的配音里哪些句子是草稿配音（合成声）
    lj = P.root / 'audio/lines/lines.json'
    return [f"{r['scene']}_{r['i']}" for r in json.loads(lj.read_text()) if r.get('engine') == 'draft'] if lj.exists() else []
def check_assets(P):   # 渲染是严格模式：storyboard.assets 登记的文件缺一个就整段失败，先在这里说清楚缺哪个
    lost = [f"{k} → {v['src'] if isinstance(v, dict) else v}" for k, v in (P.SB.get('assets') or {}).items()
            if not k.startswith('_') and isinstance(v, (str, dict)) and not (P.root / (v['src'] if isinstance(v, dict) else v)).exists()]
    if lost: raise RuntimeError('storyboard.assets 登记了但文件不在（补上文件，或从 assets 里删掉这条、场景代码里别再用）：' + '；'.join(lost))
def latest_preview(P):
    ms = sorted(P.rdir.glob(f'{P.project}_preview_v*.mp4'), key=lambda f: int(re.search(r'_v(\d+)\.mp4$', f.name).group(1)))
    return int(re.search(r'_v(\d+)\.mp4$', ms[-1].name).group(1)) if ms else 0

class Stage:
    name = ''; hard = None
    def __init__(self, P, args): self.P, self.args = P, args
    def inputs(self): return []
    def outputs(self): return []
    def run(self): pass

class S0(Stage):
    name = 's0'
    def inputs(self): SB = self.P.SB; return [sb_sub(SB, ['title', 'version', 'characters', 'claims', 'red_flags', 'red_flags_action', 'sources', 'chapters', 'anatomy_checks', 'est']), scenes_sig(SB), fbytes(self.P.tools / 'gen_doc.py')] + [fbytes(f) for f in sorted((self.P.root / 'design').glob('s0_summary_v*.md')) + sorted((self.P.root / 'design').glob('review_head_v*.md'))]
    def outputs(self): SB = self.P.SB; return [self.P.root / 'design' / f"{SB.get('doc_name') or SB['project'] + '_修订稿'}_v{SB['version']}.md"]
    def run(self):
        check_sb(self.P)
        self.P.pyt('gen_doc.py')

class S3(Stage):
    """角色 / 场景定妆与配音分工（S3 的出图由 AI 在对话里用平台生图工具做，这里只核对登记）"""
    name = 's3'
    def inputs(self): SB = self.P.C.sb_strip(self.P.SB); return [sb_sub(SB, ['characters', 'places', 'voices', 'assets'])]
    def run(self):
        SB = self.P.SB; R = self.P.root
        for who, ch in (SB.get('characters') or {}).items():
            if who == 'narrator': continue
            art = ch.get('art3d') or ch.get('art')
            print(f"  角色 {ch.get('name', who)}：定妆图 " + (f'{art}' if art and (R / art).exists() else '缺（S3 用平台生图出全身 3D 定妆图，存 assets/lib/characters/<who>/，登记 characters[who].art3d）'))
        places = SB.get('places') or {}; used = sorted({s.get('place') for s in SB['scenes'] if s.get('place')})
        if used:
            miss = [pl for pl in used if not (places.get(pl) or {}).get('art') or not (R / places[pl]['art']).exists()]
            print(f"  场景定妆图：{len(used) - len(miss)}/{len(used)} 个已定稿" + (f"；缺 {miss}（出空场景图 → 选定 → places[place].art 登记）" if miss else ''))
        assets = SB.get('assets') or {}
        lost = [k for k, v in assets.items() if not k.startswith('_') and isinstance(v, (str, dict)) and not (R / (v if isinstance(v, str) else v.get('src', ''))).exists()]
        if lost: print(f'  !! storyboard.assets 登记了但文件不在：{lost}')
        for who, v in (SB.get('voices') or {}).items():
            if who.startswith('_'): continue
            print(f"  配音 {who}：{(v or {}).get('actor') or '（未定谁来配）'}  {(v or {}).get('desc', '')}")

class Voice(Stage):
    """用户自己配音：台词本 → 用户录音放进 audio/recordings/ → 导入、处理、回读核对 → audio/lines/lines.json（timeline 直接用）"""
    name = 'voice'
    def inputs(self): SB = self.P.C.sb_strip(self.P.SB); return [lines_sig(SB), sb_sub(SB, ['voices', 'tts']), rec_sig(self.P), *tool_sig(self.P, 'voice.py', 'asr.py', 'align.py'), jdump(self.redo())]
    def redo(self): return [a for a in self.args if a in ('--reimport', '--draft') or re.match(r's\d+_\d+$', a)]   # 指定重做：不管哈希都重跑（导入缓存只重做这些句子）
    def outputs(self): return [self.P.root / 'audio/lines/lines.json']
    def run(self):
        self.P.pyt('voice.py', 'script')
        if '--draft' in self.args:   # 草稿配音：没录音的句子先用合成声（只用于预演）
            r = subprocess.run([self.P.py, '-X', 'utf8', '-W', 'ignore', self.P.tools / 'voice.py', 'draft'], cwd=self.P.root, env=self.P.env())
            if r.returncode: raise RuntimeError('草稿配音没出成（看上面的原因）；也可以不用草稿，直接照台词本录音')
        extra = [a for a in self.args if re.match(r's\d+_\d+$', a) or a in ('--reimport',)]
        r = subprocess.run([self.P.py, '-X', 'utf8', '-W', 'ignore', self.P.tools / 'voice.py', 'import', *extra], cwd=self.P.root, env=self.P.env())
        if r.returncode == 6: raise WaitRecording('录音还没齐：照 audio/台词本.md 录好，文件放进 audio/recordings/ 再跑 pipeline.py voice（想先看预演的节奏：pipeline.py voice --draft 用合成声顶上，要联网、要装 edge-tts）')
        if r.returncode: raise RuntimeError(f'录音导入失败（退出码 {r.returncode}）')
        rows = json.loads((self.P.root / 'audio/lines/lines.json').read_text()); ear = set((self.P.SB.get('tts') or {}).get('ear_confirmed') or [])
        bad = [f"{r['scene']}_{r['i']}" for r in rows if r.get('passed') is False and f"{r['scene']}_{r['i']}" not in ear]
        if bad: print('  !! 回读和台词对不上、需要人耳确认或重录的句子：', bad, '（听过没问题就写进 storyboard.tts.ear_confirmed；否则重录这几句再跑 voice）')
        else: print('  录音全部过回读核对（或已人耳确认）')

class Timeline(Stage):
    name = 'timeline'
    def est(self): return '--estimate' in self.args
    def inputs(self): SB = self.P.SB; return [scenes_sig(SB), sb_sub(SB, ['timing', 'subtitle_numbers', 'cover', 'chapters', 'fps', 'width', 'height', 'references', 'references_pages', 'references_page_seconds']), fbytes(self.P.root / 'audio/lines/lines.json') if not self.est() else b'estimate', fbytes(self.P.layout_file), self.P.orient.encode(), *tool_sig(self.P, 'timeline.py')]
    def outputs(self): return [self.P.rdir / 'timeline.json']
    def run(self):
        if not self.est() and not (self.P.root / 'audio/lines/lines.json').exists(): raise RuntimeError('没有 audio/lines/lines.json：先导入录音（pipeline.py voice），或 timeline --estimate 先调画面')
        check_sb(self.P, warn=False)
        self.P.pyt('timeline.py', *(['--estimate'] if self.est() else []))
        tl = json.loads((self.P.rdir / 'timeline.json').read_text()); tgt = self.P.SB.get('target_seconds')
        if tgt and tl['duration'] > tgt * 1.15: print(f"  !! 片长 {tl['duration']:.0f} 秒，超过目标 {tgt} 秒（storyboard.target_seconds）：删减台词，或跟用户确认后改目标")

class Mix(Stage):
    name = 'mix'
    def inputs(self): return [fbytes(self.P.rdir / 'timeline.json'), fbytes(self.P.root / 'audio/lines/lines.json'), jdump(self.P.SB.get('audio')), *tool_sig(self.P, 'mix.py', 'sfx.py')]
    def outputs(self): return [self.P.rdir / 'mix.wav']
    def run(self): self.P.pyt('mix.py')

class Frames(Stage):
    name = 'frames'
    def inputs(self): return [fbytes(self.P.rdir / 'timeline.json'), fbytes(self.P.layout_file), jdump([s.get('check_frames') for s in self.P.SB['scenes']])] + src_sig(self.P) + [fbytes(self.P.tools / f) for f in ('frames.js', 'checkset.js', 'anatset.js', 'sheet.py', 'emptyscan.py')] + [jdump([s.get('allow_empty') for s in self.P.SB['scenes']])]
    def outputs(self): return [self.P.rdir / 'check_sheet.png', self.P.rdir / 'check/overlay_check.json']
    def run(self):
        lint_scenes(self.P); check_assets(self.P)
        R = self.P.rdir; rr = self.P.rrel; (R / 'check').mkdir(exist_ok=True)
        for f in (R / 'check').glob('*.png'): f.unlink()
        lst = self.P.node('checkset.js', capture=True).stdout; (R / 'check/list.txt').write_text(lst)
        with self.P.lock('frames', 'frames 抽帧'):
            try: self.P.node('frames.js', rr('check'), '--list', rr('check/list.txt'))
            except RuntimeError: raise RuntimeError('画面代码运行时出错（上面列出了哪一场、什么错、第几行）；改完再跑 frames')
            self.P.pyt('sheet.py', rr('check'), rr('check_sheet.png'), '6')
            r = subprocess.run([self.P.py, '-X', 'utf8', self.P.tools / 'emptyscan.py', rr('check')], cwd=self.P.root, env=self.P.env())   # 有的场是不是空的
            if r.returncode: raise RuntimeError('有的场画面是空的（上面列出了是哪一场）；改完再跑 frames。联系表 ' + rr('check_sheet.png') + ' 可以对照着看')
            if any(s.get('check_frames') for s in self.P.SB['scenes']):
                (R / 'anat').mkdir(exist_ok=True); [f.unlink() for f in (R / 'anat').glob('*.png')]
                al = self.P.node('anatset.js', capture=True).stdout; (R / 'anat/list.txt').write_text(al)
                if al.strip(): self.P.node('frames.js', rr('anat'), '--list', rr('anat/list.txt')); self.P.pyt('sheet.py', rr('anat'), rr('anat_sheet.png'), '4')
        ck = json.loads((R / 'check/overlay_check.json').read_text())['counts']; gate = self.P.layout.get('qa_gate', {})
        th = lambda k: gate.get(k, 'warn_until_verified' if k in ('safe_right', 'safe_bottom') else 0)
        hard = {k: v for k, v in ck.items() if isinstance(th(k), int) and v > th(k)}
        print('  叠字层自检（抽帧）：', ck or '无记录')
        if hard: raise RuntimeError(f'叠字层硬错（先修再预演）：{hard}，样本见 {self.P.rrel("check/overlay_check.json")}')

def arg_workers(args): return next((a.split('=')[1] for a in args if a.startswith('--workers=')), str(default_workers()))

class Animatic(Stage):
    name = 'animatic'; hard = 's6a'
    def inputs(self): return [fbytes(self.P.rdir / 'timeline.json'), fbytes(self.P.layout_file), b'mix:' + fsha(self.P.rdir / 'mix.wav')] + src_sig(self.P) + [fbytes(self.P.tools / 'render.js')]
    def outputs(self):
        n = latest_preview(self.P); return [self.P.rdir / f'{self.P.project}_preview_v{n}.mp4'] if n else [self.P.rdir / '__no_preview_yet__']
    def run(self):
        n = latest_preview(self.P) + 1; tag = f'preview_v{n}'; P = self.P; rr = P.rrel
        tl = json.loads((P.rdir / 'timeline.json').read_text())
        if tl.get('estimate'): print('  !! timeline 是 --estimate（没有录音）：预演只看画面节奏，字幕时刻是估的')
        lint_scenes(P); check_assets(P)
        with P.lock('render', f'animatic {tag}'): P.node('render.js', tag, arg_workers(self.args), env_extra={'FPS': str(tl['fps']), 'SUB': '1'})
        mp4 = P.rdir / f'{P.project}_{tag}.mp4'; sheet_dir = P.rdir / f'{tag}_frames'; sheet_dir.mkdir(exist_ok=True)
        for f in sheet_dir.glob('*.png'): f.unlink()
        P.sh(['ffmpeg', '-v', 'error', '-y', '-i', mp4, '-vf', f'fps=0.5:round=up,scale={270 if not P.land else 320}:-1', str(sheet_dir / 'f%04d.png')])   # 每 2 秒一张：f0001 = 0 s
        P.pyt('sheet.py', str(sheet_dir), rr(f'{P.project}_{tag}_sheet.png'), '8' if not P.land else '6')
        P.pyt('qa.py', tag, '--no-asr')
        print(f'  预演：{rr(P.project + "_" + tag + ".mp4")}  联系表：{rr(P.project + "_" + tag + "_sheet.png")}  QA：{rr(P.project + "_" + tag + ".qa.json")}')

def fstat(p): p = Path(p); return f'{p.stat().st_size}:{p.stat().st_mtime}'.encode() if p.exists() else b'<missing>'
class Render(Stage):
    name = 'render'
    def tag(self): return next((a.split('=')[1] for a in self.args if a.startswith('--tag=')), self.P.final_tag)
    def fps_sub(self):
        """画质档位：standard（默认）30 帧 + 2 子帧运动模糊；high 60 帧 + 4 子帧（竖屏；横屏按 layout_land.submit）。--quality=high 或 storyboard.quality；环境变量 FPS / SUB 再覆盖"""
        q = (argval(self.args, '--quality') or self.P.SB.get('quality') or 'standard').lower()
        if q not in ('standard', 'high'): raise RuntimeError('--quality 只能是 standard（默认）或 high')
        LS = (self.P.layout.get('submit') or {}) if self.P.land else {}
        fps, sub = (30, 2) if q == 'standard' else ((LS.get('fps', 30), LS.get('sub', 4)) if self.P.land else (60, 4))
        return os.environ.get('FPS', str(fps)), os.environ.get('SUB', str(sub))
    def inputs(self): fps, sub = self.fps_sub(); return [fbytes(self.P.rdir / 'timeline.json'), fbytes(self.P.layout_file), b'mix:' + fsha(self.P.rdir / 'mix.wav'), jdump(self.P.SB.get('cover'))] + src_sig(self.P) + [fbytes(self.P.tools / 'render.js'), self.tag().encode(), fps.encode(), sub.encode()]
    def outputs(self): return [self.P.rdir / f'{self.P.project}_{self.tag()}.mp4']
    def run(self):
        P = self.P; tag = self.tag(); fps, sub = self.fps_sub()
        if not (P.rdir / 'mix.wav').exists() and tag in ('final', 'master'): raise RuntimeError(f'没有 {P.rrel("mix.wav")}：正式版必须先 mix')
        lint_scenes(P); check_assets(P)
        if tag in ('final', 'master') and draft_lines(P): raise WaitRecording('现在的配音是草稿配音（voice --draft 合成的），只能用于预演；正式版要先导入真人录音（pipeline.py voice）')
        ok, why = P.audit_check('pre')
        if not ok:
            if '哈希与当前不符' in why:
                try: P.audit('diff')
                except Exception as e: print('  !! 差异稿没出来：', e)
            raise AuditPending('渲染前审核门：' + why)
        print('  渲染前审核门：' + why)
        if '--dry-run' in self.args: print(f'  dry-run：门都过了，将渲染 {tag}（{fps} fps × {sub} 子帧）——未执行'); return 'dry'
        rng = next((a.split('=')[1] for a in self.args if a.startswith('--range=')), None)
        with P.lock('render', f'render {tag}'): P.node('render.js', tag, arg_workers(self.args), *(rng.split(',') if rng else []), env_extra={'FPS': fps, 'SUB': sub})
        if (P.root / 'src/cover.html').exists():   # 封面图与视频第一帧同一段代码
            sb = os.path.relpath(P.sb_path, P.root / 'src').replace(os.sep, '/')
            if P.land: P.node('shot.js', f'src/cover.html?sb={sb}&orient=land', P.rrel(f'{P.project}_cover_16x9.png'), '1920', '1080')
            elif P.SB.get('cover'): P.node('shot.js', f'src/cover.html?sb={sb}', f'render/{P.project}_cover_9x16.png')

class QA(Stage):
    name = 'qa'
    def tag(self): return next((a.split('=')[1] for a in self.args if a.startswith('--tag=')), self.P.final_tag)
    def inputs(self): return [fstat(self.P.rdir / f'{self.P.project}_{self.tag()}.mp4'), *tool_sig(self.P, 'qa.py', 'subcheck.py', 'check_refs.py', 'check_fonts.py', 'dipscan.py', 'asr.py'), fbytes(self.P.layout_file), jdump({k: self.P.SB.get(k) for k in ('qa', 'red_flags')}), b'noasr' if '--no-asr' in self.args else b'']
    def outputs(self): return [self.P.rdir / f'{self.P.project}_{self.tag()}.qa.json']
    def run(self):
        r = subprocess.run([self.P.py, '-X', 'utf8', '-W', 'ignore', self.P.tools / 'qa.py', self.tag(), '--gate', *(['--no-asr'] if '--no-asr' in self.args else [])], cwd=self.P.root, env=self.P.env())
        if r.returncode: raise RuntimeError(f"QA 不通过：见 {self.P.rrel(self.P.project + '_' + self.tag() + '.qa.json')} 的 failures")

class AuditPre(Stage):
    """渲染前审核关卡（animatic 之后、HARD S6a 之前）：打包材料 → 最新 design/audit_pre_v{n}.md 要 result pass 且哈希与当前一致；否则等审核（退出码 5）。
    审核员 = 另开一个对话或子代理（提示词 references/audit_pre_prompt.md）：非口径问题可直接改并记录，口径类只提交给用户。"""
    name = 'audit_pre'
    def inputs(self): P = self.P; n = latest_preview(P); return [jdump(P.C.sb_strip(P.SB)), fbytes(P.rdir / 'timeline.json'), fstat(P.rdir / f'{P.project}_preview_v{n}.mp4')] + src_sig(P) + tool_sig(P, 'audit.py') + [fbytes(f) for f in sorted((P.root / 'design').glob('audit_pre_v*.md'))]
    def run(self):
        P = self.P; dl = draft_lines(P)
        if dl: raise WaitRecording(f"预演用的是草稿配音（{len(dl)} 句合成声）：可以先看节奏、改画面，但预演审核和 S6a 确认要等真人录音导入之后。照 audio/台词本.md 录好放进 audio/recordings/，再跑 pipeline.py voice")
        ok, why = P.audit_check('pre')
        if ok: print('  ' + why); return
        if '哈希与当前不符' in why:
            try: P.audit('diff')
            except Exception as e: print('  !! 差异稿没出来：', e)
        P.audit('pack', 'pre')
        raise AuditPending(why + '\n  → 另开一个对话（或子代理）当独立审核员：提示词 references/audit_pre_prompt.md，材料见上面的 index.md；审核员改完、重跑预演、写好报告并 stamp 后再跑 pipeline')

class AuditPost(Stage):
    """成片审核关卡（qa 之后、deliver 之前）：render[/land]/audit_post_{tag}.md 要 pass 且成片哈希一致；否则等审核（退出码 5）"""
    name = 'audit_post'
    def tag(self): return next((a.split('=')[1] for a in self.args if a.startswith('--tag=')), self.P.final_tag)
    def inputs(self): P = self.P; t = self.tag(); return [fstat(P.rdir / f'{P.project}_{t}.mp4'), fbytes(P.rdir / f'audit_post_{t}.md'), *tool_sig(P, 'audit.py')]
    def run(self):
        P = self.P; t = self.tag(); ok, why = P.audit_check('post', t)
        if ok: print('  ' + why); return
        P.audit('pack', 'post', '--tag', t)
        raise AuditPending(why + '\n  → 另开一个对话（或子代理）当独立审核员：提示词 references/audit_post_prompt.md，材料见上面的 index.md；不过就修、重渲、复审')

class Deliver(Stage):
    """交付检查：audit_post pass 且成片哈希一致、QA pass → render[/land]/deliver_{tag}.json（文件、大小、sha1）"""
    name = 'deliver'
    def tag(self): return next((a.split('=')[1] for a in self.args if a.startswith('--tag=')), self.P.final_tag)
    def inputs(self): P = self.P; t = self.tag(); return [fstat(P.rdir / f'{P.project}_{t}.mp4'), fbytes(P.rdir / f'audit_post_{t}.md'), fbytes(P.rdir / f'{P.project}_{t}.qa.json'), *tool_sig(P, 'audit.py')]
    def outputs(self): return [self.P.rdir / f'deliver_{self.tag()}.json']
    def run(self):
        P = self.P; t = self.tag(); ok, why = P.audit_check('post', t)
        if not ok: raise AuditPending('交付门：' + why)
        qf = P.rdir / f'{P.project}_{t}.qa.json'; qa = json.loads(qf.read_text()) if qf.exists() else None
        if not qa or not qa.get('pass'): raise RuntimeError(f'成片 QA 未通过或没有 {P.rrel(qf.name)}')
        files = [P.rdir / f'{P.project}_{t}.mp4', qf, P.rdir / f'{P.project}_{t}.overlay.json', P.rdir / 'timeline.json', P.rdir / f'audit_post_{t}.md'] + ([P.root / f'render/{P.project}_cover_9x16.png'] if not P.land else [P.rdir / f'{P.project}_cover_16x9.png'])
        rows = [{'path': f.relative_to(P.root).as_posix(), 'bytes': f.stat().st_size, 'sha1': hashlib.sha1(f.read_bytes()).hexdigest()[:16]} for f in files if f.exists()]
        man = {'project': P.project, 'tag': t, 'orient': P.orient, 'at': now(), 'audit_post': why, 'qa_pass': True, 'files': rows}
        (P.rdir / f'deliver_{t}.json').write_text(json.dumps(man, ensure_ascii=False, indent=1))
        print(f'  交付清单 {P.rrel("deliver_" + t + ".json")}：' + '、'.join(r['path'] for r in rows))
        print('  可选：python pipeline.py export_subs <project> 导出 srt 字幕；python pipeline.py clean <project> 看清理清单 → clean --apply')

STAGE_CLS = {c.name: c for c in (S0, S3, Voice, Timeline, Mix, Frames, Animatic, AuditPre, Render, QA, AuditPost, Deliver)}

def run_stage(P, name, args, force=False):
    """返回 'ok' | 'skip' | 'fail' | 'wait' | 'rec' | 'dry'"""
    st = STAGE_CLS[name](P, args); h = sha(st.inputs()); prev = P.status.get(name, {}); outs = st.outputs()
    if hasattr(st, 'redo') and st.redo(): force = True
    if not force and prev.get('ok') and prev.get('hash') == h and all(Path(o).exists() for o in outs):
        print(f'— {name}: 跳过（输入未变，产物在）'); P.log(f'SKIP {name} hash={h}'); return 'skip'
    print(f'▶ {name} …'); P.log(f'START {name} hash={h} args={args}'); t0 = time.time()
    try:
        r = st.run()
        if r == 'dry': P.log(f'DRY {name}'); return 'dry'
        outs = st.outputs(); missing = [str(o) for o in outs if not Path(o).exists()]
        if missing: raise RuntimeError(f'阶段结束但产物缺失：{missing}')
        P.status[name] = {'ok': True, 'hash': h, 'at': now(), 'seconds': round(time.time() - t0, 1), 'outputs': [Path(o).relative_to(P.root).as_posix() for o in outs], 'args': args}; P.save_status()
        P.log(f'OK {name} {round(time.time() - t0, 1)}s'); print(f'✓ {name} {round(time.time() - t0, 1)} s'); return 'ok'
    except AuditPending as e:
        P.status[name] = {'ok': False, 'wait': 'audit', 'hash': h, 'at': now(), 'error': str(e)[-600:], 'args': args}; P.save_status()
        P.log(f'WAIT_AUDIT {name}: {str(e).splitlines()[0][-300:]}'); print(f'⏸ {name} 等审核：{e}'); return 'wait'
    except WaitRecording as e:
        P.status[name] = {'ok': False, 'wait': 'recording', 'hash': h, 'at': now(), 'error': str(e), 'args': args}; P.save_status()
        P.log(f'WAIT_REC {name}'); print(f'⏸ {name} 等录音：{e}'); return 'rec'
    except Exception as e:
        P.status[name] = {'ok': False, 'hash': h, 'at': now(), 'seconds': round(time.time() - t0, 1), 'error': str(e)[-600:], 'args': args}; P.save_status()
        P.log(f'FAIL {name}: {str(e)[-300:]}'); print(f'✗ {name} 失败：{e}'); return 'fail'
CODE = {'fail': 2, 'wait': 5, 'rec': 6}

def run_until(P, until, args, force=False, start=None):
    """按顺序跑阶段，过 HARD 点才继续。返回退出码。"""
    if until not in STAGES and until != 's6a': die(f'--until 只能是 {STAGES} 或 s6a')
    last = 'audit_pre' if until == 's6a' else until
    for name in STAGES:
        if start and STAGES.index(name) < STAGES.index(start): continue
        r = run_stage(P, name, args, force)
        if r in CODE: return CODE[r]
        if r == 'dry': break
        if name in HARD_AFTER and not P.confirmed(HARD_AFTER[name]): return P.hard_stop(HARD_AFTER[name])
        if name == last: break
    print(f'\n✓ {P.project}: 已到 {until}'); return 0

# ---------------- new：建专题 ----------------
def argval(args, name):
    v = next((a.split('=', 1)[1] for a in args if a.startswith(name + '=')), None)
    if name in args and args.index(name) + 1 < len(args): v = args[args.index(name) + 1]
    return v
def load_themes():
    d = json.loads((HERE / 'themes.json').read_text()); return {k: v for k, v in d.items() if not k.startswith('_')}
def apply_theme(root, name):
    """把主题预设写进专题：layout.json / layout_land.json 的 theme（叠字层颜色）+ storyboard.style.palette 里的底色（纸面、家、诊室、地面、墨色）"""
    T = load_themes()
    if name not in T: die('没有主题 ' + name + '；可选：' + '、'.join(k + '（' + v['label'] + '）' for k, v in T.items()))
    root = Path(root)
    for n in ('layout.json', 'layout_land.json'):
        f = root / n
        if f.exists(): d = json.loads(f.read_text()); d['theme'] = dict(T[name]['theme']); f.write_text(json.dumps(d, ensure_ascii=False, indent=1) + '\n')
    for f in sorted((root / 'design').glob('storyboard*.json')):
        d = json.loads(f.read_text()); st = d.setdefault('style', {}); st['theme'] = name; st.setdefault('palette', {}).update(T[name]['palette']); f.write_text(json.dumps(d, ensure_ascii=False, indent=1) + '\n')
    return T[name]['label']
def cmd_theme(args):
    pos = [a for a in args if not a.startswith('--')]; T = load_themes()
    if len(pos) < 2:
        print('pipeline.py theme <专题> <主题名>   换一套配色（叠字层颜色 + 画面底色）。可选主题：'); [print('  ' + k.ljust(8) + ' ' + v['label']) for k, v in T.items()]; return 4 if pos else 0
    root = Path(pos[0]).resolve()
    if not (root / 'design').is_dir(): die(f'{root} 不是专题目录')
    print(f'✓ 主题已换成 {pos[1]}（{apply_theme(root, pos[1])}）。已经出过的预演 / 成片要重跑才会变。'); return 0
def cmd_new(args):
    pos = [a for i, a in enumerate(args) if not a.startswith('--') and (i == 0 or args[i - 1] not in ('--title', '--dir', '--theme'))]
    if not pos: die('pipeline.py new <project> [--title "片名"] [--dir 工作目录] [--example] [--theme mint|indigo|amber]')
    theme = argval(args, '--theme')
    if theme and theme not in load_themes(): die(f"没有主题 {theme}；可选：{'、'.join(load_themes())}")
    name, title = pos[0], argval(args, '--title'); base = Path(argval(args, '--dir') or Path.cwd()).resolve()
    dst = Path(name) if Path(name).is_absolute() else base / name
    if not re.match(r'^[a-z][a-z0-9_]*$', dst.name): die('专题目录名用小写字母、数字、下划线（成片名 render/{project}_final.mp4 要用它）')
    if dst.exists(): die(f'{dst} 已存在，不覆盖')
    font = HERE / 'assets/fonts'
    if not list(font.glob('*.otf')) + list(font.glob('*.ttf')): die('字体还没装好：先跑 python pipeline.py setup')
    dst.mkdir(parents=True)
    shutil.copytree(HERE / 'src', dst / 'src', ignore=shutil.ignore_patterns('__pycache__', 'demo_*', '*.bak*'))
    shutil.copytree(font, dst / 'assets/fonts')
    for d in ('assets/lib/characters', 'assets/lib/scenes', 'assets/lib/props', 'assets/keyframes', 'audio/recordings', 'audio/lines', 'render', 'design/source'): (dst / d).mkdir(parents=True, exist_ok=True)
    for n in ('layout.json', 'layout_land.json'): shutil.copy(HERE / n, dst / n)
    sb = json.loads((HERE / 'design/storyboard_template.json').read_text())
    sb['project'] = dst.name; sb['title'] = title or f'{dst.name}：（片名待定）'; sb['title_card'] = {'main': title or '（片名）', 'sub': '（副标题）'}; sb['version'] = '0.1'
    for k in ('s0', 's3', 's6a'): sb['status'][k] = {'confirmed': False, 'by': None, 'date': None, 'note': None}
    (dst / 'design' / f'storyboard_{dst.name}.json').write_text(json.dumps(sb, ensure_ascii=False, indent=1) + '\n')
    if '--example' in args:   # 样例专题：分镜、场景代码、解剖、3D 素材都带上，直接能出预演
        EX = HERE.parent / 'templates/example'; sb = json.loads((EX / 'design/storyboard_example.json').read_text()); sb['project'] = dst.name
        if title: sb['title'] = title
        (dst / 'design' / f'storyboard_{dst.name}.json').write_text(json.dumps(sb, ensure_ascii=False, indent=1) + '\n')
        for f in ('scenes.js', 'anat.js'): shutil.copy(EX / 'src' / f, dst / 'src' / f)
        shutil.copytree(EX / 'assets/lib', dst / 'assets/lib', dirs_exist_ok=True)
    if theme: apply_theme(dst, theme)
    me = Path(__file__).resolve()
    (dst / 'README.md').write_text(f"# {dst.name}\n\n由 med-explainer-video 生成（{now()[:10]}）。\n\n"
                                   f"下一步：改 `design/storyboard_{dst.name}.json`（title / characters / claims / red_flags / chapters / scenes / voices），然后\n\n"
                                   f"```\npython \"{me}\" s0 \"{dst}\"\n```\n")
    print(f'✓ 新专题 {dst}\n  下一步：编辑 design/storyboard_{dst.name}.json → python "{me}" s0 "{dst}" → 等用户确认 S0')

def cmd_status(P):
    print(f'{P.project}  {P.root}  [{P.orient}: {P.rrel()}]\n  HARD: s0={P.confirmed("s0")} s3={P.confirmed("s3")} s6a={P.confirmed("s6a")}')
    for k, t in (('pre', None), ('post', P.final_tag)):
        ok, why = P.audit_check(k, t); print(f"  审核 {k:4s}: {'通过' if ok else '未过'}  {why[:150]}")
    for n in STAGES:
        s = P.status.get(n)
        flag = 'ok  ' if s and s.get('ok') else ('REC ' if s.get('wait') == 'recording' else 'WAIT' if s.get('wait') else 'FAIL') if s else '—   '
        print(f"  {n:10s} {flag} {s.get('at', '') if s else ''} {s.get('seconds', '') if s else ''}s {('ERR ' + s.get('error', '').splitlines()[0][:120]) if s and not s.get('ok') and s.get('error') else ''}")

# ---------------- 后台运行：长命令别卡在一次工具调用里 ----------------
def pid_alive(pid):
    if os.name == 'nt':
        import ctypes
        h = ctypes.windll.kernel32.OpenProcess(0x1000, False, int(pid))
        if not h: return False
        code = ctypes.c_ulong(); ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(code)); ctypes.windll.kernel32.CloseHandle(h); return code.value == 259
    try: os.kill(int(pid), 0); return True
    except OSError: return False
def bg_paths(root): r = Path(root) / 'render'; r.mkdir(parents=True, exist_ok=True); return r / 'bg_job.json', r / 'bg_job.log'
def bg_job(root):
    jf, _ = bg_paths(root)
    try: j = json.loads(jf.read_text(encoding='utf-8'))
    except (OSError, ValueError): return None
    if not j.get('done') and not pid_alive(j.get('pid', -1)): j.update(done=True, exit=j.get('exit', 1), died=True)   # 进程没了却没写结果：被杀掉或崩了
    return j
def bg_start(argv, root):
    j = bg_job(root)
    if j and not j.get('done'): print(f"已有后台任务在跑（{j['cmd']}，{j['started']} 开始）：先用 wait 等它结束"); return 4
    jf, lf = bg_paths(root); args = [a for a in argv if a != '--bg']
    env = dict(os.environ, KEPU_BG_JOB=str(jf), PYTHONUNBUFFERED='1'); cmd = [sys.executable, '-X', 'utf8', '-u', str(Path(__file__).resolve()), *args, '--bg-child']
    with open(lf, 'w', encoding='utf-8') as log:
        kw = dict(stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, env=env, cwd=os.getcwd())
        if os.name == 'nt':
            flags = 0x08000000 | 0x00000200   # CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP
            try: pr = subprocess.Popen(cmd, creationflags=flags | 0x01000000, **kw)   # 再加 CREATE_BREAKAWAY_FROM_JOB：调用方结束时不被一起关掉
            except OSError: pr = subprocess.Popen(cmd, creationflags=flags, **kw)
        else: pr = subprocess.Popen(cmd, start_new_session=True, **kw)
    jf.write_text(json.dumps({'pid': pr.pid, 'cmd': ' '.join(a for a in args if not Path(a).is_dir()), 'started': now(), 'done': False}, ensure_ascii=False), encoding='utf-8')
    me = Path(__file__).resolve()
    print(f'已在后台开始：{" ".join(a for a in args if not Path(a).is_dir())}\n  看进度 / 等结果：python "{me}" wait "{root}"（最多等 90 秒就返回；退出码 7 = 还在跑，再 wait 一次）\n  日志：{lf}')
    return 0
def bg_child(argv):
    argv = [a for a in argv if a != '--bg-child']; jf = os.environ.get('KEPU_BG_JOB'); code = 1
    try: code = main(argv)
    except SystemExit as e: code = e.code if isinstance(e.code, int) else 1
    except BaseException:
        import traceback; traceback.print_exc()
    finally:
        try:
            j = json.loads(Path(jf).read_text(encoding='utf-8')); j.update(done=True, exit=code, ended=now()); Path(jf).write_text(json.dumps(j, ensure_ascii=False), encoding='utf-8')
        except Exception: pass
    return code
EXIT_MEAN = {0: '完成', 2: '失败（看日志里 ✗ 那几行）', 3: '停在 HARD 点，等用户确认', 4: '参数错', 5: '等审核', 6: '等用户录音'}
def bg_tail(root, n=14):
    _, lf = bg_paths(root)
    try: lines = [l for l in lf.read_text(encoding='utf-8', errors='replace').splitlines() if l.strip()]
    except OSError: return []
    keep = [l for l in lines if l.lstrip().startswith(('✗', '✓', '▶', '⏸', '■', '!!', '—')) or 'frames,' in l or 'QA ' in l]
    return (keep or lines)[-n:]
def cmd_wait(root, args):
    tmo = float(argval(args, '--timeout') or 90); t0 = time.time(); j = bg_job(root)
    if not j: print('没有后台任务（加 --bg 启动的才有）'); return 4
    while not j.get('done') and time.time() - t0 < tmo: time.sleep(2); j = bg_job(root)
    for l in bg_tail(root): print('  ' + l[:300])
    if not j.get('done'): print(f"… 还在跑：{j['cmd']}（{j['started']} 开始）。再跑一次 wait 接着等"); return 7
    code = j.get('exit', 1)
    print(f"后台任务结束：{j['cmd']} → 退出码 {code}（{'进程中途没了：被关掉或崩溃，看日志' if j.get('died') else EXIT_MEAN.get(code, '失败')}）；完整日志 {bg_paths(root)[1]}")
    return code
def cmd_check(P):
    """只检查不渲染：分镜 + 场景代码。改完任何东西都可以先跑它（1–2 秒）"""
    bad = 0
    try: check_sb(P)
    except RuntimeError as e: print('✗', e); bad = 1
    if bad == 0 or True:
        try: lint_scenes(P)
        except RuntimeError as e: print('✗', e); bad = 1
    print('检查通过：分镜和场景代码都没有错误' if not bad else '有错误：按上面的提示改完再跑 check')
    return 2 if bad else 0

# ---------------- main ----------------
def main(argv):
    if not argv or argv[0] in ('-h', '--help'): print(__doc__); return 0
    cmd, rest = argv[0], argv[1:]
    if cmd == 'setup': return subprocess.call([sys.executable, '-X', 'utf8', str(HERE / 'setup_env.py'), *rest])
    if cmd == 'new': cmd_new(rest); return 0
    if cmd == 'theme': return cmd_theme(rest)
    orient = argval(rest, '--orient')
    if '--orient' in rest: i = rest.index('--orient'); rest = rest[:i] + rest[i + 2:]
    rest = [a for a in rest if not a.startswith('--orient=')]
    if orient and orient not in ('land', 'port'): die('--orient 只能是 land（横屏）或 port（竖屏，默认）')
    force = '--force' in rest; until = argval(rest, '--until')
    if '--until' in rest: i = rest.index('--until'); rest = rest[:i] + rest[i + 2:]
    rest = [a for a in rest if not a.startswith('--until=')]
    def is_proj(a): return not a.startswith('--') and Path(a).is_dir() and (Path(a) / 'design').is_dir()
    proj = next((a for a in rest if is_proj(a)), None); args = [a for a in rest if a != proj and a != '--force']
    root = Path(proj or Path.cwd()).resolve()
    if cmd == 'wait': return cmd_wait(root, args)
    if '--bg' in argv:
        if not (root / 'design').is_dir(): die(f'{root} 不是专题目录（没有 design/）')
        return bg_start(argv, root)
    P = Project(root, orient)
    if cmd == 'check': return cmd_check(P)
    if cmd == 'status':
        cmd_status(P); j = bg_job(P.root)
        if j: print(f"  后台任务：{j['cmd']}  " + (f"已结束，退出码 {j.get('exit')}" if j.get('done') else f"进行中（{j['started']} 开始；用 wait 看进度）"))
        return 0
    if cmd == 'clean': return subprocess.call([sys.executable, '-X', 'utf8', str(P.tools / 'cleanup.py'), *args], cwd=P.root, env=P.env())
    if cmd == 'export_subs': return subprocess.call([sys.executable, '-X', 'utf8', str(P.tools / 'export_subs.py'), *args], cwd=P.root, env=P.env())
    if cmd == 'run': return run_until(P, until or 'qa', args, force, start=next((a.split('=')[1] for a in args if a.startswith('--from=')), None))
    if cmd in STAGE_CLS:
        if cmd in HARD_BEFORE and not P.confirmed(HARD_BEFORE[cmd]): return P.hard_stop(HARD_BEFORE[cmd])
        r = run_stage(P, cmd, args, force)
        if r in CODE: return CODE[r]
        if r != 'dry' and cmd in HARD_AFTER and not P.confirmed(HARD_AFTER[cmd]): return P.hard_stop(HARD_AFTER[cmd])
        return 0
    die(f'未知子命令 {cmd}；可用：setup new theme check run wait status clean export_subs {" ".join(STAGES)}（--orient land 横屏；长命令加 --bg 放后台）')

if __name__ == '__main__': sys.exit(bg_child(sys.argv[1:]) if '--bg-child' in sys.argv else main(sys.argv[1:]))

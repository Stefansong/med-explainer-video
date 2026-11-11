#!/usr/bin/env python3
"""运行环境检查与安装（Windows / macOS 通用）。由 `python pipeline.py setup [--check] [--asr] [--align]` 调用。

  Python 包     requirements.txt（python -m pip install；连不上 PyPI 自动改用清华镜像）
  Node 包       package.json（puppeteer-core，只控制浏览器、不下载浏览器；连不上 npmjs 自动改用 npmmirror）
  ffmpeg       系统里有且带 libx264 就用系统的；否则用 imageio-ffmpeg 自带的，复制到 scripts/bin/
  浏览器        找本机 Chrome / Edge（Windows 10/11 自带 Edge）；都没有就下载 chrome-headless-shell 到 scripts/bin/browsers/
  字体          scripts/assets/fonts/ 里的开源字体（思源黑体子集、得意黑）
  --asr        预先下载语音识别模型（默认 large-v3-turbo，约 1.6 GB；不预下载的话第一次导入录音时自动下载）
  --align      另装 torch + torchaudio，逐字时刻改用 MMS_FA 强制对齐（更准，约多 1 GB 下载）
  --check      只检查，不安装
结果写进 scripts/bin/env.json（CHROME_PATH、NODE、HF_ENDPOINT），pipeline.py 每次启动时读。"""
import sys, os, json, shutil, subprocess, platform, urllib.request
from pathlib import Path
HERE = Path(__file__).resolve().parent; BIN = HERE / 'bin'; ENVF = BIN / 'env.json'
A = sys.argv[1:]; CHECK = '--check' in A
WIN = os.name == 'nt'; EXE = '.exe' if WIN else ''
env = json.loads(ENVF.read_text(encoding='utf-8')) if ENVF.exists() else {}
rows = []
def row(name, ok, info): rows.append((name, ok, info)); print(f"{'✓' if ok else '✗'} {name}: {info}", flush=True)
def reach(url, t=4):
    try: urllib.request.urlopen(urllib.request.Request(url, method='HEAD'), timeout=t); return True
    except Exception: return False
def run(cmd, **kw): print('  $', ' '.join(map(str, cmd)), flush=True); return subprocess.run([str(c) for c in cmd], **kw)

# ---------- Python ----------
if sys.version_info < (3, 9): row('Python', False, f'{platform.python_version()}：需要 3.9 或更新'); sys.exit(1)
row('Python', True, f'{platform.python_version()}（{sys.executable}）')
def missing_py():
    need = {'numpy': 'numpy', 'scipy': 'scipy', 'soundfile': 'soundfile', 'pypinyin': 'pypinyin', 'jieba': 'jieba', 'PIL': 'pillow', 'fontTools': 'fonttools',
            'filelock': 'filelock', 'send2trash': 'send2trash', 'imageio_ffmpeg': 'imageio-ffmpeg', 'faster_whisper': 'faster-whisper', 'docx': 'python-docx'}
    out = []
    for mod, pkg in need.items():
        try: __import__(mod)
        except Exception: out.append(pkg)
    return out
miss = missing_py()
if miss and not CHECK:
    idx = [] if reach('https://pypi.org/simple/pip/') else ['-i', 'https://pypi.tuna.tsinghua.edu.cn/simple']
    run([sys.executable, '-m', 'pip', 'install', '-r', HERE / 'requirements.txt', *idx])
    if '--align' in A: run([sys.executable, '-m', 'pip', 'install', 'torch', 'torchaudio', *idx])
    import importlib; importlib.invalidate_caches(); miss = missing_py()
row('Python 包', not miss, '齐' if not miss else f'缺 {miss}（python -m pip install -r requirements.txt）')

# ---------- ffmpeg ----------
def has_x264(ff):
    try: return 'libx264' in subprocess.run([ff, '-hide_banner', '-encoders'], capture_output=True, text=True, timeout=30).stdout
    except Exception: return False
ff_local = BIN / f'ffmpeg{EXE}'; ff_sys = shutil.which('ffmpeg')
if ff_local.exists() and has_x264(str(ff_local)): row('ffmpeg', True, str(ff_local))
elif ff_sys and has_x264(ff_sys): row('ffmpeg', True, ff_sys)
elif not CHECK:
    try:
        import imageio_ffmpeg
        src = imageio_ffmpeg.get_ffmpeg_exe(); BIN.mkdir(exist_ok=True); shutil.copy2(src, ff_local)
        if not WIN: os.chmod(ff_local, 0o755)
        row('ffmpeg', has_x264(str(ff_local)), f'{ff_local}（来自 imageio-ffmpeg）')
    except Exception as e: row('ffmpeg', False, f'没装上：{e}')
else: row('ffmpeg', False, '没有（setup 会从 imageio-ffmpeg 复制一份）')

# ---------- Node ----------
node = env.get('NODE') if env.get('NODE') and Path(env['NODE']).exists() else shutil.which('node')
ver = ''
if node:
    try: ver = subprocess.run([node, '-v'], capture_output=True, text=True, timeout=20).stdout.strip()
    except Exception: node = None
okn = bool(node) and ver.lstrip('v').split('.')[0].isdigit() and int(ver.lstrip('v').split('.')[0]) >= 18
row('Node.js', okn, f'{ver}（{node}）' if node else '没找到：装 Node.js 18 或更新（https://nodejs.org 或 npmmirror 的镜像），装完重跑 setup')
if okn: env['NODE'] = node
npm = shutil.which('npm') or (str(Path(node).parent / ('npm.cmd' if WIN else 'npm')) if node else None)
pc = HERE / 'node_modules' / 'puppeteer-core'
if okn and not pc.exists() and not CHECK and npm:
    reg = [] if reach('https://registry.npmjs.org/puppeteer-core') else ['--registry=https://registry.npmmirror.com']
    run([npm, 'install', '--no-audit', '--no-fund', *reg], cwd=HERE, shell=WIN)
row('Node 包', pc.exists(), 'puppeteer-core 已装' if pc.exists() else '缺（在 scripts/ 下 npm install）')

# ---------- 浏览器 ----------
def browsers():
    if WIN:
        bases = [os.environ.get(k) for k in ('PROGRAMFILES', 'PROGRAMFILES(X86)', 'LOCALAPPDATA')]
        return [str(Path(b) / s) for b in bases if b for s in ('Google/Chrome/Application/chrome.exe', 'Microsoft/Edge/Application/msedge.exe')]
    if sys.platform == 'darwin':
        return ['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge', '/Applications/Chromium.app/Contents/MacOS/Chromium',
                str(Path.home() / 'Applications/Google Chrome.app/Contents/MacOS/Google Chrome')]
    return ['/usr/bin/google-chrome', '/usr/bin/chromium', '/usr/bin/chromium-browser', '/usr/bin/microsoft-edge']
chrome = os.environ.get('CHROME_PATH') or (env.get('CHROME_PATH') if env.get('CHROME_PATH') and Path(env['CHROME_PATH']).exists() else None) or next((b for b in browsers() if Path(b).exists()), None)
if not chrome and not CHECK and okn:
    npx = shutil.which('npx') or (str(Path(node).parent / ('npx.cmd' if WIN else 'npx')))
    base = [] if reach('https://storage.googleapis.com/chrome-for-testing-public/') else ['--base-url=https://cdn.npmmirror.com/binaries/chrome-for-testing']
    r = run([npx, '-y', '@puppeteer/browsers', 'install', 'chrome-headless-shell@stable', f'--path={BIN / "browsers"}', *base], cwd=HERE, capture_output=True, text=True, shell=WIN)
    line = next((l for l in (r.stdout or '').splitlines()[::-1] if 'chrome-headless-shell' in l and ' ' in l), '')
    chrome = line.split(' ', 1)[1].strip() if line else None
if chrome: env['CHROME_PATH'] = chrome
row('浏览器', bool(chrome), chrome or '没找到 Chrome / Edge：装 Chrome，或重跑 setup 自动下载 chrome-headless-shell')

# ---------- 字体 ----------
fonts = sorted(p.name for p in (HERE / 'assets/fonts').glob('*') if p.suffix.lower() in ('.otf', '.ttf'))
row('字体', len(fonts) >= 2, '、'.join(fonts) or '缺：scripts/assets/fonts/ 里应有 SourceHanSansSC-VF.otf 与 SmileySans-Oblique.ttf')

# ---------- 语音识别模型 ----------
if not os.environ.get('HF_ENDPOINT') and not env.get('HF_ENDPOINT') and not reach('https://huggingface.co'):
    env['HF_ENDPOINT'] = 'https://hf-mirror.com'; print('  （连不上 huggingface.co：语音识别模型改从 hf-mirror.com 下载）')
if env.get('HF_ENDPOINT'): os.environ['HF_ENDPOINT'] = env['HF_ENDPOINT']
if '--asr' in A and not CHECK:
    try:
        sys.path.insert(0, str(HERE / 'tools')); import asr
        asr._model(); row('语音识别模型', True, f'{asr.MODEL} 已就绪')
    except BaseException as e: row('语音识别模型', False, f'下载失败：{e}')
else: row('语音识别模型', True, '第一次导入录音时自动下载（约 1.6 GB）；想先下好：setup --asr')

BIN.mkdir(exist_ok=True); ENVF.write_text(json.dumps(env, ensure_ascii=False, indent=1), encoding='utf-8')
bad = [n for n, ok, _ in rows if not ok]
print('\n' + ('环境齐了。' if not bad else f'还缺：{"、".join(bad)}（见上面每一项的说明）'))
sys.exit(0 if not bad else 1)

"""共享资源锁：同一台电脑上同时做几集时排队（渲染同时 1 个、抽帧最多 2 个）。Windows / macOS 通用（filelock）。
  with Slot('render', project, stage): ...     阻塞等待，每分钟打印一次“等待其他专题：<持锁者>”
锁目录：$KEPU_LOCKS，否则 <工作目录>/.locks（工作目录 = 专题目录的上一级）。没装 filelock 时不加锁（单集照常跑）。"""
import os, sys, time, json, datetime
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import ROOT
LOCK_DIR = Path(os.environ['KEPU_LOCKS']).resolve() if os.environ.get('KEPU_LOCKS') else ROOT.parent / '.locks'
POOLS = {'render': 1, 'frames': 2}
try:
    from filelock import FileLock, Timeout
except ImportError:
    FileLock = None

class Slot:
    def __init__(self, pool, project=None, stage=''):
        self.pool, self.n = pool, POOLS.get(pool, 1); self.who = project or ROOT.name; self.stage = stage; self.lock = None
    def _info(self, k): return LOCK_DIR / f'{self.pool}_{k}.json'
    def __enter__(self):
        if FileLock is None: return self
        LOCK_DIR.mkdir(parents=True, exist_ok=True); t0 = time.time(); last = 0
        while True:
            for k in range(self.n):
                lk = FileLock(str(LOCK_DIR / f'{self.pool}_{k}.lock'))
                try: lk.acquire(timeout=0)
                except Timeout: continue
                self.lock, self.k = lk, k
                self._info(k).write_text(json.dumps({'project': self.who, 'stage': self.stage, 'pid': os.getpid(), 'at': datetime.datetime.now().isoformat(timespec='seconds')}, ensure_ascii=False), encoding='utf-8')
                return self
            if time.time() - last > 60:
                last = time.time(); holders = []
                for k in range(self.n):
                    try: holders.append(json.loads(self._info(k).read_text(encoding='utf-8')).get('project', '?'))
                    except (OSError, ValueError): pass
                print(f'  等待其他专题{self.pool}：{"、".join(holders) or "?"}（已等 {int(time.time() - t0)} s）', flush=True)
            time.sleep(2)
    def __exit__(self, *a):
        if self.lock:
            try: self._info(self.k).unlink()
            except OSError: pass
            self.lock.release()
        return False

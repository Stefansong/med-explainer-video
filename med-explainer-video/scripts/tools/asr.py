"""语音识别（录音回读核对、逐字时刻、成片 QA 用）：faster-whisper，CPU 运行，Windows / macOS 通用。
接口同 openai-whisper 的 transcribe：返回 {'text', 'segments': [{start, end, text, words?: [{word, start, end, probability}]}], 'language'}。
模型：环境变量 KEPU_ASR_MODEL（默认 large-v3-turbo，约 1.6 GB；机器慢可设 medium / small，回读核对会粗一些）。
国内下载慢：setup 会在 bin/env.json 写 HF_ENDPOINT=https://hf-mirror.com，pipeline 启动时带上。
回读提示词只写领域、不写目标词（写了会把读对的字硬改成提示词）：storyboard.tts.asr_prompt，默认“医学科普。”"""
import os, functools
from pathlib import Path
os.environ.setdefault('HF_HUB_DISABLE_TELEMETRY', '1')
MODEL = os.environ.get('KEPU_ASR_MODEL') or 'large-v3-turbo'

@functools.lru_cache(1)
def _model():
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise SystemExit('缺 faster-whisper：先跑 python pipeline.py setup')
    return WhisperModel(MODEL, device='cpu', compute_type='int8', cpu_threads=max(1, (os.cpu_count() or 4)))

def load16k(path):
    """读成 16 kHz 单声道 float32（自己解码，不走 faster-whisper 的 PyAV：新版 PyAV 改了接口会直接报错）"""
    import numpy as np, soundfile as sf, subprocess, tempfile, math
    try: a, sr = sf.read(str(path), dtype='float32', always_2d=False)
    except Exception:
        tmp = Path(tempfile.gettempdir()) / f'asr_{os.getpid()}.wav'
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(path), '-vn', '-ac', '1', '-ar', '16000', str(tmp)], check=True)
        a, sr = sf.read(str(tmp), dtype='float32', always_2d=False); tmp.unlink(missing_ok=True)
    if a.ndim > 1: a = a.mean(1)
    if sr != 16000:
        from scipy.signal import resample_poly
        g = math.gcd(sr, 16000); a = resample_poly(a, 16000 // g, sr // g)
    return np.ascontiguousarray(a, dtype=np.float32)

def transcribe(path, language='zh', initial_prompt=None, word_timestamps=False, **_):
    segs, info = _model().transcribe(load16k(path), language=language, initial_prompt=initial_prompt, word_timestamps=word_timestamps,
                                     beam_size=1, condition_on_previous_text=False, vad_filter=False)
    out = []
    for s in segs:
        d = {'start': float(s.start), 'end': float(s.end), 'text': s.text}
        if word_timestamps: d['words'] = [{'word': w.word, 'start': float(w.start), 'end': float(w.end), 'probability': float(w.probability)} for w in (s.words or [])]
        out.append(d)
    return {'text': ''.join(d['text'] for d in out).strip(), 'segments': out, 'language': info.language}

if __name__ == '__main__':
    import sys, json
    print(json.dumps(transcribe(sys.argv[1], word_timestamps='--words' in sys.argv), ensure_ascii=False, indent=1))

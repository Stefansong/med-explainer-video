"""读视频 / 音频的规格（时长、分辨率、帧率、像素格式、色彩范围）。系统有 ffprobe 就用它；没有（Windows 上只装了 pip 自带的 ffmpeg）就解析 `ffmpeg -i` 的输出。
返回与 `ffprobe -show_entries stream=…:format=duration -of json` 同样的结构：{'streams': [{codec_type, width, height, r_frame_rate, pix_fmt, color_space, color_range}], 'format': {'duration': '12.34'}}"""
import json, re, shutil, subprocess

def _ffmpeg_parse(path):
    err = subprocess.run(['ffmpeg', '-hide_banner', '-i', str(path)], capture_output=True, text=True, encoding='utf-8', errors='ignore').stderr
    m = re.search(r'Duration:\s*(\d+):(\d+):([\d.]+)', err)
    dur = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else 0.0
    streams = []
    for line in err.splitlines():
        sm = re.search(r'Stream #\d+:\d+.*?:\s*(Video|Audio):\s*(.*)', line)
        if not sm: continue
        kind, rest = sm.group(1).lower(), sm.group(2); s = {'codec_type': kind, 'codec_name': rest.split()[0].strip(',')}
        if kind == 'video':
            r = re.search(r'(\d{2,5})x(\d{2,5})', rest)
            if r: s['width'], s['height'] = int(r.group(1)), int(r.group(2))
            pf = re.search(r'\),\s*([a-z0-9_]+)(?:\(([^)]*)\))?,', rest) or re.search(r',\s*([a-z0-9_]+)(?:\(([^)]*)\))?,\s*\d{2,5}x\d{2,5}', rest)
            if pf:
                s['pix_fmt'] = pf.group(1); parts = [p.strip() for p in (pf.group(2) or '').split(',')]
                if parts and parts[0] in ('tv', 'pc'): s['color_range'] = parts.pop(0)
                if parts and parts[0] and parts[0] not in ('progressive', 'top first', 'bottom first'): s['color_space'] = parts[0].split('/')[0]
            f = re.search(r'([\d.]+)\s*fps', rest)
            if f:
                v = float(f.group(1)); s['r_frame_rate'] = f'{round(v)}/1' if abs(v - round(v)) < 0.01 else f'{round(v * 1001)}/1001'
        streams.append(s)
    return {'streams': streams, 'format': {'duration': f'{dur:.6f}'}}

def info(path):
    if shutil.which('ffprobe'):
        r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'stream=codec_type,codec_name,width,height,r_frame_rate,color_space,color_range,pix_fmt:format=duration', '-of', 'json', str(path)],
                           capture_output=True, text=True, encoding='utf-8', errors='ignore')
        if r.returncode == 0 and r.stdout.strip(): return json.loads(r.stdout)
    return _ffmpeg_parse(path)

def duration(path): return float(info(path)['format']['duration'])
def video(path): return next(s for s in info(path)['streams'] if s.get('codec_type') == 'video')

if __name__ == '__main__':
    import sys
    print(json.dumps(info(sys.argv[1]) if '--ffmpeg' not in sys.argv else _ffmpeg_parse(sys.argv[1]), indent=1))

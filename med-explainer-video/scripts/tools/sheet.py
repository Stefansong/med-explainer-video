#!/usr/bin/env python3
"""把一组竖屏抽帧拼成联系表：python3 tools/sheet.py <dir> <out.png> [cols=5]"""
import sys, glob
from PIL import Image, ImageDraw, ImageFont
d, out = sys.argv[1], sys.argv[2]; cols = int(sys.argv[3]) if len(sys.argv) > 3 else 5
fs = sorted(glob.glob(f'{d}/*.png'), key=lambda f: f)
w, h = 360, 640
rows = -(-len(fs) // cols); im = Image.new('RGB', (cols * w, rows * (h + 30)), 'white'); dr = ImageDraw.Draw(im)
for k, f in enumerate(fs):
    x, y = (k % cols) * w, (k // cols) * (h + 30)
    im.paste(Image.open(f).convert('RGB').resize((w, h)), (x, y + 30)); dr.text((x + 6, y + 6), f.split('/')[-1][:-4], fill='black')
im.save(out); print(out, len(fs))

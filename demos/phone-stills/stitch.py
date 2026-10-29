# stitches the phone screens into one page, then cuts it into webp strips for the landing page; prints the manifest
import json, sys
from pathlib import Path
from PIL import Image
src, dst = Path(sys.argv[1]), Path(sys.argv[2])
info = json.loads((src / 'shots.json').read_text())
k, W = info['dpr'], info['w'] * info['dpr']
H = info['H'] * k
page = Image.new('RGB', (W, H), 'white')
for i, y in enumerate(info['ys']):
    page.paste(Image.open(src / f's{i:02d}.png').convert('RGB'), (0, y * k))
dst.mkdir(parents=True, exist_ok=True)
TILE = 1600
hs = []
for n, y in enumerate(range(0, H, TILE)):
    t = page.crop((0, y, W, min(H, y + TILE)))
    t.save(dst / f'm{n}.webp', 'WEBP', quality=72, method=6)
    hs.append(t.height // k)
if info['head']:
    Image.open(src / 'head.png').convert('RGB').save(dst / 'head.webp', 'WEBP', quality=80, method=6)
size = sum(f.stat().st_size for f in dst.glob('*.webp'))
print(json.dumps({'w': info['w'], 'h': hs, 'head': info['head'] and {'top': info['head']['top'], 'h': info['head']['h']}}), f'{size // 1024} KB')

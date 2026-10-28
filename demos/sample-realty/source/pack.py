"""rendered PNG frames -> web frames: d/ desktop (default 1440x810) and m/ a 9:16 centre crop for portrait phones (WebP)

py pack.py <png dir> <site frames dir> [quality] [desktop height]"""
import sys
from pathlib import Path

from PIL import Image

src, dst = Path(sys.argv[1]), Path(sys.argv[2])
q = int(sys.argv[3]) if len(sys.argv) > 3 else 48
H = int(sys.argv[4]) if len(sys.argv) > 4 else 810
W = round(H * 16 / 9)
MW = round(H * 0.5625)
(dst / "d").mkdir(parents=True, exist_ok=True)
(dst / "m").mkdir(parents=True, exist_ok=True)
tot = {"d": 0, "m": 0}
files = sorted(src.glob("f[0-9][0-9][0-9].png"))
for p in files:
    out_d, out_m = dst / "d" / f"{p.stem}.webp", dst / "m" / f"{p.stem}.webp"
    if not (out_m.exists() and out_m.stat().st_mtime > p.stat().st_mtime):
        im = Image.open(p).convert("RGB").resize((W, H), Image.LANCZOS)
        im.save(out_d, quality=q, method=6)
        im.crop(((W - MW) // 2, 0, (W - MW) // 2 + MW, H)).save(out_m, quality=q, method=6)
    tot["d"] += out_d.stat().st_size
    tot["m"] += out_m.stat().st_size
print(len(files), "frames", f"{W}x{H}", {k: f"{v / 1e6:.1f} MB" for k, v in tot.items()})

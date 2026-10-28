"""rendered PNG frames -> web frames: d/ 1600x900 and m/ a 506x900 centre crop for portrait phones (WebP)

py pack.py <png dir> <site frames dir> [quality]"""
import sys
from pathlib import Path

from PIL import Image

src, dst = Path(sys.argv[1]), Path(sys.argv[2])
q = int(sys.argv[3]) if len(sys.argv) > 3 else 62
(dst / "d").mkdir(parents=True, exist_ok=True)
(dst / "m").mkdir(parents=True, exist_ok=True)
tot = {"d": 0, "m": 0}
for p in sorted(src.glob("f[0-9][0-9][0-9].png")):
    if (dst / "m" / f"{p.stem}.webp").exists() and (dst / "m" / f"{p.stem}.webp").stat().st_mtime > p.stat().st_mtime:
        for k in tot:
            tot[k] += (dst / k / f"{p.stem}.webp").stat().st_size
        continue
    im = Image.open(p).convert("RGB")
    w, h = im.size
    d = im if (w, h) == (1600, 900) else im.resize((1600, 900), Image.LANCZOS)
    d.save(dst / "d" / f"{p.stem}.webp", quality=q, method=6)
    mw = round(h * 0.5625)
    m = im.crop(((w - mw) // 2, 0, (w - mw) // 2 + mw, h))
    if m.size[1] != 900:
        m = m.resize((round(900 * 0.5625), 900), Image.LANCZOS)
    m.save(dst / "m" / f"{p.stem}.webp", quality=q, method=6)
    for k in tot:
        tot[k] += (dst / k / f"{p.stem}.webp").stat().st_size
n = len(list(src.glob("f[0-9][0-9][0-9].png")))
print(n, "frames", {k: f"{v / 1e6:.1f} MB" for k, v in tot.items()})

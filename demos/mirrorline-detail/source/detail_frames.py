"""Mirrorline scroll frames: the AI-dirtied photo, a dissolve into the foamed photo (the clip's first frame), then the
rinse clip up to the clean car. Desktop 1440x810 and a portrait centre crop for phones.

py detail_frames.py <dirty image> <rinse clip> <out frames dir> <clip seconds to use> <clip fps> <quality>
"""
import subprocess, sys, tempfile
from pathlib import Path
from PIL import Image

dirty, clip, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
secs, fps, q = float(sys.argv[4]), float(sys.argv[5]), int(sys.argv[6])
W, H, FADE, CX = 1440, 810, 14, 0.45  # CX: where the car sits across the frame, for the phone crop
tmp = Path(tempfile.mkdtemp())
subprocess.run(["ffmpeg", "-v", "error", "-i", str(clip), "-t", str(secs), "-vf", f"fps={fps},scale={W}:{H}:flags=lanczos",
                str(tmp / "c%04d.png")], check=True)
clip_frames = [Image.open(p).convert("RGB") for p in sorted(tmp.glob("c*.png"))]
d = Image.open(dirty).convert("RGB").resize((W, H), Image.LANCZOS)
ease = lambda t: t * t * (3 - 2 * t)
seq = [d] + [Image.blend(d, clip_frames[0], ease((k + 1) / (FADE + 1))) for k in range(FADE)] + clip_frames
for s in "dm":
    (out / s).mkdir(parents=True, exist_ok=True)
mw = round(H * 0.5625)
x0 = min(max(round(W * CX - mw / 2), 0), W - mw)
tot = {"d": 0, "m": 0}
for k, im in enumerate(seq):
    pd, pm = out / "d" / f"f{k:03d}.webp", out / "m" / f"f{k:03d}.webp"
    im.save(pd, quality=q, method=6)
    im.crop((x0, 0, x0 + mw, H)).save(pm, quality=q, method=6)
    tot["d"] += pd.stat().st_size; tot["m"] += pm.stat().st_size
print(len(seq), "frames", {k: f"{v / 1e6:.2f} MB" for k, v in tot.items()})

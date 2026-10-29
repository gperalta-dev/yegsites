"""append the interior walk-through (AI video) after the 240 exterior frames: crossfade from the last exterior frame into
the clip (a push-in toward the porch while it dissolves), extract frames with ffmpeg, write desktop (1440x810) and mobile (456x810) WebP, update the demo page.

py add_interior.py <clip.mp4> <last exterior png> <site demo dir> <n frames> <quality> [--fade-only]
--fade-only rewrites just the dissolve frames (after the flight is re-rendered) and leaves the clip frames and the page alone
"""
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

clip, last_png, site, n, q = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5])
EXT = 240
FADE = 14
PORCH = (950 / 1600, 532 / 900)  # the porch in the last exterior frame, as a fraction of the frame
ZOOM = 3.2
tmp = Path(tempfile.mkdtemp())
dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(clip)],
                           capture_output=True, text=True).stdout.strip())
fps = n / dur
subprocess.run(["ffmpeg", "-v", "error", "-i", str(clip), "-vf", f"fps={fps:.5f},scale=1440:810:flags=lanczos", str(tmp / "c%04d.png")],
               check=True)
clip_frames = sorted(tmp.glob("c*.png"))[:n]
last = Image.open(last_png).convert("RGB")
first = Image.open(clip_frames[0]).convert("RGB")


def ease(t):
    return t * t * (3 - 2 * t)


def push(t):
    # crop the exterior frame toward the porch, so the street view seems to walk up to the door as the clip fades in
    W, H = last.size
    z = 1 + (ZOOM - 1) * ease(t)
    w, h = W / z, H / z
    cx = W / 2 + (PORCH[0] * W - W / 2) * ease(t)
    cy = H / 2 + (PORCH[1] * H - H / 2) * ease(t)
    x0 = min(max(cx - w / 2, 0), W - w)
    y0 = min(max(cy - h / 2, 0), H - h)
    return last.crop((round(x0), round(y0), round(x0 + w), round(y0 + h))).resize((1440, 810), Image.LANCZOS)


seq = []
for k in range(FADE):
    t = (k + 1) / (FADE + 1)
    seq.append(Image.blend(push(t), first, ease(min(1, max(0, (t - 0.2) / 0.8)))))
FADE_ONLY = "--fade-only" in sys.argv
if not FADE_ONLY:
    seq += [Image.open(p).convert("RGB") for p in clip_frames]
fd, fm = site / "frames" / "d", site / "frames" / "m"
tot_d = tot_m = 0
for k, im in enumerate(seq):
    name = f"f{EXT + k:03d}.webp"
    im.save(fd / name, quality=q, method=6)
    mw = round(810 * 0.5625)
    im.crop(((1440 - mw) // 2, 0, (1440 - mw) // 2 + mw, 810)).save(fm / name, quality=q, method=6)
    tot_d += (fd / name).stat().st_size
    tot_m += (fm / name).stat().st_size
total = EXT + len(seq)
if FADE_ONLY:
    print("dissolve frames", len(seq), "rewritten, f240 to", f"f{EXT + len(seq) - 1:03d}")
    raise SystemExit(0)
print("interior frames", len(seq), "desktop", round(tot_d / 1e6, 2), "MB mobile", round(tot_m / 1e6, 2), "MB; total frames", total)

# page: more frames, a sixth chapter, story height grows with the frame count so the first five beats keep their pace
page = site / "index.html"
s = page.read_text(encoding="utf-8")
scale = EXT / total
s = re.sub(r"const COUNT = \d+", f"const COUNT = {total}", s)
s = s.replace(".story { position: relative; height: 640vh; }", f".story {{ position: relative; height: {round(640 * total / EXT)}vh; }}")


def rescale(m):
    a, b = float(m.group(1)), float(m.group(2))
    return f'data-from="{a * scale:.3f}" data-to="{(b * scale if b <= 1 else scale - 0.004):.3f}"'


chap = re.findall(r'data-from="([\d.]+)" data-to="([\d.]+)"', s)
if len(chap) == 5:  # only rescale the original five once
    s = re.sub(r'data-from="([\d.]+)" data-to="([\d.]+)"', rescale, s)
    six = (f'      <div class="ch" data-from="{scale + 0.03:.3f}" data-to="1.01"><small>Sample interior, made with AI</small>'
           f'<h2>Step inside.</h2><p>The entry, the living room and the kitchen. This interior was generated with AI from our '
           f'render of the front door. It is not a real home.</p><a class="btn btn-main" href="#showing">Book a showing</a></div>\n')
    s = s.replace('    </div>\n  </div>\n</div>\n\n<section id="listing">', six + '    </div>\n  </div>\n</div>\n\n<section id="listing">', 1)
    s = s.replace('Poly Haven</a> (CC0).</span>', 'Poly Haven</a> (CC0). Interior walk-through generated with Google Veo from '
                                                  'our render of the front door.</span>')
for a, b in [
    ('  // portrait screens get a lighter centre-cropped set (506x900), wider screens the 1600x900 set',
     '  // portrait screens get a lighter centre-cropped set (456x810), wider screens the 1440x810 set.\n  // frames 0-239 are the rendered flight, 240 on the AI walk inside'),
    ('    want = COUNT - 1;\n    load(COUNT - 1);',
     '    want = 239;  // reduced motion keeps the house, the last rendered frame\n    load(239);'),
]:
    s = s.replace(a, b, 1)
page.write_text(s, encoding="utf-8")
print("page updated, story height", round(640 * total / EXT), "vh")

"""append the interior walk-through (AI video) after the 240 exterior frames: crossfade from the last exterior frame into
the clip, extract frames with ffmpeg, write desktop (1600x900) and mobile (506x900) WebP, update the demo page.

py add_interior.py <clip.mp4> <last exterior png> <site demo dir> <n frames> <quality>
"""
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

clip, last_png, site, n, q = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5])
EXT = 240
FADE = 10
tmp = Path(tempfile.mkdtemp())
dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(clip)],
                           capture_output=True, text=True).stdout.strip())
fps = n / dur
subprocess.run(["ffmpeg", "-v", "error", "-i", str(clip), "-vf", f"fps={fps:.5f},scale=1600:900:flags=lanczos", str(tmp / "c%04d.png")],
               check=True)
clip_frames = sorted(tmp.glob("c*.png"))[:n]
last = Image.open(last_png).convert("RGB").resize((1600, 900), Image.LANCZOS)
first = Image.open(clip_frames[0]).convert("RGB")
seq = [Image.blend(last, first, (k + 1) / (FADE + 1)) for k in range(FADE)]
seq += [Image.open(p).convert("RGB") for p in clip_frames]
fd, fm = site / "frames" / "d", site / "frames" / "m"
tot_d = tot_m = 0
for k, im in enumerate(seq):
    name = f"f{EXT + k:03d}.webp"
    im.save(fd / name, quality=q, method=6)
    mw = round(900 * 0.5625)
    im.crop(((1600 - mw) // 2, 0, (1600 - mw) // 2 + mw, 900)).save(fm / name, quality=q, method=6)
    tot_d += (fd / name).stat().st_size
    tot_m += (fm / name).stat().st_size
total = EXT + len(seq)
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
page.write_text(s, encoding="utf-8")
print("page updated, story height", round(640 * total / EXT), "vh")

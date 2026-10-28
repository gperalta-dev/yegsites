"""append another walk-through clip (one that starts on the previous clip's last frame) to the realty demo frames,
then rescale the chapters and add one for the new rooms.

py add_interior_more.py <clip.mp4> <site demo dir> <n frames> <quality> "<chapter title>" "<chapter text>"
"""
import re, subprocess, sys, tempfile
from pathlib import Path
from PIL import Image

clip, site, n, q, title, text = Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), sys.argv[5], sys.argv[6]
fd, fm = site / "frames" / "d", site / "frames" / "m"
old = len(list(fd.glob("f*.webp")))
dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(clip)],
                           capture_output=True, text=True).stdout.strip())
tmp = Path(tempfile.mkdtemp())
# skip the clip's first frame: it is the previous clip's last frame again
subprocess.run(["ffmpeg", "-v", "error", "-i", str(clip), "-vf", f"fps={n / dur:.5f},scale=1440:810:flags=lanczos", str(tmp / "c%04d.png")], check=True)
frames = sorted(tmp.glob("c*.png"))[1:n + 1]
mw = round(810 * 0.5625)
tot = [0, 0]
for k, p in enumerate(frames):
    im = Image.open(p).convert("RGB")
    name = f"f{old + k:03d}.webp"
    im.save(fd / name, quality=q, method=6)
    im.crop(((1440 - mw) // 2, 0, (1440 - mw) // 2 + mw, 810)).save(fm / name, quality=q, method=6)
    tot[0] += (fd / name).stat().st_size; tot[1] += (fm / name).stat().st_size
new = old + len(frames)
print("added", len(frames), "frames", round(tot[0] / 1e6, 2), "MB desktop", round(tot[1] / 1e6, 2), "MB mobile; total", new)

page = site / "index.html"
s = page.read_text(encoding="utf-8")
scale = old / new
s = re.sub(r"const COUNT = \d+", f"const COUNT = {new}", s)
s = re.sub(r"\.story \{ position: relative; height: (\d+)vh; \}", lambda m: f".story {{ position: relative; height: {round(int(m.group(1)) * new / old)}vh; }}", s)
s = re.sub(r'data-from="([\d.]+)" data-to="([\d.]+)"',
           lambda m: f'data-from="{float(m.group(1)) * scale:.3f}" data-to="{(float(m.group(2)) * scale if float(m.group(2)) <= 1 else scale - 0.004):.3f}"', s)
ch = (f'      <div class="ch" data-from="{scale + 0.02:.3f}" data-to="1.01"><small>Sample interior, made with AI</small>'
      f'<h2>{title}</h2><p>{text}</p><a class="btn btn-main" href="#showing">Book a showing</a></div>\n')
s = s.replace('    </div>\n  </div>\n</div>\n\n<section id="listing">', ch + '    </div>\n  </div>\n</div>\n\n<section id="listing">', 1)
page.write_text(s, encoding="utf-8")
print("page: COUNT", new)

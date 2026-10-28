"""land-cover colour map and tree positions for the city, from geo/out/city.json + dem.npy (system python).

writes landcover.png (2 m per pixel over the DEM frame) and trees.npy rows (x, y, z, kind, scale, rot).
kinds: 0 broadleaf, 1 spruce, 2 small broadleaf. the fictional suburb disk (SUBURB) is left open for its own layout.
"""
import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

G = Path(sys.argv[1])
SUBURB = (float(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4]))  # cx, cy, radius
city = json.load(open(G / "city.json"))
dm = json.load(open(G / "dem.json"))
dem = np.load(G / "dem.npy")
X0, Y0, ST = dm["x0"], dm["y0"], dm["step"]
X1, Y1 = X0 + (dm["nx"] - 1) * ST, Y0 + (dm["ny"] - 1) * ST
RES = 2.0
W, H = int((X1 - X0) / RES), int((Y1 - Y0) / RES)
P = lambda x, y: ((x - X0) / RES, (Y1 - y) / RES)
rng = np.random.default_rng(7)

img = Image.new("RGB", (W, H), (92, 102, 62))
dr = ImageDraw.Draw(img)
mask = Image.new("L", (W, H), 0)  # 1 forest, 2 park, 3 road, 4 water, 5 building, 6 urban paved
md = ImageDraw.Draw(mask)
# downtown core is paved between buildings
for x0, y0, x1, y1 in ((-350, 350, 1350, 1750), (1300, 950, 1900, 1500)):
    dr.rectangle([P(x0, y1), P(x1, y0)], fill=(112, 110, 106))
    md.rectangle([P(x0, y1), P(x1, y0)], fill=6)
for l in city["land"]:
    pts = [P(*q) for q in l["r"]]
    if l["kind"] in ("wood", "forest", "scrub"):
        dr.polygon(pts, fill=(48, 58, 30))
        md.polygon(pts, fill=1)
for l in city["land"]:
    pts = [P(*q) for q in l["r"]]
    if l["kind"] in ("park", "golf_course", "grass", "recreation_ground", "cemetery", "meadow", "pitch", "grassland"):
        dr.polygon(pts, fill=(74, 104, 44))
        md.polygon(pts, fill=2)
for l in city["land"]:  # woods inside parks stay woods
    pts = [P(*q) for q in l["r"]]
    if l["kind"] in ("wood", "forest", "scrub"):
        dr.polygon(pts, fill=(48, 58, 30))
        md.polygon(pts, fill=1)
WID = {"motorway": 24, "trunk": 22, "primary": 18, "secondary": 15, "tertiary": 12, "residential": 9, "unclassified": 8,
       "living_street": 7, "service": 5, "footway": 2.2, "cycleway": 2.5, "path": 1.8}
for r in sorted(city["roads"], key=lambda r: WID.get(r["hw"], 4)):
    if r["tunnel"]:
        continue
    w = WID.get(r["hw"], 4) / RES
    col = (150, 147, 138) if r["hw"] in ("footway", "path", "cycleway") else (62, 62, 64)
    if r["hw"] == "path":
        col = (120, 110, 90)
    pts = [P(*q) for q in r["p"]]
    dr.line(pts, fill=col, width=max(1, int(round(w))), joint="curve")
    if r["hw"] not in ("footway", "path", "cycleway"):
        md.line(pts, fill=3, width=max(1, int(round(w + 2))))
for wpoly in city["water"]:
    pts = [P(*q) for q in wpoly]
    dr.polygon(pts, fill=(28, 36, 40))
    md.polygon(pts, fill=4)
bm = Image.new("L", (W, H), 0)
bd = ImageDraw.Draw(bm)
cx, cy, cr = SUBURB
for b in city["buildings"]:
    bx = sum(q[0] for q in b["r"]) / len(b["r"])
    by = sum(q[1] for q in b["r"]) / len(b["r"])
    if math.hypot(bx - cx, by - cy) < cr:
        continue
    bd.polygon([P(*q) for q in b["r"]], fill=255)
bm = bm.filter(ImageFilter.MaxFilter(3))
# the suburb disk: lawn colour, its streets are modelled
dr.ellipse([P(cx - cr, cy + cr), P(cx + cr, cy - cr)], fill=(56, 74, 36))
img.save(G / "landcover.png")
print("landcover", img.size)

M = np.asarray(mask)
B = np.asarray(bm) > 0


def ok(x, y):
    i, j = int((Y1 - y) / RES), int((x - X0) / RES)
    if i < 0 or j < 0 or i >= H or j >= W:
        return False
    return not B[i, j] and M[i, j] not in (3, 4) and math.hypot(x - cx, y - cy) > cr - 15


def zat(x, y):
    fx, fy = (x - X0) / ST, (y - Y0) / ST
    i, j = int(fy), int(fx)
    i, j = max(0, min(dem.shape[0] - 2, i)), max(0, min(dem.shape[1] - 2, j))
    a, b = fx - j, fy - i
    return float(dem[i, j] * (1 - a) * (1 - b) + dem[i, j + 1] * a * (1 - b) + dem[i + 1, j] * (1 - a) * b + dem[i + 1, j + 1] * a * b)


trees = []
# forests: jittered grid, about one tree per 42 m2
step = 6.5
ys, xs = np.mgrid[Y0:Y1:step, X0:X1:step]
xs = xs + rng.uniform(-step / 2, step / 2, xs.shape)
ys = ys + rng.uniform(-step / 2, step / 2, ys.shape)
for x, y in zip(xs.ravel(), ys.ravel()):
    i, j = int((Y1 - y) / RES), int((x - X0) / RES)
    if not (0 <= i < H and 0 <= j < W):
        continue
    m = M[i, j]
    if m == 1 and ok(x, y):
        r = rng.random()
        kind = 0 if r < 0.62 else (1 if r < 0.85 else 2)
        trees.append((x, y, kind))
    elif m == 2 and rng.random() < 0.06 and ok(x, y):
        trees.append((x, y, 0 if rng.random() < 0.7 else 1))
# back-yard trees in the old neighbourhoods (base land cover, away from roads and roofs)
for x, y in zip(xs.ravel()[::3], ys.ravel()[::3]):
    i, j = int((Y1 - y) / RES), int((x - X0) / RES)
    if 0 <= i < H and 0 <= j < W and M[i, j] == 0 and rng.random() < 0.42 and ok(x, y):
        trees.append((x, y, 0 if rng.random() < 0.75 else (1 if rng.random() < 0.6 else 2)))
# street trees in residential areas: both sides, in the boulevard or front yard
for r in city["roads"]:
    if r["hw"] not in ("residential", "tertiary", "unclassified", "living_street"):
        continue
    pts = r["p"]
    for (ax, ay), (bx, by) in zip(pts, pts[1:]):
        L = math.hypot(bx - ax, by - ay)
        if L < 1:
            continue
        tx, ty = (bx - ax) / L, (by - ay) / L
        s = rng.uniform(0, 10)
        while s < L:
            for side in (1, -1):
                if rng.random() < 0.72:
                    off = rng.uniform(7.0, 9.5) * side
                    x, y = ax + tx * s - ty * off, ay + ty * s + tx * off
                    if ok(x, y) and M[int((Y1 - y) / RES), int((x - X0) / RES)] != 6:
                        trees.append((x, y, 0 if rng.random() < 0.85 else 1))
            s += rng.uniform(9, 13)
# a planted belt around the suburb so the old grid and the new streets do not meet edge to edge
for k in range(int(2 * math.pi * cr / 7)):
    a = k * 7 / cr
    for ring in (cr + 8, cr + 18):
        x, y = cx + ring * math.cos(a) + rng.uniform(-3, 3), cy + ring * math.sin(a) + rng.uniform(-3, 3)
        if ok(x, y) and rng.random() < 0.8:
            trees.append((x, y, 0 if rng.random() < 0.6 else 1))
arr = np.zeros((len(trees), 6), np.float32)
for n, (x, y, kind) in enumerate(trees):
    sc = {0: rng.uniform(2.1, 3.4), 1: rng.uniform(1.5, 2.5), 2: rng.uniform(1.8, 2.8)}[kind]
    arr[n] = (x, y, zat(x, y), kind, sc, rng.uniform(0, 2 * math.pi))
np.save(G / "trees.npy", arr)
print("trees", len(arr), "by kind", np.bincount(arr[:, 3].astype(int)))

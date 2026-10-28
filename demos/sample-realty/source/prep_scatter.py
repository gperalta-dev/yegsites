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

img = Image.new("RGB", (W, H), (96, 96, 62))
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
        dr.polygon(pts, fill=(62, 54, 33))
        md.polygon(pts, fill=1)
for l in city["land"]:
    pts = [P(*q) for q in l["r"]]
    if l["kind"] in ("park", "golf_course", "grass", "recreation_ground", "cemetery", "meadow", "pitch", "grassland"):
        dr.polygon(pts, fill=(90, 98, 52))
        md.polygon(pts, fill=2)
for l in city["land"]:  # woods inside parks stay woods
    pts = [P(*q) for q in l["r"]]
    if l["kind"] in ("wood", "forest", "scrub"):
        dr.polygon(pts, fill=(62, 54, 33))
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
dr.ellipse([P(cx - cr, cy + cr), P(cx + cr, cy - cr)], fill=(80, 90, 48))
img.save(G / "landcover.png")
np.save(G / "landmask.npy", np.asarray(mask)[::2, ::2])  # 4 m per cell, 4 = water
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


def value_noise(x, y, cell, seed):
    """smooth value noise in [0, 1] over map metres, for stands, gaps and ages"""
    r = np.random.default_rng(seed)
    gw, gh = int((X1 - X0) / cell) + 3, int((Y1 - Y0) / cell) + 3
    grid = r.random((gh, gw))
    fx, fy = (np.asarray(x) - X0) / cell, (np.asarray(y) - Y0) / cell
    j, i = np.floor(fx).astype(int).clip(0, gw - 2), np.floor(fy).astype(int).clip(0, gh - 2)
    a, b = fx - j, fy - i
    a, b = a * a * (3 - 2 * a), b * b * (3 - 2 * b)
    return (grid[i, j] * (1 - a) * (1 - b) + grid[i, j + 1] * a * (1 - b) + grid[i + 1, j] * (1 - a) * b +
            grid[i + 1, j + 1] * a * b)


def fbm(x, y, cell, seed):
    return 0.55 * value_noise(x, y, cell, seed) + 0.3 * value_noise(x, y, cell / 2.7, seed + 1) + \
        0.15 * value_noise(x, y, cell / 7.0, seed + 2)


# terrain slope: spruce holds the cool north-facing valley walls, aspen the sunny ones, poplar and ash the river flats
gy_, gx_ = np.gradient(dem, ST)


def aspect_north(x, y):
    j = np.clip(((np.asarray(x) - X0) / ST).astype(int), 0, dem.shape[1] - 1)
    i = np.clip(((np.asarray(y) - Y0) / ST).astype(int), 0, dem.shape[0] - 1)
    return np.clip(-gy_[i, j] * 6.0, 0, 1), np.hypot(gx_[i, j], gy_[i, j]), dem[i, j]


# forests: a fine jittered grid thinned by layered noise, so trees stand in clumps with glades between
step = 5.2
ys, xs = np.mgrid[Y0:Y1:step, X0:X1:step]
xs = (xs + rng.uniform(-step / 2, step / 2, xs.shape)).ravel()
ys = (ys + rng.uniform(-step / 2, step / 2, ys.shape)).ravel()
ii = ((Y1 - ys) / RES).astype(int)
jj = ((xs - X0) / RES).astype(int)
inb = (ii >= 0) & (ii < H) & (jj >= 0) & (jj < W)
xs, ys, ii, jj = xs[inb], ys[inb], ii[inb], jj[inb]
mk = M[ii, jj]
dens = fbm(xs, ys, 240.0, 11)
stand = fbm(xs, ys, 160.0, 21)
age = fbm(xs, ys, 110.0, 31)
north, slope, elev = aspect_north(xs, ys)
keep_p = np.clip((dens - 0.28) / 0.3, 0, 1) * 0.92 + 0.05
pick = rng.random(len(xs))
for n in np.nonzero(mk == 1)[0]:
    x, y = float(xs[n]), float(ys[n])
    if pick[n] > keep_p[n] or not ok(x, y):
        continue
    spruce_p = np.clip(0.12 + 0.6 * north[n] + 0.45 * (stand[n] - 0.5), 0.02, 0.85)
    young = age[n] < 0.33
    if rng.random() < spruce_p:
        kind = 4 if (young and rng.random() < 0.7) else 1
    elif elev[n] < 626 and rng.random() < 0.55:
        kind = 3
    else:
        r = rng.random()
        kind = 0 if r < 0.62 else (2 if r < 0.8 else 3)
    trees.append((x, y, kind, 0.65 + 0.55 * float(age[n])))
# park trees: scattered, a little clumped
for n in np.nonzero(mk == 2)[0]:
    x, y = float(xs[n]), float(ys[n])
    if rng.random() < 0.045 * (0.4 + dens[n]) and ok(x, y):
        r = rng.random()
        trees.append((x, y, 0 if r < 0.45 else (3 if r < 0.7 else (1 if r < 0.88 else 2)), 0.8 + 0.35 * float(age[n])))
# back-yard trees in the old neighbourhoods (base land cover, away from roads and roofs)
for n in np.nonzero(mk == 0)[0][::3]:
    x, y = float(xs[n]), float(ys[n])
    if rng.random() < 0.42 and ok(x, y):
        r = rng.random()
        trees.append((x, y, 0 if r < 0.5 else (3 if r < 0.7 else (1 if r < 0.88 else 2)), 0.8 + 0.4 * float(age[n])))
# street trees in residential areas: both sides, in the boulevard or front yard; elm, ash and some spruce
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
                        q = rng.random()
                        trees.append((x, y, 0 if q < 0.55 else (3 if q < 0.85 else 1), rng.uniform(0.85, 1.15)))
            s += rng.uniform(9, 13)
# a planted belt around the suburb so the old grid and the new streets do not meet edge to edge
for k in range(int(2 * math.pi * cr / 7)):
    a = k * 7 / cr
    for ring in (cr + 8, cr + 18):
        x, y = cx + ring * math.cos(a) + rng.uniform(-3, 3), cy + ring * math.sin(a) + rng.uniform(-3, 3)
        if ok(x, y) and rng.random() < 0.8:
            trees.append((x, y, 0 if rng.random() < 0.6 else 1, 1.0))
arr = np.zeros((len(trees), 6), np.float32)
BASE = {0: (2.3, 3.8), 1: (1.5, 2.6), 2: (2.0, 3.2), 3: (0.55, 0.95), 4: (3.5, 8.0)}
for n, (x, y, kind, ag) in enumerate(trees):
    lo, hi = BASE[kind]
    sc = rng.uniform(lo, hi) * (ag if kind != 4 else 1.0)
    arr[n] = (x, y, zat(x, y), kind, sc, rng.uniform(0, 2 * math.pi))
np.save(G / "trees.npy", arr)
print("trees", len(arr), "by kind", np.bincount(arr[:, 3].astype(int)))

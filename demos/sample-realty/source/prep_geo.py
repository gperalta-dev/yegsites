"""OSM + terrain tiles -> local metres (x east, y north, origin ORIGIN) for Blender. run with the system python (PIL, numpy).

writes geo/city.json (buildings with height, roads, water, parks, bridges) and geo/dem.npy (+ dem.json with its frame)
and an overview png to plan the camera path.
"""
import json
import math
import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

SRC = Path(sys.argv[1])
OUT = Path(sys.argv[2])
OUT.mkdir(parents=True, exist_ok=True)
LAT0, LON0 = 53.5300, -113.5050
KX = 111320.0 * math.cos(math.radians(LAT0))
KY = 110574.0


def xy(lat, lon):
    return ((lon - LON0) * KX, (lat - LAT0) * KY)


def num(v):
    m = re.match(r"[\d.]+", str(v or "").strip())
    return float(m.group()) if m else None


def rings(el):
    """outer rings of a way or multipolygon relation, as lists of (x, y)"""
    if el["type"] == "way" and "geometry" in el:
        return [[xy(p["lat"], p["lon"]) for p in el["geometry"]]]
    out = []
    if el["type"] == "relation":
        segs = [[xy(p["lat"], p["lon"]) for p in m["geometry"]] for m in el.get("members", []) if m.get("role") == "outer" and "geometry" in m]
        # stitch member ways into closed rings
        while segs:
            ring = segs.pop(0)
            changed = True
            while changed and (abs(ring[0][0] - ring[-1][0]) > 0.5 or abs(ring[0][1] - ring[-1][1]) > 0.5):
                changed = False
                for i, s in enumerate(segs):
                    if math.dist(ring[-1], s[0]) < 0.5:
                        ring += s[1:]
                    elif math.dist(ring[-1], s[-1]) < 0.5:
                        ring += s[::-1][1:]
                    elif math.dist(ring[0], s[-1]) < 0.5:
                        ring = s[:-1] + ring
                    elif math.dist(ring[0], s[0]) < 0.5:
                        ring = s[::-1][:-1] + ring
                    else:
                        continue
                    segs.pop(i)
                    changed = True
                    break
            out.append(ring)
    return out


def area(r):
    return 0.5 * sum(r[i][0] * r[(i + 1) % len(r)][1] - r[(i + 1) % len(r)][0] * r[i][1] for i in range(len(r)))


def inside(pt, r):
    x, y = pt
    c = False
    for i in range(len(r)):
        x1, y1 = r[i]
        x2, y2 = r[(i + 1) % len(r)]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1 + 1e-12) + x1:
            c = not c
    return c


DEFAULT_H = {"house": 7.0, "detached": 7.0, "garage": 3.0, "garages": 3.0, "shed": 2.5, "apartments": 13.0, "residential": 10.0,
             "retail": 6.0, "commercial": 9.0, "office": 15.0, "school": 9.0, "university": 16.0, "church": 12.0,
             "industrial": 9.0, "hospital": 20.0, "hotel": 30.0, "terrace": 8.0, "semidetached_house": 7.0, "roof": 0.0,
             "parking": 10.0, "civic": 12.0, "government": 14.0, "public": 10.0}

els = json.load(open(SRC / "buildings.json"))["elements"]
outlines, parts = [], []
for e in els:
    t = e.get("tags", {})
    for r in rings(e):
        if len(r) < 4:
            continue
        if area(r) < 0:
            r = r[::-1]
        a = area(r)
        if a < 6:
            continue
        kind = t.get("building") or "part"
        h = num(t.get("height"))
        lv = num(t.get("building:levels"))
        if h is None and lv is not None:
            h = lv * 3.4 + (1.5 if lv > 3 else 1.0)
        mh = num(t.get("min_height")) or ((num(t.get("building:min_level")) or 0) * 3.4)
        rec = dict(r=[(round(x, 2), round(y, 2)) for x, y in r[:-1] if True], h=h, mh=mh, kind=kind, a=a,
                   name=t.get("name"), roof=t.get("roof:shape"), mat=t.get("building:material") or t.get("building:facade:material"),
                   col=t.get("building:colour"), id=e["id"])
        (parts if "building:part" in t else outlines).append(rec)
# outlines that hold parts are replaced by their parts
for o in outlines:
    o["bb"] = (min(p[0] for p in o["r"]), min(p[1] for p in o["r"]), max(p[0] for p in o["r"]), max(p[1] for p in o["r"]))
skip = set()
for p in parts:
    cx = sum(q[0] for q in p["r"]) / len(p["r"])
    cy = sum(q[1] for q in p["r"]) / len(p["r"])
    for o in outlines:
        b = o["bb"]
        if b[0] <= cx <= b[2] and b[1] <= cy <= b[3] and o["a"] > p["a"] * 0.9 and inside((cx, cy), o["r"]):
            skip.add(o["id"])
buildings = []
for o in outlines:
    if o["id"] in skip or o["kind"] == "roof":
        continue
    if o["h"] is None:
        o["h"] = DEFAULT_H.get(o["kind"], 6.5 if o["a"] < 250 else 9.0)
        o["guess"] = True
    o.pop("bb")
    buildings.append(o)
for p in parts:
    if p["h"] is None:
        continue
    buildings.append(p)
print("buildings", len(buildings), "skipped outlines with parts", len(skip))

roads = []
for e in json.load(open(SRC / "roads.json"))["elements"]:
    t = e.get("tags", {})
    if "geometry" not in e:
        continue
    roads.append(dict(p=[(round(x, 1), round(y, 1)) for x, y in (xy(q["lat"], q["lon"]) for q in e["geometry"])], hw=t.get("highway"),
                      bridge=t.get("bridge") is not None, tunnel=t.get("tunnel") is not None, lanes=num(t.get("lanes"))))
water = []
for e in json.load(open(SRC / "water.json"))["elements"]:
    t = e.get("tags", {})
    if t.get("waterway") == "river":
        continue
    for r in rings(e):
        if len(r) > 3:
            water.append([(round(x, 1), round(y, 1)) for x, y in r])
land = []
for e in json.load(open(SRC / "land.json"))["elements"]:
    t = e.get("tags", {})
    kind = t.get("natural") or t.get("landuse") or t.get("leisure")
    for r in rings(e):
        if len(r) > 3:
            land.append(dict(kind=kind, r=[(round(x, 1), round(y, 1)) for x, y in r]))
bridges = []
for e in json.load(open(SRC / "bridges.json"))["elements"]:
    t = e.get("tags", {})
    if "geometry" in e:
        bridges.append(dict(name=t.get("name"), p=[xy(q["lat"], q["lon"]) for q in e["geometry"]], hw=t.get("highway"),
                            rail=t.get("railway"), layer=num(t.get("layer"))))
json.dump(dict(origin=[LAT0, LON0], buildings=buildings, roads=roads, water=water, land=land, bridges=bridges),
          open(OUT / "city.json", "w"))

# terrain: stitch terrarium tiles, then resample to a local metre grid
tiles = sorted((SRC / "terrain").glob("14_*.png"))
tx = sorted({int(p.stem.split("_")[1]) for p in tiles})
ty = sorted({int(p.stem.split("_")[2]) for p in tiles})
big = np.zeros((len(ty) * 256, len(tx) * 256), np.float32)
for p in tiles:
    _, a, b = p.stem.split("_")
    im = np.asarray(Image.open(p).convert("RGB")).astype(np.float32)
    h = im[..., 0] * 256 + im[..., 1] + im[..., 2] / 256 - 32768
    i, j = ty.index(int(b)), tx.index(int(a))
    big[i * 256:(i + 1) * 256, j * 256:(j + 1) * 256] = h
n = 2 ** 14


def merc(lat, lon):
    return ((lon + 180) / 360 * n - tx[0]) * 256, ((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n - ty[0]) * 256


STEP = 8.0
X0, X1, Y0, Y1 = -4200.0, 4200.0, -3400.0, 3600.0
gx = np.arange(X0, X1 + 1, STEP)
gy = np.arange(Y0, Y1 + 1, STEP)
dem = np.zeros((len(gy), len(gx)), np.float32)
for j, y in enumerate(gy):
    lat = LAT0 + y / KY
    for i, x in enumerate(gx):
        lon = LON0 + x / KX
        px, py = merc(lat, lon)
        x0, y0 = int(px), int(py)
        fx, fy = px - x0, py - y0
        v = (big[y0, x0] * (1 - fx) * (1 - fy) + big[y0, x0 + 1] * fx * (1 - fy) + big[y0 + 1, x0] * (1 - fx) * fy + big[y0 + 1, x0 + 1] * fx * fy)
        dem[j, i] = v
np.save(OUT / "dem.npy", dem)
json.dump(dict(x0=X0, y0=Y0, step=STEP, nx=len(gx), ny=len(gy)), open(OUT / "dem.json", "w"))
print("dem", dem.shape, "elev", round(float(dem.min()), 1), round(float(dem.max()), 1))

# overview map, 1 px = 4 m
S = 4.0
W_, H_ = int((X1 - X0) / S), int((Y1 - Y0) / S)
d8 = ((dem - dem.min()) / (dem.max() - dem.min()) * 200 + 30).astype(np.uint8)
ov = Image.fromarray(d8[::-1]).resize((W_, H_)).convert("RGB")
dr = ImageDraw.Draw(ov)
P = lambda x, y: ((x - X0) / S, (Y1 - y) / S)
for l in land:
    if l["kind"] in ("wood", "forest", "scrub"):
        dr.polygon([P(*q) for q in l["r"]], fill=(40, 110, 40))
    elif l["kind"] in ("park", "golf_course", "grass", "recreation_ground"):
        dr.polygon([P(*q) for q in l["r"]], outline=(90, 170, 90))
for w in water:
    dr.polygon([P(*q) for q in w], fill=(60, 90, 200))
for r in roads:
    if r["hw"] in ("motorway", "trunk", "primary", "secondary", "tertiary", "residential"):
        dr.line([P(*q) for q in r["p"]], fill=(230, 230, 230) if r["hw"] != "residential" else (170, 170, 170), width=1)
for b in buildings:
    col = (255, 60, 60) if b["h"] > 40 else ((255, 170, 60) if b["h"] > 15 else (120, 120, 120))
    dr.polygon([P(*q) for q in b["r"]], fill=col)
for k in range(-4000, 4001, 1000):
    dr.line([P(k, Y0), P(k, Y1)], fill=(255, 255, 0))
    dr.line([P(X0, k), P(X1, k)], fill=(255, 255, 0))
    dr.text(P(k + 10, Y1 - 10), str(k), fill=(255, 255, 0))
    dr.text(P(X0 + 10, k + 30), str(k), fill=(255, 255, 0))
ov.save(OUT / "overview.png")
print("overview", ov.size)

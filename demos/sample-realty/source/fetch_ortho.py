"""City of Edmonton 2024 orthophoto (7.5 cm, Sept-Oct 2024, Open Government Licence - City of Edmonton), via the Data for
Canada PMTiles mirror, read with HTTP range requests: only the tiles we need, at two zoom levels.

writes geo/ortho/{lo,hi}_<i>_<j>.jpg, 1024 px pieces resampled onto the local metre frame of dem.json, and ortho.json
py fetch_ortho.py <geo/out dir>
"""
import concurrent.futures as cf
import gzip
import io
import json
import math
import sys
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image

G = Path(sys.argv[1])
OUT = G / "ortho"
OUT.mkdir(exist_ok=True)
CACHE = G / "ortho_tiles"
CACHE.mkdir(exist_ok=True)
URL = ("https://data.source.coop/dataforcanada/d4c-datapkg-orthoimagery/processed/"
       "ca-ab_edmonton-2024A00054811061_d4c-datapkg-orthoimagery_2024_075mm_v0.1.0-beta.pmtiles")
UA = {"User-Agent": "WhyteWebDemo/1.0"}
LAT0, LON0 = 53.5300, -113.5050
KX = 111320.0 * math.cos(math.radians(LAT0))
KY = 110574.0
dm = json.load(open(G / "dem.json"))
FX0, FY0 = dm["x0"], dm["y0"]
FX1, FY1 = FX0 + (dm["nx"] - 1) * dm["step"], FY0 + (dm["ny"] - 1) * dm["step"]
LEVELS = [("lo", 15, (FX0, FY0, FX1, FY1)), ("hi", 16, (-1300.0, -2400.0, 1300.0, 1800.0))]
TS = 512  # this archive stores 512 px tiles


def rng_get(off, length):
    req = urllib.request.Request(URL, headers={**UA, "Range": f"bytes={off}-{off + length - 1}"})
    for attempt in range(4):
        try:
            return urllib.request.urlopen(req, timeout=60).read()
        except Exception:
            if attempt == 3:
                raise


def varint(b, i):
    r = s = 0
    while True:
        c = b[i]
        i += 1
        r |= (c & 0x7F) << s
        if c < 0x80:
            return r, i
        s += 7


def directory(raw):
    b = gzip.decompress(raw)
    n, i = varint(b, 0)
    ids, runs, lens, offs = [], [], [], []
    last = 0
    for _ in range(n):
        d, i = varint(b, i)
        last += d
        ids.append(last)
    for _ in range(n):
        v, i = varint(b, i)
        runs.append(v)
    for _ in range(n):
        v, i = varint(b, i)
        lens.append(v)
    for k in range(n):
        v, i = varint(b, i)
        offs.append(offs[k - 1] + lens[k - 1] if (v == 0 and k > 0) else v - 1)
    return list(zip(ids, runs, lens, offs))


def zxy_to_id(z, x, y):
    acc = sum(4 ** k for k in range(z))
    n = 1 << z
    d = 0
    s = n // 2
    while s > 0:
        rx = 1 if (x & s) > 0 else 0
        ry = 1 if (y & s) > 0 else 0
        d += s * s * ((3 * rx) ^ ry)
        if ry == 0:
            if rx == 1:
                x, y = s - 1 - x, s - 1 - y
            x, y = y, x
        s //= 2
    return acc + d


hdr = rng_get(0, 127)
import struct
root_off, root_len, _, _, leaf_off, leaf_len, data_off = struct.unpack("<7Q", hdr[8:64])
root = directory(rng_get(root_off, root_len))
leaf_blob = rng_get(leaf_off, leaf_len)
print("root entries", len(root), "leaf bytes", len(leaf_blob), flush=True)


def find(tid, entries):
    lo, hi = 0, len(entries) - 1
    while lo <= hi:
        m = (lo + hi) // 2
        e = entries[m]
        if tid < e[0]:
            hi = m - 1
        elif e[1] > 0 and tid < e[0] + e[1]:
            return e
        elif e[1] == 0 and tid == e[0]:
            return e
        else:
            lo = m + 1
    if hi >= 0 and entries[hi][1] == 0 and entries[hi][0] <= tid:
        return entries[hi]  # leaf pointer covering this range
    return None


leaf_cache = {}


def locate(z, x, y):
    tid = zxy_to_id(z, x, y)
    entries = root
    for _ in range(4):
        e = find(tid, entries)
        if e is None:
            return None
        if e[1] > 0:
            return data_off + e[3], e[2]
        key = e[3]
        if key not in leaf_cache:
            leaf_cache[key] = directory(leaf_blob[e[3]:e[3] + e[2]])
        entries = leaf_cache[key]
    return None


def tile_xy(lat, lon, z):
    n = 2 ** z
    return (lon + 180) / 360 * n, (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n


def fetch_tile(z, x, y):
    p = CACHE / f"{z}_{x}_{y}.webp"
    if p.exists():
        return p
    loc = locate(z, x, y)
    if loc is None:
        return None
    p.write_bytes(rng_get(*loc))
    return p


index = {"source": "City of Edmonton Orthophoto Repository 2024 (7.5 cm, Sept-Oct 2024) via Data for Canada PMTiles",
         "levels": []}
for name, z, (x0, y0, x1, y1) in LEVELS:
    lat_a, lat_b = LAT0 + y0 / KY, LAT0 + y1 / KY
    lon_a, lon_b = LON0 + x0 / KX, LON0 + x1 / KX
    tx0, ty0 = tile_xy(lat_b, lon_a, z)
    tx1, ty1 = tile_xy(lat_a, lon_b, z)
    xs, ys = range(int(tx0), int(tx1) + 1), range(int(ty0), int(ty1) + 1)
    jobs = [(z, x, y) for x in xs for y in ys]
    # locate every tile first, then fetch them in merged byte ranges (tiles are stored in Hilbert order)
    locs = {}
    for job in jobs:
        if not (CACHE / f"{job[0]}_{job[1]}_{job[2]}.webp").exists():
            loc = locate(*job)
            if loc is not None:
                locs[job] = loc
    order = sorted(locs.items(), key=lambda kv: kv[1][0])
    chunks, cur = [], []
    for job, (off, ln) in order:
        if cur and (off - (cur[-1][1][0] + cur[-1][1][1]) > 2_000_000 or off + ln - cur[0][1][0] > 24_000_000):
            chunks.append(cur)
            cur = []
        cur.append((job, (off, ln)))
    if cur:
        chunks.append(cur)
    print(name, "to fetch", len(locs), "tiles in", len(chunks), "ranges", flush=True)

    def grab(chunk):
        start = chunk[0][1][0]
        end = max(o + l for _, (o, l) in chunk)
        blob = rng_get(start, end - start)
        for (z_, x, y), (o, l) in chunk:
            (CACHE / f"{z_}_{x}_{y}.webp").write_bytes(blob[o - start:o - start + l])
        return len(chunk)

    with cf.ThreadPoolExecutor(8) as ex:
        for done in ex.map(grab, chunks):
            pass
    paths = [CACHE / f"{z_}_{x}_{y}.webp" if (CACHE / f"{z_}_{x}_{y}.webp").exists() else None for z_, x, y in jobs]
    mosaic = np.zeros((len(ys) * TS, len(xs) * TS, 3), np.uint8)
    for (z_, x, y), p in zip(jobs, paths):
        if p is None:
            continue
        im = Image.open(p).convert("RGB")
        if im.size != (TS, TS):
            im = im.resize((TS, TS), Image.LANCZOS)
        mosaic[(y - ys[0]) * TS:(y - ys[0] + 1) * TS, (x - xs[0]) * TS:(x - xs[0] + 1) * TS] = np.asarray(im)
    print(name, "z", z, "tiles", len(jobs), "mosaic", mosaic.shape, flush=True)
    # resample onto the local metre frame, in overlapping 1024 px pieces
    res = 40075016.7 * math.cos(math.radians(LAT0)) / (2 ** z) / TS  # metres per mosaic pixel
    piece_m = 1024 * res
    step_m = (1024 - 24) * res
    nx, ny = math.ceil((x1 - x0 - 24 * res) / step_m), math.ceil((y1 - y0 - 24 * res) / step_m)
    lvl = {"name": name, "zoom": z, "res": res, "pieces": []}
    for j in range(ny):
        for i in range(nx):
            px0, py0 = x0 + i * step_m, y0 + j * step_m
            u = np.linspace(px0, px0 + piece_m, 1024, endpoint=False) + res / 2
            v = np.linspace(py0 + piece_m, py0, 1024, endpoint=False) - res / 2  # image rows go north to south
            UU, VV = np.meshgrid(u, v)
            lat, lon = LAT0 + VV / KY, LON0 + UU / KX
            mx = (lon + 180) / 360 * 2 ** z * TS - xs[0] * TS
            my = (1 - np.arcsinh(np.tan(np.radians(lat))) / np.pi) / 2 * 2 ** z * TS - ys[0] * TS
            mx = np.clip(mx, 0, mosaic.shape[1] - 1.001)
            my = np.clip(my, 0, mosaic.shape[0] - 1.001)
            ix, iy = mx.astype(int), my.astype(int)
            fx, fy = (mx - ix)[..., None], (my - iy)[..., None]
            g = lambda a, b: mosaic[a, b].astype(np.float32)
            out = (g(iy, ix) * (1 - fx) * (1 - fy) + g(iy, ix + 1) * fx * (1 - fy) + g(iy + 1, ix) * (1 - fx) * fy +
                   g(iy + 1, ix + 1) * fx * fy)
            fn = f"{name}_{i}_{j}.jpg"
            Image.fromarray(out.clip(0, 255).astype(np.uint8)).save(OUT / fn, quality=90)
            lvl["pieces"].append({"file": fn, "x0": px0, "y0": py0, "x1": px0 + piece_m, "y1": py0 + piece_m})
    index["levels"].append(lvl)
    print(name, "pieces", len(lvl["pieces"]), "piece metres", round(piece_m, 1), flush=True)
json.dump(index, open(G / "ortho.json", "w"), indent=1)
print("done")

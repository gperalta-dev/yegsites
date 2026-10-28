"""OpenStreetMap data for central Edmonton (Overpass API) and terrain tiles (AWS open data, terrarium png) into assets/geo/"""
import json
import math
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)
UA = {"User-Agent": "WhyteWebDemo/1.0 (concept render, contact gperaltainbox@gmail.com)"}
S, W, N, E = 53.500, -113.570, 53.565, -113.440
BB = f"({S},{W},{N},{E})"
QUERIES = {
    "buildings": f'[out:json][timeout:240];(way["building"]{BB};relation["building"]{BB};way["building:part"]{BB};);out geom;',
    "water": f'[out:json][timeout:120];(way["natural"="water"]{BB};relation["natural"="water"]{BB};way["waterway"="riverbank"]{BB};'
             f'relation["waterway"="riverbank"]{BB};way["waterway"="river"]{BB};);out geom;',
    "roads": f'[out:json][timeout:180];(way["highway"~"motorway|trunk|primary|secondary|tertiary|residential|unclassified|living_street|service|footway|cycleway|path"]{BB};);out geom;',
    "land": f'[out:json][timeout:180];(way["leisure"~"park|golf_course|pitch"]{BB};relation["leisure"~"park|golf_course"]{BB};'
            f'way["natural"~"wood|scrub|grassland"]{BB};relation["natural"~"wood|scrub"]{BB};way["landuse"~"forest|grass|meadow|recreation_ground|cemetery"]{BB};'
            f'relation["landuse"~"forest|grass"]{BB};);out geom;',
    "bridges": f'[out:json][timeout:120];(way["bridge"]["highway"]{BB};way["bridge"]["railway"]{BB};way["man_made"="bridge"]{BB};);out geom;',
}
def overpass(q):
    for attempt in range(5):
        try:
            req = urllib.request.Request("https://overpass-api.de/api/interpreter", data=urllib.parse.urlencode({"data": q}).encode(), headers=UA)
            return urllib.request.urlopen(req, timeout=300).read()
        except Exception as e:
            print("retry", attempt, e, flush=True)
            time.sleep(20 * (attempt + 1))
    raise SystemExit("overpass failed")


for name, q in QUERIES.items():
    dest = OUT / f"{name}.json"
    if dest.exists() and dest.stat().st_size > 1000:
        continue
    if name == "buildings":  # too big for one request: 4 x 4 tiles, merged by element id
        els = {}
        for i in range(4):
            for j in range(4):
                s, n = S + (N - S) * i / 4, S + (N - S) * (i + 1) / 4
                w, e = W + (E - W) * j / 4, W + (E - W) * (j + 1) / 4
                bb = f"({s},{w},{n},{e})"
                part = json.loads(overpass(f'[out:json][timeout:240];(way["building"]{bb};relation["building"]{bb};way["building:part"]{bb};);out geom;'))
                for el in part["elements"]:
                    els[(el["type"], el["id"])] = el
                print("buildings tile", i, j, len(els), flush=True)
                time.sleep(3)
        data = json.dumps({"elements": list(els.values())}).encode()
    else:
        data = overpass(q)
    dest.write_bytes(data)
    print(name, len(json.loads(data)["elements"]), "elements", round(len(data) / 1e6, 1), "MB", flush=True)

# terrarium elevation tiles, zoom 14
Z = 14


def tile(lat, lon):
    n = 2 ** Z
    x = (lon + 180) / 360 * n
    y = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n
    return x, y


x0, y0 = tile(N, W)
x1, y1 = tile(S, E)
td = OUT / "terrain"
td.mkdir(exist_ok=True)
for tx in range(int(x0), int(x1) + 1):
    for ty in range(int(y0), int(y1) + 1):
        dest = td / f"{Z}_{tx}_{ty}.png"
        if dest.exists():
            continue
        u = f"https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{Z}/{tx}/{ty}.png"
        dest.write_bytes(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=120).read())
print("terrain tiles", int(x0), int(x1), int(y0), int(y1), flush=True)

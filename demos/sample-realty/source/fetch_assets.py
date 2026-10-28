"""download the CC0 Poly Haven assets the realty scene uses into assets/dl/<asset>/ (md5 checked, skips what is there)"""
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

DL = Path(sys.argv[1])
UA = {"User-Agent": "SouthsitesDemo/1.0"}
MODELS = ["tree_small_02", "island_tree_02", "fir_sapling_medium", "pine_sapling_small", "searsia_lucida", "grass_medium_01"]
MODELS_1K = ["jacaranda_tree", "fir_sapling"]  # big or distant-only trees: 1k textures are plenty
TEXTURES = ["grey_roof_01", "exterior_wall_cladding_03", "castle_wall_slates", "concrete_pavement", "asphalt_02", "leafy_grass",
            "brown_mud_leaves_01", "brown_planks_07", "aerial_grass_rock", "forrest_ground_01", "aerial_asphalt_01"]
TEXTURES_1K = ["red_brick_03", "concrete_wall_008", "concrete_tile_facade"]  # downtown facades
HDRI = "kloppenheim_06_puresky"


def get_json(u):
    return json.load(urllib.request.urlopen(urllib.request.Request(u, headers=UA)))


def fetch(url, dest, md5):
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and hashlib.md5(dest.read_bytes()).hexdigest() == md5:
        return
    data = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=300).read()
    if hashlib.md5(data).hexdigest() != md5:
        raise SystemExit(f"md5 mismatch {url}")
    dest.write_bytes(data)
    print("got", dest.relative_to(DL), round(len(data) / 1e6, 1), "MB", flush=True)


for a in MODELS + MODELS_1K:
    g = get_json(f"https://api.polyhaven.com/files/{a}")["gltf"]["1k" if a in MODELS_1K else "2k"]["gltf"]
    fetch(g["url"], DL / a / f"{a}.gltf", g["md5"])
    for rel, inc in g.get("include", {}).items():
        fetch(inc["url"], DL / a / rel, inc["md5"])
for a in TEXTURES + TEXTURES_1K:
    f = get_json(f"https://api.polyhaven.com/files/{a}")
    for kind, key in (("Diffuse", "diff"), ("nor_gl", "nor"), ("arm", "arm")):
        if kind in f:
            v = f[kind]["1k" if a in TEXTURES_1K else "2k"]["jpg"]
            fetch(v["url"], DL / a / f"{key}.jpg", v["md5"])
h = get_json(f"https://api.polyhaven.com/files/{HDRI}")["hdri"]
for r in ("1k", "8k"):
    v = h[r]["hdr"]
    fetch(v["url"], DL / "hdri" / f"{HDRI}_{r}.hdr", v["md5"])
print("done", flush=True)

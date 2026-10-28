"""drape the City of Edmonton 2024 orthophoto (1024 px pieces from fetch_ortho.py) on the terrain and on low roofs.

each piece is its own material (planar x/y projection from world position), so every texture stays within the 1k render
texture limit. faces pick the sharpest piece that covers their centre; the made-up suburb keeps its own lawn ground.
"""
import json
import math
from pathlib import Path

import bpy
import numpy as np

from common import N, new_mat

PIECES = []  # (level, x0, y0, x1, y1, core box, material)


def load(geo_dir):
    idx = json.load(open(Path(geo_dir) / "ortho.json"))
    for lvl in idx["levels"]:
        res = lvl["res"]
        for p in lvl["pieces"]:
            m, nt, pr = new_mat(f"ortho {p['file']}")
            tc = N(nt, "ShaderNodeTexCoord", -1000, 0)
            sep = N(nt, "ShaderNodeSeparateXYZ", -850, 0)
            nt.links.new(tc.outputs["Object"], sep.inputs["Vector"])
            u = N(nt, "ShaderNodeMapRange", -650, 100)
            u.inputs["From Min"].default_value, u.inputs["From Max"].default_value = p["x0"], p["x1"]
            v = N(nt, "ShaderNodeMapRange", -650, -100)
            v.inputs["From Min"].default_value, v.inputs["From Max"].default_value = p["y0"], p["y1"]
            for mr in (u, v):
                mr.clamp = False
            nt.links.new(sep.outputs["X"], u.inputs["Value"])
            nt.links.new(sep.outputs["Y"], v.inputs["Value"])
            cv = N(nt, "ShaderNodeCombineXYZ", -450, 0)
            nt.links.new(u.outputs["Result"], cv.inputs["X"])
            nt.links.new(v.outputs["Result"], cv.inputs["Y"])
            im = N(nt, "ShaderNodeTexImage", -250, 0)
            im.image = bpy.data.images.load(str(Path(geo_dir) / "ortho" / p["file"]), check_existing=True)
            im.extension = "EXTEND"
            im.interpolation = "Cubic"
            nt.links.new(cv.outputs["Vector"], im.inputs["Vector"])
            # a midday photo under golden-hour light: pull the exposure down a touch and keep it matte
            g = N(nt, "ShaderNodeGamma", -50, 100)
            g.inputs["Gamma"].default_value = 1.12
            nt.links.new(im.outputs["Color"], g.inputs["Color"])
            nt.links.new(g.outputs["Color"], pr.inputs["Base Color"])
            pr.inputs["Roughness"].default_value = 0.9
            b = N(nt, "ShaderNodeBump", -50, -250)
            b.inputs["Strength"].default_value = 0.15
            nt.links.new(im.outputs["Color"], b.inputs["Height"])
            nt.links.new(b.outputs["Normal"], pr.inputs["Normal"])
            ov = 12 * res  # half the overlap: the core is where this piece wins
            PIECES.append((lvl["name"], p["x0"], p["y0"], p["x1"], p["y1"],
                           (p["x0"] + ov, p["y0"] + ov, p["x1"] - ov, p["y1"] - ov), m))
    print("ortho pieces", len(PIECES))
    return PIECES


def assign(ob, only=None, keep_disk=None, max_z=None):
    """set faces of ob (identity transform) to ortho materials, vectorised. only: material indices to replace (None = all).
    keep_disk (cx, cy, r): faces inside keep their material. max_z: faces above keep theirs"""
    me = ob.data
    base = len(me.materials)
    for _, _, _, _, _, _, m in PIECES:
        me.materials.append(m)
    n = len(me.polygons)
    c = np.empty(n * 3, np.float32)
    me.polygons.foreach_get("center", c)
    c = c.reshape(-1, 3)
    mi = np.empty(n, np.int32)
    me.polygons.foreach_get("material_index", mi)
    ok = np.ones(n, bool) if only is None else np.isin(mi, list(only))
    if max_z is not None:
        ok &= c[:, 2] <= max_z
    if keep_disk is not None:
        ok &= np.hypot(c[:, 0] - keep_disk[0], c[:, 1] - keep_disk[1]) >= keep_disk[2]
    new = np.full(n, -1, np.int32)
    for level in ("lo", "hi"):  # hi pieces win where they exist
        for k, (name, x0, y0, x1, y1, core, m) in enumerate(PIECES):
            if name != level:
                continue
            inside = (c[:, 0] >= core[0]) & (c[:, 0] < core[2]) & (c[:, 1] >= core[1]) & (c[:, 1] < core[3])
            new[inside] = base + k
    sel = ok & (new >= 0)
    mi[sel] = new[sel]
    me.polygons.foreach_set("material_index", mi)
    me.update()
    print("ortho on", ob.name, int(sel.sum()), "of", n, "faces")

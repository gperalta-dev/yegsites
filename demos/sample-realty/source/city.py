"""central Edmonton from OpenStreetMap: terrain from elevation tiles, land-cover colour, buildings extruded to their OSM
heights with procedural window facades (curtain wall, precast, brick), older houses as hip and gable roofed boxes on their
real footprints, the river, the High Level Bridge truss and the other bridges, and 200k instanced trees.

world frame: metres, x east, y north, origin at 53.5300 N 113.5050 W, z = elevation minus Z_REF (the suburb's level).
"""
import json
import math
import random
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

from common import N, flat, link, new_mat, pbr

G = None
DEM = None
DM = None
Z_REF = 0.0
SUB = (0.0, 0.0, 0.0)


def setup(geo_dir, suburb):
    global G, DEM, DM, Z_REF, SUB
    G = Path(geo_dir)
    DEM = np.load(G / "dem.npy").astype(np.float64)
    DM = json.load(open(G / "dem.json"))
    SUB = suburb
    Z_REF = raw_z(suburb[0], suburb[1])
    print("Z_REF", round(Z_REF, 1))


def raw_z(x, y):
    fx, fy = (x - DM["x0"]) / DM["step"], (y - DM["y0"]) / DM["step"]
    j, i = int(math.floor(fx)), int(math.floor(fy))
    i = max(0, min(DEM.shape[0] - 2, i))
    j = max(0, min(DEM.shape[1] - 2, j))
    a, b = min(1, max(0, fx - j)), min(1, max(0, fy - i))
    return float(DEM[i, j] * (1 - a) * (1 - b) + DEM[i, j + 1] * a * (1 - b) + DEM[i + 1, j] * (1 - a) * b + DEM[i + 1, j + 1] * a * b)


def flat_w(x, y):
    """1 inside the suburb disk (flattened to z=0), fading to 0 over 80 m"""
    d = math.hypot(x - SUB[0], y - SUB[1])
    t = min(1, max(0, (d - SUB[2]) / 80.0))
    return 1 - t * t * (3 - 2 * t)


def z_at(x, y):
    return (raw_z(x, y) - Z_REF) * (1 - flat_w(x, y))


# ---------------------------------------------------------------- terrain
def terrain(col, step=1):
    ny, nx = DEM.shape
    xs = DM["x0"] + np.arange(0, nx, step) * DM["step"]
    ys = DM["y0"] + np.arange(0, ny, step) * DM["step"]
    Z = DEM[::step, ::step] - Z_REF
    XX, YY = np.meshgrid(xs, ys)
    d = np.hypot(XX - SUB[0], YY - SUB[1])
    t = np.clip((d - SUB[2]) / 80.0, 0, 1)
    w = 1 - t * t * (3 - 2 * t)
    Z = Z * (1 - w) - 0.25 * w  # suburb ground sits just under its lots
    h, w_ = Z.shape
    verts = np.stack([XX, YY, Z], -1).reshape(-1, 3)
    idx = np.arange(h * w_).reshape(h, w_)
    a, b, c, d_ = idx[:-1, :-1].ravel(), idx[:-1, 1:].ravel(), idx[1:, 1:].ravel(), idx[1:, :-1].ravel()
    faces = np.stack([a, b, c, d_], -1)
    me = bpy.data.meshes.new("terrain")
    me.vertices.add(len(verts))
    me.vertices.foreach_set("co", verts.astype(np.float32).ravel())
    me.loops.add(len(faces) * 4)
    me.loops.foreach_set("vertex_index", faces.astype(np.int32).ravel())
    me.polygons.add(len(faces))
    me.polygons.foreach_set("loop_start", np.arange(0, len(faces) * 4, 4, dtype=np.int32))
    me.update()
    me.shade_smooth()
    # uv = landcover image space
    X1 = DM["x0"] + (DM["nx"] - 1) * DM["step"]
    Y1 = DM["y0"] + (DM["ny"] - 1) * DM["step"]
    uv = me.uv_layers.new(name="UVMap")
    lv = np.empty(len(me.loops), np.int32)
    me.loops.foreach_get("vertex_index", lv)
    u = (verts[lv, 0] - DM["x0"]) / (X1 - DM["x0"])
    v = (verts[lv, 1] - DM["y0"]) / (Y1 - DM["y0"])
    uv.data.foreach_set("uv", np.stack([u, v], -1).astype(np.float32).ravel())
    me.materials.append(ground_mat())
    ob = bpy.data.objects.new("terrain", me)
    link(ob, col)
    print("terrain", len(verts), "verts")
    return ob


def far_ground(col, reach=30000.0):
    """a skirt that carries the terrain's own edge out to the horizon, so the sky never shows below the land"""
    ny, nx = DEM.shape
    st = 4
    ring = [(0, j) for j in range(0, nx, st)] + [(i, nx - 1) for i in range(0, ny, st)] +            [(ny - 1, j) for j in range(nx - 1, -1, -st)] + [(i, 0) for i in range(ny - 1, -1, -st)]
    cx = DM["x0"] + (nx - 1) * DM["step"] / 2
    cy = DM["y0"] + (ny - 1) * DM["step"] / 2
    verts, faces = [], []
    for i, j in ring:
        x, y = DM["x0"] + j * DM["step"], DM["y0"] + i * DM["step"]
        z = float(DEM[i, j]) - Z_REF - 0.3
        d = math.hypot(x - cx, y - cy)
        k = reach / d
        verts.append((x, y, z))
        verts.append((cx + (x - cx) * k, cy + (y - cy) * k, min(z, 0.0) - 8.0))
    n = len(ring)
    for a in range(n):
        b = (a + 1) % n
        faces.append((2 * a, 2 * a + 1, 2 * b + 1, 2 * b))
    m, nt, p = new_mat("far ground")
    tc = N(nt, "ShaderNodeTexCoord", -900, 0)
    nz = N(nt, "ShaderNodeTexNoise", -700, 0)
    nz.inputs["Scale"].default_value = 0.002
    nz.inputs["Detail"].default_value = 12.0
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    ramp = N(nt, "ShaderNodeValToRGB", -450, 0)
    ramp.color_ramp.elements[0].color = (0.06, 0.07, 0.045, 1)
    ramp.color_ramp.elements[1].color = (0.14, 0.14, 0.12, 1)
    nt.links.new(nz.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], p.inputs["Base Color"])
    p.inputs["Roughness"].default_value = 0.95
    me = bpy.data.meshes.new("far ground")
    me.from_pydata(verts, [], faces)
    me.materials.append(m)
    ob = bpy.data.objects.new("far ground", me)
    link(ob, col)
    return ob


def ground_mat():
    m, nt, p = new_mat("land cover")
    tc = N(nt, "ShaderNodeTexCoord", -1200, 0)
    im = N(nt, "ShaderNodeTexImage", -900, 300)
    im.image = bpy.data.images.load(str(G / "landcover.png"), check_existing=True)
    im.interpolation = "Cubic"
    nt.links.new(tc.outputs["UV"], im.inputs["Vector"])
    # small-scale variation: lawns, dirt, shade under trees
    nz = N(nt, "ShaderNodeTexNoise", -900, 0)
    nz.inputs["Scale"].default_value = 0.08
    nz.inputs["Detail"].default_value = 10.0
    nz.inputs["Roughness"].default_value = 0.65
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    mr = N(nt, "ShaderNodeMapRange", -650, 0)
    mr.inputs["To Min"].default_value, mr.inputs["To Max"].default_value = 0.72, 1.22
    nt.links.new(nz.outputs["Fac"], mr.inputs["Value"])
    mul = N(nt, "ShaderNodeMix", -400, 200, data_type="RGBA", blend_type="MULTIPLY")
    mul.inputs["Factor"].default_value = 1.0
    nt.links.new(im.outputs["Color"], mul.inputs["A"])
    comb = N(nt, "ShaderNodeCombineColor", -500, 0)
    for k in ("Red", "Green", "Blue"):
        nt.links.new(mr.outputs["Result"], comb.inputs[k])
    nt.links.new(comb.outputs["Color"], mul.inputs["B"])
    nt.links.new(mul.outputs["Result"], p.inputs["Base Color"])
    p.inputs["Roughness"].default_value = 0.92
    b = N(nt, "ShaderNodeBump", -300, -300)
    fine = N(nt, "ShaderNodeTexNoise", -600, -300)
    fine.inputs["Scale"].default_value = 2.0
    fine.inputs["Detail"].default_value = 8.0
    nt.links.new(tc.outputs["Object"], fine.inputs["Vector"])
    nt.links.new(fine.outputs["Fac"], b.inputs["Height"])
    b.inputs["Strength"].default_value = 0.3
    nt.links.new(b.outputs["Normal"], p.inputs["Normal"])
    return m


# ---------------------------------------------------------------- facade shaders
def facade_mat(name, wall_color, glass_color, floor_h, module, win_w, win_h, lit=0.12, curtain=False, rough_wall=0.7):
    """procedural windows in wall uv space (u metres along the wall, v metres up): glass with Fresnel reflection, a few
    rooms lit, mullions, spandrels. per-building variation from the face attribute `bid`"""
    m, nt, p = new_mat(name)
    out = nt.nodes.get("Material Output")
    L = nt.links.new
    tc = N(nt, "ShaderNodeTexCoord", -1800, 0)
    attr = N(nt, "ShaderNodeAttribute", -1800, -400)
    attr.attribute_type = "GEOMETRY"
    attr.attribute_name = "bid"
    sep = N(nt, "ShaderNodeSeparateXYZ", -1600, 0)
    L(tc.outputs["UV"], sep.inputs["Vector"])

    def math_(op, a, b=None, x=-1400, y=0):
        n = N(nt, "ShaderNodeMath", x, y, operation=op)
        if isinstance(a, (int, float)):
            n.inputs[0].default_value = a
        else:
            L(a, n.inputs[0])
        if b is not None:
            if isinstance(b, (int, float)):
                n.inputs[1].default_value = b
            else:
                L(b, n.inputs[1])
        return n.outputs[0]

    # per-building floor height jitter
    fh = math_("MULTIPLY_ADD", attr.outputs["Fac"], 0.0)
    fh_node = fh.node
    fh_node.inputs[1].default_value = floor_h * 0.12
    fh_node.inputs[2].default_value = floor_h * 0.94
    cu = math_("DIVIDE", sep.outputs["X"], module)
    cv = math_("DIVIDE", sep.outputs["Y"], fh)
    fu = math_("FRACT", cu)
    fv = math_("FRACT", cv)
    iu = math_("FLOOR", cu)
    iv = math_("FLOOR", cv)
    hu = (1 - win_w) / 2
    in_u = math_("MULTIPLY", math_("GREATER_THAN", fu, hu), math_("LESS_THAN", fu, 1 - hu))
    in_v = math_("MULTIPLY", math_("GREATER_THAN", fv, 0.5 - win_h / 2 + 0.05), math_("LESS_THAN", fv, 0.5 + win_h / 2 + 0.05))
    win = math_("MULTIPLY", in_u, in_v)
    # random per window cell: lit rooms, blinds, a few darker panes
    cell = N(nt, "ShaderNodeCombineXYZ", -1100, -600)
    L(iu, cell.inputs["X"])
    L(iv, cell.inputs["Y"])
    bidx = math_("MULTIPLY", attr.outputs["Fac"], 977.0)
    L(bidx, cell.inputs["Z"])
    wn = N(nt, "ShaderNodeTexWhiteNoise", -900, -600)
    wn.noise_dimensions = "3D"
    L(cell.outputs["Vector"], wn.inputs["Vector"])
    lit_mask = math_("MULTIPLY", math_("LESS_THAN", wn.outputs["Value"], lit), win)
    # wall
    wall = N(nt, "ShaderNodeBsdfPrincipled", -300, 300)
    if True:
        hsv = N(nt, "ShaderNodeHueSaturation", -500, 400)
        hsv.inputs["Color"].default_value = (*wall_color, 1)
        vv = N(nt, "ShaderNodeMapRange", -700, 400)
        vv.inputs["To Min"].default_value, vv.inputs["To Max"].default_value = 0.7, 1.25
        L(attr.outputs["Fac"], vv.inputs["Value"])
        L(vv.outputs["Result"], hsv.inputs["Value"])
        L(hsv.outputs["Color"], wall.inputs["Base Color"])
    wall.inputs["Roughness"].default_value = rough_wall
    # glass: dark, glossy, tinted, with Fresnel; lit rooms glow warm
    gl = N(nt, "ShaderNodeBsdfPrincipled", -300, -100)
    gl.inputs["Base Color"].default_value = (*glass_color, 1)
    gl.inputs["Roughness"].default_value = 0.04
    gl.inputs["Metallic"].default_value = 0.75 if curtain else 0.15
    try:
        gl.inputs["Specular IOR Level"].default_value = 0.9
    except Exception:
        pass
    gl.inputs["Emission Color"].default_value = (1.0, 0.74, 0.46, 1)
    em = math_("MULTIPLY", lit_mask, 0.7)
    L(em, gl.inputs["Emission Strength"])
    # panes vary a little building to building and window to window
    pv = N(nt, "ShaderNodeMapRange", -600, -300)
    pv.inputs["To Min"].default_value, pv.inputs["To Max"].default_value = 0.02, 0.09
    L(wn.outputs["Value"], pv.inputs["Value"])
    L(pv.outputs["Result"], gl.inputs["Roughness"])
    mix = N(nt, "ShaderNodeMixShader", 100, 0)
    L(win, mix.inputs["Fac"])
    L(wall.outputs[0], mix.inputs[1])
    L(gl.outputs[0], mix.inputs[2])
    L(mix.outputs[0], out.inputs["Surface"])
    # depth: windows sit in, mullions stand out
    b = N(nt, "ShaderNodeBump", -100, -500)
    b.inputs["Strength"].default_value = 0.6
    b.inputs["Distance"].default_value = 0.05
    L(math_("SUBTRACT", 1.0, win), b.inputs["Height"])
    L(b.outputs["Normal"], wall.inputs["Normal"])
    return m


def city_mats():
    mats = [
        facade_mat("curtain wall blue", (0.16, 0.18, 0.19), (0.035, 0.06, 0.075), 3.9, 1.5, 0.95, 0.93, lit=0.02, curtain=True, rough_wall=0.3),
        facade_mat("curtain wall bronze", (0.13, 0.11, 0.09), (0.06, 0.05, 0.035), 3.9, 1.5, 0.94, 0.9, lit=0.02, curtain=True, rough_wall=0.35),
        facade_mat("precast office", (0.31, 0.29, 0.26), (0.04, 0.05, 0.06), 3.8, 1.6, 0.62, 0.55, lit=0.03),
        facade_mat("brick lowrise", (0.19, 0.12, 0.09), (0.04, 0.04, 0.04), 3.6, 2.6, 0.45, 0.45, lit=0.03, rough_wall=0.85),
        facade_mat("stucco apartments", (0.36, 0.33, 0.29), (0.04, 0.045, 0.05), 3.0, 3.2, 0.38, 0.45, lit=0.04),
        pbr("roof gravel", "aerial_grass_rock", 4.0, value=0.75, sat=0.0, rough=(0.8, 1.0)),
        facade_mat("old house walls", (0.34, 0.32, 0.28), (0.035, 0.04, 0.045), 2.8, 3.4, 0.33, 0.42, lit=0.03, rough_wall=0.75),
        pbr("old roofs", "grey_roof_01", 6.0, value=0.75, sat=0.5, rough=(0.65, 0.95)),
        flat("bridge steel", (0.045, 0.048, 0.05), rough=0.65, metal=0.3, noise=0.2),
        flat("bridge concrete", (0.48, 0.46, 0.43), rough=0.85, noise=0.25, bump=0.3),
        water_mat(),
    ]
    return mats


M_GLASS_B, M_GLASS_Z, M_PRECAST, M_BRICK, M_STUCCO, M_GRAVEL, M_OLDWALL, M_OLDROOF, M_STEEL, M_BCONC, M_WATER = range(11)


def water_mat():
    m, nt, p = new_mat("river")
    p.inputs["Base Color"].default_value = (0.035, 0.045, 0.04, 1)
    p.inputs["Roughness"].default_value = 0.06
    try:
        p.inputs["Specular IOR Level"].default_value = 0.6
    except Exception:
        pass
    tc = N(nt, "ShaderNodeTexCoord", -900, -200)
    mp = N(nt, "ShaderNodeMapping", -700, -200)
    mp.inputs["Scale"].default_value = (1.0, 2.5, 1.0)
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    nz = N(nt, "ShaderNodeTexNoise", -500, -200)
    nz.inputs["Scale"].default_value = 0.35
    nz.inputs["Detail"].default_value = 6.0
    nt.links.new(mp.outputs["Vector"], nz.inputs["Vector"])
    b = N(nt, "ShaderNodeBump", -250, -200)
    b.inputs["Strength"].default_value = 0.12
    nt.links.new(nz.outputs["Fac"], b.inputs["Height"])
    nt.links.new(b.outputs["Normal"], p.inputs["Normal"])
    return m


# ---------------------------------------------------------------- buildings
def obb(ring):
    """minimum-area rectangle of a footprint: centre, unit long axis, half sizes"""
    pts = [Vector(p) for p in ring]
    best = None
    for i in range(len(pts)):
        e = pts[(i + 1) % len(pts)] - pts[i]
        if e.length < 0.5:
            continue
        e.normalize()
        n_ = Vector((-e.y, e.x))
        us = [p.dot(e) for p in pts]
        vs = [p.dot(n_) for p in pts]
        a = (max(us) - min(us)) * (max(vs) - min(vs))
        if best is None or a < best[0]:
            best = (a, e, n_, (min(us) + max(us)) / 2, (min(vs) + max(vs)) / 2, (max(us) - min(us)) / 2, (max(vs) - min(vs)) / 2)
    if best is None:
        return None
    _, e, n_, cu, cv, hu, hv = best
    c = e * cu + n_ * cv
    if hv > hu:
        e, n_, hu, hv = n_, -e, hv, hu
    return c, e, n_, hu, hv


class Acc:
    def __init__(self):
        self.v, self.f, self.mi, self.uv, self.bid = [], [], [], [], []

    def face(self, pts, mi, uvs, bid):
        base = len(self.v)
        self.v.extend(pts)
        self.f.append(list(range(base, base + len(pts))))
        self.mi.append(mi)
        self.uv.extend(uvs)
        self.bid.append(bid)

    def build(self, name, mats, col):
        me = bpy.data.meshes.new(name)
        me.from_pydata(self.v, [], self.f)
        me.polygons.foreach_set("material_index", self.mi)
        uv = me.uv_layers.new(name="UVMap")
        uv.data.foreach_set("uv", [c for t in self.uv for c in t])
        at = me.attributes.new("bid", "FLOAT", "FACE")
        at.data.foreach_set("value", self.bid)
        for m in mats:
            me.materials.append(m)
        me.update()
        ob = bpy.data.objects.new(name, me)
        link(ob, col)
        return ob


def extrude(acc, ring, z0, z1, mi_wall, mi_roof, bid):
    u = 0.0
    n = len(ring)
    for i in range(n):
        a, b = ring[i], ring[(i + 1) % n]
        L = math.dist(a, b)
        if L < 0.05:
            continue
        acc.face([(a[0], a[1], z0), (b[0], b[1], z0), (b[0], b[1], z1), (a[0], a[1], z1)], mi_wall,
                 [(u, -0.6), (u + L, -0.6), (u + L, z1 - z0 - 0.6), (u, z1 - z0 - 0.6)], bid)
        u += L
    acc.face([(p[0], p[1], z1) for p in ring], mi_roof, [(p[0], p[1]) for p in ring], bid)


def small_house(acc, ring, z0, rng, bid, kind):
    r = obb(ring)
    if r is None:
        return
    c, e, n_, a, b = r
    e3, n3 = Vector((e.x, e.y, 0)), Vector((n_.x, n_.y, 0))
    c3 = Vector((c.x, c.y, 0))
    garage = kind in ("garage", "garages", "shed")
    hw = (2.5 if garage else (5.4 if (a * b * 4 > 110 and rng.random() < 0.55) else 2.9)) + 0.4
    z1 = z0 + hw
    P = lambda u, v, z: c3 + e3 * u + n3 * v + Vector((0, 0, z))
    corners = [(-a, -b), (a, -b), (a, b), (-a, b)]
    u = 0.0
    for i in range(4):
        (ua, va), (ub, vb) = corners[i], corners[(i + 1) % 4]
        L = math.hypot(ub - ua, vb - va)
        acc.face([P(ua, va, z0), P(ub, vb, z0), P(ub, vb, z1), P(ua, va, z1)], M_OLDWALL,
                 [(u, -0.6), (u + L, -0.6), (u + L, hw - 0.6), (u, hw - 0.6)], bid)
        u += L
    t = math.tan(math.radians(rng.uniform(22, 32) if not garage else 18))
    o = 0.4
    A, B = a + o, b + o
    ze = z1 - o * t
    zr = z1 + b * t
    rf = lambda pts: acc.face([P(*p) for p in pts], M_OLDROOF, [((P(*p)).dot(e3), (P(*p)).dot(n3) + p[2] * 1.1) for p in pts], bid)
    if rng.random() < 0.65 and a > b * 1.05:  # hip
        r_ = B
        rf([(-A, -B, ze), (A, -B, ze), (A - r_, 0, ze + r_ * t), (-A + r_, 0, ze + r_ * t)])
        rf([(A, B, ze), (-A, B, ze), (-A + r_, 0, ze + r_ * t), (A - r_, 0, ze + r_ * t)])
        rf([(A, -B, ze), (A, B, ze), (A - r_, 0, ze + r_ * t)])
        rf([(-A, B, ze), (-A, -B, ze), (-A + r_, 0, ze + r_ * t)])
    else:  # gable, ridge along the long side
        rf([(-A, -B, ze), (A, -B, ze), (A, 0, zr), (-A, 0, zr)])
        rf([(A, B, ze), (-A, B, ze), (-A, 0, zr), (A, 0, zr)])
        for s in (-1, 1):
            acc.face([P(s * a, -b * s, z1), P(s * a, b * s, z1), P(s * a, 0, zr)], M_OLDWALL,
                     [(0, hw - 0.6), (2 * b, hw - 0.6), (b, hw - 0.6 + b * t)], bid)


def buildings(col, skip_disk=True):
    city = json.load(open(G / "city.json"))
    rng = random.Random(3)
    acc_t, acc_h = Acc(), Acc()
    n_t = n_h = 0
    for bdg in city["buildings"]:
        ring = bdg["r"]
        cx = sum(p[0] for p in ring) / len(ring)
        cy = sum(p[1] for p in ring) / len(ring)
        if skip_disk and math.hypot(cx - SUB[0], cy - SUB[1]) < SUB[2] + 10:
            continue
        if not (DM["x0"] + 20 < cx < DM["x0"] + (DM["nx"] - 2) * DM["step"] and DM["y0"] + 20 < cy < DM["y0"] + (DM["ny"] - 2) * DM["step"]):
            continue
        z0 = min(z_at(p[0], p[1]) for p in ring[:: max(1, len(ring) // 6)]) - 0.6
        h = bdg["h"]
        bid = rng.random()
        kind = bdg["kind"]
        houseish = kind in ("house", "detached", "yes", "semidetached_house", "garage", "garages", "shed", "residential", "terrace")
        if houseish and bdg["a"] < 300 and h <= 10.5 and len(ring) <= 14:
            small_house(acc_h, ring, z0, rng, bid, kind)
            n_h += 1
            continue
        z0 += bdg.get("mh", 0) or 0
        if h > 60:
            mi = M_GLASS_B if bid < 0.45 else (M_GLASS_Z if bid < 0.7 else M_PRECAST)
        elif h > 22:
            mi = (M_PRECAST, M_STUCCO, M_GLASS_B, M_GLASS_Z)[int(bid * 4)]
        else:
            mi = (M_BRICK, M_STUCCO, M_PRECAST)[int(bid * 3)]
        extrude(acc_t, ring, z0, z0 + max(3.0, h - (bdg.get("mh", 0) or 0)) + 0.6, mi, M_GRAVEL, bid)
        n_t += 1
    mats = city_mats()
    acc_t.build("city buildings", mats, col)
    acc_h.build("city houses", mats, col)
    print("city: extruded", n_t, "houses", n_h)
    return mats, city


def water(col, mats, city):
    acc = Acc()
    for poly in city["water"]:
        zs = [raw_z(x, y) for x, y in poly[:: max(1, len(poly) // 40)]]
        z = min(zs) - Z_REF + 0.8
        ring = poly if sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1]
                           for i in range(len(poly))) > 0 else poly[::-1]
        acc.face([(x, y, z) for x, y in ring], M_WATER, [(x, y) for x, y in ring], 0.0)
    ob = acc.build("river", mats, col)
    return ob


def bridges(col, mats, city):
    acc = Acc()
    made = []
    for br in city["bridges"]:
        pts = [Vector(p) for p in br["p"]]
        L = sum((b - a).length for a, b in zip(pts, pts[1:]))
        if L < 60 or (pts[0] - pts[-1]).length < 1.0:  # closed ways are bridge outlines, not decks
            continue
        hl = br.get("name") == "109 Street NW" and L > 600
        za, zb = raw_z(*pts[0]) - Z_REF, raw_z(*pts[-1]) - Z_REF
        width = 4.0 if br.get("hw") in ("footway", "cycleway", "path") else (8.0 if br.get("rail") else 13.0)
        deck = max(za, zb) + (0.5 if not hl else 1.5)
        s = 0.0
        for a, b in zip(pts, pts[1:]):
            d = b - a
            seg = d.length
            if seg < 0.1:
                continue
            t = d / seg
            n_ = Vector((-t.y, t.x))
            q = [a + n_ * width / 2, b + n_ * width / 2, b - n_ * width / 2, a - n_ * width / 2]
            for z_top, z_bot in ((deck, deck - 1.6),):
                acc.face([(p.x, p.y, z_top) for p in q][::-1], M_BCONC, [(p.x, p.y) for p in q][::-1], 0.0)
                acc.face([(p.x, p.y, z_bot) for p in q], M_BCONC, [(p.x, p.y) for p in q], 0.0)
                for i in range(4):
                    p0, p1 = q[i], q[(i + 1) % 4]
                    acc.face([(p0.x, p0.y, z_bot), (p1.x, p1.y, z_bot), (p1.x, p1.y, z_top), (p0.x, p0.y, z_top)], M_BCONC,
                             [(0, 0), (1, 0), (1, 1), (0, 1)], 0.0)
            # piers down to the ground every ~45 m
            k = 0.0
            while k < seg:
                p = a + t * k
                g = raw_z(p.x, p.y) - Z_REF - 2
                if deck - g > 4:
                    pw = 2.2 if not hl else 4.0
                    box(acc, p, t, n_, pw, width * (0.8 if not hl else 1.1), g, deck - 1.6, M_BCONC if not hl else M_STEEL)
                k += 45.0 if not hl else 52.0
            if hl:  # the steel truss over the deck: chords, posts and diagonals on both sides
                th = 9.0
                for side in (-1, 1):
                    o = n_ * side * (width / 2 + 0.3)
                    for zc in (deck + 0.2, deck + th):
                        box(acc, a + o + t * seg / 2, t, n_, seg, 0.5, zc - 0.25, zc + 0.25, M_STEEL)
                    kk = 0.0
                    while kk <= seg:
                        p = a + o + t * kk
                        box(acc, p, t, n_, 0.35, 0.35, deck + 0.2, deck + th, M_STEEL)
                        diag(acc, p, p + t * 6.5, deck + 0.2, deck + th, n_, M_STEEL)
                        kk += 6.5
                    # deck-level lattice under the deck
                    box(acc, a + o + t * seg / 2, t, n_, seg, 0.6, deck - 6.0, deck - 5.4, M_STEEL)
            s += seg
        made.append((br.get("name"), round(L)))
    ob = acc.build("bridges", mats, col)
    print("bridges", made[:12], "...", len(made))
    return ob


def box(acc, c, t, n_, lu, lv, z0, z1, mi):
    t3, n3 = Vector((t.x, t.y, 0)) * lu / 2, Vector((n_.x, n_.y, 0)) * lv / 2
    c3 = Vector((c.x, c.y, 0))
    q = [c3 - t3 - n3, c3 + t3 - n3, c3 + t3 + n3, c3 - t3 + n3]
    for i in range(4):
        p0, p1 = q[i], q[(i + 1) % 4]
        acc.face([(p0.x, p0.y, z0), (p1.x, p1.y, z0), (p1.x, p1.y, z1), (p0.x, p0.y, z1)], mi, [(0, 0), (1, 0), (1, 1), (0, 1)], 0.0)
    acc.face([(p.x, p.y, z1) for p in q], mi, [(0, 0), (1, 0), (1, 1), (0, 1)], 0.0)
    acc.face([(p.x, p.y, z0) for p in reversed(q)], mi, [(0, 0), (1, 0), (1, 1), (0, 1)], 0.0)


def diag(acc, a, b, z0, z1, n_, mi, w=0.25):
    A, B = Vector((a.x, a.y, z0)), Vector((b.x, b.y, z1))
    o = Vector((n_.x, n_.y, 0)) * w
    up = Vector((0, 0, w))
    acc.face([A - o, B - o, B + o, A + o], mi, [(0, 0), (1, 0), (1, 1), (0, 1)], 0.0)
    acc.face([A - up, B - up, B + up, A + up], mi, [(0, 0), (1, 0), (1, 1), (0, 1)], 0.0)


# ---------------------------------------------------------------- trees (geometry nodes instancing)
def tree_points(path=None):
    arr = np.load(path or (G / "trees.npy"))
    z = np.array([z_at(float(x), float(y)) for x, y in arr[:, :2]], np.float32)
    arr[:, 2] = z
    return arr


def gn_scatter(name, pts, kinds_to_protos, col, rng=None):
    """pts rows (x, y, z, kind, scale, rot). one mesh of points + an Instance on Points modifier"""
    rng = rng or np.random.default_rng(3)
    order = []
    for k in sorted(kinds_to_protos):
        order.append((k, kinds_to_protos[k]))
    flat_protos, kind_index = [], {}
    for k, protos in order:
        kind_index[k] = list(range(len(flat_protos), len(flat_protos) + len(protos)))
        flat_protos.extend(protos)
    sc = bpy.data.collections.new(name + " set")
    for i, p in enumerate(flat_protos):
        o = bpy.data.objects.new(f"{i:03d}_{p.name}", p.data)
        sc.objects.link(o)
    idx = np.array([rng.choice(kind_index[int(k)]) for k in pts[:, 3]], np.int32)
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(pts))
    me.vertices.foreach_set("co", pts[:, :3].astype(np.float32).ravel())
    for an, dt, vals in (("pidx", "INT", idx), ("scl", "FLOAT", pts[:, 4]), ("rot", "FLOAT", pts[:, 5])):
        a = me.attributes.new(an, dt, "POINT")
        a.data.foreach_set("value", vals)
    me.update()
    ob = bpy.data.objects.new(name, me)
    link(ob, col)
    ng = bpy.data.node_groups.new(name + " nodes", "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    gi, go = ng.nodes.new("NodeGroupInput"), ng.nodes.new("NodeGroupOutput")
    ci = ng.nodes.new("GeometryNodeCollectionInfo")
    ci.inputs["Collection"].default_value = sc
    ci.inputs["Separate Children"].default_value = True
    ci.inputs["Reset Children"].default_value = True
    iop = ng.nodes.new("GeometryNodeInstanceOnPoints")
    iop.inputs["Pick Instance"].default_value = True
    na = {}
    for an, dt in (("pidx", "INT"), ("scl", "FLOAT"), ("rot", "FLOAT")):
        n_ = ng.nodes.new("GeometryNodeInputNamedAttribute")
        n_.data_type = dt
        n_.inputs["Name"].default_value = an
        na[an] = n_
    cx = ng.nodes.new("ShaderNodeCombineXYZ")
    ng.links.new(na["rot"].outputs["Attribute"], cx.inputs["Z"])
    e2r = ng.nodes.new("FunctionNodeEulerToRotation")
    ng.links.new(cx.outputs["Vector"], e2r.inputs["Euler"])
    ng.links.new(gi.outputs[0], iop.inputs["Points"])
    ng.links.new(ci.outputs["Instances"], iop.inputs["Instance"])
    ng.links.new(na["pidx"].outputs["Attribute"], iop.inputs["Instance Index"])
    ng.links.new(e2r.outputs["Rotation"], iop.inputs["Rotation"])
    ng.links.new(na["scl"].outputs["Attribute"], iop.inputs["Scale"])
    ng.links.new(iop.outputs["Instances"], go.inputs[0])
    mod = ob.modifiers.new("scatter", "NODES")
    mod.node_group = ng
    print("scatter", name, len(pts), "instances of", len(flat_protos), "prototypes")
    return ob

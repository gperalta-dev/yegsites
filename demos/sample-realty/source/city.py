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

import common
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
    lm_path = G / "landmask.npy"
    if lm_path.exists():  # the river bed sits well under the water surface, so the photo of the river never shows through
        lm = np.load(lm_path)
        X1_ = DM["x0"] + (DM["nx"] - 1) * DM["step"]
        Y1_ = DM["y0"] + (DM["ny"] - 1) * DM["step"]
        ci = np.clip(((Y1_ - YY) / 4.0).astype(int), 0, lm.shape[0] - 1)
        cj = np.clip(((XX - DM["x0"]) / 4.0).astype(int), 0, lm.shape[1] - 1)
        Z = Z - 4.0 * (lm[ci, cj] == 4)
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


def far_ground(col, reach=120000.0):
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
    ramp.color_ramp.elements[0].color = (0.13, 0.13, 0.10, 1)
    ramp.color_ramp.elements[1].color = (0.26, 0.25, 0.21, 1)
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
def facade_mat(name, wall_color, glass_tint, fh0, mw0, ww0, wh0, refl0=0.1, lit=0.06, curtain=False, rough_wall=0.7,
               wall_tex=None, tex_size=2.0, storefront=True, spandrel=(0.05, 0.06, 0.07)):
    """facade in wall uv space (u metres along the wall, v metres up). per building (face attribute `bid`) the floor
    height, window module and window size drift; glass reflects the sky with a Fresnel falloff over a dark interior,
    some floors are lit, curtain walls get slab-edge bands and spandrel panels, and the ground floor is a storefront"""
    m, nt, p = new_mat(name)
    out = nt.nodes.get("Material Output")
    nt.nodes.remove(p)
    L = nt.links.new
    tc = N(nt, "ShaderNodeTexCoord", -2200, 0)
    attr = N(nt, "ShaderNodeAttribute", -2200, -500)
    attr.attribute_type = "GEOMETRY"
    attr.attribute_name = "bid"
    sep = N(nt, "ShaderNodeSeparateXYZ", -2000, 0)
    L(tc.outputs["UV"], sep.inputs["Vector"])
    U, V, B = sep.outputs["X"], sep.outputs["Y"], attr.outputs["Fac"]

    def M(op, a, b=None, c=None):
        n = N(nt, "ShaderNodeMath", -1600, 0, operation=op)
        for k, x in enumerate((a, b, c)):
            if x is None:
                continue
            if isinstance(x, (int, float)):
                n.inputs[k].default_value = x
            else:
                L(x, n.inputs[k])
        return n.outputs[0]

    def rnd(k):
        return M("FRACT", M("MULTIPLY", B, k))

    r1, r2, r3, r4, r5 = rnd(7.31), rnd(13.71), rnd(29.13), rnd(51.7), rnd(91.3)
    fh = M("MULTIPLY_ADD", r1, fh0 * 0.16, fh0 * 0.92)
    mw = M("MULTIPLY_ADD", r2, mw0 * 0.6, mw0 * 0.75)
    ww = M("MINIMUM", M("MULTIPLY_ADD", r3, ww0 * 0.3, ww0 * 0.85), 0.975)
    wh = M("MINIMUM", M("MULTIPLY_ADD", r4, wh0 * 0.3, wh0 * 0.85), 0.95)
    GF = 4.3
    vu = M("MAXIMUM", M("SUBTRACT", V, GF), 0.0)
    cu, cv = M("DIVIDE", U, mw), M("DIVIDE", vu, fh)
    fu, fv, iu, iv = M("FRACT", cu), M("FRACT", cv), M("FLOOR", cu), M("FLOOR", cv)
    upper = M("GREATER_THAN", V, GF)
    in_u = M("LESS_THAN", M("ABSOLUTE", M("SUBTRACT", fu, 0.5)), M("MULTIPLY", ww, 0.5))
    in_v = M("LESS_THAN", M("ABSOLUTE", M("SUBTRACT", fv, 0.56)), M("MULTIPLY", wh, 0.5))
    win_up = M("MULTIPLY", M("MULTIPLY", in_u, in_v), upper)
    if storefront:
        gu = M("FRACT", M("DIVIDE", U, 3.3))
        st = M("MULTIPLY", M("LESS_THAN", M("ABSOLUTE", M("SUBTRACT", gu, 0.5)), 0.45),
               M("MULTIPLY", M("GREATER_THAN", V, 0.15), M("LESS_THAN", V, 3.2)))
        win = M("MAXIMUM", win_up, st)
        sign = M("MULTIPLY", M("GREATER_THAN", V, 3.35), M("LESS_THAN", V, 4.05))
    else:
        win, sign = win_up, None
    band = M("MULTIPLY", M("LESS_THAN", fv, 0.075), upper) if curtain else None
    # random per window and per floor: lit rooms, warm or cool light
    cell = N(nt, "ShaderNodeCombineXYZ", -1300, -700)
    L(iu, cell.inputs["X"])
    L(iv, cell.inputs["Y"])
    L(M("MULTIPLY", B, 977.0), cell.inputs["Z"])
    wn = N(nt, "ShaderNodeTexWhiteNoise", -1100, -700)
    wn.noise_dimensions = "3D"
    L(cell.outputs["Vector"], wn.inputs["Vector"])
    flr = N(nt, "ShaderNodeCombineXYZ", -1300, -900)
    L(iv, flr.inputs["Y"])
    L(M("MULTIPLY_ADD", B, 977.0, 5.0), flr.inputs["Z"])
    wf = N(nt, "ShaderNodeTexWhiteNoise", -1100, -900)
    wf.noise_dimensions = "3D"
    L(flr.outputs["Vector"], wf.inputs["Vector"])
    busy = M("MULTIPLY_ADD", M("GREATER_THAN", wf.outputs["Value"], 0.72), 4.0, 0.35)
    lit_m = M("MULTIPLY", M("LESS_THAN", wn.outputs["Value"], M("MULTIPLY", busy, lit)), win_up)
    sep_c = N(nt, "ShaderNodeSeparateColor", -900, -800)
    L(wn.outputs["Color"], sep_c.inputs["Color"])
    lc = N(nt, "ShaderNodeMix", -700, -800, data_type="RGBA")
    L(M("GREATER_THAN", sep_c.outputs["Red"], 0.55), lc.inputs["Factor"])
    lc.inputs["A"].default_value = (1.0, 0.70, 0.42, 1)
    lc.inputs["B"].default_value = (0.86, 0.90, 1.0, 1)
    # interior behind the glass: dark, a little different per window, glowing where lit
    inner = N(nt, "ShaderNodeBsdfPrincipled", -400, -500)
    iv_col = N(nt, "ShaderNodeMapRange", -700, -500)
    iv_col.inputs["To Min"].default_value, iv_col.inputs["To Max"].default_value = 0.012, 0.06
    L(wn.outputs["Value"], iv_col.inputs["Value"])
    ic = N(nt, "ShaderNodeCombineColor", -550, -500)
    for k in ("Red", "Green", "Blue"):
        L(iv_col.outputs["Result"], ic.inputs[k])
    L(ic.outputs["Color"], inner.inputs["Base Color"])
    inner.inputs["Roughness"].default_value = 0.9
    L(lc.outputs["Result"], inner.inputs["Emission Color"])
    L(M("MULTIPLY", lit_m, M("MULTIPLY_ADD", wn.outputs["Value"], 2.0, 0.4)), inner.inputs["Emission Strength"])
    gl = N(nt, "ShaderNodeBsdfGlossy", -400, -200)
    gl.inputs["Color"].default_value = (*glass_tint, 1)
    L(M("MULTIPLY_ADD", r5, 0.05, 0.01), gl.inputs["Roughness"])
    lw_ = N(nt, "ShaderNodeLayerWeight", -700, -200)
    lw_.inputs["Blend"].default_value = 0.22
    fres = M("MULTIPLY_ADD", lw_.outputs["Fresnel"], 1 - refl0, refl0)
    glass = N(nt, "ShaderNodeMixShader", -150, -300)
    L(fres, glass.inputs["Fac"])
    L(inner.outputs[0], glass.inputs[1])
    L(gl.outputs[0], glass.inputs[2])
    # wall: texture or flat colour, shade and hue drift per building
    wall = N(nt, "ShaderNodeBsdfPrincipled", -400, 300)
    hsv = N(nt, "ShaderNodeHueSaturation", -650, 350)
    vv = N(nt, "ShaderNodeMapRange", -900, 450)
    vv.inputs["To Min"].default_value, vv.inputs["To Max"].default_value = 0.72, 1.3
    L(r1, vv.inputs["Value"])
    L(vv.outputs["Result"], hsv.inputs["Value"])
    hv = N(nt, "ShaderNodeMapRange", -900, 600)
    hv.inputs["To Min"].default_value, hv.inputs["To Max"].default_value = 0.47, 0.53
    L(r4, hv.inputs["Value"])
    L(hv.outputs["Result"], hsv.inputs["Hue"])
    if wall_tex:
        mp = N(nt, "ShaderNodeMapping", -1100, 300)
        mp.inputs["Scale"].default_value = (1 / tex_size, 1 / tex_size, 1)
        L(tc.outputs["UV"], mp.inputs["Vector"])
        ti = N(nt, "ShaderNodeTexImage", -900, 250)
        ti.image = bpy.data.images.load(str(common.DL / wall_tex / "diff.jpg"), check_existing=True)
        L(mp.outputs["Vector"], ti.inputs["Vector"])
        tint = N(nt, "ShaderNodeMix", -800, 250, data_type="RGBA", blend_type="MULTIPLY")
        tint.inputs["Factor"].default_value = 1.0
        L(ti.outputs["Color"], tint.inputs["A"])
        tint.inputs["B"].default_value = (*wall_color, 1)
        L(tint.outputs["Result"], hsv.inputs["Color"])
    else:
        hsv.inputs["Color"].default_value = (*wall_color, 1)
    if curtain:  # the solid parts of a curtain wall are spandrel glass, not paint
        hsv.inputs["Color"].default_value = (*spandrel, 1)
        wall.inputs["Metallic"].default_value = 0.4
    L(hsv.outputs["Color"], wall.inputs["Base Color"])
    wall.inputs["Roughness"].default_value = rough_wall
    surf = N(nt, "ShaderNodeMixShader", 100, 0)
    L(win, surf.inputs["Fac"])
    L(wall.outputs[0], surf.inputs[1])
    L(glass.outputs[0], surf.inputs[2])
    final = surf
    mask = band if sign is None else (sign if band is None else M("MAXIMUM", band, sign))
    if mask is not None:
        metal = N(nt, "ShaderNodeBsdfPrincipled", -150, 600)
        metal.inputs["Base Color"].default_value = (0.06, 0.065, 0.07, 1)
        metal.inputs["Metallic"].default_value = 0.8
        metal.inputs["Roughness"].default_value = 0.35
        f2 = N(nt, "ShaderNodeMixShader", 300, 0)
        L(M("MULTIPLY", mask, M("SUBTRACT", 1.0, win)), f2.inputs["Fac"])
        L(surf.outputs[0], f2.inputs[1])
        L(metal.outputs[0], f2.inputs[2])
        final = f2
    L(final.outputs[0], out.inputs["Surface"])
    b = N(nt, "ShaderNodeBump", -100, 800)
    b.inputs["Strength"].default_value = 0.7
    b.inputs["Distance"].default_value = 0.06
    L(M("SUBTRACT", 1.0, win), b.inputs["Height"])
    L(b.outputs["Normal"], wall.inputs["Normal"])
    return m


def city_mats():
    return [
        facade_mat("curtain wall blue", (0.08, 0.10, 0.12), (0.62, 0.70, 0.76), 3.9, 1.5, 0.965, 0.70, refl0=0.22, lit=0.03,
                   curtain=True, rough_wall=0.25, spandrel=(0.05, 0.07, 0.085)),
        facade_mat("curtain wall bronze", (0.08, 0.065, 0.05), (0.80, 0.64, 0.45), 3.9, 1.5, 0.96, 0.68, refl0=0.2, lit=0.03,
                   curtain=True, rough_wall=0.3, spandrel=(0.07, 0.055, 0.04)),
        facade_mat("precast office", (0.62, 0.60, 0.56), (0.70, 0.74, 0.76), 3.8, 1.8, 0.55, 0.52, refl0=0.1, lit=0.04,
                   wall_tex="concrete_tile_facade", tex_size=2.09),
        facade_mat("brick", (0.80, 0.62, 0.55), (0.65, 0.68, 0.70), 3.6, 2.4, 0.42, 0.5, refl0=0.08, lit=0.04, rough_wall=0.85,
                   wall_tex="red_brick_03", tex_size=1.0),
        facade_mat("apartments", (0.78, 0.74, 0.68), (0.66, 0.70, 0.72), 3.0, 3.1, 0.4, 0.5, refl0=0.08, lit=0.06,
                   wall_tex="concrete_wall_008", tex_size=2.71, storefront=False),
        pbr("roof gravel", "aerial_grass_rock", 4.0, value=0.75, sat=0.0, rough=(0.8, 1.0)),
        facade_mat("old house walls", (0.34, 0.32, 0.28), (0.6, 0.62, 0.64), 2.8, 3.4, 0.33, 0.42, refl0=0.06, lit=0.03,
                   rough_wall=0.75, storefront=False),
        pbr("old roofs", "grey_roof_01", 6.0, value=0.75, sat=0.5, rough=(0.65, 0.95)),
        flat("bridge steel", (0.045, 0.048, 0.05), rough=0.65, metal=0.3, noise=0.2),
        flat("bridge concrete", (0.48, 0.46, 0.43), rough=0.85, noise=0.25, bump=0.3),
        water_mat(),
        facade_mat("ribbon office", (0.55, 0.54, 0.52), (0.60, 0.68, 0.74), 3.9, 6.0, 0.985, 0.46, refl0=0.18, lit=0.04,
                   wall_tex="concrete_wall_008", tex_size=2.71),
        flat("parapet cap", (0.36, 0.35, 0.33), rough=0.8, noise=0.3, bump=0.2),
        flat("rooftop units", (0.42, 0.43, 0.44), rough=0.5, metal=0.4, noise=0.25, bump=0.1),
    ]


(M_GLASS_B, M_GLASS_Z, M_PRECAST, M_BRICK, M_STUCCO, M_GRAVEL, M_OLDWALL, M_OLDROOF, M_STEEL, M_BCONC, M_WATER, M_RIBBON,
 M_PARAPET, M_MECH) = range(14)


def water_mat():
    """silty prairie river: dark green-brown, mirror-smooth with long ripples along the flow and fine wind chop"""
    m, nt, p = new_mat("river")
    p.inputs["Base Color"].default_value = (0.045, 0.06, 0.045, 1)
    p.inputs["Roughness"].default_value = 0.03
    p.inputs["IOR"].default_value = 1.333
    try:
        p.inputs["Specular IOR Level"].default_value = 0.65
    except Exception:
        pass
    tc = N(nt, "ShaderNodeTexCoord", -1100, -200)
    mp = N(nt, "ShaderNodeMapping", -900, -100)
    mp.inputs["Scale"].default_value = (0.6, 2.2, 1.0)
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    big = N(nt, "ShaderNodeTexNoise", -700, -100)
    big.inputs["Scale"].default_value = 0.08
    big.inputs["Detail"].default_value = 4.0
    nt.links.new(mp.outputs["Vector"], big.inputs["Vector"])
    fine = N(nt, "ShaderNodeTexNoise", -700, -350)
    fine.inputs["Scale"].default_value = 1.6
    fine.inputs["Detail"].default_value = 6.0
    nt.links.new(tc.outputs["Object"], fine.inputs["Vector"])
    add = N(nt, "ShaderNodeMath", -500, -200, operation="MULTIPLY_ADD")
    nt.links.new(fine.outputs["Fac"], add.inputs[0])
    add.inputs[1].default_value = 0.35
    nt.links.new(big.outputs["Fac"], add.inputs[2])
    b = N(nt, "ShaderNodeBump", -250, -200)
    b.inputs["Strength"].default_value = 0.22
    b.inputs["Distance"].default_value = 0.08
    nt.links.new(add.outputs[0], b.inputs["Height"])
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


def rooftop(acc, ring, z1, h, area, rng, bid):
    """parapet around the roof edge, and mechanical units or a penthouse on bigger roofs"""
    ph = 0.9 if h < 40 else 1.4
    u = 0.0
    n = len(ring)
    for i in range(n):
        a, b = ring[i], ring[(i + 1) % n]
        L = math.dist(a, b)
        if L < 0.05:
            continue
        acc.face([(a[0], a[1], z1), (b[0], b[1], z1), (b[0], b[1], z1 + ph), (a[0], a[1], z1 + ph)], M_PARAPET,
                 [(u, 0), (u + L, 0), (u + L, ph), (u, ph)], bid)
        u += L
    if area < 220:
        return
    r = obb(ring)
    if r is None:
        return
    c, e, n_, ha, hb = r
    e3, n3 = Vector((e.x, e.y, 0)), Vector((n_.x, n_.y, 0))
    units = []
    if h > 55:  # penthouse for the lifts and plant
        units.append((0.0, 0.0, ha * rng.uniform(0.35, 0.55), hb * rng.uniform(0.35, 0.6), rng.uniform(5.0, 9.0)))
    for _ in range(rng.randint(1, 4 if area > 900 else 2)):
        units.append((rng.uniform(-0.55, 0.55) * ha, rng.uniform(-0.5, 0.5) * hb, min(ha * 0.3, rng.uniform(1.2, 5.0)),
                      min(hb * 0.3, rng.uniform(1.0, 3.5)), rng.uniform(1.4, 3.6)))
    for du, dv, sa, sb, hh in units:
        cc = Vector((c.x, c.y, 0)) + e3 * du + n3 * dv
        q = [cc - e3 * sa - n3 * sb, cc + e3 * sa - n3 * sb, cc + e3 * sa + n3 * sb, cc - e3 * sa + n3 * sb]
        mi = M_MECH if hh < 5 else M_PARAPET
        for i in range(4):
            p0, p1 = q[i], q[(i + 1) % 4]
            acc.face([(p0.x, p0.y, z1), (p1.x, p1.y, z1), (p1.x, p1.y, z1 + hh), (p0.x, p0.y, z1 + hh)], mi,
                     [(0, 0), (1, 0), (1, 1), (0, 1)], bid)
        acc.face([(p.x, p.y, z1 + hh) for p in q], mi, [(0, 0), (1, 0), (1, 1), (0, 1)], bid)


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
            mi = (M_GLASS_B, M_GLASS_B, M_GLASS_Z, M_PRECAST, M_RIBBON)[int(bid * 5)]
        elif h > 22:
            mi = (M_PRECAST, M_STUCCO, M_GLASS_B, M_GLASS_Z, M_RIBBON, M_STUCCO)[int(bid * 6)]
        else:
            mi = (M_BRICK, M_BRICK, M_STUCCO, M_PRECAST, M_RIBBON)[int(bid * 5)]
        z1 = z0 + max(3.0, h - (bdg.get("mh", 0) or 0)) + 0.6
        extrude(acc_t, ring, z0, z1, mi, M_GRAVEL, bid)
        if h > 5:
            rooftop(acc_t, ring, z1, h, bdg["a"], rng, bid)
        n_t += 1
    mats = city_mats()
    acc_t.build("city buildings", mats, col)
    acc_h.build("city houses", mats, col)
    print("city: extruded", n_t, "houses", n_h)
    return mats, city


def water(col, mats, city):
    acc = Acc()
    for poly in city["water"]:
        zs = sorted(raw_z(x, y) for x, y in poly[:: max(1, len(poly) // 40)])
        z = zs[0] - Z_REF + 0.5  # lowest bank point: the bed under it is sunk 4 m, so the photo never shows through
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

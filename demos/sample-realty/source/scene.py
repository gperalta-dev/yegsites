"""Edmonton skyline-to-suburban-home flight, procedural, for the Local Studio real estate concept demo.

blender -b -P scene.py -- --out <dir> [--frames 0,60,120] [--samples 64] [--res 1280x720] [--save scene.blend]
Units are metres. North is +Y. The river runs roughly east-west through y=0, downtown sits on the north bank,
the suburb is south of the river and the hero house is at HERO.
"""
import math
import random
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector, noise

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def arg(name, default):
    return ARGS[ARGS.index(name) + 1] if name in ARGS else default


OUT = Path(arg("--out", "frames"))
FRAMES = arg("--frames", "")
SAMPLES = int(arg("--samples", "64"))
RES = [int(v) for v in arg("--res", "1280x720").split("x")]
SAVE = arg("--save", "")
FRAME_END = 239
rng = random.Random(7)

# ---------------------------------------------------------------- reset
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
COL = scene.collection


def link(obj):
    COL.objects.link(obj)
    return obj


# ---------------------------------------------------------------- materials
def mat(name, color=(0.8, 0.8, 0.8), rough=0.5, metal=0.0, emit=None, build=None):
    m = bpy.data.materials.new(name)
    try:
        m.use_nodes = True
    except Exception:
        pass
    nt = m.node_tree
    p = nt.nodes.get("Principled BSDF")
    p.inputs["Base Color"].default_value = (*color, 1)
    p.inputs["Roughness"].default_value = rough
    p.inputs["Metallic"].default_value = metal
    if emit:
        p.inputs["Emission Color"].default_value = (*emit[0], 1)
        p.inputs["Emission Strength"].default_value = emit[1]
    if build:
        build(nt, p)
    return m


def n(nt, kind, **props):
    node = nt.nodes.new(kind)
    for k, v in props.items():
        setattr(node, k, v)
    return node


def obj_color(nt, p):
    """base colour from the object's own colour, so one material serves every house"""
    info = n(nt, "ShaderNodeObjectInfo")
    nt.links.new(info.outputs["Color"], p.inputs["Base Color"])
    return info


def siding(nt, p):
    obj_color(nt, p)
    tc = n(nt, "ShaderNodeTexCoord")
    wave = n(nt, "ShaderNodeTexWave", wave_type="BANDS", bands_direction="Z")
    wave.inputs["Scale"].default_value = 0.9
    nt.links.new(tc.outputs["Object"], wave.inputs["Vector"])
    bump = n(nt, "ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.25
    nt.links.new(wave.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], p.inputs["Normal"])


def noisy(scale, a, b, strength=0.15):
    def build(nt, p):
        tex = n(nt, "ShaderNodeTexNoise")
        tex.inputs["Scale"].default_value = scale
        ramp = n(nt, "ShaderNodeValToRGB")
        ramp.color_ramp.elements[0].color = (*a, 1)
        ramp.color_ramp.elements[1].color = (*b, 1)
        nt.links.new(tex.outputs["Fac"], ramp.inputs["Fac"])
        nt.links.new(ramp.outputs["Color"], p.inputs["Base Color"])
        bump = n(nt, "ShaderNodeBump")
        bump.inputs["Strength"].default_value = strength
        nt.links.new(tex.outputs["Fac"], bump.inputs["Height"])
        nt.links.new(bump.outputs["Normal"], p.inputs["Normal"])
    return build


def shingles(nt, p):
    tc = n(nt, "ShaderNodeTexCoord")
    brick = n(nt, "ShaderNodeTexBrick")
    brick.inputs["Scale"].default_value = 1.6
    brick.inputs["Mortar Size"].default_value = 0.015
    brick.inputs["Color1"].default_value = (0.09, 0.09, 0.095, 1)
    brick.inputs["Color2"].default_value = (0.13, 0.125, 0.12, 1)
    brick.inputs["Mortar"].default_value = (0.05, 0.05, 0.05, 1)
    nt.links.new(tc.outputs["Object"], brick.inputs["Vector"])
    nt.links.new(brick.outputs["Color"], p.inputs["Base Color"])
    bump = n(nt, "ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.3
    nt.links.new(brick.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], p.inputs["Normal"])


def stone(nt, p):
    tc = n(nt, "ShaderNodeTexCoord")
    brick = n(nt, "ShaderNodeTexBrick")
    brick.inputs["Scale"].default_value = 3.2
    brick.inputs["Mortar Size"].default_value = 0.03
    brick.inputs["Color1"].default_value = (0.42, 0.37, 0.31, 1)
    brick.inputs["Color2"].default_value = (0.3, 0.27, 0.23, 1)
    brick.inputs["Mortar"].default_value = (0.55, 0.53, 0.5, 1)
    nt.links.new(tc.outputs["Object"], brick.inputs["Vector"])
    nt.links.new(brick.outputs["Color"], p.inputs["Base Color"])
    bump = n(nt, "ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.6
    nt.links.new(brick.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], p.inputs["Normal"])


def house_glass(nt, p):
    """dark reflective glass; roughly half the houses have a warm lamp on inside"""
    info = n(nt, "ShaderNodeObjectInfo")
    gt = n(nt, "ShaderNodeMath", operation="GREATER_THAN")
    gt.inputs[1].default_value = 0.72
    nt.links.new(info.outputs["Random"], gt.inputs[0])
    mul = n(nt, "ShaderNodeMath", operation="MULTIPLY")
    mul.inputs[1].default_value = 0.6
    nt.links.new(gt.outputs[0], mul.inputs[0])
    nt.links.new(mul.outputs[0], p.inputs["Emission Strength"])
    p.inputs["Emission Color"].default_value = (1.0, 0.55, 0.25, 1)


def curtain_wall(nt, p):
    """tower glass with a mullion grid; colour per tower from the object colour"""
    info = obj_color(nt, p)
    tc = n(nt, "ShaderNodeTexCoord")
    mapping = n(nt, "ShaderNodeMapping")
    mapping.inputs["Scale"].default_value = (1.0, 1.0, 1.0)
    nt.links.new(tc.outputs["Object"], mapping.inputs["Vector"])
    brick = n(nt, "ShaderNodeTexBrick", offset=0.0)
    brick.inputs["Scale"].default_value = 0.28
    brick.inputs["Mortar Size"].default_value = 0.05
    brick.inputs["Brick Width"].default_value = 1.0
    brick.inputs["Row Height"].default_value = 1.2
    nt.links.new(mapping.outputs["Vector"], brick.inputs["Vector"])
    mix = n(nt, "ShaderNodeMix", data_type="RGBA")
    nt.links.new(brick.outputs["Fac"], mix.inputs["Factor"])
    nt.links.new(info.outputs["Color"], mix.inputs[6])
    mix.inputs[7].default_value = (0.18, 0.19, 0.2, 1)
    nt.links.new(mix.outputs[2], p.inputs["Base Color"])
    rough = n(nt, "ShaderNodeMath", operation="MULTIPLY_ADD")
    rough.inputs[1].default_value = 0.4
    rough.inputs[2].default_value = 0.06
    nt.links.new(brick.outputs["Fac"], rough.inputs[0])
    nt.links.new(rough.outputs[0], p.inputs["Roughness"])
    # a few lit office floors
    office = n(nt, "ShaderNodeTexBrick", offset=0.5)
    office.inputs["Scale"].default_value = 0.07
    office.inputs["Mortar Size"].default_value = 0.0
    office.inputs["Color1"].default_value = (0, 0, 0, 1)
    office.inputs["Color2"].default_value = (1, 1, 1, 1)
    nt.links.new(mapping.outputs["Vector"], office.inputs["Vector"])
    gt = n(nt, "ShaderNodeMath", operation="GREATER_THAN")
    gt.inputs[1].default_value = 0.82
    nt.links.new(office.outputs["Color"], gt.inputs[0])
    mul = n(nt, "ShaderNodeMath", operation="MULTIPLY")
    mul.inputs[1].default_value = 1.2
    nt.links.new(gt.outputs[0], mul.inputs[0])
    nt.links.new(mul.outputs[0], p.inputs["Emission Strength"])
    p.inputs["Emission Color"].default_value = (1.0, 0.85, 0.65, 1)


def precast(nt, p):
    """concrete frame with a grid of dark punched windows, some lit"""
    info = n(nt, "ShaderNodeObjectInfo")
    tc = n(nt, "ShaderNodeTexCoord")
    brick = n(nt, "ShaderNodeTexBrick", offset=0.0)
    brick.inputs["Scale"].default_value = 0.3
    brick.inputs["Mortar Size"].default_value = 0.22
    brick.inputs["Brick Width"].default_value = 0.8
    brick.inputs["Row Height"].default_value = 1.1
    brick.inputs["Color1"].default_value = (0.02, 0.025, 0.03, 1)
    brick.inputs["Color2"].default_value = (0.03, 0.035, 0.04, 1)
    nt.links.new(tc.outputs["Object"], brick.inputs["Vector"])
    mix = n(nt, "ShaderNodeMix", data_type="RGBA")
    nt.links.new(brick.outputs["Fac"], mix.inputs["Factor"])
    nt.links.new(brick.outputs["Color"], mix.inputs[6])
    nt.links.new(info.outputs["Color"], mix.inputs[7])
    nt.links.new(mix.outputs[2], p.inputs["Base Color"])
    rough = n(nt, "ShaderNodeMath", operation="MULTIPLY_ADD")
    rough.inputs[1].default_value = 0.75
    rough.inputs[2].default_value = 0.08
    nt.links.new(brick.outputs["Fac"], rough.inputs[0])
    nt.links.new(rough.outputs[0], p.inputs["Roughness"])


def leaves(nt, p):
    info = n(nt, "ShaderNodeObjectInfo")
    ramp = n(nt, "ShaderNodeValToRGB")
    els = ramp.color_ramp.elements
    els[0].position, els[0].color = 0.0, (0.16, 0.24, 0.07, 1)
    els[1].position, els[1].color = 0.62, (0.24, 0.31, 0.08, 1)
    e = els.new(0.8)
    e.color = (0.55, 0.42, 0.06, 1)
    e = els.new(0.95)
    e.color = (0.62, 0.3, 0.05, 1)
    nt.links.new(info.outputs["Random"], ramp.inputs["Fac"])
    tex = n(nt, "ShaderNodeTexNoise")
    tex.inputs["Scale"].default_value = 3.0
    mix = n(nt, "ShaderNodeMix", data_type="RGBA", blend_type="MULTIPLY")
    mix.inputs["Factor"].default_value = 0.45
    nt.links.new(ramp.outputs["Color"], mix.inputs[6])
    nt.links.new(tex.outputs["Color"], mix.inputs[7])
    nt.links.new(mix.outputs[2], p.inputs["Base Color"])
    bump = n(nt, "ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.8
    nt.links.new(tex.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], p.inputs["Normal"])


def water(nt, p):
    tc = n(nt, "ShaderNodeTexCoord")
    tex = n(nt, "ShaderNodeTexNoise")
    tex.inputs["Scale"].default_value = 0.08
    tex.inputs["Detail"].default_value = 6
    nt.links.new(tc.outputs["Object"], tex.inputs["Vector"])
    bump = n(nt, "ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.08
    nt.links.new(tex.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], p.inputs["Normal"])


def city_ground(nt, p):
    """downtown blocks: brick texture where the mortar is the street grid"""
    tc = n(nt, "ShaderNodeTexCoord")
    brick = n(nt, "ShaderNodeTexBrick", offset=0.0)
    brick.inputs["Scale"].default_value = 0.0105
    brick.inputs["Mortar Size"].default_value = 0.09
    brick.inputs["Brick Width"].default_value = 1.0
    brick.inputs["Row Height"].default_value = 0.7
    brick.inputs["Color1"].default_value = (0.34, 0.33, 0.31, 1)
    brick.inputs["Color2"].default_value = (0.28, 0.29, 0.25, 1)
    brick.inputs["Mortar"].default_value = (0.05, 0.05, 0.055, 1)
    nt.links.new(tc.outputs["Object"], brick.inputs["Vector"])
    nt.links.new(brick.outputs["Color"], p.inputs["Base Color"])


M = {
    "grass": mat("grass", rough=0.95, build=noisy(0.02, (0.1, 0.15, 0.05), (0.2, 0.22, 0.09), 0.05)),
    "lawn": mat("lawn", rough=0.95, build=noisy(0.4, (0.1, 0.17, 0.05), (0.17, 0.22, 0.07), 0.1)),
    "bank": mat("bank", rough=0.95, build=noisy(0.05, (0.09, 0.14, 0.04), (0.22, 0.2, 0.1), 0.1)),
    "water": mat("water", color=(0.03, 0.06, 0.07), rough=0.03, build=water),
    "asphalt": mat("asphalt", rough=0.85, build=noisy(2.0, (0.04, 0.04, 0.045), (0.08, 0.08, 0.08), 0.05)),
    "concrete": mat("concrete", rough=0.8, build=noisy(1.5, (0.5, 0.49, 0.46), (0.62, 0.6, 0.57), 0.05)),
    "city": mat("city", rough=0.85, build=city_ground),
    "siding": mat("siding", rough=0.6, build=siding),
    "roof": mat("roof", rough=0.85, build=shingles),
    "trim": mat("trim", color=(0.7, 0.7, 0.68), rough=0.45),
    "glass": mat("glass", color=(0.02, 0.025, 0.03), rough=0.05, build=house_glass),
    "garage": mat("garage", color=(0.56, 0.55, 0.52), rough=0.55),
    "stone": mat("stone", rough=0.9, build=stone),
    "door": mat("door", color=(0.08, 0.06, 0.05), rough=0.4),
    "tower": mat("tower", rough=0.04, metal=0.85, build=curtain_wall),
    "precast": mat("precast", rough=0.75, build=precast),
    "sandstone": mat("sandstone", color=(0.62, 0.5, 0.36), rough=0.8),
    "dome": mat("dome", color=(0.32, 0.48, 0.38), rough=0.45, metal=0.6),
    "steel": mat("steel", color=(0.16, 0.12, 0.1), rough=0.5, metal=0.7),
    "leaves": mat("leaves", rough=0.8, build=leaves),
    "spruce": mat("spruce", color=(0.035, 0.08, 0.04), rough=0.85),
    "bark": mat("bark", color=(0.12, 0.09, 0.07), rough=0.9),
    "fence": mat("fence", color=(0.36, 0.27, 0.2), rough=0.8),
}


# ---------------------------------------------------------------- terrain
def river_y(x):
    return 70 * math.sin(x / 430) + 28 * math.sin(x / 170 + 1.3)


def ground_z(x, y):
    d = abs(y - river_y(x))
    if d < 70:
        return -57 + (d / 70) ** 2 * 5
    if d < 340:
        t = (d - 70) / 270
        t = t * t * (3 - 2 * t)
        wobble = 4 * noise.noise(Vector((x / 90, y / 90, 0.3))) * math.sin(t * math.pi)
        return -52 + 52 * t + wobble
    return (0.6 if y > -900 else 0.0) * noise.noise(Vector((x / 300, y / 300, 1.7)))


def mesh_obj(name, bm, mats, smooth=False):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for m in mats:
        me.materials.append(m)
    if smooth:
        for poly in me.polygons:
            poly.use_smooth = True
    return link(bpy.data.objects.new(name, me))


def terrain():
    bm = bmesh.new()
    size, steps = 7000, 350
    half = size / 2
    grid = []
    for j in range(steps + 1):
        row = []
        for i in range(steps + 1):
            x = -half + size * i / steps
            y = -half + size * j / steps + 600
            row.append(bm.verts.new((x, y, ground_z(x, y))))
        grid.append(row)
    for j in range(steps):
        for i in range(steps):
            f = bm.faces.new((grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]))
            cx = sum(v.co.x for v in f.verts) / 4
            cy = sum(v.co.y for v in f.verts) / 4
            d = abs(cy - river_y(cx))
            f.material_index = 1 if d < 345 else 0
    mesh_obj("terrain", bm, [M["grass"], M["bank"]], smooth=True)
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 600, -50.5))
    w = bpy.context.active_object
    w.name, w.scale = "river", (7000, 7000, 1)
    w.data.materials.append(M["water"])


# ---------------------------------------------------------------- helpers for boxes
def add_box(bm, lo, hi, mi):
    (x0, y0, z0), (x1, y1, z1) = lo, hi
    v = [bm.verts.new(c) for c in [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
                                   (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]]
    for idx in [(0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7), (4, 5, 6, 7), (3, 2, 1, 0)]:
        bm.faces.new([v[i] for i in idx]).material_index = mi


def add_gable(bm, x0, x1, y0, y1, z, rise, mi_roof, mi_wall, over=0.45, along="x"):
    """gable roof; ridge runs along x (or y) through the middle"""
    if along == "x":
        yc = (y0 + y1) / 2
        a = [bm.verts.new(c) for c in [(x0 - over, y0 - over, z - over * 0.5), (x1 + over, y0 - over, z - over * 0.5),
                                       (x1 + over, yc, z + rise), (x0 - over, yc, z + rise),
                                       (x1 + over, y1 + over, z - over * 0.5), (x0 - over, y1 + over, z - over * 0.5)]]
        bm.faces.new([a[0], a[1], a[2], a[3]]).material_index = mi_roof
        bm.faces.new([a[3], a[2], a[4], a[5]]).material_index = mi_roof
        g = [bm.verts.new(c) for c in [(x0, y0, z), (x0, y1, z), (x0, yc, z + rise - 0.1), (x1, y0, z), (x1, y1, z), (x1, yc, z + rise - 0.1)]]
        bm.faces.new([g[0], g[1], g[2]]).material_index = mi_wall
        bm.faces.new([g[3], g[5], g[4]]).material_index = mi_wall
    else:
        xc = (x0 + x1) / 2
        a = [bm.verts.new(c) for c in [(x0 - over, y0 - over, z - over * 0.5), (xc, y0 - over, z + rise),
                                       (xc, y1 + over, z + rise), (x0 - over, y1 + over, z - over * 0.5),
                                       (x1 + over, y0 - over, z - over * 0.5), (x1 + over, y1 + over, z - over * 0.5)]]
        bm.faces.new([a[0], a[1], a[2], a[3]]).material_index = mi_roof
        bm.faces.new([a[1], a[4], a[5], a[2]]).material_index = mi_roof
        g = [bm.verts.new(c) for c in [(x0, y1, z), (x1, y1, z), (xc, y1, z + rise - 0.1), (x0, y0, z), (x1, y0, z), (xc, y0, z + rise - 0.1)]]
        bm.faces.new([g[0], g[1], g[2]]).material_index = mi_wall
        bm.faces.new([g[3], g[5], g[4]]).material_index = mi_wall


def window(bm, cx, cy, cz, w, h, face):
    """framed window sitting just proud of a wall; face is +y, -y, +x or -x"""
    t, fr = 0.08, 0.09
    if face in ("+y", "-y"):
        s = 1 if face == "+y" else -1
        add_box(bm, (cx - w / 2 - fr, cy, cz - h / 2 - fr), (cx + w / 2 + fr, cy + s * t, cz + h / 2 + fr), 2)
        add_box(bm, (cx - w / 2, cy, cz - h / 2), (cx + w / 2, cy + s * (t + 0.02), cz + h / 2), 3)
    else:
        s = 1 if face == "+x" else -1
        add_box(bm, (cx, cy - w / 2 - fr, cz - h / 2 - fr), (cx + s * t, cy + w / 2 + fr, cz + h / 2 + fr), 2)
        add_box(bm, (cx, cy - w / 2, cz - h / 2), (cx + s * (t + 0.02), cy + w / 2, cz + h / 2), 3)


HOUSE_MATS = ["siding", "roof", "trim", "glass", "garage", "stone", "concrete", "door", "lawn", "fence"]


def house_mesh(name, w=12, d=12, gw=7.0, gside=-1, bonus=True, hero=False, setback=14.0):
    """front-attached double garage two-storey, front faces +y at y=0"""
    bm = bmesh.new()
    h = 6.0
    x0, x1 = -w / 2, w / 2
    add_box(bm, (x0, -d, 0), (x1, 0, h), 0)
    add_box(bm, (x0, -d, 0), (x1, 0.02, 0.7), 5)  # stone skirt
    # garage pushed forward on one side
    gx0, gx1 = (x0 - 0.5, x0 - 0.5 + gw) if gside < 0 else (x1 + 0.5 - gw, x1 + 0.5)
    gy1 = 2.6
    gh = h if bonus else 3.1
    add_box(bm, (gx0, -6.5, 0), (gx1, gy1, gh), 0)
    add_box(bm, (gx0 + 0.6, gy1, 0), (gx1 - 0.6, gy1 + 0.06, 2.4), 4)  # garage door
    for k in range(4):
        add_box(bm, (gx0 + 0.6, gy1 + 0.06, 0.55 + k * 0.55), (gx1 - 0.6, gy1 + 0.08, 0.58 + k * 0.55), 2)
    # stone columns at the garage corners
    add_box(bm, (gx0 - 0.15, gy1 - 0.5, 0), (gx0 + 0.45, gy1 + 0.1, 2.9), 5)
    add_box(bm, (gx1 - 0.45, gy1 - 0.5, 0), (gx1 + 0.15, gy1 + 0.1, 2.9), 5)
    # roofs: main ridge along x, garage gable facing the street
    add_gable(bm, x0, x1, -d, 0, h, 3.0, 1, 0)
    add_gable(bm, gx0, gx1, -6.5, gy1, gh, 2.6 if bonus else 2.2, 1, 0, along="y")
    # front door and windows on the living side
    lx0, lx1 = (gx1, x1) if gside < 0 else (x0, gx0)
    lw = lx1 - lx0
    dcx = lx0 + lw * 0.32
    add_box(bm, (dcx - 0.55, 0, 0), (dcx + 0.55, 0.1, 2.3), 7)
    add_box(bm, (dcx - 0.75, 0, 2.3), (dcx + 0.75, 0.12, 2.45), 2)
    window(bm, lx0 + lw * 0.72, 0, 1.6, 1.6, 1.5, "+y")
    window(bm, lx0 + lw * 0.5, 0, 4.4, 2.2, 1.3, "+y")
    if bonus:
        window(bm, (gx0 + gx1) / 2, gy1, 4.4, 2.6, 1.3, "+y")
    # sides and back
    for z in (1.6, 4.4):
        window(bm, x1, -d * 0.35, z, 1.2, 1.3, "+x")
        window(bm, x0, -d * 0.6, z, 1.2, 1.3, "-x")
        for fx in (-0.3, 0.05, 0.35):
            window(bm, w * fx, -d, z, 1.4, 1.35, "-y")
    # driveway and front walk
    add_box(bm, (gx0, gy1, 0), (gx1, setback, 0.04), 6)
    add_box(bm, (dcx - 0.7, 0.1, 0), (dcx + 0.7, setback, 0.035), 6)
    if hero:
        # covered porch with stone columns
        add_box(bm, (dcx - 1.8, 0, 0), (dcx + 1.8, 1.8, 0.25), 6)
        add_box(bm, (dcx - 1.9, 0, 2.9), (dcx + 1.9, 1.95, 3.1), 2)
        for px in (dcx - 1.65, dcx + 1.45):
            add_box(bm, (px, 1.5, 0.25), (px + 0.3, 1.8, 2.9), 5)
        add_gable(bm, dcx - 1.9, dcx + 1.9, 0, 1.95, 3.1, 1.2, 1, 0, over=0.2, along="y")
        # back deck and fenced yard
        add_box(bm, (x0 + 1, -d - 4, 0), (x0 + 7, -d, 0.6), 9)
        window(bm, x0 + 4, -d, 1.4, 2.2, 2.2, "-y")
        for fx in [x0 - 1 + i * 0.25 for i in range(int((w + 2) / 0.25))]:
            add_box(bm, (fx, -d - 14, 0), (fx + 0.2, -d - 13.9, 1.8), 9)
        for fy in [-d - 14 + i * 0.25 for i in range(int(14 / 0.25))]:
            add_box(bm, (x0 - 1, fy, 0), (x0 - 0.9, fy + 0.2, 1.8), 9)
            add_box(bm, (x1 + 0.9, fy, 0), (x1 + 1, fy + 0.2, 1.8), 9)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for k in HOUSE_MATS:
        me.materials.append(M[k])
    return me


SIDING = [(0.48, 0.47, 0.44), (0.62, 0.58, 0.5), (0.3, 0.31, 0.32), (0.55, 0.52, 0.47), (0.2, 0.22, 0.23),
          (0.66, 0.64, 0.6), (0.42, 0.36, 0.29), (0.36, 0.4, 0.42)]


# ---------------------------------------------------------------- trees
def tree_meshes():
    import mathutils
    bm = bmesh.new()
    lumps = [(0, 0, 0, 1.0)] + [(math.cos(a) * 0.55, math.sin(a) * 0.55, rng.uniform(-0.25, 0.35), rng.uniform(0.55, 0.75))
                               for a in [i * 1.2566 for i in range(5)]] + [(0, 0, 0.6, 0.6)]
    for x, y, z, rad in lumps:
        bmesh.ops.create_icosphere(bm, subdivisions=2, radius=rad, matrix=mathutils.Matrix.Translation((x, y, z)))
    for v in bm.verts:
        v.co += v.normal * 0.18 * noise.noise(v.co * 3.1)
    for f in bm.faces:
        f.smooth = True
    bmesh.ops.create_cone(bm, cap_ends=False, segments=6, radius1=0.12, radius2=0.08, depth=1.4,
                          matrix=mathutils.Matrix.Translation((0, 0, -1.2)))
    for f in bm.faces[-6:]:
        f.material_index = 1
    leafy = bpy.data.meshes.new("leafy")
    bm.to_mesh(leafy)
    bm.free()
    leafy.materials.append(M["leaves"])
    leafy.materials.append(M["bark"])
    bm = bmesh.new()
    tiers = 6
    for i in range(tiers):
        z0 = 0.12 + i * 0.14
        r = 1.0 - i * 0.15
        bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=r, radius2=0.03, depth=0.32,
                              matrix=mathutils.Matrix.Translation((0, 0, z0 + 0.16)))
    for v in bm.verts:
        if v.co.z > 0.05:
            v.co.x *= 1 + 0.25 * noise.noise(v.co * 9)
            v.co.y *= 1 + 0.25 * noise.noise(v.co * 9 + Vector((3, 1, 0)))
    spruce = bpy.data.meshes.new("spruce")
    bm.to_mesh(spruce)
    bm.free()
    spruce.materials.append(M["spruce"])
    return leafy, spruce


LEAFY, SPRUCE = None, None


def tree(x, y, z, kind=None, s=1.0):
    kind = kind or ("spruce" if rng.random() < 0.3 else "leafy")
    if kind == "spruce":
        o = link(bpy.data.objects.new("t", SPRUCE))
        hgt = rng.uniform(9, 16) * s
        o.scale = (hgt * 0.24, hgt * 0.24, hgt)
        o.location = (x, y, z)
    else:
        o = link(bpy.data.objects.new("t", LEAFY))
        r = rng.uniform(2.2, 3.6) * s
        o.scale = (r, r, r * rng.uniform(1.05, 1.3))
        o.location = (x, y, z + r * 1.9)
    o.rotation_euler.z = rng.uniform(0, 6.28)
    return o


# ---------------------------------------------------------------- downtown
def tower(x, y, w, d, h, color, kind="tower", top=None):
    bm = bmesh.new()
    add_box(bm, (-w / 2, -d / 2, 0), (w / 2, d / 2, h), 0)
    if top == "taper":  # slim crown like the tallest downtown tower
        add_box(bm, (-w * 0.32, -d * 0.32, h), (w * 0.32, d * 0.32, h + 14), 0)
        add_box(bm, (-w * 0.14, -d * 0.14, h + 14), (w * 0.14, d * 0.14, h + 24), 0)
    elif top == "slope":
        v = [bm.verts.new(c) for c in [(-w / 2, -d / 2, h), (w / 2, -d / 2, h), (w / 2, d / 2, h + 16), (-w / 2, d / 2, h + 16),
                                       (-w / 2, d / 2, h), (w / 2, d / 2, h)]]
        bm.faces.new([v[0], v[1], v[2], v[3]])
        bm.faces.new([v[1], v[5], v[2]])
        bm.faces.new([v[0], v[3], v[4]])
        bm.faces.new([v[4], v[3], v[2], v[5]])
    elif top == "step":
        add_box(bm, (-w * 0.4, -d * 0.4, h), (w * 0.4, d * 0.4, h + 8), 0)
    o = mesh_obj("tower", bm, [M[kind]])
    o.location = (x, y, ground_z(x, y) - 1)
    o.color = (*color, 1)
    return o


def downtown():
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 860, 0.15))
    g = bpy.context.active_object
    g.scale = (1500, 760, 1)
    g.data.materials.append(M["city"])
    blue, teal, bronze, grey, white = (0.05, 0.09, 0.13), (0.05, 0.11, 0.11), (0.09, 0.06, 0.04), (0.08, 0.09, 0.1), (0.6, 0.58, 0.54)
    tower(0, 700, 36, 36, 226, blue, top="taper")          # tallest, slim crown
    tower(-140, 640, 46, 34, 136, teal, top="slope")       # sloped glass top
    tower(-60, 760, 52, 40, 140, bronze, top="step")       # dark bronze slab
    tower(130, 760, 36, 36, 108, white, kind="precast")    # white concrete grid
    tower(80, 880, 40, 40, 180, grey, top="step")          # arena-district tower
    tower(-200, 800, 40, 30, 120, blue)
    tower(200, 660, 34, 30, 95, grey, top="step")
    tower(-20, 600, 30, 28, 82, white, kind="precast")
    tower(-280, 700, 34, 34, 90, teal)
    tower(260, 860, 30, 30, 110, blue, top="slope")
    # arena: low oval with a metallic roof
    bpy.ops.mesh.primitive_uv_sphere_add(segments=40, ring_count=16, location=(40, 1000, -4))
    a = bpy.context.active_object
    a.scale = (95, 70, 22)
    a.data.materials.append(M["steel"])
    for _ in range(140):
        x, y = rng.uniform(-620, 620), rng.uniform(560, 1180)
        if abs(x) < 70 and 640 < y < 760:
            continue
        h = rng.choice([14, 22, 30, 38, 46, 60, 75]) * rng.uniform(0.8, 1.2)
        kind = rng.choice(["tower", "precast", "precast"])
        col = rng.choice([blue, teal, grey, white, (0.5, 0.45, 0.38), (0.45, 0.3, 0.22), (0.62, 0.56, 0.47)])
        tower(x, y, rng.uniform(20, 42), rng.uniform(20, 42), h, col, kind=kind, top=rng.choice([None, None, "step"]))
    for _ in range(160):  # street trees between blocks
        x, y = rng.uniform(-700, 700), rng.uniform(520, 1200)
        tree(round(x / 95) * 95 + rng.choice([-46, 46]), y, 0, "leafy", 0.7)


def legislature(x, y):
    z = ground_z(x, y)
    for lo, hi in [((-55, -32, 0), (55, 32, 22)), ((-14, 32, 0), (14, 44, 18))]:
        bm = bmesh.new()
        add_box(bm, lo, hi, 0)
        o = mesh_obj("leg", bm, [M["sandstone"]])
        o.location = (x, y, z)
    bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=13, depth=14, location=(x, y, z + 29))
    bpy.context.active_object.data.materials.append(M["sandstone"])
    bpy.ops.mesh.primitive_uv_sphere_add(segments=40, ring_count=20, radius=14, location=(x, y, z + 36))
    dome = bpy.context.active_object
    dome.scale.z = 1.15
    dome.data.materials.append(M["dome"])
    bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=2.5, depth=8, location=(x, y, z + 55))
    bpy.context.active_object.data.materials.append(M["sandstone"])
    for i in range(40):  # formal grounds
        tree(x + rng.uniform(-150, 150), y - rng.uniform(50, 130), z, "leafy", 0.8)


def high_level_bridge(x):
    """long steel truss deck at bank height on tall steel trestle towers"""
    y0, y1 = river_y(x) - 330, river_y(x) + 330
    bm = bmesh.new()
    add_box(bm, (x - 7, y0, -3), (x + 7, y1, 0.5), 0)
    for sx in (x - 7, x + 6.4):
        add_box(bm, (sx, y0, 0.5), (sx + 0.6, y1, 1.0), 0)
        add_box(bm, (sx, y0, 9.0), (sx + 0.6, y1, 9.6), 0)
        y = y0
        while y < y1:
            add_box(bm, (sx, y, 0.5), (sx + 0.6, y + 0.6, 9.6), 0)
            y += 9
    y = y0 + 20
    while y < y1 - 10:
        zb = ground_z(x, y) - 2
        for sx in (x - 6, x + 5):
            add_box(bm, (sx, y, zb), (sx + 1, y + 1, -3), 0)
            add_box(bm, (sx, y + 9, zb), (sx + 1, y + 10, -3), 0)
        add_box(bm, (x - 6, y, -12), (x + 6, y + 10, -11), 0)
        y += 40
    mesh_obj("bridge", bm, [M["steel"]])


# ---------------------------------------------------------------- suburb
HERO = Vector((0.0, -1700.0, 0.0))
STREETS = [-760 - 120 * k for k in range(16)]


def street_y(base, x):
    return base + 34 * math.sin(x / 190 + base * 0.013)


def suburb():
    variants = [house_mesh(f"house{i}", w=rng.uniform(10.5, 13), d=rng.uniform(10.5, 13), gw=rng.uniform(6.6, 7.4),
                           gside=rng.choice([-1, 1]), bonus=rng.random() < 0.6) for i in range(8)]
    hero_me = house_mesh("hero", w=13.5, d=13, gw=7.3, gside=-1, bonus=True, hero=True)
    # arterial road south of the river valley
    for base in STREETS:
        bm = bmesh.new()
        prev = None
        for i in range(0, 321):
            x = -1800 + i * 11.25
            yc = street_y(base, x)
            a, b = bm.verts.new((x, yc - 5, 0.05)), bm.verts.new((x, yc + 5, 0.05))
            s1, s2 = bm.verts.new((x, yc - 7.5, 0.06)), bm.verts.new((x, yc + 7.5, 0.06))
            if prev:
                pa, pb, ps1, ps2 = prev
                bm.faces.new((pa, a, b, pb)).material_index = 0
                bm.faces.new((ps1, s1, a, pa)).material_index = 1
                bm.faces.new((pb, b, s2, ps2)).material_index = 1
            prev = (a, b, s1, s2)
        mesh_obj("street", bm, [M["asphalt"], M["concrete"]])
    bm = bmesh.new()
    add_box(bm, (-2500, -640, 0), (2500, -616, 0.07), 0)
    mesh_obj("arterial", bm, [M["asphalt"]])
    hero_placed = False
    for si, base in enumerate(STREETS):
        for side in (1, -1):
            x = -1780 + rng.uniform(0, 8)
            while x < 1780:
                w = rng.uniform(16, 19)
                yc = street_y(base, x)
                slope = math.atan2(street_y(base, x + 1) - yc, 1)
                py = yc + side * 21.5
                is_hero = (not hero_placed and base == -1720 and side == -1 and abs(x - HERO.x) < 10)
                me = hero_me if is_hero else rng.choice(variants)
                o = link(bpy.data.objects.new("hero" if is_hero else "house", me))
                o.location = (x, py, 0)
                o.rotation_euler.z = slope + (0 if side < 0 else math.pi)
                o.color = (*(SIDING[2] if is_hero else rng.choice(SIDING)), 1)
                if is_hero:
                    hero_placed = True
                    HERO.x, HERO.y = x, py
                    o.color = (0.27, 0.29, 0.3, 1)
                    for dx, dy in [(-13, -6), (14, -8), (-4, -26), (7, -28)]:
                        tree(x + dx, py + dy, 0, "spruce" if dy < 0 else "leafy", 0.9)
                if rng.random() < 0.7 and not is_hero and abs(x - HERO.x) > 25:  # boulevard tree
                    tree(x + rng.uniform(-3, 3), yc + side * 9.5, 0, "leafy", 0.75)
                if rng.random() < 0.9:  # backyard tree
                    tree(x + rng.uniform(-6, 6), py + side * rng.uniform(22, 30), 0, None, 0.9)
                x += w
    # park with a pond in the middle of the neighbourhood
    for _ in range(120):
        tree(rng.uniform(-2300, -1850), rng.uniform(-2600, -700), 0, None, 1.0)
        tree(rng.uniform(1850, 2300), rng.uniform(-2600, -700), 0, None, 1.0)
    for _ in range(1600):  # strip of trees between the arterial and the valley edge
        x = rng.uniform(-2300, 2300)
        tree(x, rng.uniform(-610, -440), 0, None, 1.2)


# ---------------------------------------------------------------- valley trees
def valley_trees():
    placed = 0
    while placed < 26000:
        x = rng.uniform(-2300, 2300)
        y = river_y(x) + rng.choice([-1, 1]) * rng.uniform(75, 360)
        if -700 < x < 700 and y > 520:
            continue
        tree(x, y, ground_z(x, y), "spruce" if rng.random() < 0.18 else "leafy", rng.uniform(1.2, 1.8))
        placed += 1


# ---------------------------------------------------------------- sky, sun, render
def world_and_sun(elev=7.0, rot=-112.0):
    w = bpy.data.worlds.new("sky")
    scene.world = w
    try:
        w.use_nodes = True
    except Exception:
        pass
    nt = w.node_tree
    bg = nt.nodes.get("Background")
    sky = nt.nodes.new("ShaderNodeTexSky")
    for t in ("MULTIPLE_SCATTERING", "SINGLE_SCATTERING", "NISHITA"):
        try:
            sky.sky_type = t
            break
        except Exception:
            continue
    for k, v in dict(sun_elevation=math.radians(elev), sun_rotation=math.radians(rot), altitude=700.0, air_density=1.0,
                     aerosol_density=0.9, dust_density=0.9, ozone_density=1.0, sun_disc=False, sun_intensity=1.0).items():
        try:
            setattr(sky, k, v)
        except Exception:
            pass
    nt.links.new(sky.outputs["Color"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = 0.13
    sun = bpy.data.lights.new("sun", "SUN")
    sun.energy = 5.0
    sun.angle = math.radians(0.8)
    sun.color = (1.0, 0.76, 0.52)
    so = link(bpy.data.objects.new("sun", sun))
    so.rotation_euler = (math.radians(90 - elev), 0, math.radians(rot))


def catmull(points, t):
    """centripetal-ish Catmull-Rom through points, t in 0..1 over the whole path"""
    n = len(points) - 1
    f = min(t * n, n - 1e-6)
    i = int(f)
    u = f - i
    p0 = points[max(i - 1, 0)]
    p1, p2 = points[i], points[i + 1]
    p3 = points[min(i + 2, n)]
    return 0.5 * ((2 * p1) + (-p0 + p2) * u + (2 * p0 - 5 * p1 + 4 * p2 - p3) * u * u + (-p0 + 3 * p1 - 3 * p2 + p3) * u * u * u)


def ease(t):
    return t * t * (3 - 2 * t)


def camera_path():
    cam = bpy.data.cameras.new("cam")
    cam.lens = 30
    cam.clip_start, cam.clip_end = 0.5, 12000
    co = link(bpy.data.objects.new("cam", cam))
    scene.camera = co
    hx, hy = HERO.x, HERO.y
    focus = link(bpy.data.objects.new("focus", None))
    focus.location = (hx, hy - 5, 4)
    cam.dof.use_dof = True
    cam.dof.focus_object = focus
    for f, fstop in [(0, 64.0), (128, 64.0), (150, 3.2), (FRAME_END, 3.2)]:
        cam.dof.aperture_fstop = fstop
        cam.dof.keyframe_insert("aperture_fstop", frame=f)
    fly_end = 150
    pos = [Vector(v) for v in [(420, 1500, 230), (260, 1220, 300), (60, 640, 340), (0, -200, 300), (hx + 20, hy + 420, 120),
                               (hx + 34, hy + 100, 40), (hx + 27, hy + 36, 21)]]
    tgt = [Vector(v) for v in [(-20, 720, 120), (-30, 560, 60), (0, -300, 0), (hx, hy - 200, 0), (hx, hy, 0),
                               (hx, hy - 4, 4), (hx, hy - 6, 4.5)]]
    for f in range(FRAME_END + 1):
        if f <= fly_end:
            t = ease(f / fly_end)
            p, q = catmull(pos, t), catmull(tgt, t)
        else:  # orbit the house, starting from the front, ending on a front three-quarter view
            u = ease((f - fly_end) / (FRAME_END - fly_end))
            a = math.atan2(pos[-1].y - hy + 6, pos[-1].x - hx) + u * math.radians(330)
            r = 40 - 4 * math.sin(u * math.pi)
            p = Vector((hx + r * math.cos(a), hy - 6 + r * math.sin(a), 21 + 4 * math.sin(u * math.pi)))
            q = Vector((hx, hy - 6, 3.0))
        co.location = p
        co.rotation_euler = (q - p).to_track_quat("-Z", "Y").to_euler()
        co.keyframe_insert("location", frame=f)
        co.keyframe_insert("rotation_euler", frame=f)
    for fc in getattr(co.animation_data.action, "fcurves", []):
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"


def render_setup():
    r = scene.render
    r.engine = "CYCLES"
    r.resolution_x, r.resolution_y = RES
    r.resolution_percentage = 100
    r.image_settings.file_format = "PNG"
    scene.frame_start, scene.frame_end = 0, FRAME_END
    c = scene.cycles
    c.samples = SAMPLES
    c.use_adaptive_sampling = True
    c.adaptive_threshold = 0.02
    c.use_denoising = True
    for dn in ("OPTIX", "OPENIMAGEDENOISE"):
        try:
            c.denoiser = dn
            break
        except Exception:
            pass
    c.max_bounces, c.diffuse_bounces, c.glossy_bounces, c.transmission_bounces = 6, 3, 3, 2
    c.sample_clamp_indirect = 8
    c.caustics_reflective = c.caustics_refractive = False
    prefs = bpy.context.preferences.addons["cycles"].preferences
    for dtype in ("OPTIX", "CUDA"):
        try:
            prefs.compute_device_type = dtype
            prefs.get_devices()
            if any(d.type == dtype for d in prefs.devices):
                for d in prefs.devices:
                    d.use = d.type == dtype
                c.device = "GPU"
                print("render device", dtype)
                break
        except Exception as e:
            print("device", dtype, e)
    vs = scene.view_settings
    try:
        vs.view_transform = "AgX"
        vs.look = "AgX - Medium High Contrast"
    except Exception:
        pass
    vs.exposure = 0.25
    # light mist so far things fade like real air
    vol = bpy.data.materials.new("haze")
    try:
        vol.use_nodes = True
    except Exception:
        pass
    nt = vol.node_tree
    nt.nodes.remove(nt.nodes.get("Principled BSDF"))
    vs_node = nt.nodes.new("ShaderNodeVolumePrincipled")
    vs_node.inputs["Density"].default_value = 0.00005
    vs_node.inputs["Color"].default_value = (0.95, 0.85, 0.75, 1)
    nt.links.new(vs_node.outputs[0], nt.nodes.get("Material Output").inputs["Volume"])
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, -200, 400))
    box = bpy.context.active_object
    box.name, box.scale = "haze", (9000, 9000, 1000)
    box.data.materials.append(vol)
    box.visible_shadow = False
    c.volume_step_rate = 8.0
    c.volume_max_steps = 64


# ---------------------------------------------------------------- build and render
LEAFY, SPRUCE = tree_meshes()
terrain()
downtown()
legislature(-470, river_y(-470) + 380)
high_level_bridge(-560)
suburb()
valley_trees()
world_and_sun()
camera_path()
render_setup()
print("objects", len(bpy.data.objects), "hero at", tuple(round(v) for v in HERO))
if SAVE:
    bpy.ops.wm.save_as_mainfile(filepath=str(Path(SAVE).resolve()))
OUT.mkdir(parents=True, exist_ok=True)
frames = [int(f) for f in FRAMES.split(",")] if FRAMES else range(FRAME_END + 1)
for f in frames:
    scene.frame_set(f)
    scene.render.filepath = str((OUT / f"f{f:03d}.png").resolve())
    bpy.ops.render.render(write_still=True)
    print("rendered", f, flush=True)

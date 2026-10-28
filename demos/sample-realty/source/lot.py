"""one suburban lot around a house, in the house's local frame (front wall y=0 facing -y, x across the lot).

driveway and walk in broom-finished concrete with control joints, mulch beds with edging, side-yard river rock, a cedar
privacy fence with posts, rails and a gate, a back deck with railing and stairs, and where the plants go. the lawn is
returned as rectangles so the hero lot can grow real hair grass on them.
"""
import math
import random

from mathutils import Vector

from common import MB, N, flat, new_mat, pbr

M_CONC, M_MULCH, M_ROCK, M_FENCE, M_POST, M_DECK, M_EDGE, M_LAWN = range(8)
LOT_DEPTH = 36.0
FRONT_SETBACK = 6.2  # garage face to property line


def concrete_mat(name="driveway concrete", joint=3.0):
    """broom-finish concrete with saw-cut control joints every `joint` metres (in the UV space, metres)"""
    m, nt, p = new_mat(name)
    tc = N(nt, "ShaderNodeTexCoord", -1300, 0)
    nz = N(nt, "ShaderNodeTexNoise", -1000, 300)
    nz.inputs["Scale"].default_value = 0.6
    nz.inputs["Detail"].default_value = 8.0
    nt.links.new(tc.outputs["UV"], nz.inputs["Vector"])
    ramp = N(nt, "ShaderNodeValToRGB", -800, 300)
    ramp.color_ramp.elements[0].color = (0.34, 0.33, 0.31, 1)
    ramp.color_ramp.elements[1].color = (0.52, 0.50, 0.47, 1)
    nt.links.new(nz.outputs["Fac"], ramp.inputs["Fac"])
    # joints: thin lines where the uv crosses multiples of `joint`
    sep = N(nt, "ShaderNodeSeparateXYZ", -1100, -200)
    nt.links.new(tc.outputs["UV"], sep.inputs["Vector"])
    lines = []
    for comp in ("X", "Y"):
        div = N(nt, "ShaderNodeMath", -950, -200, operation="DIVIDE")
        div.inputs[1].default_value = joint
        nt.links.new(sep.outputs[comp], div.inputs[0])
        fr = N(nt, "ShaderNodeMath", -800, -200, operation="FRACT")
        nt.links.new(div.outputs[0], fr.inputs[0])
        d = N(nt, "ShaderNodeMath", -650, -200, operation="PINGPONG")
        d.inputs[1].default_value = 0.5
        nt.links.new(fr.outputs[0], d.inputs[0])
        st = N(nt, "ShaderNodeMath", -500, -200, operation="LESS_THAN")
        st.inputs[1].default_value = 0.004 / joint
        nt.links.new(d.outputs[0], st.inputs[0])
        lines.append(st)
    mx = N(nt, "ShaderNodeMath", -350, -200, operation="MAXIMUM")
    nt.links.new(lines[0].outputs[0], mx.inputs[0])
    nt.links.new(lines[1].outputs[0], mx.inputs[1])
    dark = N(nt, "ShaderNodeMix", -300, 300, data_type="RGBA")
    nt.links.new(mx.outputs[0], dark.inputs["Factor"])
    nt.links.new(ramp.outputs["Color"], dark.inputs["A"])
    dark.inputs["B"].default_value = (0.12, 0.115, 0.11, 1)
    nt.links.new(dark.outputs["Result"], p.inputs["Base Color"])
    p.inputs["Roughness"].default_value = 0.88
    # broom texture: stretched noise across the slab, plus the joint groove
    mp = N(nt, "ShaderNodeMapping", -1000, -500)
    mp.inputs["Scale"].default_value = (12.0, 300.0, 1.0)
    nt.links.new(tc.outputs["UV"], mp.inputs["Vector"])
    br = N(nt, "ShaderNodeTexNoise", -800, -500)
    br.inputs["Scale"].default_value = 1.0
    br.inputs["Detail"].default_value = 3.0
    nt.links.new(mp.outputs["Vector"], br.inputs["Vector"])
    h = N(nt, "ShaderNodeMath", -500, -500, operation="SUBTRACT")
    nt.links.new(br.outputs["Fac"], h.inputs[0])
    nt.links.new(mx.outputs[0], h.inputs[1])
    bump = N(nt, "ShaderNodeBump", -250, -500)
    bump.inputs["Strength"].default_value = 0.35
    bump.inputs["Distance"].default_value = 0.004
    nt.links.new(h.outputs[0], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], p.inputs["Normal"])
    return m


def lawn_mat():
    """mown lawn seen from a distance: leafy grass photo pushed green, with mowing stripes and patchy variation"""
    m = pbr("mown lawn", "leafy_grass", 2.0, tint=(0.40, 0.62, 0.20), sat=1.6, value=0.75, rough=(0.75, 1.0), bump=0.8)
    nt = m.node_tree
    p = nt.nodes.get("Principled BSDF")
    src = p.inputs["Base Color"].links[0].from_socket
    tc = N(nt, "ShaderNodeTexCoord", -900, 700)
    sep = N(nt, "ShaderNodeSeparateXYZ", -700, 700)
    nt.links.new(tc.outputs["UV"], sep.inputs["Vector"])
    wave = N(nt, "ShaderNodeMath", -500, 700, operation="PINGPONG")
    wave.inputs[1].default_value = 0.6
    nt.links.new(sep.outputs["X"], wave.inputs[0])
    stripe = N(nt, "ShaderNodeMath", -350, 700, operation="GREATER_THAN")
    stripe.inputs[1].default_value = 0.3
    nt.links.new(wave.outputs[0], stripe.inputs[0])
    nz = N(nt, "ShaderNodeTexNoise", -500, 900)
    nz.inputs["Scale"].default_value = 0.25
    nt.links.new(tc.outputs["UV"], nz.inputs["Vector"])
    mix = N(nt, "ShaderNodeMix", -100, 700, data_type="RGBA", blend_type="MULTIPLY")
    mix.inputs["Factor"].default_value = 1.0
    nt.links.new(src, mix.inputs["A"])
    ramp = N(nt, "ShaderNodeMapRange", -200, 900)
    ramp.inputs["To Min"].default_value, ramp.inputs["To Max"].default_value = 0.8, 1.15
    add = N(nt, "ShaderNodeMath", -250, 800, operation="MULTIPLY_ADD")
    nt.links.new(stripe.outputs[0], add.inputs[0])
    add.inputs[1].default_value = 0.12
    nt.links.new(nz.outputs["Fac"], add.inputs[2])
    nt.links.new(add.outputs[0], ramp.inputs["Value"])
    comb = N(nt, "ShaderNodeCombineColor", -50, 900)
    for k in ("Red", "Green", "Blue"):
        nt.links.new(ramp.outputs["Result"], comb.inputs[k])
    nt.links.new(comb.outputs["Color"], mix.inputs["B"])
    nt.links.new(mix.outputs["Result"], p.inputs["Base Color"])
    return m


def lot_mats():
    return [concrete_mat(),
            pbr("bark mulch", "brown_mud_leaves_01", 1.3, value=0.55, sat=0.7, rough=(0.8, 1.0), bump=1.5),
            pbr("river rock", "aerial_grass_rock", 3.0, value=1.25, sat=0.0, rough=(0.6, 0.9), bump=2.0),
            pbr("cedar fence", "brown_planks_07", 1.0, rot=math.pi / 2, tint=(0.95, 0.72, 0.52), value=0.9, rough=(0.6, 0.9), bump=1.0),
            flat("fence post", (0.30, 0.20, 0.13), rough=0.8, noise=0.2, bump=0.3),
            pbr("deck boards", "brown_planks_07", 1.0, tint=(0.75, 0.5, 0.32), rough=(0.5, 0.85), bump=1.2),
            flat("black edging", (0.02, 0.02, 0.02), rough=0.5),
            lawn_mat()]


def fence(mb, a, b, h=1.83, gate_at=None):
    """privacy fence from a to b (2D): posts every 2.4 m, boards as one textured face per bay, top cap and bottom rail"""
    a, b = Vector((a[0], a[1], 0)), Vector((b[0], b[1], 0))
    d = b - a
    L = d.length
    if L < 0.3:
        return
    t = d / L
    n = Vector((-t.y, t.x, 0))
    bays = max(1, round(L / 2.4))
    for i in range(bays + 1):
        p = a + t * (L * i / bays)
        mb.obox(p + Vector((0, 0, h / 2 + 0.05)), t * 0.045, n * 0.045, Vector((0, 0, h / 2 + 0.05)), M_POST)
    for i in range(bays):
        p0, p1 = a + t * (L * i / bays + 0.045), a + t * (L * (i + 1) / bays - 0.045)
        if gate_at is not None and i == gate_at:
            # gate: frame and diagonal brace on the inside
            c = (p0 + p1) / 2 + Vector((0, 0, h / 2 + 0.05))
            mb.obox(c, t * ((p1 - p0).length / 2 - 0.01), n * 0.012, Vector((0, 0, h / 2 - 0.02)), M_FENCE)
            continue
        c = (p0 + p1) / 2 + Vector((0, 0, h / 2 + 0.06))
        mb.obox(c, t * (p1 - p0).length / 2, n * 0.011, Vector((0, 0, h / 2 - 0.02)), M_FENCE)
        mb.obox((p0 + p1) / 2 + Vector((0, 0, 0.12)) + n * 0.03, t * (p1 - p0).length / 2, n * 0.02, Vector((0, 0, 0.045)), M_POST)
    mb.obox((a + b) / 2 + Vector((0, 0, h + 0.07)), t * (L / 2 + 0.05), n * 0.07, Vector((0, 0, 0.02)), M_POST)


def build(info, rng, hero=False, lot_w=None):
    """returns the lot mesh builder, lawn rectangles, plant placements [(kind, (x, y, z), rot, scale)] and the street edge"""
    W, D, gp, gx0, gx1 = info["W"], info["D"], info["gp"], info["gx0"], info["gx1"]
    ox0, ox1, left, pd = info["ox0"], info["ox1"], info["left"], info["pd"]
    lw = lot_w or (W + 2.8)
    lx0, lx1 = -lw / 2, lw / 2
    pl = -gp - FRONT_SETBACK  # property line, sidewalk is beyond it
    back = pl + LOT_DEPTH
    mb = MB()
    plants = []
    lawn = []
    # driveway flares a little toward the street
    dx0, dx1 = gx0 + 0.35, gx1 - 0.35
    mb.face([(dx0, -gp, 0.03), (dx0 - 0.25, pl, 0.03), (dx1 + 0.25, pl, 0.03), (dx1, -gp, 0.03)][::-1], M_CONC)
    mb.face([(dx0 - 0.25, pl, 0.0), (dx0 - 0.25, pl, 0.03), (dx0, -gp, 0.03), (dx0, -gp, 0.0)][::-1], M_CONC)
    mb.face([(dx1 + 0.25, pl, 0.03), (dx1 + 0.25, pl, 0.0), (dx1, -gp, 0.0), (dx1, -gp, 0.03)][::-1], M_CONC)
    # walk from the steps to the driveway
    door = info["door"]
    du0 = ox0 + door["u0"]
    wx0, wx1 = du0 - 0.25, du0 + 1.0
    walk_y0 = -pd - 0.64
    if left:
        mb.box((dx1 + 0.2, walk_y0 - 1.3, 0.0), (wx1, walk_y0, 0.03), M_CONC)
    else:
        mb.box((wx0, walk_y0 - 1.3, 0.0), (dx0 - 0.2, walk_y0, 0.03), M_CONC)
    # front bed along the house beside the walk and under the bonus room windows
    bed_x0, bed_x1 = (wx1 + 0.05, lx1 - 0.4) if left else (lx0 + 0.4, wx0 - 0.05)
    bed_y0 = -pd - 1.6
    mb.box((bed_x0, bed_y0, 0.0), (bed_x1, 0.0, 0.035), M_MULCH)
    for x, y0_, y1_ in ((bed_x0, bed_y0, 0.0), (bed_x1, bed_y0, 0.0)):
        mb.box((x - 0.01, y0_, 0.0), (x + 0.01, y1_, 0.07), M_EDGE)
    mb.box((bed_x0, bed_y0 - 0.01, 0.0), (bed_x1, bed_y0 + 0.01, 0.07), M_EDGE)
    # side yards: river rock strips
    side = lx1 - W / 2
    for sx0, sx1 in ((lx0, -W / 2), (W / 2, lx1)):
        mb.box((sx0 + 0.02, 0.4 if not ((sx0 == lx0) == left) else -gp + 0.2, 0.0), (sx1 - 0.02, D - 0.4, 0.04), M_ROCK)
    # lawns: front (the part not covered by driveway, walk and bed), back yard
    fl = (dx1 + 0.35, pl + 0.05, lx1 - 0.05, bed_y0 - 0.05) if left else (lx0 + 0.05, pl + 0.05, dx0 - 0.35, bed_y0 - 0.05)
    if left:
        lawn.append((dx1 + 0.35, pl + 0.05, lx1 - 0.05, walk_y0 - 1.35))
        lawn.append((wx1 + 0.05, walk_y0 - 1.3, lx1 - 0.05, bed_y0 - 0.05))
        lawn.append((lx0 + 0.05, pl + 0.05, dx0 - 0.3, -gp - 0.3))
    else:
        lawn.append((lx0 + 0.05, pl + 0.05, dx0 - 0.35, walk_y0 - 1.35))
        lawn.append((lx0 + 0.05, walk_y0 - 1.3, wx0 - 0.05, bed_y0 - 0.05))
        lawn.append((dx1 + 0.3, pl + 0.05, lx1 - 0.05, -gp - 0.3))
    # back deck at main floor height, with railing and stairs
    deck_x0, deck_x1, deck_y1 = -W / 2 + 0.9, -W / 2 + 0.9 + 5.2, D + 3.8
    mb.box((deck_x0, D, 0.52), (deck_x1, deck_y1, 0.57), M_DECK)
    mb.box((deck_x0, deck_y1 - 0.05, 0.25), (deck_x1, deck_y1, 0.52), M_POST)
    mb.box((deck_x0, D, 0.25), (deck_x0 + 0.05, deck_y1, 0.52), M_POST)
    mb.box((deck_x1 - 0.05, D, 0.25), (deck_x1, deck_y1, 0.52), M_POST)
    for x in (deck_x0 + 0.05, (deck_x0 + deck_x1) / 2, deck_x1 - 0.05):
        mb.box((x - 0.045, deck_y1 - 0.09, 0.0), (x + 0.045, deck_y1, 0.52), M_POST)
    rail_h = 0.57 + 0.92
    for (x0_, y0_, x1_, y1_) in ((deck_x0, deck_y1 - 0.06, deck_x1 - 1.4, deck_y1), (deck_x0, D + 0.1, deck_x0 + 0.06, deck_y1),
                                (deck_x1 - 0.06, D + 0.1, deck_x1, deck_y1)):
        mb.box((x0_, y0_, rail_h - 0.05), (x1_, y1_, rail_h), M_POST)
        L = max(x1_ - x0_, y1_ - y0_)
        nb = int(L / 0.12)
        for k in range(nb):
            if x1_ - x0_ > y1_ - y0_:
                x = x0_ + (k + 0.5) * L / nb
                mb.box((x - 0.02, y0_ + 0.01, 0.57), (x + 0.02, y1_ - 0.01, rail_h - 0.05), M_POST)
            else:
                y = y0_ + (k + 0.5) * L / nb
                mb.box((x0_ + 0.01, y - 0.02, 0.57), (x1_ - 0.01, y + 0.02, rail_h - 0.05), M_POST)
    for k in range(3):  # stairs off the open end
        mb.box((deck_x1 - 1.35, deck_y1 + k * 0.28, 0.0), (deck_x1 - 0.1, deck_y1 + (k + 1) * 0.28, 0.52 - k * 0.18 - 0.02), M_DECK)
    lawn.append((lx0 + 0.05, D + 0.45, lx1 - 0.05, back - 0.1))
    # fence: side lot lines from the house to the back, back line, short returns with gates
    gy = 1.2
    fence(mb, (lx0 + 0.05, gy), (lx0 + 0.05, back - 0.05))
    fence(mb, (lx1 - 0.05, back - 0.05), (lx1 - 0.05, gy))
    fence(mb, (lx0 + 0.05, back - 0.05), (lx1 - 0.05, back - 0.05))
    fence(mb, (-W / 2, gy), (lx0 + 0.05, gy), gate_at=0)
    fence(mb, (lx1 - 0.05, gy), (W / 2, gy), gate_at=0)
    # plants: front bed shrubs and grasses, a young spruce, a yard tree near the street, back yard trees
    bx = lambda f: bed_x0 + (bed_x1 - bed_x0) * f
    for f in (0.15, 0.42, 0.7, 0.92):
        plants.append(("shrub", (bx(f), bed_y0 + 0.55 + rng.uniform(-0.1, 0.15), 0.03), rng.uniform(0, 6.28), rng.uniform(0.45, 0.62)))
    for f in (0.28, 0.56, 0.82):
        plants.append(("grass", (bx(f), bed_y0 + 0.35, 0.03), rng.uniform(0, 6.28), rng.uniform(2.6, 3.4)))
    plants.append(("conifer", (bx(0.97) if left else bx(0.03), bed_y0 + 0.9, 0.03), rng.uniform(0, 6.28), rng.uniform(1.0, 1.3)))
    tx = (lx1 - 2.2) if left else (lx0 + 2.2)
    plants.append(("tree", (tx, pl + 1.6, 0.0), rng.uniform(0, 6.28), rng.uniform(1.45, 1.8)))
    plants.append(("tree2", (rng.uniform(lx0 + 2.5, lx1 - 2.5), back - rng.uniform(3, 5), 0.0), rng.uniform(0, 6.28), rng.uniform(1.1, 1.5)))
    if rng.random() < 0.55:
        plants.append(("tree", (rng.uniform(lx0 + 2.5, lx1 - 2.5), back - rng.uniform(8, 13), 0.0), rng.uniform(0, 6.28),
                       rng.uniform(1.2, 1.7)))
    if rng.random() < 0.6:
        plants.append(("spruce", ((lx1 - 1.8) if rng.random() < 0.5 else (lx0 + 1.8), back - 2.0, 0.0), rng.uniform(0, 6.28),
                       rng.uniform(0.9, 1.25)))
    return mb, lawn, plants, dict(pl=pl, back=back, lw=lw)

"""Edmonton front-garage two-storey house, built from real parts.

Lap-siding walls with cut openings and reveals, framed windows with trim, sills and blinds or sheers behind the glass,
a roof slab with shingles, fascia, soffit, gutters, downspouts and ridge caps, a sectional garage door, porch with a stone
column, coach lights, foundation parging, floors, partitions and ceilings inside. Local frame: x across the lot, the main
front wall is y=0 and faces -y (the street), z=0 is grade. One spec in, one bevelled mesh plus light spots out.
"""
import math
import random

from mathutils import Vector

from common import MB, Z, backface_mix, emission, flat, glass, new_mat, N, pbr

(M_SIDING, M_TRIM, M_STONE, M_ROOF, M_SOFFIT, M_GLASS, M_FRAME, M_GDOOR, M_DOOR, M_CONC, M_FLOOR, M_PAINT, M_METAL, M_LAMP,
 M_DRESS, M_ACCENT, M_CAP) = range(17)
PITCH = math.atan(6 / 12)
T = math.tan(PITCH)
MAIN_FLOOR, SECOND_FLOOR, WALL_TOP = 0.6, 3.45, 6.25

SPECS = {
    # the listing: light grey siding, black trim and windows, charcoal board and batten gable, ledgestone, black garage door
    "hero": dict(W=10.6, D=12.8, gw=6.9, gp=4.4, gside="L", bonus=True, siding=(0.62, 0.62, 0.60), accent=(0.10, 0.10, 0.10),
                 trim=(0.035, 0.035, 0.035), frame=(0.03, 0.03, 0.03), stone=(0.95, 0.92, 0.88), gdoor=(0.04, 0.04, 0.04),
                 door=(0.30, 0.15, 0.07), seed=3),
    "taupe": dict(W=10.2, D=12.4, gw=6.8, gp=4.0, gside="R", bonus=True, siding=(0.55, 0.47, 0.38), accent=(0.85, 0.82, 0.76),
                  trim=(0.85, 0.84, 0.80), frame=(0.85, 0.84, 0.80), stone=(0.85, 0.75, 0.62), gdoor=(0.82, 0.81, 0.78),
                  door=(0.08, 0.10, 0.14), seed=5),
    "blue": dict(W=10.4, D=12.0, gw=6.7, gp=3.6, gside="L", bonus=False, siding=(0.36, 0.44, 0.50), accent=(0.80, 0.80, 0.78),
                 trim=(0.85, 0.85, 0.83), frame=(0.85, 0.85, 0.83), stone=None, gdoor=(0.82, 0.82, 0.80),
                 door=(0.35, 0.06, 0.05), seed=7),
    "charcoal": dict(W=10.8, D=13.0, gw=7.0, gp=4.6, gside="R", bonus=True, siding=(0.26, 0.27, 0.27), accent=(0.55, 0.36, 0.20),
                     trim=(0.03, 0.03, 0.03), frame=(0.03, 0.03, 0.03), stone=(0.75, 0.72, 0.70), gdoor=(0.40, 0.25, 0.13),
                     door=(0.03, 0.03, 0.03), seed=11),
    "beige": dict(W=10.0, D=12.2, gw=6.6, gp=3.8, gside="L", bonus=False, siding=(0.78, 0.72, 0.60), accent=(0.45, 0.33, 0.22),
                  trim=(0.88, 0.87, 0.84), frame=(0.88, 0.87, 0.84), stone=(0.80, 0.70, 0.58), gdoor=(0.86, 0.85, 0.82),
                  door=(0.10, 0.18, 0.12), seed=13),
}


# ---------------------------------------------------------------- materials
def dressing_mat():
    m, nt, p = new_mat("window dressing")
    out = nt.nodes.get("Material Output")
    p.inputs["Base Color"].default_value = (0.82, 0.80, 0.75, 1)
    p.inputs["Roughness"].default_value = 0.9
    tl = N(nt, "ShaderNodeBsdfTranslucent", -200, -200)
    tl.inputs["Color"].default_value = (0.9, 0.85, 0.75, 1)
    mx = N(nt, "ShaderNodeMixShader", 200, 0)
    mx.inputs["Fac"].default_value = 0.45
    nt.links.new(p.outputs[0], mx.inputs[1])
    nt.links.new(tl.outputs[0], mx.inputs[2])
    nt.links.new(mx.outputs[0], out.inputs["Surface"])
    return m


def vary(m, amount=0.22, hue=0.025):
    """per-instance shade and hue drift so a street of one variant does not look stamped"""
    nt = m.node_tree
    p = nt.nodes.get("Principled BSDF")
    src = p.inputs["Base Color"].links[0].from_socket
    oi = N(nt, "ShaderNodeObjectInfo", -500, 700)
    hsv = N(nt, "ShaderNodeHueSaturation", -100, 650)
    for inp, lo, hi in (("Hue", 0.5 - hue, 0.5 + hue), ("Value", 1 - amount, 1 + amount * 0.6), ("Saturation", 0.8, 1.25)):
        mr = N(nt, "ShaderNodeMapRange", -300, 700)
        mr.inputs["To Min"].default_value, mr.inputs["To Max"].default_value = lo, hi
        nt.links.new(oi.outputs["Random"], mr.inputs["Value"])
        nt.links.new(mr.outputs["Result"], hsv.inputs[inp])
    nt.links.new(src, hsv.inputs["Color"])
    nt.links.new(hsv.outputs["Color"], p.inputs["Base Color"])
    return m


def house_mats(name, s):
    sid = backface_mix(pbr(f"{name} siding", "exterior_wall_cladding_03", 1.96, tint=s["siding"], rough=(0.35, 0.6), bump=1.2,
                               sat=0.15, value=1.15))
    acc = backface_mix(pbr(f"{name} board and batten", "exterior_wall_cladding_03", 1.2, tint=s["accent"], rough=(0.4, 0.65),
                           bump=1.6, rot=math.pi / 2, sat=0.15))
    stone = pbr(f"{name} stone", "castle_wall_slates", 2.2, tint=s["stone"] or (0.8, 0.8, 0.8), bump=1.6, value=1.05)
    roof = pbr(f"{name} shingles", "grey_roof_01", 6.5, value=0.8, sat=0.6, rough=(0.65, 0.95), bump=1.3)
    trim = flat(f"{name} trim", s["trim"], rough=0.42, noise=0.06, bump=0.05)
    frame = flat(f"{name} frame", s["frame"], rough=0.35, noise=0.03)
    gd = flat(f"{name} garage door", s["gdoor"], rough=0.38, noise=0.05, bump=0.08)
    door = flat(f"{name} door", s["door"], rough=0.3, noise=0.12, bump=0.1, coat=0.3)
    conc = flat("concrete parging", (0.42, 0.40, 0.37), rough=0.9, noise=0.25, bump=0.6)
    floor = flat("hardwood", (0.30, 0.18, 0.10), rough=0.35)
    paint = flat("drywall", (0.74, 0.70, 0.64), rough=0.85)
    metal = flat("black metal", (0.025, 0.025, 0.025), rough=0.35, metal=0.7)
    lamp = emission("coach light", (1.0, 0.72, 0.42), 9.0)
    cap = flat("cap stone", (0.55, 0.52, 0.48), rough=0.8, noise=0.2, bump=0.4)
    if name != "hero":
        vary(sid)
        vary(roof, amount=0.25, hue=0.01)
    return [sid, trim, stone, roof, trim, glass(f"{name} glass"), frame, gd, door, conc, floor, paint, metal, lamp, dressing_mat(),
            acc, cap]


# ---------------------------------------------------------------- wall frame helpers
class Wall:
    """a wall plane from p0 to p1 (outside face), normal outward. walls go counter-clockwise seen from above."""

    def __init__(self, p0, p1):
        self.p0 = Vector((p0[0], p0[1], 0))
        d = Vector((p1[0], p1[1], 0)) - self.p0
        self.L = d.length
        self.t = d / self.L
        self.n = Vector((self.t.y, -self.t.x, 0))

    def P(self, u, z, d=0.0):
        """u along the wall, z height, d depth into the house (negative = proud of the wall)"""
        return self.p0 + self.t * u - self.n * d + Z * z

    def box(self, mb, u0, u1, z0, z1, d0, d1, mi):
        c = self.P((u0 + u1) / 2, (z0 + z1) / 2, (d0 + d1) / 2)
        mb.obox(c, self.t * (u1 - u0) / 2, -self.n * (d1 - d0) / 2, Z * (z1 - z0) / 2, mi)

    def quad(self, mb, u0, u1, z0, z1, d, mi, uvs=None):
        mb.face([self.P(u0, z0, d), self.P(u1, z0, d), self.P(u1, z1, d), self.P(u0, z1, d)], mi, uvs)


def wall(mb, w, z0, z1, openings, mi, mi_rev=M_TRIM, depth=0.16):
    """lap siding wall with openings cut out, plus the reveals into each opening"""
    us = sorted({0.0, w.L, *[o["u0"] for o in openings], *[o["u1"] for o in openings]})
    zs = sorted({z0, z1, *[o["z0"] for o in openings], *[o["z1"] for o in openings]})
    us = [u for u in us if -1e-6 <= u <= w.L + 1e-6]
    zs = [z for z in zs if z0 - 1e-6 <= z <= z1 + 1e-6]
    mb.begin()
    for i in range(len(us) - 1):
        for j in range(len(zs) - 1):
            uc, zc = (us[i] + us[i + 1]) / 2, (zs[j] + zs[j + 1]) / 2
            if any(o["u0"] < uc < o["u1"] and o["z0"] < zc < o["z1"] for o in openings):
                continue
            w.quad(mb, us[i], us[i + 1], zs[j], zs[j + 1], 0.0, mi)
    mb.end()
    for o in openings:
        u0, u1, oz0, oz1 = o["u0"], o["u1"], o["z0"], o["z1"]
        d = o.get("depth", depth)
        mb.begin()
        mb.face([w.P(u0, oz0, 0), w.P(u0, oz0, d), w.P(u0, oz1, d), w.P(u0, oz1, 0)], mi_rev)
        mb.face([w.P(u1, oz1, 0), w.P(u1, oz1, d), w.P(u1, oz0, d), w.P(u1, oz0, 0)], mi_rev)
        mb.face([w.P(u0, oz1, 0), w.P(u0, oz1, d), w.P(u1, oz1, d), w.P(u1, oz1, 0)], mi_rev)
        mb.face([w.P(u1, oz0, 0), w.P(u1, oz0, d), w.P(u0, oz0, d), w.P(u0, oz0, 0)], mi_rev)
        mb.end()


def window(mb, w, o, rng, trim=True, dressing=True):
    u0, u1, z0, z1 = o["u0"], o["u1"], o["z0"], o["z1"]
    tw, fw = 0.095, 0.058
    if trim:
        w.box(mb, u0 - tw, u1 + tw, z1, z1 + tw + 0.02, -0.024, 0.0, M_TRIM)
        w.box(mb, u0 - tw, u0, z0, z1, -0.022, 0.0, M_TRIM)
        w.box(mb, u1, u1 + tw, z0, z1, -0.022, 0.0, M_TRIM)
        w.box(mb, u0 - tw - 0.03, u1 + tw + 0.03, z0 - 0.055, z0, -0.05, 0.0, M_TRIM)
    w.box(mb, u0, u1, z0, z0 + fw, 0.03, 0.13, M_FRAME)
    w.box(mb, u0, u1, z1 - fw, z1, 0.03, 0.13, M_FRAME)
    w.box(mb, u0, u0 + fw, z0 + fw, z1 - fw, 0.03, 0.13, M_FRAME)
    w.box(mb, u1 - fw, u1, z0 + fw, z1 - fw, 0.03, 0.13, M_FRAME)
    width, height = u1 - u0, z1 - z0
    if width > 1.05:  # two casements or a slider
        n = 3 if width > 2.2 else 2
        for k in range(1, n):
            uc = u0 + width * k / n
            w.box(mb, uc - 0.035, uc + 0.035, z0 + fw, z1 - fw, 0.04, 0.12, M_FRAME)
    if height > 1.75 and o.get("kind") != "patio":
        zc = z0 + height * 0.7
        w.box(mb, u0 + fw, u1 - fw, zc - 0.03, zc + 0.03, 0.04, 0.12, M_FRAME)
    w.quad(mb, u0 + fw, u1 - fw, z0 + fw, z1 - fw, 0.085, M_GLASS)
    if dressing:
        r = rng.random()
        di = 0.3
        if r < 0.3:  # sheers
            w.quad(mb, u0 + 0.02, u1 - 0.02, z0 + 0.02, z1 - 0.02, di, M_DRESS)
        elif r < 0.6:  # blind partly down
            k = rng.uniform(0.25, 0.65)
            w.quad(mb, u0 + 0.02, u1 - 0.02, z1 - height * k, z1 - 0.02, di, M_DRESS)
            w.box(mb, u0 + 0.02, u1 - 0.02, z1 - height * k - 0.03, z1 - height * k, di - 0.01, di + 0.01, M_FRAME)
        elif r < 0.78:  # curtains pulled to the sides
            cw = width * rng.uniform(0.18, 0.28)
            w.quad(mb, u0 - 0.05, u0 + cw, z0 - 0.1, z1 + 0.05, di, M_DRESS)
            w.quad(mb, u1 - cw, u1 + 0.05, z0 - 0.1, z1 + 0.05, di, M_DRESS)


def front_door(mb, w, o):
    u0, u1, z0, z1 = o["u0"], o["u1"], o["z0"], o["z1"]
    tw = 0.1
    w.box(mb, u0 - tw, u1 + tw, z1, z1 + tw + 0.03, -0.026, 0.0, M_TRIM)
    w.box(mb, u0 - tw, u0, z0, z1, -0.024, 0.0, M_TRIM)
    w.box(mb, u1, u1 + tw, z0, z1, -0.024, 0.0, M_TRIM)
    w.box(mb, u0, u1, z0, z0 + 0.02, 0.0, 0.14, M_METAL)  # threshold
    w.box(mb, u0 + 0.04, u1 - 0.04, z0 + 0.02, z1 - 0.04, 0.08, 0.13, M_DOOR)
    w.box(mb, u0, u0 + 0.04, z0, z1, 0.02, 0.14, M_TRIM)
    w.box(mb, u1 - 0.04, u1, z0, z1, 0.02, 0.14, M_TRIM)
    w.box(mb, u0, u1, z1 - 0.04, z1, 0.02, 0.14, M_TRIM)
    dw = u1 - u0 - 0.08
    # two tall recessed panels and a narrow glass lite, like a modern craftsman door
    for k in range(2):
        a = u0 + 0.04 + 0.14 + k * (dw - 0.28) / 2 + k * 0.0
        b = a + (dw - 0.28 - 0.1) / 2
        w.box(mb, a, b, z0 + 0.2, z0 + 1.15, 0.065, 0.085, M_DOOR)
    w.quad(mb, u0 + 0.22, u1 - 0.22, z0 + 1.35, z1 - 0.25, 0.075, M_GLASS)
    w.box(mb, u0 + 0.2, u1 - 0.2, z0 + 1.33, z0 + 1.35, 0.06, 0.09, M_DOOR)
    w.box(mb, u0 + 0.2, u1 - 0.2, z1 - 0.25, z1 - 0.23, 0.06, 0.09, M_DOOR)
    w.box(mb, u1 - 0.14, u1 - 0.11, z0 + 0.95, z0 + 1.25, 0.02, 0.08, M_METAL)  # handle set


def garage_door(mb, w, o, style):
    u0, u1, z0, z1 = o["u0"], o["u1"], o["z0"], o["z1"]
    tw = 0.11
    w.box(mb, u0 - tw, u1 + tw, z1, z1 + tw, -0.026, 0.0, M_TRIM)
    w.box(mb, u0 - tw, u0, z0, z1, -0.024, 0.0, M_TRIM)
    w.box(mb, u1, u1 + tw, z0, z1, -0.024, 0.0, M_TRIM)
    w.box(mb, u0, u1, z0, z1, 0.22, 0.24, M_METAL)  # dark garage behind the seams
    secs = 4
    hs = (z1 - z0) / secs
    width = u1 - u0
    for k in range(secs):
        a, b = z0 + k * hs + 0.006, z0 + (k + 1) * hs - 0.006
        w.box(mb, u0 + 0.01, u1 - 0.01, a, b, 0.07, 0.11, M_GDOOR)
        n = 4 if style == "long" else 8
        pw = (width - 0.02 - (n + 1) * 0.09) / n
        for i in range(n):
            pa = u0 + 0.01 + 0.09 + i * (pw + 0.09)
            if k == secs - 1:  # windows in the top section
                w.quad(mb, pa, pa + pw, a + 0.1, b - 0.1, 0.06, M_GLASS)
                w.box(mb, pa, pa + pw, a + 0.1, b - 0.1, 0.075, 0.08, M_METAL)
            else:
                w.box(mb, pa, pa + pw, a + 0.09, b - 0.09, 0.06, 0.07, M_GDOOR)


def coach_light(mb, w, u, z):
    w.box(mb, u - 0.07, u + 0.07, z - 0.2, z + 0.2, -0.03, 0.0, M_METAL)
    w.box(mb, u - 0.09, u + 0.09, z - 0.16, z + 0.14, -0.22, -0.04, M_LAMP)
    w.box(mb, u - 0.11, u + 0.11, z + 0.14, z + 0.19, -0.24, -0.02, M_METAL)
    w.box(mb, u - 0.1, u + 0.1, z - 0.19, z - 0.16, -0.23, -0.03, M_METAL)
    for du in (-0.09, 0.09):  # corner posts of the lantern
        w.box(mb, u + du - 0.008, u + du + 0.008, z - 0.16, z + 0.14, -0.225, -0.205, M_METAL)


# ---------------------------------------------------------------- roofs
def slope_uv(pts):
    a, b, c = pts[0], pts[1], pts[2]
    n = (b - a).cross(c - a).normalized()
    s = (Z - n * n.dot(Z))
    s = s.normalized() if s.length > 1e-6 else Vector((0, 1, 0))
    e = s.cross(n)
    return [(p.dot(e), p.dot(s)) for p in pts]


def roof_slab(mb, polys, thick=0.2, gutters=True, caps=True):
    """roof surface polygons (counter-clockwise from above) become a slab: shingles on top, soffit under, fascia on the
    open edges, gutters on horizontal eaves, caps on ridges and hips"""
    polys = [[Vector(p) for p in poly] for poly in polys]
    key = lambda p: (round(p.x, 3), round(p.y, 3), round(p.z, 3))
    count = {}
    for poly in polys:
        for i in range(len(poly)):
            a, b = poly[i], poly[(i + 1) % len(poly)]
            k = tuple(sorted((key(a), key(b))))
            count[k] = count.get(k, 0) + 1
    dn = Vector((0, 0, -thick))
    for poly in polys:
        mb.face(poly, M_ROOF, slope_uv(poly))
        mb.face([p + dn for p in reversed(poly)], M_SOFFIT)
    eaves = []
    for poly in polys:
        zmin = min(p.z for p in poly)
        for i in range(len(poly)):
            a, b = poly[i], poly[(i + 1) % len(poly)]
            k = tuple(sorted((key(a), key(b))))
            if count[k] == 1:
                mb.face([a, a + dn, b + dn, b], M_SOFFIT)
                if abs(a.z - zmin) < 1e-3 and abs(b.z - zmin) < 1e-3:
                    eaves.append((a, b))
            elif caps and count[k] == 2 and key(a) < key(b):
                d = b - a
                if d.length < 0.3:
                    continue
                side = d.cross(Z)
                if side.length < 1e-6:
                    continue
                side = side.normalized() * 0.13
                up = d.normalized().cross(side.normalized()) * 0.03
                if up.z < 0:
                    up = -up
                mb.obox((a + b) / 2 + up, d / 2, side, up, M_ROOF)
    if gutters:
        for a, b in eaves:
            d = (b - a)
            out = Vector((d.y, -d.x, 0)).normalized()
            c = (a + b) / 2 + out * 0.07 + Vector((0, 0, -0.08))
            mb.obox(c, d / 2 + d.normalized() * 0.02, out * 0.065, Vector((0, 0, 0.065)), M_SOFFIT)
    return eaves


def hip_polys(x0, x1, y0, y1, zt, over=0.5):
    ex0, ex1, ey0, ey1 = x0 - over, x1 + over, y0 - over, y1 + over
    ze = zt - over * T
    w, d = ex1 - ex0, ey1 - ey0
    A, B, C, D = (ex0, ey0, ze), (ex1, ey0, ze), (ex1, ey1, ze), (ex0, ey1, ze)
    if w >= d:
        r = d / 2
        cy, zr = (ey0 + ey1) / 2, ze + r * T
        R0, R1 = (ex0 + r, cy, zr), (ex1 - r, cy, zr)
        return [[A, B, R1, R0], [B, C, R1], [C, D, R0, R1], [D, A, R0]]
    r = w / 2
    cx, zr = (ex0 + ex1) / 2, ze + r * T
    R0, R1 = (cx, ey0 + r, zr), (cx, ey1 - r, zr)
    return [[A, B, R0], [B, C, R1, R0], [C, D, R1], [D, A, R0, R1]]


def gable_y_polys(x0, x1, y0, y1, zt, over=0.45, rake=0.35):
    """ridge along y, gable ends face -y and +y"""
    ex0, ex1, ey0, ey1 = x0 - over, x1 + over, y0 - rake, y1 + rake
    ze = zt - over * T
    cx, zr = (x0 + x1) / 2, zt + (x1 - x0) / 2 * T
    return [[(ex0, ey0, ze), (cx, ey0, zr), (cx, ey1, zr), (ex0, ey1, ze)],
            [(cx, ey0, zr), (ex1, ey0, ze), (ex1, ey1, ze), (cx, ey1, zr)]], zr


def shed_polys(x0, x1, y0, y1, zh, over=0.45, side=0.3):
    """slopes down toward -y, high edge against the wall at y1"""
    ey0 = y0 - over
    ze = zh - (y1 - ey0) * T
    return [[(x0 - side, ey0, ze), (x1 + side, ey0, ze), (x1 + side, y1, zh), (x0 - side, y1, zh)]]


def downspout(mb, x, y, ztop, out):
    """vertical pipe from a gutter corner to a splash block, `out` is the direction away from the wall"""
    ox, oy = out
    mb.box((x - 0.04, y - 0.035, 0.25), (x + 0.04, y + 0.035, ztop), M_SOFFIT)
    mb.box((min(x, x + ox * 0.35) - 0.04, min(y, y + oy * 0.35) - 0.035, 0.12),
           (max(x, x + ox * 0.35) + 0.04, max(y, y + oy * 0.35) + 0.035, 0.25), M_SOFFIT)
    mb.box((min(x + ox * 0.3, x + ox * 0.9) - 0.15, min(y + oy * 0.3, y + oy * 0.9) - 0.15, 0.0),
           (max(x + ox * 0.3, x + ox * 0.9) + 0.15, max(y + oy * 0.3, y + oy * 0.9) + 0.15, 0.05), M_CONC)


# ---------------------------------------------------------------- the house
def build(spec_name, mats=None, mb=None):
    s = SPECS[spec_name]
    rng = random.Random(s["seed"])
    mb = mb or MB()
    W, D, gw, gp = s["W"], s["D"], s["gw"], s["gp"]
    x0, x1 = -W / 2, W / 2
    left = s["gside"] == "L"
    gx0, gx1 = (x0, x0 + gw) if left else (x1 - gw, x1)
    ox0, ox1 = (gx1, x1) if left else (x0, gx0)  # open front beside the garage (entry, porch)
    bonus = s["bonus"]
    gtop = WALL_TOP if bonus else 2.95
    lights = []
    win = lambda u0, u1, z0, z1, **k: dict(u0=u0, u1=u1, z0=z0, z1=z1, kind="win", **k)
    f1, f2 = (MAIN_FLOOR + 0.62, MAIN_FLOOR + 2.12), (SECOND_FLOOR + 0.75, SECOND_FLOOR + 2.15)

    # main body walls, counter-clockwise: front (only the open part shows), right, back, left
    fw_open = ox1 - ox0
    door_u0 = (0.35 if left else fw_open - 1.65)
    front_open = []
    door = dict(u0=door_u0, u1=door_u0 + 0.92, z0=MAIN_FLOOR - 0.02, z1=MAIN_FLOOR + 2.05, kind="door", depth=0.16)
    side_lite = win(door["u1"] + 0.14, door["u1"] + 0.50, MAIN_FLOOR + 0.25, MAIN_FLOOR + 2.05) if left else \
        win(door["u0"] - 0.50, door["u0"] - 0.14, MAIN_FLOOR + 0.25, MAIN_FLOOR + 2.05)
    front_open += [door, side_lite]
    wu = (side_lite["u1"] + 0.35, fw_open - 0.35) if left else (0.35, side_lite["u0"] - 0.35)
    if wu[1] - wu[0] > 0.8:
        front_open.append(win(wu[0], wu[1], f1[0], f1[1]))
    up_w = 1.3 if fw_open > 3.0 else 0.9
    front_open.append(win(fw_open / 2 - up_w / 2, fw_open / 2 + up_w / 2, f2[0], f2[1]))
    walls = [
        (Wall((ox0, 0), (ox1, 0)), front_open),
        (Wall((x1, 0), (x1, D)), [win(2.0, 3.2, f1[0], f1[1]), win(D - 4.2, D - 3.4, f2[0] + 0.5, f2[1]),
                                    win(D - 2.4, D - 1.2, f2[0], f2[1])]),
        (Wall((x1, D), (x0, D)), [dict(u0=W * 0.18, u1=W * 0.18 + 2.4, z0=MAIN_FLOOR, z1=MAIN_FLOOR + 2.1, kind="patio"),
                                    win(W * 0.55, W * 0.55 + 1.6, f1[0] + 0.3, f1[1]),
                                    win(W * 0.12, W * 0.12 + 1.4, f2[0], f2[1]), win(W * 0.42, W * 0.42 + 0.8, f2[0] + 0.6, f2[1]),
                                    win(W * 0.68, W * 0.68 + 1.4, f2[0], f2[1])]),
        (Wall((x0, D), (x0, 0)), [win(1.4, 2.6, f2[0], f2[1]), win(D * 0.45, D * 0.45 + 0.8, f1[0] + 0.4, f1[1])]),
    ]
    for w, ops in walls:
        wall(mb, w, MAIN_FLOOR - 0.05, WALL_TOP, ops, M_SIDING)
        for o in ops:
            if o["kind"] == "door":
                front_door(mb, w, o)
            else:
                window(mb, w, o, rng)
        # foundation parging below the siding
        w.box(mb, -0.02, w.L + 0.02, 0.0, MAIN_FLOOR - 0.05, -0.018, 0.2, M_CONC)
    # belly band between floors on the front and sides
    for w, _ in walls:
        w.box(mb, 0, w.L, SECOND_FLOOR - 0.12, SECOND_FLOOR + 0.06, -0.03, 0.0, M_TRIM)

    # garage: front, outer side, inner side (only the part in front of the main body shows)
    gfront = Wall((gx0, -gp), (gx1, -gp))
    gd_w = 4.88
    gu0 = (gw - gd_w) / 2
    gops = [dict(u0=gu0, u1=gu0 + gd_w, z0=0.08, z1=0.08 + 2.13, kind="garage", depth=0.12)]
    if bonus:
        gops += [win(gw / 2 - 2.05, gw / 2 - 0.55, f2[0], f2[1]), win(gw / 2 + 0.55, gw / 2 + 2.05, f2[0], f2[1])]
    gside_out = Wall((gx0, 0.02), (gx0, -gp)) if left else Wall((gx1, -gp), (gx1, 0.02))
    gside_in = Wall((gx1, -gp), (gx1, 0.02)) if left else Wall((gx0, 0.02), (gx0, -gp))
    side_ops = [win(gp / 2 - 0.6, gp / 2 + 0.6, f2[0], f2[1])] if bonus else []
    for w, ops in ((gfront, gops), (gside_out, side_ops), (gside_in, list(side_ops) if bonus else [])):
        wall(mb, w, 0.22, gtop, ops, M_SIDING)
        for o in ops:
            if o["kind"] == "garage":
                garage_door(mb, w, o, "long" if rng.random() < 0.6 else "short")
            else:
                window(mb, w, o, rng)
        w.box(mb, -0.02, w.L + 0.02, 0.0, 0.22, -0.018, 0.2, M_CONC)
    if bonus:
        gfront.box(mb, 0, gw, SECOND_FLOOR - 0.12, SECOND_FLOOR + 0.06, -0.03, 0.0, M_TRIM)
    coach_light(mb, gfront, gu0 - 0.42, 1.95)
    coach_light(mb, gfront, gu0 + gd_w + 0.42, 1.95)
    if s["stone"]:
        for a, b in ((0.0, gu0 - 0.11), (gu0 + gd_w + 0.11, gw)):
            gfront.box(mb, a - 0.06, b, 0.0, 1.32, -0.06, 0.0, M_STONE)
            gfront.box(mb, a - 0.08, b, 1.32, 1.38, -0.085, 0.0, M_CAP)
    # corner boards
    for cx, cy in ((x0, D), (x1, D), (x1, 0), (x0, 0)):
        if cy == 0 and cx == (x0 if left else x1):
            continue
        sx, sy = (1 if cx == x0 else -1), (1 if cy == 0 else -1)
        mb.box((min(cx, cx + sx * 0.12) - (0.026 if sx > 0 else 0), min(cy, cy + sy * 0.12) - (0.026 if sy > 0 else 0), MAIN_FLOOR - 0.05),
               (max(cx, cx + sx * 0.12) + (0.026 if sx < 0 else 0), max(cy, cy + sy * 0.12) + (0.026 if sy < 0 else 0), WALL_TOP), M_TRIM)
    for cx in (gx0, gx1):
        sx = 1 if cx == gx0 else -1
        mb.box((min(cx, cx + sx * 0.12) - (0.026 if sx > 0 else 0), -gp - 0.026, 0.22),
               (max(cx, cx + sx * 0.12) + (0.026 if sx < 0 else 0), -gp + 0.12, gtop), M_TRIM)

    # roofs
    main_eaves = roof_slab(mb, hip_polys(x0, x1, 0, D, WALL_TOP))
    if bonus:
        polys, zr = gable_y_polys(gx0, gx1, -gp, gw / 2 + 0.6, WALL_TOP)
        roof_slab(mb, polys)
        cx = (gx0 + gx1) / 2
        gable = [(gx0, -gp, WALL_TOP), (gx1, -gp, WALL_TOP), (cx, -gp, zr)]
        mb.face(gable, M_ACCENT)
        gfront.box(mb, 0, gw, WALL_TOP - 0.02, WALL_TOP + 0.14, -0.035, 0.0, M_TRIM)  # frieze under the gable
        gfront.box(mb, gw / 2 - 0.3, gw / 2 + 0.3, zr - 1.25, zr - 0.6, -0.03, 0.0, M_TRIM)  # louvre vent
        for k in range(5):
            zz = zr - 1.2 + k * 0.12
            gfront.box(mb, gw / 2 - 0.25, gw / 2 + 0.25, zz, zz + 0.05, -0.05, -0.03, M_TRIM)
        gutter_z = WALL_TOP - 0.45 * T
    else:
        roof_slab(mb, hip_polys(gx0, gx1, -gp, 0.0, gtop))
        over = Wall((gx0, 0), (gx1, 0))
        ops = [win(gw / 2 - 2.0, gw / 2 - 0.6, f2[0], f2[1]), win(gw / 2 + 0.6, gw / 2 + 2.0, f2[0], f2[1])]
        wall(mb, over, 2.6, WALL_TOP, ops, M_SIDING)
        for o in ops:
            window(mb, over, o, rng)
        over.box(mb, 0, gw, SECOND_FLOOR - 0.12, SECOND_FLOOR + 0.06, -0.03, 0.0, M_TRIM)
        gutter_z = gtop - 0.5 * T
    # porch roof over the entry, with a stone-based column at the outer corner
    pz = 2.9  # beam top
    pd = 1.75
    beam_y = -pd + 0.1
    roof_slab(mb, shed_polys(ox0 + (0.05 if left else 0), ox1 - (0 if left else 0.05), -pd, 0.0, pz + 0.22 - beam_y * T,
                             over=0.25, side=0.15))
    mb.box((ox0, beam_y - 0.12, pz - 0.28), (ox1, beam_y + 0.12, pz), M_TRIM)
    colx = ox1 - 0.35 if left else ox0 + 0.35
    mb.box((colx - 0.27, beam_y - 0.27, 0.0), (colx + 0.27, beam_y + 0.27, 1.25), M_STONE if s["stone"] else M_TRIM)
    mb.box((colx - 0.31, beam_y - 0.31, 1.25), (colx + 0.31, beam_y + 0.31, 1.32), M_CAP)
    mb.box((colx - 0.13, beam_y - 0.13, 1.32), (colx + 0.13, beam_y + 0.13, pz - 0.28), M_TRIM)
    # concrete stoop and steps
    mb.box((ox0 + 0.02, -pd, 0.0), (ox1 - 0.02, 0.0, MAIN_FLOOR - 0.04), M_CONC)
    sx0, sx1 = (door["u0"] + ox0 - 0.3, door["u1"] + ox0 + 0.6) if left else (ox0 + door["u0"] - 0.6, ox0 + door["u1"] + 0.3)
    mb.box((sx0, -pd - 0.32, 0.0), (sx1, -pd, 0.36), M_CONC)
    mb.box((sx0, -pd - 0.64, 0.0), (sx1, -pd - 0.32, 0.18), M_CONC)
    pw = Wall((ox0, 0), (ox1, 0))
    coach_light(mb, pw, (door["u0"] - 0.3) if left else (door["u1"] + 0.3), MAIN_FLOOR + 1.75)
    # downspouts at the main back corners and the garage front corners
    for x, y, out in ((x0 + 0.25, D + 0.06, (0, 1)), (x1 - 0.25, D + 0.06, (0, 1))):
        downspout(mb, x, y, WALL_TOP - 0.5 * T - 0.1, out)
    for x in (gx0 - 0.06, gx1 + 0.06):
        downspout(mb, x, -gp + 0.25, gutter_z - 0.1, (0, -1))

    # inside: floors, ceilings, a partition per floor, so windows look into rooms
    mb.box((x0 + 0.1, 0.1, MAIN_FLOOR - 0.2), (x1 - 0.1, D - 0.1, MAIN_FLOOR), M_FLOOR)
    mb.box((x0 + 0.1, 0.1, SECOND_FLOOR - 0.25), (x1 - 0.1, D - 0.1, SECOND_FLOOR), M_FLOOR, {"-z": M_PAINT})
    mb.face([(x0 + 0.1, D - 0.1, WALL_TOP - 0.1), (x1 - 0.1, D - 0.1, WALL_TOP - 0.1), (x1 - 0.1, 0.1, WALL_TOP - 0.1),
             (x0 + 0.1, 0.1, WALL_TOP - 0.1)], M_PAINT)
    for zb, zt_ in ((MAIN_FLOOR, SECOND_FLOOR - 0.25), (SECOND_FLOOR, WALL_TOP - 0.1)):
        yp = D * 0.52
        mb.box((x0 + 0.1, yp, zb), (-0.6, yp + 0.12, zt_), M_PAINT)
        mb.box((0.4, yp, zb), (x1 - 0.1, yp + 0.12, zt_), M_PAINT)
        mb.box((-0.06, 0.1, zb), (0.06, yp, zt_), M_PAINT)
    if bonus:
        mb.box((gx0 + 0.1, -gp + 0.1, SECOND_FLOOR - 0.25), (gx1 - 0.1, 0.0, SECOND_FLOOR), M_FLOOR, {"-z": M_PAINT})
        mb.face([(gx0 + 0.1, 0.0, WALL_TOP - 0.1), (gx1 - 0.1, 0.0, WALL_TOP - 0.1), (gx1 - 0.1, -gp + 0.1, WALL_TOP - 0.1),
                 (gx0 + 0.1, -gp + 0.1, WALL_TOP - 0.1)], M_PAINT)
        lights.append(Vector(((gx0 + gx1) / 2, -gp / 2, SECOND_FLOOR + 2.2)))
    lights += [Vector((x1 - 2.5, 3.0, MAIN_FLOOR + 2.3)), Vector((x0 + 2.5, D - 3.0, MAIN_FLOOR + 2.3)),
               Vector((x1 - 2.5, D - 2.5, SECOND_FLOOR + 2.3))]
    return mb, lights, dict(gx0=gx0, gx1=gx1, gp=gp, ox0=ox0, ox1=ox1, door=door, pd=pd, W=W, D=D, left=left)

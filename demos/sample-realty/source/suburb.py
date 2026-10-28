"""a fictional front-garage neighbourhood: curved streets with asphalt, curbs, sidewalks and street lights, lots placed by
arc length on both sides, five detailed house variants instanced with their lot kits, and the plants scattered per lot.
the hero lot is unique (wider, hair-grass lawn, room lights)."""
import math
import random

import bpy
from mathutils import Matrix, Vector

import house
import lot
import plants
from common import MB, flat, link, pbr

ROAD_HALF, SIDEWALK = 4.6, 1.55


def road_mats():
    asphalt = pbr("asphalt", "asphalt_02", 3.0, value=0.62, sat=0.4, rough=(0.75, 0.95), bump=1.0)
    conc = lot.concrete_mat("sidewalk concrete", joint=1.5)
    metal = flat("pole metal", (0.06, 0.06, 0.06), rough=0.5, metal=0.6)
    lamp = flat("lamp lens", (0.8, 0.8, 0.75), rough=0.2)
    return [asphalt, conc, metal, lamp]


class Path2:
    """polyline with cumulative length, sampled by arc length"""

    def __init__(self, pts):
        self.p = [Vector((x, y)) for x, y in pts]
        self.s = [0.0]
        for a, b in zip(self.p, self.p[1:]):
            self.s.append(self.s[-1] + (b - a).length)
        self.L = self.s[-1]

    def at(self, s):
        s = max(0.0, min(self.L, s))
        for i in range(len(self.s) - 1):
            if self.s[i + 1] >= s:
                a, b = self.p[i], self.p[i + 1]
                f = (s - self.s[i]) / max(1e-9, self.s[i + 1] - self.s[i])
                t = (b - a).normalized()
                return a + (b - a) * f, t
        return self.p[-1], (self.p[-1] - self.p[-2]).normalized()


def arc(cx, cy, r, a0, a1, step=4.0):
    n = max(2, int(abs(a1 - a0) * r / step))
    return [(cx + r * math.cos(a0 + (a1 - a0) * i / n), cy + r * math.sin(a0 + (a1 - a0) * i / n)) for i in range(n + 1)]


def street(mb, path, lights=None, rng=None):
    """asphalt strip, curb faces and sidewalks on both sides, along the path"""
    pts = []
    s = 0.0
    while s < path.L:
        pts.append(path.at(s))
        s += 2.0
    pts.append(path.at(path.L))
    prof = [(-ROAD_HALF - SIDEWALK, 0.02, 1), (-ROAD_HALF, 0.02, 1), (-ROAD_HALF, -0.15, 1), (-ROAD_HALF + 0.35, -0.15, 0),
            (ROAD_HALF - 0.35, -0.15, 0), (ROAD_HALF, -0.15, 1), (ROAD_HALF, 0.02, 1), (ROAD_HALF + SIDEWALK, 0.02, 1)]
    mi_seg = [1, 1, 1, 0, 1, 1, 1]  # sidewalk, curb face, gutter pan, asphalt, gutter, curb, sidewalk
    acc = 0.0
    for (p0, t0), (p1, t1) in zip(pts, pts[1:]):
        n0, n1 = Vector((-t0.y, t0.x)), Vector((-t1.y, t1.x))
        seg_len = (p1 - p0).length
        for k in range(len(prof) - 1):
            (o0, z0, _), (o1, z1, _) = prof[k], prof[k + 1]
            a0, b0 = p0 + n0 * o0, p0 + n0 * o1
            a1, b1 = p1 + n1 * o0, p1 + n1 * o1
            quad = [(a0.x, a0.y, z0), (a1.x, a1.y, z0), (b1.x, b1.y, z1), (b0.x, b0.y, z1)]
            uvs = [(acc, o0), (acc + seg_len, o0), (acc + seg_len, o1), (acc, o1)]
            mb.face(quad[::-1], mi_seg[k], uvs[::-1])
        acc += seg_len
    if lights is not None:
        s = 18.0
        side = 1
        while s < path.L - 5:
            p, t = path.at(s)
            n = Vector((-t.y, t.x)) * side
            base = p + n * (ROAD_HALF + 0.5)
            mb.cyl((base.x, base.y, 0.0), 0.09, 7.6, 2, seg=10)
            arm_end = base - n * 1.6
            mb.obox(((base.x + arm_end.x) / 2, (base.y + arm_end.y) / 2, 7.55), Vector((-n.x, -n.y, 0)) * 0.8,
                    Vector((t.x, t.y, 0)) * 0.04, Vector((0, 0, 0.04)), 2)
            mb.obox((arm_end.x, arm_end.y, 7.45), Vector((-n.x, -n.y, 0)) * 0.3, Vector((t.x, t.y, 0)) * 0.16, Vector((0, 0, 0.07)), 2)
            mb.obox((arm_end.x, arm_end.y, 7.37), Vector((-n.x, -n.y, 0)) * 0.24, Vector((t.x, t.y, 0)) * 0.12, Vector((0, 0, 0.012)), 3)
            s += 48.0
            side = -side


class Kit:
    """one house variant plus its standard lot, as shared meshes"""

    def __init__(self, variant, rng, col):
        mb, self.lights, self.info = house.build(variant)
        self.house = mb.build(f"house {variant}", house.house_mats(variant, house.SPECS[variant]), bevel=0.006, col=col)
        lmb, self.lawn, self.plants, self.lotinfo = lot.build(self.info, rng)
        self.lot_mats = LOT_MATS
        self._add_lawn_base(lmb, self.lotinfo, self.info)
        self.lot = lmb.build(f"lot {variant}", LOT_MATS, bevel=0.0, col=col)
        self.width = self.lotinfo["lw"]

    @staticmethod
    def _add_lawn_base(lmb, li, info):
        lw = li["lw"]
        lmb.face([(-lw / 2, li["pl"], 0.0), (lw / 2, li["pl"], 0.0), (lw / 2, li["back"], 0.0), (-lw / 2, li["back"], 0.0)], lot.M_LAWN)


LOT_MATS = None


def place(obj_data, name, matrix, col):
    o = bpy.data.objects.new(name, obj_data)
    o.matrix_world = matrix
    col.objects.link(o)
    return o


def lot_matrix(path, s, side, gp, setback=0.0):
    """world matrix for a lot whose street edge is at arc length s; side +1 = left of the path direction"""
    p, t = path.at(s)
    n = Vector((-t.y, t.x)) * side
    # local -y points to the street, so local +y = n; local +x = t * side... keep right handed
    y_axis = Vector((n.x, n.y, 0))
    x_axis = Vector((y_axis.y, -y_axis.x, 0))
    origin = p + n * (ROAD_HALF + SIDEWALK + 0.05 + lot.FRONT_SETBACK + gp + setback)
    m = Matrix.Identity(4)
    m.col[0][:3] = x_axis
    m.col[1][:3] = y_axis
    m.col[2][:3] = (0, 0, 1)
    m.col[3][:3] = (origin.x, origin.y, 0)
    return m


def build(streets, hero_street, hero_s, col, lit_radius=160.0, hair=True, rng=None, keep=None, extra_streets=()):
    """streets: list of point lists. hero at arc length hero_s on the left side of streets[hero_street].
    returns hero world matrix and hero info"""
    global LOT_MATS
    rng = rng or random.Random(42)
    LOT_MATS = lot.lot_mats()
    variants = ["taupe", "blue", "charcoal", "beige", "hero"]
    kits = {v: Kit(v, random.Random(hash(v) & 0xFFFF), col_hidden(col)) for v in variants}
    rmb = MB()
    paths = [Path2(p) for p in streets]
    for pth in paths + [Path2(p) for p in extra_streets]:
        street(rmb, pth, lights=True, rng=rng)
    rmb.build("streets", road_mats(), col=col)
    items = []
    hero_m = None
    hero_info = None
    room_lights = []
    hp = paths[hero_street]
    hero_kit = kits["hero"]
    hero_lot_w = hero_kit.info["W"] + 5.0
    def slots(si, side, L):
        """(start s, kit, width, is_hero) along one side; the hero side packs outward from the hero lot, no gaps"""
        out = []
        if si == hero_street and side == 1:
            out.append((hero_s, hero_kit, hero_lot_w, True))
            s = hero_s + hero_lot_w + 0.02
            while s < L - 8.0:
                k = kits[variants[rng.randrange(4)]]
                out.append((s, k, k.width, False))
                s += k.width + 0.02
            s = hero_s - 0.02
            while s > 8.0:
                k = kits[variants[rng.randrange(4)]]
                s -= k.width
                if s < 8.0:
                    break
                out.append((s, k, k.width, False))
                s -= 0.02
            return out
        s = 8.0
        while s < L - 8.0:
            k = kits[variants[rng.randrange(4)]]
            out.append((s, k, k.width, False))
            s += k.width + 0.02
        return out

    for si, pth in enumerate(paths):
        for side in (1, -1):
            for s, k, lw, is_hero in slots(si, side, pth.L):
                m = lot_matrix(pth, s + lw / 2, side, k.info["gp"], 0.0 if is_hero else rng.uniform(-1.1, 0.0))
                if not is_hero and keep is not None and not keep(m):
                    continue
                if is_hero:
                    hero_m, hero_info = m, k
                    hero_lot(k, m, col, hair, rng)
                else:
                    place(k.house.data, "house", m, col)
                    place(k.lot.data, "lot", m, col)
                    for kind, loc, rot, sc in k.plants:
                        if rng.random() < 0.15 and kind in ("shrub", "grass"):
                            continue
                        jitter = Vector((rng.uniform(-0.3, 0.3), rng.uniform(-0.3, 0.3), 0)) if kind.startswith("tree") else Vector()
                        wl = m @ (Vector(loc) + jitter)
                        items.append((kind, wl, rot + math.atan2(m.col[1][1], m.col[1][0]), sc * rng.uniform(0.9, 1.1)))
                    if (m.translation - hp.at(hero_s)[0].to_3d()).length < lit_radius and rng.random() < 0.7:
                        for lp in k.lights:
                            if rng.random() < 0.5:
                                room_lights.append(m @ lp)
    made = plants.scatter(items, col, rng)
    for p in room_lights:
        L = bpy.data.lights.new("room", "POINT")
        L.energy, L.color, L.shadow_soft_size = rng.uniform(25, 70), (1.0, 0.70, 0.42), 0.3
        link(bpy.data.objects.new("room", L), col).location = p
    print("suburb: plants", made, "room lights", len(room_lights))
    return hero_m, hero_info


def col_hidden(col):
    name = "kits"
    if name not in bpy.data.collections:
        c = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(c)
        c.hide_render = True
        c.hide_viewport = True
    return bpy.data.collections[name]


def hero_lot(k, m, col, hair, rng):
    """the listing: its own wider lot, hair lawn, its plants exactly as designed, rooms lit"""
    hi = k.info
    lmb, lawn, pl_items, li = lot.build(hi, random.Random(5), hero=True, lot_w=hi["W"] + 5.0)
    if not hair:
        Kit._add_lawn_base(lmb, li, hi)
    else:
        lw = li["lw"]
        # soil under the hair, only where the lawn is (beds, drive, walk are their own faces)
        Kit._add_lawn_base(lmb, li, hi)
    lo = lmb.build("hero lot", LOT_MATS, col=col)
    lo.matrix_world = m
    place(k.house.data, "hero house", m, col)
    if hair:
        plants.hair_lawn("hero lawn", lawn, LOT_MATS[lot.M_LAWN], m, density=560, children=10, col=col)
    items = []
    for kind, loc, rot, sc in pl_items:
        items.append((kind, m @ Vector(loc), rot + math.atan2(m.col[1][1], m.col[1][0]), sc))
    plants.scatter(items, col, random.Random(9))
    for lp in k.lights:
        L = bpy.data.lights.new("room", "POINT")
        L.energy, L.color, L.shadow_soft_size = 55, (1.0, 0.71, 0.43), 0.3
        link(bpy.data.objects.new("hero room", L), col).location = m @ lp

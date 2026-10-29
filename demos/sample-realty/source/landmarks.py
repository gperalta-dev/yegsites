"""the two bridges the flight goes past, modelled from their real dimensions, plus plain decks for every other bridge.

High Level Bridge (1913): black steel, 777 m, two decks 6.5 m apart inside a Pratt truss, the streetcar on top about
47.5 m over the river; four concrete piers in the river carry three long spans, steel towers carry the approaches.
Walterdale Bridge (2017): two white steel arches over a 206 m single span, 54 m tall, leaning 13.5 degrees toward
each other, the deck hung from them on cables, with the shared path on its own deck beside the road.
"""
import math

from mathutils import Vector

import city
from city import Acc, box, raw_z
from common import flat

LEAN = math.tan(math.radians(13.5))


def rod(acc, a, b, w, mi):
    """square beam of width w from a to b (3D points)"""
    d = (b - a)
    if d.length < 1e-3:
        return
    d.normalize()
    u = d.cross(Vector((0, 0, 1)))
    if u.length < 1e-3:
        u = d.cross(Vector((1, 0, 0)))
    u.normalize()
    v = u.cross(d)
    u, v = u * w / 2, v * w / 2
    ca = [a + u + v, a - u + v, a - u - v, a + u - v]
    cb = [b + u + v, b - u + v, b - u - v, b + u - v]
    for i in range(4):
        j = (i + 1) % 4
        acc.face([ca[i], ca[j], cb[j], cb[i]], mi, [(0, 0), (1, 0), (1, 1), (0, 1)], 0.0)


def sweep(acc, pts, side, w, h, mi):
    """rectangular tube along a 3D polyline; side is the horizontal vector across it"""
    rings = []
    for k, p in enumerate(pts):
        t = (pts[min(k + 1, len(pts) - 1)] - pts[max(k - 1, 0)]).normalized()
        up = side.cross(t).normalized()
        s, u = side.normalized() * w / 2, up * h / 2
        rings.append([p + s + u, p - s + u, p - s - u, p + s - u])
    for ra, rb in zip(rings, rings[1:]):
        for i in range(4):
            j = (i + 1) % 4
            acc.face([ra[i], ra[j], rb[j], rb[i]], mi, [(0, 0), (1, 0), (1, 1), (0, 1)], 0.0)


def slab(acc, a, b, n_, width, z_top, depth, mi):
    q = [a + n_ * width / 2, b + n_ * width / 2, b - n_ * width / 2, a - n_ * width / 2]
    z_bot = z_top - depth
    acc.face([(p.x, p.y, z_top) for p in q][::-1], mi, [(p.x, p.y) for p in q][::-1], 0.0)
    acc.face([(p.x, p.y, z_bot) for p in q], mi, [(p.x, p.y) for p in q], 0.0)
    for i in range(4):
        p0, p1 = q[i], q[(i + 1) % 4]
        acc.face([(p0.x, p0.y, z_bot), (p1.x, p1.y, z_bot), (p1.x, p1.y, z_top), (p0.x, p0.y, z_top)], mi,
                 [(0, 0), (1, 0), (1, 1), (0, 1)], 0.0)


def g(p):
    return raw_z(p.x, p.y) - city.Z_REF


def walk(pts, step):
    """points every `step` metres along a 2D polyline: (s, point, tangent, normal)"""
    out, s0 = [], 0.0
    nxt = 0.0
    for a, b in zip(pts, pts[1:]):
        d = b - a
        L = d.length
        if L < 0.1:
            continue
        t = d / L
        while nxt <= s0 + L:
            out.append((nxt, a + t * (nxt - s0), t, Vector((-t.y, t.x))))
            nxt += step
        s0 += L
    return out, s0


def high_level(acc, pts, M_STEEL, M_BCONC):
    road_w = 11.0
    samples, L = walk(pts, 2.0)
    river = min(g(p) for _, p, _, _ in samples)
    deck = river + 41.0          # road deck; the streetcar runs on top, 6.5 m higher
    top = deck + 6.5
    # OSM stops the bridge a little short of the bank tops: carry it on until it meets the ground
    pts = list(pts)
    for end, nxt in ((0, 1), (-1, -2)):
        t = (pts[end] - pts[nxt]).normalized()
        k = 0
        while g(pts[end]) < deck - 1.0 and k < 50:
            if end == 0:
                pts.insert(0, pts[0] + t * 4.0)
            else:
                pts.append(pts[-1] + t * 4.0)
            k += 1
    samples, L = walk(pts, 2.0)
    # decks: the road inside the truss, the streetcar deck on top
    for a, b in zip(pts, pts[1:]):
        d = b - a
        if d.length < 0.1:
            continue
        n_ = Vector((-d.y, d.x)).normalized()
        slab(acc, a, b, n_, road_w, deck, 1.4, M_STEEL)
        slab(acc, a, b, n_, road_w + 1.2, top + 0.5, 0.5, M_STEEL)
    # side trusses: chords, a post every 7 m, Pratt diagonals sloping down toward mid-bridge
    posts, _ = walk(pts, 7.0)
    for side in (-1, 1):
        prev = None
        for s, p, t, n_ in posts:
            o = n_ * side * (road_w / 2 + 0.4)
            b_, t_ = p + o, p + o
            B, T = Vector((b_.x, b_.y, deck)), Vector((t_.x, t_.y, top))
            rod(acc, B, T, 0.45, M_STEEL)
            if prev is not None:
                pB, pT = prev
                rod(acc, pB, B, 0.6, M_STEEL)
                rod(acc, pT, T, 0.6, M_STEEL)
                rod(acc, pT, B, 0.3, M_STEEL) if s < L / 2 else rod(acc, pB, T, 0.3, M_STEEL)
            prev = (B, T)
    # under-deck stringers
    for side in (-1, 1):
        for a, b in zip(pts, pts[1:]):
            d = b - a
            if d.length < 0.1:
                continue
            n_ = Vector((-d.y, d.x)).normalized()
            o = n_ * side * (road_w / 2 - 1.0)
            rod(acc, Vector((a.x + o.x, a.y + o.y, deck - 2.2)), Vector((b.x + o.x, b.y + o.y, deck - 2.2)), 1.6, M_STEEL)
    # supports: where the ground is the river (or close to it) four concrete piers make three long spans,
    # elsewhere a steel tower (two braced bents 9 m apart) every 37 m
    wet = [s for s, p, _, _ in samples if g(p) < river + 3.0]
    s_a, s_b = (min(wet), max(wet)) if wet else (L / 2, L / 2)
    piers = [s_a - 6, s_a + (s_b - s_a) / 3, s_a + 2 * (s_b - s_a) / 3, s_b + 6]
    by_s = {round(s): (p, t, n_) for s, p, t, n_ in samples}

    def at(s):
        k = min(by_s, key=lambda x: abs(x - s))
        return by_s[k]

    for s in piers:
        p, t, n_ = at(s)
        box(acc, p, t, n_, 7.0, road_w + 3.0, g(p) - 3.0, deck - 2.9, M_BCONC)
        box(acc, p, t, n_, 8.5, road_w + 4.5, g(p) - 3.0, g(p) + 2.0, M_BCONC)
    s = 4.0
    while s < L - 4:
        if s_a - 30 < s < s_b + 30:
            s += 37.0
            continue
        bents = []
        for ds in (0.0, 9.0):
            p, t, n_ = at(s + ds)
            h = deck - 2.9 - g(p)
            if h < 3:
                continue
            legs = []
            for side in (-1, 1):
                top_pt = p + n_ * side * (road_w / 2 - 0.5)
                foot = p + n_ * side * (road_w / 2 - 0.5 + h * 0.09)
                A, B = Vector((foot.x, foot.y, g(foot) - 0.5)), Vector((top_pt.x, top_pt.y, deck - 2.9))
                rod(acc, A, B, 1.0, M_STEEL)
                legs.append((A, B))
            (A1, B1), (A2, B2) = legs
            # X braces in panels about 9 m tall, and a strut on each panel line
            panels = max(1, round(h / 9.0))
            for k in range(panels):
                u0, u1 = k / panels, (k + 1) / panels
                P1, Q1 = A1.lerp(B1, u0), A1.lerp(B1, u1)
                P2, Q2 = A2.lerp(B2, u0), A2.lerp(B2, u1)
                rod(acc, P1, Q2, 0.35, M_STEEL)
                rod(acc, P2, Q1, 0.35, M_STEEL)
                rod(acc, Q1, Q2, 0.5, M_STEEL)
            box(acc, p, t, n_, 2.2, road_w + h * 0.18 + 2, g(p) - 1.5, g(p) + 0.6, M_BCONC)
            bents.append(legs)
        if len(bents) == 2:  # tie the two bents of a tower together, lengthwise
            for side in range(2):
                (A1, B1), (A2, B2) = bents[0][side], bents[1][side]
                rod(acc, A1.lerp(B1, 0.5), A2.lerp(B2, 0.5), 0.4, M_STEEL)
                rod(acc, A1, B2, 0.3, M_STEEL)
                rod(acc, A2, B1, 0.3, M_STEEL)
        s += 37.0
    return deck, top


def walterdale(acc, road, paths, M_WHITE, M_BCONC):
    a, b = road[0], road[-1]
    t = (b - a).normalized()
    n_ = Vector((-t.y, t.x))
    mid = (a + b) / 2
    # the paths run on their own decks beside the road: put the arches either side of all of them
    offs = [((sum(p, Vector((0, 0))) / len(p)) - mid).dot(n_) for p in paths]
    lo, hi = min([-7.0] + [o - 2.5 for o in offs]), max([7.0] + [o + 2.5 for o in offs])
    c = mid + n_ * (lo + hi) / 2
    samples, L = walk(road, 4.0)
    river = min(g(p) for _, p, _, _ in samples)
    deck = max(river + 8.0, max(g(a), g(b)) + 0.5)
    span = min(206.0, L * 0.86)
    rise = 54.0 - (deck - river)
    half0 = (hi - lo) / 2 + 2.5
    # decks (the plain deck pass skips this bridge)
    slab(acc, a, b, n_, 14.0, deck, 1.8, M_BCONC)
    for p in paths:
        slab(acc, p[0], p[-1], n_, 5.0, deck - 0.2, 1.2, M_BCONC)
    ribs = []
    for side in (-1, 1):
        pts = []
        for k in range(61):
            u = k / 60
            z = rise * (1 - (2 * u - 1) ** 2)
            lat = half0 - z * LEAN
            q = c + t * (u - 0.5) * span + n_ * side * lat
            pts.append(Vector((q.x, q.y, deck + z)))
        sweep(acc, pts, Vector((n_.x, n_.y, 0)), 2.6, 3.2, M_WHITE)
        ribs.append(pts)
        # footings where the arch meets the bank
        for end in (pts[0], pts[-1]):
            box(acc, end.to_2d(), t, n_, 9.0, 7.0, g(end.to_2d()) - 2.0, deck + 0.5, M_BCONC)
        # 16 hangers per arch, down to the deck edge (tie beam along it)
        for k in range(1, 17):
            u = k / 17
            top_pt = pts[round(u * 60)]
            foot = c + t * (u - 0.5) * span + n_ * side * (half0 - 1.0)
            rod(acc, top_pt, Vector((foot.x, foot.y, deck + 0.3)), 0.22, M_WHITE)
        e0 = c + t * (-span / 2) + n_ * side * (half0 - 1.0)
        e1 = c + t * (span / 2) + n_ * side * (half0 - 1.0)
        rod(acc, Vector((e0.x, e0.y, deck + 0.4)), Vector((e1.x, e1.y, deck + 0.4)), 1.4, M_WHITE)
    return deck


def bridges(col, mats, cdata):
    """returns the bridge object; prints where the two landmarks ended up"""
    M_STEEL, M_BCONC = city.M_STEEL, city.M_BCONC
    white = flat("bridge white", (0.80, 0.80, 0.77), rough=0.38, noise=0.08)
    ms = list(mats) + [white]
    M_WHITE = len(mats)
    acc = Acc()
    made = []
    wd_road, wd_paths = None, []
    lrt_done = False
    for br in cdata["bridges"]:
        pts = [Vector(p) for p in br["p"]]
        L = sum((q - p).length for p, q in zip(pts, pts[1:]))
        if L < 60 or (pts[0] - pts[-1]).length < 1.0:
            continue
        xs = [p.x for p in pts]
        is_wd = 150 < min(xs) and max(xs) < 320 and 180 < L < 300
        if is_wd and br.get("name") == "105 Street NW":
            wd_road = pts
            continue
        if is_wd and br.get("hw") in ("cycleway", "footway", "path"):
            wd_paths.append(pts)
            continue
        if br.get("name") == "109 Street NW" and L > 600:
            d, tp = high_level(acc, pts, M_STEEL, M_BCONC)
            print("High Level Bridge: road deck", round(d, 1), "streetcar deck", round(tp, 1), "length", round(L))
            made.append(("High Level", round(L)))
            continue
        if br.get("name") in ("High Level Bridge",) or (br.get("rail") == "tram" and L > 600):
            continue  # the outline and the streetcar line: the model above has both decks
        if L > 600 and min(xs) > -560 and max(xs) < -290 and br.get("hw") in ("cycleway", "footway", "path"):
            continue  # the High Level's walkway, inside the model
        ys = [p.y for p in pts]
        near_hl = -720 < min(xs) and max(xs) < -370 and -310 < min(ys) and max(ys) < 310
        lrt = near_hl and br.get("rail") == "light_rail" and L > 600
        if near_hl and br.get("hw") in ("cycleway", "footway", "path"):
            continue  # the Dudley B. Menzies Bridge's path hangs under its deck
        if lrt and lrt_done:
            continue  # its two tracks are one deck
        lrt_done = lrt_done or lrt
        width = 4.0 if br.get("hw") in ("footway", "cycleway", "path") else (8.0 if br.get("rail") else 13.0)
        width = 12.0 if lrt else width
        spacing, pier_w = (95.0, 3.2) if lrt else (45.0, 2.2)
        za, zb = raw_z(*pts[0]) - city.Z_REF, raw_z(*pts[-1]) - city.Z_REF
        deck = max(za, zb) + 0.5
        s0, nxt = 0.0, spacing / 2  # piers evenly along the whole bridge, not restarting at every bend of the line
        for a, b in zip(pts, pts[1:]):
            d = b - a
            if d.length < 0.1:
                continue
            t = d / d.length
            n_ = Vector((-t.y, t.x))
            slab(acc, a, b, n_, width, deck, 1.6, M_BCONC)
            while nxt < s0 + d.length:
                p = a + t * (nxt - s0)
                gz = raw_z(p.x, p.y) - city.Z_REF - 2
                if deck - gz > 4:
                    box(acc, p, t, n_, pier_w, width * (0.5 if lrt else 0.8), gz, deck - 1.6, M_BCONC)
                nxt += spacing
            s0 += d.length
        made.append((br.get("name"), round(L)))
    if wd_road:
        d = walterdale(acc, wd_road, wd_paths, M_WHITE, M_BCONC)
        print("Walterdale Bridge: deck", round(d, 1), "paths", len(wd_paths))
        made.append(("Walterdale", 0))
    ob = acc.build("bridges", ms, col)
    print("bridges", len(made))
    return ob

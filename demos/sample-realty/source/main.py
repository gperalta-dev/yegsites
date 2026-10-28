"""Whyte Web Sample Realty demo: golden hour over central Edmonton (real OSM footprints and heights, real terrain), across
the river and down into a made-up suburb, ending on a detailed house and a walk around it.

blender -b -P main.py -- --dl <assets/dl> --geo <assets/geo/out> --out <dir> [--frames 0,60] [--res 1600x900]
      [--samples 160] [--save scene.blend] [--nohair]
"""
import math
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import bpy
import numpy as np
from mathutils import Matrix, Vector

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def arg(name, default=None):
    return ARGS[ARGS.index(name) + 1] if name in ARGS else default


bpy.ops.wm.read_factory_settings(use_empty=True)
import common
common.set_dl(arg("--dl"))
import city
import look
import plants
import suburb

T0 = time.time()
OUT = Path(arg("--out", "frames")).resolve()
RES = tuple(int(v) for v in arg("--res", "1600x900").split("x"))
SAMPLES = int(arg("--samples", "160"))
FRAME_END = 239
SUN_PHI, SUN_EL = -160.0, 15.0
# the made-up suburb: a disk on the south side, the hero street a crescent whose houses face south-west (into the sun)
SUB = (-150.0, -1850.0, 520.0)
FRONT = Vector((-math.sin(math.radians(40)), -math.cos(math.radians(40))))  # from house to street, azimuth 220
S_HERO = Vector((-205.0, -1905.0))
R_HERO = 300.0
C = S_HERO - FRONT * R_HERO  # crescent centre, on the house side
SPACING = 86.0

scene = bpy.context.scene
col = scene.collection
city.setup(arg("--geo"), SUB)
plants.load_prototypes()


def edge_r(a):
    """irregular outline of the new subdivision (distance from SUB centre by angle)"""
    return SUB[2] - 40 + 38 * math.sin(3 * a + 1.0) + 22 * math.sin(5 * a + 2.3)


def inside_sub(x, y, margin=0.0):
    a = math.atan2(y - SUB[1], x - SUB[0])
    return math.hypot(x - SUB[0], y - SUB[1]) < edge_r(a) - margin


T_DIR = Vector((-FRONT.y, FRONT.x))  # along the hero street (azimuth 130), hero lots on its left
N_DIR = -FRONT                        # across the streets, toward the hero house side


def wave(s):
    return 14.0 * math.sin(s / 105.0 + 0.6) + 6.0 * math.sin(s / 47.0 + 2.0)


CROSS = (-175.0, 160.0)  # cross streets at these distances along the hero street


def layout():
    """parallel gently winding streets 86 m apart (back-to-back lots between them), two cross streets, all clipped to an
    irregular outline. returns streets, hero index and arc length, cross streets"""
    streets, hero_idx, hero_s = [], None, None
    for k in range(-5, 6):
        pts = []
        for i in range(-260, 261):
            s_ = i * 3.0
            p = S_HERO + T_DIR * s_ + N_DIR * (k * SPACING + wave(s_) - wave(0.0))
            pts.append((s_, (p.x, p.y)))
        run, best = [], []
        for s_, p in pts:
            if inside_sub(*p, margin=44):
                run.append((s_, p))
            else:
                best = run if len(run) > len(best) else best
                run = []
        best = run if len(run) > len(best) else best
        if len(best) < 15:
            continue
        if k == 0:
            hero_idx = len(streets)
            acc = 0.0
            for (s0, p0), (s1, p1) in zip(best, best[1:]):
                if s0 <= 0.0 < s1:
                    hero_s = acc + math.dist(p0, (S_HERO.x, S_HERO.y)) - 7.5
                acc += math.dist(p0, p1)
        streets.append([p for _, p in best])
    cross = []
    for c in CROSS:
        pts = []
        for i in range(-200, 201):
            p = S_HERO + T_DIR * (c + wave(i * 3.0) * 0.0) + N_DIR * (i * 3.0)
            p = p + N_DIR * 0 + T_DIR * 0
            if inside_sub(p.x, p.y, margin=44):
                pts.append((p.x, p.y))
        if len(pts) > 10:
            cross.append(pts)
    return streets, hero_idx, hero_s, cross


def keep_lot(m):
    o = m.translation
    y_axis = Vector(m.col[1][:3])
    back = o + y_axis * 18.0
    if not (inside_sub(o.x, o.y, 10) and inside_sub(back.x, back.y, 0)):
        return False
    rel = (o.to_2d() - S_HERO)
    along = rel.dot(T_DIR)
    return all(abs(along - c) > 16.0 for c in CROSS)


streets, hero_idx, hero_s, cross = layout()
hero_m, hero_kit = suburb.build(streets, hero_idx, hero_s, col, hair="--nohair" not in ARGS, keep=keep_lot, extra_streets=cross)
H = hero_m.translation.copy()
HX, HY = Vector(hero_m.col[0][:3]), Vector(hero_m.col[1][:3])
print("hero house at", tuple(round(v, 1) for v in H), "front faces", tuple(round(-v, 2) for v in HY[:2]))

terr = city.terrain(col)
city.far_ground(col)
mats, cdata = city.buildings(col)
if (Path(arg("--geo")) / "ortho.json").exists() and "--noortho" not in ARGS:
    import ortho
    ortho.load(arg("--geo"))
    ortho.assign(terr, keep_disk=(SUB[0], SUB[1], SUB[2] + 40))
    ortho.assign(bpy.data.objects["city houses"], only={city.M_OLDROOF})
    ortho.assign(bpy.data.objects["city buildings"], only={city.M_GRAVEL}, max_z=30.0)
city.water(col, mats, cdata)
city.bridges(col, mats, cdata)
trees = city.tree_points()
city.gn_scatter("city trees", trees, {0: plants.PROTO["tree"], 1: plants.PROTO["spruce"], 2: plants.PROTO["tree2"],
                                      3: plants.PROTO["tree3"], 4: plants.PROTO["sapling"]}, col)
# suburb park strips and back-lot trees: a ring of trees between the collector and the back fences
rng = np.random.default_rng(11)
extra = []
for k in range(1400):
    a = rng.uniform(0, 2 * math.pi)
    r = edge_r(a) - rng.uniform(-12, 30)
    x, y = SUB[0] + r * math.cos(a), SUB[1] + r * math.sin(a)
    k_ = 0 if rng.random() < 0.55 else (1 if rng.random() < 0.5 else 3)
    extra.append((x, y, 0.0, k_, rng.uniform(1.6, 2.6) if k_ < 3 else rng.uniform(0.45, 0.7), rng.uniform(0, 6.28)))
city.gn_scatter("suburb edge trees", np.array(extra, np.float32), {0: plants.PROTO["tree"], 1: plants.PROTO["spruce"],
                                                                     3: plants.PROTO["tree3"]}, col)
HDRI = arg("--hdri", "kloppenheim_06_puresky")
look.sky(common.DL / "hdri" / f"{HDRI}_8k.hdr", common.DL / "hdri" / f"{HDRI}_1k.hdr", sun_phi_deg=SUN_PHI, sun_el_deg=SUN_EL,
         strength=1.0)
print("scene built in", round(time.time() - T0, 1), "s")


# ---------------------------------------------------------------- camera
def catmull(points, t):
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


def hl(x, y, z):
    """point in the hero house frame"""
    return H + HX * x + HY * y + Vector((0, 0, z))


DOWNTOWN = Vector((640.0, 1300.0, 70.0))
FLY_END = 172
ORBIT_R, ORBIT_Z = 30.0, 30.0
# north bank looking east at downtown (sun behind), across the river west of the High Level Bridge, south over Garneau,
# hook round the west side of the suburb and come in to the front of the house from the street
fly_pos = [Vector((-950, 1800, 265)), Vector((-760, 1240, 250)), Vector((-600, 90, 228)), Vector((-430, -950, 200)),
           hl(-230, -40, 140), hl(-120, -110, 70), hl(-45, -42, 24), hl(-8, -27, 7.5)]
fly_tgt = [DOWNTOWN, DOWNTOWN + Vector((-80, -260, -20)), Vector((-200, -700, 0)), hl(-40, -60, 0),
           hl(0, -30, 0), hl(0, -12, 2), hl(0, -6, 3), hl(0.3, -2.5, 3.4)]
lens_keys = [(0, 30), (60, 28), (120, 30), (FLY_END, 30), (FRAME_END, 34)]


def cam_at(f):
    if f <= FLY_END:
        t = ease(f / FLY_END) * 0.6 + (f / FLY_END) * 0.4
        return catmull(fly_pos, t), catmull(fly_tgt, t)
    u = ease((f - FLY_END) / (FRAME_END - FLY_END))
    p_end = fly_pos[-1]
    q_c = hl(0, 2.0, 3.0)
    a0 = math.atan2(p_end.y - q_c.y, p_end.x - q_c.x)
    r0 = (p_end.to_2d() - q_c.to_2d()).length
    a = a0 + u * math.radians(360)
    r = r0 + (ORBIT_R - r0) * math.sin(u * math.pi) ** 0.6 if u < 1 else r0
    z = p_end.z + (ORBIT_Z - p_end.z) * math.sin(u * math.pi) ** 0.5
    p = Vector((q_c.x + r * math.cos(a), q_c.y + r * math.sin(a), z))
    q = q_c + (fly_tgt[-1] - q_c) * (1 - math.sin(u * math.pi))
    return p, q


def camera():
    cd = bpy.data.cameras.new("cam")
    cd.clip_start, cd.clip_end = 0.3, 15000
    cd.sensor_width = 36
    co = bpy.data.objects.new("cam", cd)
    col.objects.link(co)
    scene.camera = co
    cd.dof.use_dof = True
    focus = bpy.data.objects.new("focus", None)
    col.objects.link(focus)
    cd.dof.focus_object = focus
    for f in range(FRAME_END + 1):
        p, q = cam_at(f)
        co.location = p
        co.rotation_euler = (q - p).to_track_quat("-Z", "Y").to_euler()
        co.keyframe_insert("location", frame=f)
        co.keyframe_insert("rotation_euler", frame=f)
        focus.location = q
        focus.keyframe_insert("location", frame=f)
        lens = np.interp(f, [k for k, _ in lens_keys], [v for _, v in lens_keys])
        cd.lens = float(lens)
        cd.keyframe_insert("lens", frame=f)
        # depth of field only when close: f/22 in the air, f/5.6 at the house
        dist = (q - p).length
        cd.dof.aperture_fstop = 8.0 if dist < 40 else (128.0 if dist > 90 else 8.0 + (dist - 40) / 50 * 120.0)
        cd.dof.keyframe_insert("aperture_fstop", frame=f)
    for fc in getattr(co.animation_data.action, "fcurves", []) or []:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"
    return co


camera()
# keep the low part of the flight clear: no yard tree crowns where the camera passes under 20 m
cam_pts = [cam_at(f)[0] for f in range(90, FRAME_END + 1)]
cut = []
for o in list(col.objects):
    if o.type == "MESH" and o.name.split(".")[0] in ("tree", "tree2", "spruce", "conifer", "shrub") and o.parent is None:
        r = 9.0 if o.name.startswith(("tree", "spruce")) else 2.0
        loc = o.location
        if any(p.z < 20 and (p.to_2d() - loc.to_2d()).length < r for p in cam_pts):
            cut.append(o)
for o in cut:
    bpy.data.objects.remove(o)
print("cleared", len(cut), "plants from the camera path")
look.render_settings(RES, SAMPLES, threshold=0.012, persistent=True, motion_blur=0.0)
hz = look.HORIZON
look.grade(start=250, length=float(arg("--haze-len", "30000")), haze_color=tuple(hz),
           near_len=4000.0, near_amt=float(arg("--near", "0.18")), near_color=(hz[0] * 1.06, hz[1] * 1.0, hz[2] * 0.9), bloom=0.08)
scene.frame_start, scene.frame_end = 0, FRAME_END
if arg("--save"):
    bpy.ops.wm.save_as_mainfile(filepath=str(Path(arg("--save")).resolve()))
if "--probe" in ARGS:  # lot edges next to the listing, in the listing's frame
    inv = hero_m.inverted()
    for o in col.objects:
        if o.type == "MESH" and o.name.split(".")[0] in ("lot", "hero lot") and (o.matrix_world.translation - H).length < 40:
            xs = [(inv @ (o.matrix_world @ v.co)).x for v in o.data.vertices]
            ys = [(inv @ (o.matrix_world @ v.co)).y for v in o.data.vertices]
            print("PROBE", o.name, "x", round(min(xs), 2), round(max(xs), 2), "y", round(min(ys), 1), round(max(ys), 1))
if arg("--still"):
    x, y, z, tx, ty, tz, lens = (float(v) for v in arg("--still").split(","))
    co = scene.camera
    co.animation_data_clear()
    co.data.animation_data_clear()
    co.location = hl(x, y, z)
    co.rotation_euler = (hl(tx, ty, tz) - co.location).to_track_quat("-Z", "Y").to_euler()
    co.data.lens = lens
    co.data.dof.use_dof = False
    OUT.mkdir(parents=True, exist_ok=True)
    scene.render.filepath = str(OUT / arg("--still-name", "still.png"))
    bpy.ops.render.render(write_still=True)
    raise SystemExit(0)
if "--norender" in ARGS:
    raise SystemExit(0)
OUT.mkdir(parents=True, exist_ok=True)
frames = [int(f) for f in arg("--frames").split(",")] if arg("--frames") else range(FRAME_END + 1)
for f in frames:
    scene.frame_set(f)
    scene.render.filepath = str(OUT / f"f{f:03d}.png")
    t1 = time.time()
    bpy.ops.render.render(write_still=True)
    print(f"rendered {f} in {time.time() - t1:.1f}s", flush=True)

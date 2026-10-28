"""shared helpers for the realty scene: a fast mesh builder with world-metre UVs, PBR materials from Poly Haven maps"""
import math
from pathlib import Path

import bpy
from mathutils import Vector

DL = Path(".")
Z = Vector((0, 0, 1))


def set_dl(p):
    global DL
    DL = Path(p).resolve()


def link(obj, col=None):
    (col or bpy.context.scene.collection).objects.link(obj)
    return obj


# ---------------------------------------------------------------- mesh builder
class MB:
    """collects faces, then makes one mesh. parts share vertices inside themselves so bevels work per part."""

    def __init__(self):
        self.verts, self.faces, self.mats, self.uvs = [], [], [], []
        self._part = None

    def begin(self):
        self._part = {}

    def end(self):
        self._part = None

    def _v(self, p):
        p = (round(p[0], 5), round(p[1], 5), round(p[2], 5))
        if self._part is not None:
            i = self._part.get(p)
            if i is None:
                i = self._part[p] = len(self.verts)
                self.verts.append(p)
            return i
        self.verts.append(p)
        return len(self.verts) - 1

    def face(self, pts, mi, uvs=None, uv_scale=1.0):
        pts = [Vector(p) for p in pts]
        if uvs is None:
            uvs = auto_uv(pts)
        self.faces.append([self._v(p) for p in pts])
        self.mats.append(mi)
        self.uvs.append([(u * uv_scale, v * uv_scale) for u, v in uvs])

    def box(self, lo, hi, mi, mis=None):
        """axis-aligned box. mis = optional per-face material dict keyed by -x +x -y +y -z +z"""
        x0, y0, z0 = lo
        x1, y1, z1 = hi
        if x1 - x0 < 1e-5 or y1 - y0 < 1e-5 or z1 - z0 < 1e-5:
            return
        mis = mis or {}
        self.begin()
        self.face([(x0, y1, z0), (x0, y0, z0), (x0, y0, z1), (x0, y1, z1)], mis.get("-x", mi))
        self.face([(x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)], mis.get("+x", mi))
        self.face([(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)], mis.get("-y", mi))
        self.face([(x1, y1, z0), (x0, y1, z0), (x0, y1, z1), (x1, y1, z1)], mis.get("+y", mi))
        self.face([(x0, y1, z0), (x1, y1, z0), (x1, y0, z0), (x0, y0, z0)], mis.get("-z", mi))
        self.face([(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)], mis.get("+z", mi))
        self.end()

    def obox(self, c, ax, ay, az, mi, skip=()):
        """oriented box from centre and three half-extent vectors (right handed)"""
        c, ax, ay, az = Vector(c), Vector(ax), Vector(ay), Vector(az)
        P = lambda i, j, k: c + ax * i + ay * j + az * k
        self.begin()
        quads = {
            "-x": [P(-1, 1, -1), P(-1, -1, -1), P(-1, -1, 1), P(-1, 1, 1)],
            "+x": [P(1, -1, -1), P(1, 1, -1), P(1, 1, 1), P(1, -1, 1)],
            "-y": [P(-1, -1, -1), P(1, -1, -1), P(1, -1, 1), P(-1, -1, 1)],
            "+y": [P(1, 1, -1), P(-1, 1, -1), P(-1, 1, 1), P(1, 1, 1)],
            "-z": [P(-1, 1, -1), P(1, 1, -1), P(1, -1, -1), P(-1, -1, -1)],
            "+z": [P(-1, -1, 1), P(1, -1, 1), P(1, 1, 1), P(-1, 1, 1)],
        }
        for k, q in quads.items():
            if k not in skip:
                self.face(q, mi)
        self.end()

    def cyl(self, c, r, h, mi, seg=12, axis="z"):
        c = Vector(c)
        self.begin()
        ring = []
        for i in range(seg):
            a = 2 * math.pi * i / seg
            if axis == "z":
                ring.append((c + Vector((r * math.cos(a), r * math.sin(a), 0)), c + Vector((r * math.cos(a), r * math.sin(a), h))))
            elif axis == "y":
                ring.append((c + Vector((r * math.cos(a), 0, r * math.sin(a))), c + Vector((r * math.cos(a), h, r * math.sin(a)))))
            else:
                ring.append((c + Vector((0, r * math.cos(a), r * math.sin(a))), c + Vector((h, r * math.cos(a), r * math.sin(a)))))
        for i in range(seg):
            a0, a1 = ring[i], ring[(i + 1) % seg]
            self.face([a0[0], a1[0], a1[1], a0[1]], mi)
        self.face([r_[1] for r_ in ring], mi)
        self.face([r_[0] for r_ in reversed(ring)], mi)
        self.end()

    def build(self, name, mats, smooth=False, bevel=0.0, col=None):
        me = bpy.data.meshes.new(name)
        me.from_pydata(self.verts, [], self.faces)
        me.polygons.foreach_set("material_index", self.mats)
        uv = me.uv_layers.new(name="UVMap")
        flat = [c for f in self.uvs for uv_ in f for c in uv_]
        uv.data.foreach_set("uv", flat)
        for m in mats:
            me.materials.append(m)
        me.validate(clean_customdata=False)
        me.update()
        if smooth:
            me.shade_smooth()
        ob = bpy.data.objects.new(name, me)
        link(ob, col)
        if bevel > 0:
            bm = ob.modifiers.new("bevel", "BEVEL")
            bm.width = bevel
            bm.segments = 2
            bm.limit_method = "ANGLE"
            bm.angle_limit = math.radians(35)
            bm.harden_normals = True
            bm.use_clamp_overlap = True
            apply_modifiers(ob)
        return ob


def apply_modifiers(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = bpy.data.meshes.new_from_object(ev)
    old = ob.data
    ob.modifiers.clear()
    ob.data = me
    bpy.data.meshes.remove(old)


def auto_uv(pts):
    """world-metre uv: horizontal faces use x,y; walls use (along wall, z)"""
    n = (pts[1] - pts[0]).cross(pts[2] - pts[0])
    if n.length < 1e-12 and len(pts) > 3:
        n = (pts[2] - pts[0]).cross(pts[3] - pts[0])
    n = n.normalized() if n.length > 1e-12 else Z.copy()
    if abs(n.z) > 0.7:
        return [(p.x, p.y) for p in pts]
    t = Z.cross(n)
    t = t.normalized() if t.length > 1e-9 else Vector((1, 0, 0))
    return [(p.dot(t), p.z) for p in pts]


# ---------------------------------------------------------------- materials
def N(nt, kind, x=0, y=0, **props):
    node = nt.nodes.new(kind)
    node.location = (x, y)
    for k, v in props.items():
        setattr(node, k, v)
    return node


def new_mat(name):
    m = bpy.data.materials.new(name)
    try:
        m.use_nodes = True
    except Exception:
        pass
    return m, m.node_tree, m.node_tree.nodes.get("Principled BSDF")


def img(path, data=False):
    im = bpy.data.images.load(str(path), check_existing=True)
    im.colorspace_settings.name = "Non-Color" if data else "sRGB"
    return im


def tex_node(nt, path, vec, data=False, x=-500, y=0):
    t = N(nt, "ShaderNodeTexImage", x, y)
    t.image = img(path, data)
    t.interpolation = "Cubic" if not data else "Linear"
    nt.links.new(vec, t.inputs["Vector"])
    return t


def mapping(nt, size_m, rot=0.0, offset=(0, 0)):
    tc = N(nt, "ShaderNodeTexCoord", -1100, 0)
    mp = N(nt, "ShaderNodeMapping", -900, 0)
    mp.inputs["Scale"].default_value = (1 / size_m, 1 / size_m, 1)
    mp.inputs["Rotation"].default_value = (0, 0, rot)
    mp.inputs["Location"].default_value = (offset[0], offset[1], 0)
    nt.links.new(tc.outputs["UV"], mp.inputs["Vector"])
    return mp.outputs["Vector"]


def pbr(name, asset, size_m, tint=None, rough=(0.0, 1.0), bump=1.0, rot=0.0, value=1.0, sat=1.0, offset=(0, 0), spec=0.5):
    """Poly Haven diff/nor/arm maps on world-metre UVs. tint multiplies the colour, value and sat adjust it, rough maps
    the arm green channel into a range."""
    m, nt, p = new_mat(name)
    d = DL / asset
    vec = mapping(nt, size_m, rot, offset)
    diff = tex_node(nt, d / "diff.jpg", vec, x=-600, y=300)
    col = diff.outputs["Color"]
    if sat != 1.0 or value != 1.0:
        hsv = N(nt, "ShaderNodeHueSaturation", -300, 300)
        hsv.inputs["Saturation"].default_value = sat
        hsv.inputs["Value"].default_value = value
        nt.links.new(col, hsv.inputs["Color"])
        col = hsv.outputs["Color"]
    if tint:
        mix = N(nt, "ShaderNodeMix", -150, 300, data_type="RGBA", blend_type="MULTIPLY")
        mix.inputs["Factor"].default_value = 1.0
        nt.links.new(col, mix.inputs["A"])
        mix.inputs["B"].default_value = (*tint, 1)
        col = mix.outputs["Result"]
    nt.links.new(col, p.inputs["Base Color"])
    if (d / "arm.jpg").exists():
        arm = tex_node(nt, d / "arm.jpg", vec, data=True, x=-600, y=0)
        sep = N(nt, "ShaderNodeSeparateColor", -350, 0)
        nt.links.new(arm.outputs["Color"], sep.inputs["Color"])
        mr = N(nt, "ShaderNodeMapRange", -150, 0)
        mr.inputs["To Min"].default_value, mr.inputs["To Max"].default_value = rough
        nt.links.new(sep.outputs["Green"], mr.inputs["Value"])
        nt.links.new(mr.outputs["Result"], p.inputs["Roughness"])
    if (d / "nor.jpg").exists() and bump > 0:
        nor = tex_node(nt, d / "nor.jpg", vec, data=True, x=-600, y=-300)
        nm = N(nt, "ShaderNodeNormalMap", -250, -300)
        nm.inputs["Strength"].default_value = bump
        nt.links.new(nor.outputs["Color"], nm.inputs["Color"])
        nt.links.new(nm.outputs["Normal"], p.inputs["Normal"])
    try:
        p.inputs["Specular IOR Level"].default_value = spec
    except Exception:
        pass
    return m


def flat(name, color, rough=0.5, metal=0.0, noise=0.0, bump=0.0, coat=0.0, spec=0.5):
    """painted or plastic surface with a little colour noise and micro bump so it never reads as CG-perfect"""
    m, nt, p = new_mat(name)
    p.inputs["Base Color"].default_value = (*color, 1)
    p.inputs["Roughness"].default_value = rough
    p.inputs["Metallic"].default_value = metal
    try:
        p.inputs["Specular IOR Level"].default_value = spec
        p.inputs["Coat Weight"].default_value = coat
    except Exception:
        pass
    if noise > 0 or bump > 0:
        tc = N(nt, "ShaderNodeTexCoord", -900, 0)
        nz = N(nt, "ShaderNodeTexNoise", -700, 0)
        nz.inputs["Scale"].default_value = 3.0
        nz.inputs["Detail"].default_value = 6.0
        nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
        if noise > 0:  # blotchy darkening, like weathering and uneven paint
            mix = N(nt, "ShaderNodeMix", -300, 200, data_type="RGBA", blend_type="MIX")
            mix.inputs["A"].default_value = (*color, 1)
            mix.inputs["B"].default_value = tuple(c * (1 - noise) for c in color) + (1,)
            nt.links.new(nz.outputs["Fac"], mix.inputs["Factor"])
            nt.links.new(mix.outputs["Result"], p.inputs["Base Color"])
        if bump > 0:
            fine = N(nt, "ShaderNodeTexNoise", -700, -250)
            fine.inputs["Scale"].default_value = 180.0
            fine.inputs["Detail"].default_value = 4.0
            nt.links.new(tc.outputs["Object"], fine.inputs["Vector"])
            b = N(nt, "ShaderNodeBump", -300, -250)
            b.inputs["Strength"].default_value = bump
            b.inputs["Distance"].default_value = 0.002
            nt.links.new(fine.outputs["Fac"], b.inputs["Height"])
            nt.links.new(b.outputs["Normal"], p.inputs["Normal"])
    return m


def emission(name, color, strength):
    m, nt, p = new_mat(name)
    p.inputs["Base Color"].default_value = (*color, 1)
    p.inputs["Emission Color"].default_value = (*color, 1)
    p.inputs["Emission Strength"].default_value = strength
    p.inputs["Roughness"].default_value = 0.3
    return m


def glass(name, tint=(0.80, 0.86, 0.84), rough=0.01, ior=1.52):
    """thin window glass: straight-through transparency plus Fresnel reflection, so panes reflect the sky at an angle,
    show the room head on, and let sunlight into the rooms"""
    m, nt, p = new_mat(name)
    out = nt.nodes.get("Material Output")
    nt.nodes.remove(p)
    tr = N(nt, "ShaderNodeBsdfTransparent", -300, -100)
    tr.inputs["Color"].default_value = (*tint, 1)
    gl = N(nt, "ShaderNodeBsdfGlossy", -300, 100)
    gl.inputs["Roughness"].default_value = rough
    fr = N(nt, "ShaderNodeFresnel", -600, 300)
    fr.inputs["IOR"].default_value = ior
    mx = N(nt, "ShaderNodeMixShader", 0, 0)
    nt.links.new(fr.outputs["Fac"], mx.inputs["Fac"])
    nt.links.new(tr.outputs[0], mx.inputs[1])
    nt.links.new(gl.outputs[0], mx.inputs[2])
    nt.links.new(mx.outputs[0], out.inputs["Surface"])
    return m


def backface_mix(m, inside_color=(0.78, 0.74, 0.68)):
    """walls are single sided: seen from inside (through a window) they show painted drywall, not siding"""
    nt = m.node_tree
    out = nt.nodes.get("Material Output")
    surf = out.inputs["Surface"].links[0].from_socket
    geo = N(nt, "ShaderNodeNewGeometry", 200, 400)
    paint = N(nt, "ShaderNodeBsdfDiffuse", 200, 250)
    paint.inputs["Color"].default_value = (*inside_color, 1)
    mx = N(nt, "ShaderNodeMixShader", 450, 300)
    nt.links.new(geo.outputs["Backfacing"], mx.inputs["Fac"])
    nt.links.new(surf, mx.inputs[1])
    nt.links.new(paint.outputs[0], mx.inputs[2])
    nt.links.new(mx.outputs[0], out.inputs["Surface"])
    return m

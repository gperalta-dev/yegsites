"""Poly Haven CC0 plants as instancing prototypes, and a hair-grass lawn.

prototypes live in a hidden collection; scatter() makes linked duplicates so Cycles stores each mesh once.
leaf materials get translucency (backlit leaves glow at golden hour) and per-instance colour variation.
"""
import math
import random

import bpy
from mathutils import Vector

import common
from common import N, link

MODELS = {
    "tree": ("tree_small_02", ["tree_small_02_LOD0"]),
    "tree2": ("island_tree_02", ["island_tree_02_LOD0"]),
    "spruce": ("fir_sapling_medium", ["fir_sapling_medium_a_LOD0", "fir_sapling_medium_b_LOD0", "fir_sapling_medium_c_LOD0"]),
    "conifer": ("pine_sapling_small", ["pine_sapling_small_a", "pine_sapling_small_b", "pine_sapling_small_c"]),
    "shrub": ("searsia_lucida", ["searsia_lucida_a_LOD0", "searsia_lucida_b_LOD0", "searsia_lucida_c_LOD0"]),
    "grass": ("grass_medium_01", ["grass_medium_01_tall_a_LOD0", "grass_medium_01_tall_b_LOD0", "grass_medium_01_tall_c_LOD0"]),
    "tree3": ("jacaranda_tree", ["jacaranda_tree_LOD0"]),
    "sapling": ("fir_sapling", ["fir_sapling_a", "fir_sapling_b", "fir_sapling_c"]),
}
BROADLEAF = ("tree", "tree2", "tree3")
PROTO = {}


def _autumn(nt, color_out, oi):
    """late October: most broadleaf crowns gold, orange or rust, a few still green, colour picked per tree"""
    pick = N(nt, "ShaderNodeMath", -100, 900, operation="FRACT")
    m1 = N(nt, "ShaderNodeMath", -250, 900, operation="MULTIPLY")
    m1.inputs[1].default_value = 7.13
    nt.links.new(oi.outputs["Random"], m1.inputs[0])
    nt.links.new(m1.outputs[0], pick.inputs[0])
    ramp = N(nt, "ShaderNodeValToRGB", 50, 900)
    cr = ramp.color_ramp
    cr.elements[0].position, cr.elements[0].color = 0.0, (0.95, 0.66, 0.13, 1)
    cr.elements[1].position, cr.elements[1].color = 1.0, (0.42, 0.27, 0.11, 1)
    for pos, col in ((0.3, (0.98, 0.54, 0.09, 1)), (0.55, (0.80, 0.32, 0.07, 1)), (0.75, (0.72, 0.64, 0.17, 1))):
        e = cr.elements.new(pos)
        e.color = col
    nt.links.new(pick.outputs[0], ramp.inputs["Fac"])
    bw = N(nt, "ShaderNodeRGBToBW", 50, 700)
    nt.links.new(color_out, bw.inputs["Color"])
    sc = N(nt, "ShaderNodeMath", 200, 700, operation="MULTIPLY")
    sc.inputs[1].default_value = 4.4
    nt.links.new(bw.outputs["Val"], sc.inputs[0])
    tinted = N(nt, "ShaderNodeMix", 350, 800, data_type="RGBA", blend_type="MULTIPLY")
    tinted.inputs["Factor"].default_value = 1.0
    nt.links.new(ramp.outputs["Color"], tinted.inputs["A"])
    cc = N(nt, "ShaderNodeCombineColor", 200, 600)
    for k in ("Red", "Green", "Blue"):
        nt.links.new(sc.outputs[0], cc.inputs[k])
    nt.links.new(cc.outputs["Color"], tinted.inputs["B"])
    turned = N(nt, "ShaderNodeMath", -100, 1100, operation="FRACT")
    m2 = N(nt, "ShaderNodeMath", -250, 1100, operation="MULTIPLY")
    m2.inputs[1].default_value = 3.71
    nt.links.new(oi.outputs["Random"], m2.inputs[0])
    nt.links.new(m2.outputs[0], turned.inputs[0])
    f = N(nt, "ShaderNodeMapRange", 50, 1100)
    f.inputs["From Min"].default_value, f.inputs["From Max"].default_value = 0.1, 0.3
    f.inputs["To Min"].default_value, f.inputs["To Max"].default_value = 0.0, 0.95
    nt.links.new(turned.outputs[0], f.inputs["Value"])
    mix = N(nt, "ShaderNodeMix", 500, 700, data_type="RGBA")
    nt.links.new(f.outputs["Result"], mix.inputs["Factor"])
    nt.links.new(color_out, mix.inputs["A"])
    nt.links.new(tinted.outputs["Result"], mix.inputs["B"])
    return mix.outputs["Result"], f.outputs["Result"]


def _thin(nt, alpha_src, turned, oi):
    """turned trees have dropped some leaves: cut out patches of the crown"""
    tc = N(nt, "ShaderNodeTexCoord", -400, 1300)
    off = N(nt, "ShaderNodeVectorMath", -250, 1300, operation="ADD")
    nt.links.new(tc.outputs["Object"], off.inputs[0])
    cmb = N(nt, "ShaderNodeCombineXYZ", -400, 1450)
    m = N(nt, "ShaderNodeMath", -550, 1450, operation="MULTIPLY")
    m.inputs[1].default_value = 173.0
    nt.links.new(oi.outputs["Random"], m.inputs[0])
    for k in ("X", "Y", "Z"):
        nt.links.new(m.outputs[0], cmb.inputs[k])
    nt.links.new(cmb.outputs["Vector"], off.inputs[1])
    nz = N(nt, "ShaderNodeTexNoise", -100, 1300)
    nz.inputs["Scale"].default_value = 1.4
    nz.inputs["Detail"].default_value = 3.0
    nt.links.new(off.outputs["Vector"], nz.inputs["Vector"])
    rt = N(nt, "ShaderNodeMath", -100, 1600, operation="FRACT")
    rm = N(nt, "ShaderNodeMath", -250, 1600, operation="MULTIPLY")
    rm.inputs[1].default_value = 11.3
    nt.links.new(oi.outputs["Random"], rm.inputs[0])
    nt.links.new(rm.outputs[0], rt.inputs[0])
    tw = N(nt, "ShaderNodeMath", 50, 1600, operation="MULTIPLY")
    nt.links.new(turned, tw.inputs[0])
    nt.links.new(rt.outputs[0], tw.inputs[1])
    thr = N(nt, "ShaderNodeMath", 50, 1450, operation="MULTIPLY")
    thr.inputs[1].default_value = 0.42
    nt.links.new(tw.outputs[0], thr.inputs[0])
    thr2 = N(nt, "ShaderNodeMath", 200, 1450, operation="ADD")
    thr2.inputs[1].default_value = 0.06
    nt.links.new(thr.outputs[0], thr2.inputs[0])
    keep = N(nt, "ShaderNodeMath", 350, 1300, operation="GREATER_THAN")
    nt.links.new(nz.outputs["Fac"], keep.inputs[0])
    nt.links.new(thr2.outputs[0], keep.inputs[1])
    a = N(nt, "ShaderNodeMath", 500, 1300, operation="MULTIPLY")
    nt.links.new(alpha_src, a.inputs[0])
    nt.links.new(keep.outputs[0], a.inputs[1])
    return a.outputs[0]


def _leafify(mat, hue_var=0.04, val_var=0.18, translucent=0.35, autumn=False):
    nt = mat.node_tree
    p = next((n for n in nt.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled"), None)
    out = next((n for n in nt.nodes if n.bl_idname == "ShaderNodeOutputMaterial"), None)
    if p is None or out is None:
        return
    base = p.inputs["Base Color"]
    if base.links:
        src = base.links[0].from_socket
        oi = N(nt, "ShaderNodeObjectInfo", -700, 600)
        hsv = N(nt, "ShaderNodeHueSaturation", -300, 500)
        mr = N(nt, "ShaderNodeMapRange", -500, 650)
        mr.inputs["To Min"].default_value, mr.inputs["To Max"].default_value = 0.5 - hue_var, 0.5 + hue_var
        nt.links.new(oi.outputs["Random"], mr.inputs["Value"])
        nt.links.new(mr.outputs["Result"], hsv.inputs["Hue"])
        mv = N(nt, "ShaderNodeMapRange", -500, 450)
        mv.inputs["To Min"].default_value, mv.inputs["To Max"].default_value = 1 - val_var, 1 + val_var * 0.5
        nt.links.new(oi.outputs["Random"], mv.inputs["Value"])
        nt.links.new(mv.outputs["Result"], hsv.inputs["Value"])
        nt.links.new(src, hsv.inputs["Color"])
        leaf_col = hsv.outputs["Color"]
        turned = None
        if autumn:
            leaf_col, turned = _autumn(nt, leaf_col, oi)
        nt.links.new(leaf_col, base)
        if turned is not None and p.inputs["Alpha"].links:
            a_src = p.inputs["Alpha"].links[0].from_socket
            nt.links.new(_thin(nt, a_src, turned, oi), p.inputs["Alpha"])
        if translucent > 0 and "bark" not in mat.name and "trunk" not in mat.name:
            tl = N(nt, "ShaderNodeBsdfTranslucent", 0, -400)
            nt.links.new(leaf_col, tl.inputs["Color"])
            surf = out.inputs["Surface"].links[0].from_socket
            mx = N(nt, "ShaderNodeMixShader", 250, -200)
            mx.inputs["Fac"].default_value = translucent
            nt.links.new(surf, mx.inputs[1])
            nt.links.new(tl.outputs[0], mx.inputs[2])
            # keep the cut-out: the translucent part must respect the leaf alpha too
            if p.inputs["Alpha"].links:
                tr = N(nt, "ShaderNodeBsdfTransparent", 250, -400)
                mx2 = N(nt, "ShaderNodeMixShader", 450, -200)
                nt.links.new(p.inputs["Alpha"].links[0].from_socket, mx2.inputs["Fac"])
                nt.links.new(tr.outputs[0], mx2.inputs[1])
                nt.links.new(mx.outputs[0], mx2.inputs[2])
                nt.links.new(mx2.outputs[0], out.inputs["Surface"])
            else:
                nt.links.new(mx.outputs[0], out.inputs["Surface"])


def load_prototypes(keys=None):
    hidden = bpy.data.collections.new("prototypes")
    bpy.context.scene.collection.children.link(hidden)
    vl = bpy.context.view_layer.layer_collection.children["prototypes"]
    vl.exclude = False
    hidden.hide_render = True
    hidden.hide_viewport = True
    for key, (asset, names) in MODELS.items():
        if keys and key not in keys:
            continue
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=str(common.DL / asset / f"{asset}.gltf"))
        new = [o for o in bpy.data.objects if o not in before]
        protos = []
        for o in new:
            for c in list(o.users_collection):
                c.objects.unlink(o)
            if o.type != "MESH":
                bpy.data.objects.remove(o)
                continue
            if o.name.split(".")[0] not in names:
                bpy.data.objects.remove(o)
                continue
            o.parent = None
            me = o.data
            # bake the object transform into the mesh, then put the origin at the trunk base
            me.transform(o.matrix_world)
            o.matrix_world.identity()
            xs = [v.co.x for v in me.vertices]
            ys = [v.co.y for v in me.vertices]
            zs = [v.co.z for v in me.vertices]
            off = Vector(((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, min(zs)))
            from mathutils import Matrix
            me.transform(Matrix.Translation(-off))
            hidden.objects.link(o)
            protos.append(o)
            for m in me.materials:
                if m and not m.get("leafified"):
                    _leafify(m, translucent=0.0 if key == "grass" else 0.3,
                             autumn=key in BROADLEAF and ("lea" in m.name.lower() or "branch" in m.name.lower()))
                    m["leafified"] = True
        PROTO[key] = protos
        print("prototype", key, [(p.name, round(p.dimensions.z, 2), len(p.data.polygons)) for p in protos])
    return PROTO


def scatter(items, col, rng=None):
    """items: (kind, location, rotation z, scale). makes linked duplicates of the prototypes"""
    rng = rng or random.Random(1)
    made = 0
    for kind, loc, rot, sc in items:
        protos = PROTO.get(kind)
        if not protos:
            continue
        src = protos[rng.randrange(len(protos))]
        o = bpy.data.objects.new(kind, src.data)
        o.location = loc
        o.rotation_euler = (0, 0, rot)
        o.scale = (sc, sc, sc * rng.uniform(0.92, 1.08))
        col.objects.link(o)
        made += 1
    return made


def lawn_material():
    m = bpy.data.materials.new("lawn blades")
    try:
        m.use_nodes = True
    except Exception:
        pass
    nt = m.node_tree
    p = nt.nodes.get("Principled BSDF")
    hi = N(nt, "ShaderNodeHairInfo", -900, 300)
    ramp = N(nt, "ShaderNodeValToRGB", -600, 300)
    ramp.color_ramp.elements[0].color = (0.022, 0.045, 0.010, 1)
    ramp.color_ramp.elements[1].color = (0.15, 0.24, 0.05, 1)
    e = ramp.color_ramp.elements.new(0.55)
    e.color = (0.065, 0.12, 0.025, 1)
    nt.links.new(hi.outputs["Intercept"], ramp.inputs["Fac"])
    hsv = N(nt, "ShaderNodeHueSaturation", -300, 300)
    mr = N(nt, "ShaderNodeMapRange", -600, 0)
    mr.inputs["To Min"].default_value, mr.inputs["To Max"].default_value = 0.47, 0.54
    nt.links.new(hi.outputs["Random"], mr.inputs["Value"])
    nt.links.new(mr.outputs["Result"], hsv.inputs["Hue"])
    mv = N(nt, "ShaderNodeMapRange", -600, -200)
    mv.inputs["To Min"].default_value, mv.inputs["To Max"].default_value = 0.75, 1.25
    nt.links.new(hi.outputs["Random"], mv.inputs["Value"])
    nt.links.new(mv.outputs["Result"], hsv.inputs["Value"])
    nt.links.new(ramp.outputs["Color"], hsv.inputs["Color"])
    # patches and mowing stripes, from the blade root position
    tc = N(nt, "ShaderNodeTexCoord", -1200, -500)
    pn = N(nt, "ShaderNodeTexNoise", -900, -500)
    pn.inputs["Scale"].default_value = 0.35
    pn.inputs["Detail"].default_value = 5.0
    nt.links.new(tc.outputs["Object"], pn.inputs["Vector"])
    sep = N(nt, "ShaderNodeSeparateXYZ", -900, -750)
    nt.links.new(tc.outputs["Object"], sep.inputs["Vector"])
    pp = N(nt, "ShaderNodeMath", -700, -750, operation="PINGPONG")
    pp.inputs[1].default_value = 0.55
    nt.links.new(sep.outputs["X"], pp.inputs[0])
    st = N(nt, "ShaderNodeMath", -550, -750, operation="GREATER_THAN")
    st.inputs[1].default_value = 0.275
    nt.links.new(pp.outputs[0], st.inputs[0])
    yel = N(nt, "ShaderNodeMix", -150, 150, data_type="RGBA")
    nt.links.new(hsv.outputs["Color"], yel.inputs["A"])
    yel.inputs["B"].default_value = (0.16, 0.17, 0.05, 1)
    pr = N(nt, "ShaderNodeMapRange", -600, -500)
    pr.inputs["From Min"].default_value, pr.inputs["From Max"].default_value = 0.45, 0.75
    pr.inputs["To Min"].default_value, pr.inputs["To Max"].default_value = 0.0, 0.55
    nt.links.new(pn.outputs["Fac"], pr.inputs["Value"])
    nt.links.new(pr.outputs["Result"], yel.inputs["Factor"])
    br = N(nt, "ShaderNodeMix", 50, 150, data_type="RGBA", blend_type="MULTIPLY")
    nt.links.new(yel.outputs["Result"], br.inputs["A"])
    sm = N(nt, "ShaderNodeMapRange", -350, -750)
    sm.inputs["To Min"].default_value, sm.inputs["To Max"].default_value = 0.82, 1.0
    nt.links.new(st.outputs[0], sm.inputs["Value"])
    cc = N(nt, "ShaderNodeCombineColor", -200, -750)
    for k in ("Red", "Green", "Blue"):
        nt.links.new(sm.outputs["Result"], cc.inputs[k])
    br.inputs["Factor"].default_value = 1.0
    nt.links.new(cc.outputs["Color"], br.inputs["B"])
    nt.links.new(br.outputs["Result"], p.inputs["Base Color"])
    hsv_out = br.outputs["Result"]
    p.inputs["Roughness"].default_value = 0.45
    try:
        p.inputs["Specular IOR Level"].default_value = 0.4
        p.inputs["Subsurface Weight"].default_value = 0.0
    except Exception:
        pass
    out = nt.nodes.get("Material Output")
    tl = N(nt, "ShaderNodeBsdfTranslucent", 0, -300)
    nt.links.new(hsv_out, tl.inputs["Color"])
    mx = N(nt, "ShaderNodeMixShader", 250, 0)
    mx.inputs["Fac"].default_value = 0.2
    nt.links.new(p.outputs[0], mx.inputs[1])
    nt.links.new(tl.outputs[0], mx.inputs[2])
    nt.links.new(mx.outputs[0], out.inputs["Surface"])
    return m


def hair_lawn(name, rects, soil_mat, matrix, density=2200, length=0.075, children=24, col=None):
    """rects in local metres (x0, y0, x1, y1). density = parent hairs per m^2, each with `children` interpolated blades"""
    verts, faces = [], []
    area = 0.0
    for x0, y0, x1, y1 in rects:
        if x1 - x0 < 0.2 or y1 - y0 < 0.2:
            continue
        # subdivide so hair spreads evenly and the soil can follow the ground
        nx, ny = max(1, int((x1 - x0) / 1.0)), max(1, int((y1 - y0) / 1.0))
        base = len(verts)
        for j in range(ny + 1):
            for i in range(nx + 1):
                verts.append((x0 + (x1 - x0) * i / nx, y0 + (y1 - y0) * j / ny, 0.012))
        for j in range(ny):
            for i in range(nx):
                a = base + j * (nx + 1) + i
                faces.append((a, a + 1, a + nx + 2, a + nx + 1))
        area += (x1 - x0) * (y1 - y0)
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    uv = me.uv_layers.new(name="UVMap")
    uv.data.foreach_set("uv", [c for p in me.polygons for li in p.loop_indices for c in verts[me.loops[li].vertex_index][:2]])
    me.materials.append(soil_mat)
    me.materials.append(lawn_material())
    ob = bpy.data.objects.new(name, me)
    ob.matrix_world = matrix
    link(ob, col)
    mod = ob.modifiers.new("grass", "PARTICLE_SYSTEM")
    ps = mod.particle_system
    st = ps.settings
    st.type = "HAIR"
    st.use_advanced_hair = True
    st.normal_factor = length
    st.count = int(area * density)
    st.hair_length = length
    st.emit_from = "FACE"
    st.use_emit_random = True
    st.use_even_distribution = True
    st.material = 2
    st.hair_step = 3
    st.display_step = 2
    st.render_step = 3
    st.child_type = "INTERPOLATED"
    st.child_percent = 2
    st.rendered_child_count = children
    st.child_radius = 0.06
    st.child_roundness = 0.6
    st.child_length = 1.0
    st.child_length_threshold = 0.35
    st.clump_factor = 0.08
    st.roughness_1 = 0.012
    st.roughness_1_size = 1.0
    st.roughness_endpoint = 0.02
    st.roughness_end_shape = 1.0
    st.roughness_2 = 0.01
    st.roughness_2_size = 0.5
    st.factor_random = length * 0.15
    st.use_rotations = True
    st.rotation_factor_random = 0.2
    st.phase_factor_random = 1.0
    st.root_radius = 0.0035 / 0.0035  # scaled by radius_scale below
    st.tip_radius = 0.15
    st.radius_scale = 0.0032
    st.use_close_tip = True
    st.shape = -0.2
    st.hair_length = length  # last: other emission settings rescale it
    print("hair lawn", name, "area", round(area, 1), "m2, parents", st.count, "blades", st.count * children)
    return ob

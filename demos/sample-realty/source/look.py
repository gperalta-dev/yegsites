"""world (HDRI sky with its sun painted out, plus a matching sun lamp), camera, Cycles settings and colour grade"""
import math
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

from common import DL, N, link


HORIZON = [0.8, 0.78, 0.76]


def sky(hdri_8k, hdri_1k, sun_phi_deg, sun_el_deg=None, strength=1.0, sun_mult=1.0, horizon_phi=(-80, 40)):
    """camera rays see the 8k sky, lighting comes from the 1k. the HDRI's own sun is clamped out of both and replaced by
    a sun lamp at the same direction (or at sun_el_deg if given), so shadows are crisp and noise free.
    sun_phi_deg is the map angle toward the sun: 0 east, 90 north, 180 west."""
    scene = bpy.context.scene
    w = bpy.data.worlds.new("sky")
    scene.world = w
    try:
        w.use_nodes = True
    except Exception:
        pass
    nt = w.node_tree
    bg = nt.nodes.get("Background")
    out = nt.nodes.get("World Output")
    info = {}
    imgs = {}
    for key, path in (("hi", hdri_8k), ("lo", hdri_1k)):
        im = bpy.data.images.load(str(path), check_existing=True)
        px = np.empty(im.size[0] * im.size[1] * 4, dtype=np.float32)
        im.pixels.foreach_get(px)
        px = px.reshape(im.size[1], im.size[0], 4)
        lum = px[..., :3] @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
        if key == "lo":
            info["lo_px"] = px
            y, x = np.unravel_index(np.argmax(lum), lum.shape)
            info["u"], info["v"] = (x + 0.5) / im.size[0], (y + 0.5) / im.size[1]  # v from the bottom row
            hot = lum > np.percentile(lum, 99.97)
            info["sun_rgb"] = px[hot][:, :3].mean(0)
        cap = np.percentile(lum, 99.5) * 1.5
        scale = np.minimum(1.0, cap / np.maximum(lum, 1e-6))
        px[..., :3] *= scale[..., None]
        if key == "hi":
            # keep only the sky above the horizon, as a half-float EXR on disk (Cycles loads it as half: 1/4 the memory)
            h = im.size[1]
            top = np.ascontiguousarray(px[h // 2:])
            out_path = Path(bpy.app.tempdir or ".") / "sky_upper_half.exr"
            if hasattr(bpy.app, "tempdir") and not bpy.app.tempdir:
                out_path = Path(str(path)).with_name("sky_upper_half.exr")
            up = bpy.data.images.new("sky upper", im.size[0], h - h // 2, alpha=True, float_buffer=True)
            up.pixels.foreach_set(top.ravel())
            up.filepath_raw = str(out_path)
            up.file_format = "OPEN_EXR"
            sc = bpy.context.scene
            sc.render.image_settings.file_format = "OPEN_EXR"
            sc.render.image_settings.color_depth = "16"
            up.save_render(str(out_path), scene=sc)
            sc.render.image_settings.file_format = "PNG"
            sc.render.image_settings.color_depth = "8"
            bpy.data.images.remove(up)
            bpy.data.images.remove(im)
            im = bpy.data.images.load(str(out_path))
            im.colorspace_settings.name = "Linear Rec.709"
            try:
                im.use_half_precision = True
            except Exception:
                pass
        else:
            im.pixels.foreach_set(px.ravel())
            im.pack()
        imgs[key] = im
    # Blender equirect: u = 0.5 - atan2(y, x) / 2pi, so the image centre looks along +X
    hdri_phi = (0.5 - info["u"]) * 360.0
    hdri_el = (info["v"] - 0.5) * 180.0
    rot = math.radians(hdri_phi - sun_phi_deg)
    # sky colour just above the horizon, averaged over the directions the camera mostly faces (away from the sun)
    lo = info["lo_px"]
    hh, ww = lo.shape[:2]
    cols = []
    for ph in range(int(horizon_phi[0]), int(horizon_phi[1]) + 1, 2):
        u = (0.5 - (math.radians(ph) + rot) / (2 * math.pi)) % 1.0
        for el in (4.0, 5.5, 7.0):
            v = 0.5 + el / 180.0
            cols.append(lo[min(hh - 1, int(v * hh)), min(ww - 1, int(u * ww)), :3])
    meas = np.mean(cols, axis=0) * strength
    lum = float(meas.mean()) * 1.06
    # the measured horizon is a little blue next to the creamy sky the camera sees above it: meet halfway
    HORIZON[:] = [float(0.4 * meas[k] + 0.6 * lum * w) for k, w in enumerate((1.03, 0.98, 0.92))]
    print("horizon colour", tuple(round(c, 3) for c in HORIZON))
    tc = N(nt, "ShaderNodeTexCoord", -1200, 0)
    mp = N(nt, "ShaderNodeMapping", -1000, 0)
    mp.inputs["Rotation"].default_value = (0, 0, rot)
    nt.links.new(tc.outputs["Generated"], mp.inputs["Vector"])
    env = {}
    e = N(nt, "ShaderNodeTexEnvironment", -750, -200)
    e.image = imgs["lo"]
    nt.links.new(mp.outputs["Vector"], e.inputs["Vector"])
    env["lo"] = e
    # equirect uv for the upper-hemisphere image: u = 0.5 - atan2(y, x) / 2pi, v = asin(z) / (pi / 2)
    nrm = N(nt, "ShaderNodeVectorMath", -950, 300, operation="NORMALIZE")
    nt.links.new(mp.outputs["Vector"], nrm.inputs[0])
    sx = N(nt, "ShaderNodeSeparateXYZ", -800, 300)
    nt.links.new(nrm.outputs["Vector"], sx.inputs["Vector"])
    at = N(nt, "ShaderNodeMath", -650, 400, operation="ARCTAN2")
    nt.links.new(sx.outputs["Y"], at.inputs[0])
    nt.links.new(sx.outputs["X"], at.inputs[1])
    uu = N(nt, "ShaderNodeMath", -500, 400, operation="MULTIPLY_ADD")
    nt.links.new(at.outputs[0], uu.inputs[0])
    uu.inputs[1].default_value = -1 / (2 * math.pi)
    uu.inputs[2].default_value = 0.5
    zc = N(nt, "ShaderNodeMath", -650, 250, operation="MAXIMUM")
    nt.links.new(sx.outputs["Z"], zc.inputs[0])
    zc.inputs[1].default_value = 0.0
    asn = N(nt, "ShaderNodeMath", -500, 250, operation="ARCSINE")
    nt.links.new(zc.outputs[0], asn.inputs[0])
    vv = N(nt, "ShaderNodeMath", -350, 250, operation="MULTIPLY")
    nt.links.new(asn.outputs[0], vv.inputs[0])
    vv.inputs[1].default_value = 2 / math.pi * 0.9995
    uv = N(nt, "ShaderNodeCombineXYZ", -200, 300)
    nt.links.new(uu.outputs[0], uv.inputs["X"])
    nt.links.new(vv.outputs[0], uv.inputs["Y"])
    e = N(nt, "ShaderNodeTexImage", -50, 300)
    e.image = imgs["hi"]
    e.interpolation = "Cubic"
    e.extension = "REPEAT"
    nt.links.new(uv.outputs["Vector"], e.inputs["Vector"])
    env["hi"] = e
    lp = N(nt, "ShaderNodeLightPath", -500, 400)
    mix = N(nt, "ShaderNodeMix", -250, 0, data_type="RGBA")
    nt.links.new(lp.outputs["Is Camera Ray"], mix.inputs["Factor"])
    nt.links.new(env["lo"].outputs["Color"], mix.inputs["A"])
    below = N(nt, "ShaderNodeMapRange", 50, 500)
    below.inputs["From Min"].default_value, below.inputs["From Max"].default_value = 0.012, -0.002
    nt.links.new(sx.outputs["Z"], below.inputs["Value"])
    hz = N(nt, "ShaderNodeMix", 200, 350, data_type="RGBA")
    nt.links.new(below.outputs["Result"], hz.inputs["Factor"])
    nt.links.new(env["hi"].outputs["Color"], hz.inputs["A"])
    hz.inputs["B"].default_value = (*HORIZON, 1)
    nt.links.new(hz.outputs["Result"], mix.inputs["B"])
    nt.links.new(mix.outputs["Result"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = strength
    el = sun_el_deg if sun_el_deg is not None else hdri_el
    sun = bpy.data.lights.new("sun", "SUN")
    rgb = info["sun_rgb"] / max(info["sun_rgb"].max(), 1e-6)
    sun.color = tuple(float(c) for c in rgb)
    warm = np.array([1.0, 0.80, 0.56])
    rgb = 0.4 * rgb + 0.6 * warm
    sun.color = tuple(float(c) for c in rgb / rgb.max())
    sun.energy = 5.2 * sun_mult
    sun.angle = math.radians(0.55)
    so = link(bpy.data.objects.new("sun", sun))
    # sun lamp points along its -Z; aim it from the sun direction toward the ground
    ph, e_ = math.radians(sun_phi_deg), math.radians(el)
    d = Vector((math.cos(e_) * math.cos(ph), math.cos(e_) * math.sin(ph), math.sin(e_)))
    so.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    print("hdri sun at phi", round(hdri_phi, 1), "el", round(hdri_el, 1), "-> sun lamp phi", sun_phi_deg, "el", round(el, 1),
          "colour", tuple(round(float(c), 3) for c in rgb))
    return so, d


def phys_sky(sun_phi_deg, sun_el_deg, strength=0.18, sun_energy=4.0, sun_color=(1.0, 0.66, 0.40), haze=(1.08, 0.86, 0.66),
             dust=2.0, sky_el_deg=None):
    """sunset: Blender's physical sky (multiple scattering), so the horizon glows orange toward the sun and fades to rose
    and blue away from it, with no sun disc in it. a sun lamp at the same direction gives the direct light.
    sun_phi_deg is the map angle toward the sun: 0 east, 90 north, 180 west. the sky node's own sun sits at
    90 - rotation, measured with a panorama render."""
    scene = bpy.context.scene
    w = bpy.data.worlds.new("sunset")
    scene.world = w
    try:
        w.use_nodes = True
    except Exception:
        pass
    nt = w.node_tree
    bg = nt.nodes.get("Background")
    s = N(nt, "ShaderNodeTexSky", -400, 0)
    s.sky_type = "MULTIPLE_SCATTERING"
    s.sun_disc = False
    s.sun_elevation = math.radians(sun_el_deg if sky_el_deg is None else sky_el_deg)
    s.sun_rotation = math.radians(90.0 - sun_phi_deg) % (2 * math.pi)
    s.altitude = 670.0
    s.aerosol_density = dust
    # the far ground stops a hair under the true horizon: look up the sky just above it there, so no dark band of
    # below-the-horizon sky shows between the hazy ground and the glow
    tc = N(nt, "ShaderNodeTexCoord", -1100, 0)
    sx = N(nt, "ShaderNodeSeparateXYZ", -900, 0)
    nt.links.new(tc.outputs["Generated"], sx.inputs["Vector"])
    zc = N(nt, "ShaderNodeMath", -750, -100, operation="MAXIMUM")
    nt.links.new(sx.outputs["Z"], zc.inputs[0])
    zc.inputs[1].default_value = 0.004
    cb = N(nt, "ShaderNodeCombineXYZ", -600, 0)
    nt.links.new(sx.outputs["X"], cb.inputs["X"])
    nt.links.new(sx.outputs["Y"], cb.inputs["Y"])
    nt.links.new(zc.outputs[0], cb.inputs["Z"])
    nm = N(nt, "ShaderNodeVectorMath", -500, 0, operation="NORMALIZE")
    nt.links.new(cb.outputs["Vector"], nm.inputs[0])
    nt.links.new(nm.outputs["Vector"], s.inputs["Vector"])
    nt.links.new(s.outputs["Color"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = strength
    HORIZON[:] = list(haze)
    sun = bpy.data.lights.new("sun", "SUN")
    sun.color = sun_color
    sun.energy = sun_energy
    sun.angle = math.radians(0.55)
    so = link(bpy.data.objects.new("sun", sun))
    ph, e_ = math.radians(sun_phi_deg), math.radians(sun_el_deg)
    d = Vector((math.cos(e_) * math.cos(ph), math.cos(e_) * math.sin(ph), math.sin(e_)))
    so.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    print("sunset sky: sun phi", sun_phi_deg, "el", sun_el_deg, "strength", strength, "sun", sun_energy, sun_color)
    return so, d


def horizon_table(res=360):
    """the world's colour just above the horizon all the way round: renders the world alone as a tiny equirectangular
    panorama in a throwaway scene. returns map angles (0 east, 90 north) and linear RGB, in the render's own units"""
    main = bpy.context.scene
    sc = bpy.data.scenes.new("horizon probe")
    sc.world = main.world
    cd = bpy.data.cameras.new("probe")
    cd.type = "PANO"
    try:
        cd.panorama_type = "EQUIRECTANGULAR"
    except Exception:
        cd.cycles.panorama_type = "EQUIRECTANGULAR"
    co = bpy.data.objects.new("probe", cd)
    sc.collection.objects.link(co)
    sc.camera = co
    co.rotation_euler = (math.radians(90), 0, math.radians(-90))  # forward along +X (east), in the middle column
    sc.render.engine = "CYCLES"
    sc.cycles.samples = 16
    sc.cycles.device = "CPU"
    sc.render.resolution_x, sc.render.resolution_y = res, res // 2
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = "OPEN_EXR"
    sc.render.image_settings.color_depth = "32"
    sc.view_settings.view_transform = "Standard"
    path = Path(bpy.app.tempdir or ".") / "horizon_probe.exr"
    sc.render.filepath = str(path)
    bpy.ops.render.render(write_still=True, scene=sc.name)
    im = bpy.data.images.load(str(path))
    px = np.array(im.pixels[:], dtype=np.float32).reshape(res // 2, res, 4)
    row = px[res // 4 + 1, :, :3].copy()  # one row (one degree) above the horizon; rows count from the bottom
    bpy.data.images.remove(im)
    bpy.data.objects.remove(co)
    bpy.data.cameras.remove(cd)
    bpy.data.scenes.remove(sc)
    phis = (res / 2 - (np.arange(res) + 0.5)) / res * 360.0  # left of the middle is counter-clockwise
    return phis, row


def horizon_toward(table, phi_deg, spread=32.0):
    """average horizon colour across the view, centred on the map angle the camera faces"""
    phis, row = table
    d = (phis - phi_deg + 180.0) % 360.0 - 180.0
    w = np.exp(-0.5 * (d / spread) ** 2)
    return (row * w[:, None]).sum(0) / w.sum()


def render_settings(res=(1600, 900), samples=128, threshold=0.015, persistent=True, motion_blur=0.0):
    scene = bpy.context.scene
    r = scene.render
    r.engine = "CYCLES"
    r.resolution_x, r.resolution_y = res
    r.resolution_percentage = 100
    r.image_settings.file_format = "PNG"
    r.image_settings.color_depth = "8"
    r.use_persistent_data = persistent
    r.film_transparent = False
    if motion_blur > 0:
        r.use_motion_blur = True
        r.motion_blur_shutter = motion_blur
    c = scene.cycles
    c.samples = samples
    c.use_adaptive_sampling = True
    c.adaptive_threshold = threshold
    c.adaptive_min_samples = 16
    c.use_denoising = True
    for dn in ("OPTIX", "OPENIMAGEDENOISE"):
        try:
            c.denoiser = dn
            break
        except Exception:
            pass
    try:
        c.denoising_input_passes = "RGB_ALBEDO_NORMAL"
        c.denoising_prefilter = "ACCURATE"
    except Exception:
        pass
    c.max_bounces, c.diffuse_bounces, c.glossy_bounces, c.transmission_bounces, c.transparent_max_bounces = 8, 3, 3, 4, 16
    c.sample_clamp_indirect = 6
    c.caustics_reflective = c.caustics_refractive = False
    c.blur_glossy = 1.0
    try:
        c.use_light_tree = True
    except Exception:
        pass
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
    try:
        c.texture_limit_render = "1024"
    except Exception as e:
        print("texture limit", e)
    vs = scene.view_settings
    try:
        vs.view_transform = "AgX"
        vs.look = "AgX - Medium High Contrast"
    except Exception:
        try:
            vs.view_transform = "Filmic"
            vs.look = "Medium High Contrast"
        except Exception:
            pass
    vs.exposure = 0.45


def grade(start=250.0, length=30000.0, haze_color=(0.86, 0.80, 0.72), near_len=4000.0, near_amt=0.18,
          near_color=(0.9, 0.82, 0.72), bloom=0.08, **_):
    """compositor (Blender 5 node group): aerial perspective from the depth pass, haze = max * (1 - exp(-d / length)),
    applied to land and buildings only (the sky keeps its own colour, so there is no grey band at the horizon), plus a
    soft bloom"""
    scene = bpy.context.scene
    vl = scene.view_layers[0]
    vl.use_pass_z = True
    tree = bpy.data.node_groups.new("grade", "CompositorNodeTree")
    tree.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    scene.compositing_node_group = tree
    out = tree.nodes.new("NodeGroupOutput")
    rl = tree.nodes.new("CompositorNodeRLayers")
    rl.scene = scene
    L = tree.links.new
    depth = rl.outputs.get("Depth") or rl.outputs.get("Z")

    def M(op, a, b=None):
        n = tree.nodes.new("ShaderNodeMath")
        n.operation = op
        for k, x in enumerate((a, b)):
            if x is None:
                continue
            if isinstance(x, (int, float)):
                n.inputs[k].default_value = x
            else:
                L(x, n.inputs[k])
        return n.outputs[0]

    d = M("MAXIMUM", M("SUBTRACT", depth, start), 0.0)
    land = M("LESS_THAN", depth, 200000.0)
    near = M("MULTIPLY", M("MULTIPLY", M("SUBTRACT", 1.0, M("EXPONENT", M("DIVIDE", d, -near_len))), near_amt), land)
    far = M("MULTIPLY", M("SUBTRACT", 1.0, M("EXPONENT", M("DIVIDE", d, -length))), land)
    mix = tree.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    L(near, mix.inputs["Factor"])
    L(rl.outputs["Image"], mix.inputs["A"])
    mix.inputs["B"].default_value = (*near_color, 1)
    mix2 = tree.nodes.new("ShaderNodeMix")
    mix2.name = "far haze"
    mix2.data_type = "RGBA"
    L(far, mix2.inputs["Factor"])
    L(mix.outputs["Result"], mix2.inputs["A"])
    mix2.inputs["B"].default_value = (*haze_color, 1)
    img = mix2.outputs["Result"]
    if bloom > 0:
        g = tree.nodes.new("CompositorNodeGlare")
        g.inputs["Type"].default_value = "Bloom"
        g.inputs["Quality"].default_value = "High"
        g.inputs["Threshold"].default_value = 1.0
        g.inputs["Strength"].default_value = bloom
        g.inputs["Size"].default_value = 0.55
        L(img, g.inputs["Image"])
        img = g.outputs["Image"]
    L(img, out.inputs[0])
    return tree

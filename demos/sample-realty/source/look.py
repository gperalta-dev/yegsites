"""world (HDRI sky with its sun painted out, plus a matching sun lamp), camera, Cycles settings and colour grade"""
import math
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

from common import DL, N, link


def sky(hdri_8k, hdri_1k, sun_phi_deg, sun_el_deg=None, strength=1.0, sun_mult=1.0):
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
    nt.links.new(env["hi"].outputs["Color"], mix.inputs["B"])
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


def grade(mist_start=150.0, mist_depth=6000.0, haze_color=(0.80, 0.78, 0.80), haze=0.55, bloom=0.12, falloff="QUADRATIC"):
    """compositor (Blender 5 node group): distance haze from the mist pass (aerial perspective) and a soft bloom"""
    scene = bpy.context.scene
    vl = scene.view_layers[0]
    vl.use_pass_mist = True
    w = scene.world
    w.mist_settings.start = mist_start
    w.mist_settings.depth = mist_depth
    w.mist_settings.falloff = falloff
    tree = bpy.data.node_groups.new("grade", "CompositorNodeTree")
    tree.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    scene.compositing_node_group = tree
    out = tree.nodes.new("NodeGroupOutput")
    rl = tree.nodes.new("CompositorNodeRLayers")
    rl.scene = scene
    L = tree.links.new
    mul = tree.nodes.new("ShaderNodeMath")
    mul.operation = "MULTIPLY"
    mul.inputs[1].default_value = haze
    L(rl.outputs["Mist"], mul.inputs[0])
    mix = tree.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    L(mul.outputs[0], mix.inputs["Factor"])
    L(rl.outputs["Image"], mix.inputs["A"])
    mix.inputs["B"].default_value = (*haze_color, 1)
    img = mix.outputs["Result"]
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

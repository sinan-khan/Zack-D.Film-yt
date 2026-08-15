#!/usr/bin/env python3
"""Render one scene of a production plan with Blender, fully headless.

Run inside the `blendergrid/blender` container (or any Blender install):

  blender -b --python scripts/render/render_scene.py -- \
      --story content/stories/story-001.json \
      --scene 0 \
      --out output/scenes/scene0.mp4

The script only needs bpy + stdlib, so it runs in the plain Blender
python environment with no extra packages. It is designed to render a
single scene in isolation so GitHub Actions can run scenes in parallel.

Path resolution for animation assets:
  1. scene["animation_file"]   (absolute or repo-relative path)
  2. scene["character_file"]   (character-only FBX, idle pose)
  3. assets/characters/hero.fbx as the default character
  4. assets/animations/{story_id}/scene{id}.fbx as the default clip
"""

import argparse
import json
import os
import sys

try:
    import bpy
    from mathutils import Vector
except ImportError:  # running outside Blender
    bpy = None
    Vector = None


def log(msg):
    print(f"[render] {msg}", flush=True)


def setup_render(scene_ctx, args, cfg):
    sc = bpy.context.scene
    sc.render.engine = args.engine.upper()
    if args.engine.upper() == "CYCLES":
        sc.cycles.samples = cfg.get("samples", 64)
        sc.cycles.device = cfg.get("device", "CPU")
    sc.render.resolution_x = args.resolution_x
    sc.render.resolution_y = args.resolution_y
    sc.render.fps = args.fps
    sc.render.fps_base = 1.0
    sc.render.image_settings.file_format = "FFMPEG"
    sc.render.ffmpeg.format = "MPEG4"
    sc.render.ffmpeg.codec = "H264"
    sc.render.ffmpeg.constant_rate_factor = cfg.get("ffmpeg_crf", "HIGH")
    sc.render.ffmpeg.audio_codec = "NONE"
    sc.render.filepath = args.out
    log(f"engine={sc.render.engine} samples={sc.cycles.samples} "
        f"{args.resolution_x}x{args.resolution_y}@{args.fps}fps")


def clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.render.threads_mode = "AUTO"


def build_world(mood):
    world = bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    tex = nt.nodes.new("ShaderNodeTexSky")
    tex.sky_type = "SINGLE_SCATTERING"  # Blender 5.0 renamed "NISHITA" to this
    tex.sun_elevation = 0.12 if "dusk" in mood or "night" in mood else 0.45
    tex.sun_rotation = -0.6
    if "storm" in mood or "rain" in mood:
        tex.sun_elevation = -0.15
    nt.links.new(tex.outputs["Background"], out.inputs["Background"])


def build_ground():
    bpy.ops.mesh.primitive_plane_add(size=60, location=(0, 0, 0))
    plane = bpy.context.object
    plane.name = "Ground"
    mat = bpy.data.materials.new("GroundMat")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.22, 0.20, 0.18, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.9
    plane.data.materials.append(mat)
    return plane


def build_lights(mood):
    # Key sun light
    sun = bpy.data.objects.new("SunLight", bpy.data.lights.new("SunLight", "SUN"))
    bpy.context.collection.objects.link(sun)
    sun.rotation_euler = (0.7, 0.0, -0.5)
    if "night" in mood or "storm" in mood:
        sun.data.energy = 1.2
        sun.data.angle = 2.0
    elif "dusk" in mood:
        sun.data.energy = 2.5
        sun.data.angle = 1.2
    else:
        sun.data.energy = 3.0
        sun.data.angle = 0.6

    # Soft warm fill light
    fill = bpy.data.objects.new("FillLight", bpy.data.lights.new("FillLight", "AREA"))
    bpy.context.collection.objects.link(fill)
    fill.location = (-6, 6, 5)
    fill.rotation_euler = (0.9, 0.0, 0.9)
    fill.data.energy = 150.0
    fill.data.size = 8.0


def load_fbx(filepath):
    if not os.path.exists(filepath):
        return None
    bpy.ops.import_scene.fbx(filepath=filepath, axis_forward="-Z", axis_up="Y")
    log(f"loaded {filepath}")
    return filepath


def scene_bounds():
    corners = []
    for o in bpy.data.objects:
        if o.type == "MESH":
            corners += [o.matrix_world @ Vector(c) for c in o.bound_box]
    if not corners:
        return None, None
    lo = Vector((min(c.x for c in corners), min(c.y for c in corners), min(c.z for c in corners)))
    hi = Vector((max(c.x for c in corners), max(c.y for c in corners), max(c.z for c in corners)))
    center = (lo + hi) / 2.0
    radius = max((c - center).length for c in corners)
    return center, max(radius, 1.0)


def find_armature():
    for o in bpy.data.objects:
        if o.type == "ARMATURE":
            return o
    return None


def build_placeholder_character(total_frames):
    """A tiny low-poly capsule figure so the pipeline renders something
    even before any FBX character has been added. Includes a gentle sway."""
    root = bpy.data.objects.new("CharacterRoot", None)
    bpy.context.collection.objects.link(root)
    root.location = (0, 0, 0)

    def part(kind, color, **kw):
        getattr(bpy.ops.mesh, f"primitive_{kind}_add")(**kw)
        obj = bpy.context.object
        obj.parent = root
        mat = bpy.data.materials.new(f"Mat_{obj.name}")
        mat.use_nodes = True
        mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = color
        obj.data.materials.append(mat)
        return obj

    part("capsule_add", (0.75, 0.45, 0.28, 1.0), radius=0.32, depth=1.1, location=(0, 0, 1.25))
    part("uv_sphere_add", (0.95, 0.75, 0.55, 1.0), radius=0.30, location=(0, 0, 2.2))
    part("cylinder_add", (0.3, 0.3, 0.35, 1.0), radius=0.11, depth=1.0, location=(-0.14, 0, 0.5))
    part("cylinder_add", (0.3, 0.3, 0.35, 1.0), radius=0.11, depth=1.0, location=(0.14, 0, 0.5))
    part("cylinder_add", (0.5, 0.32, 0.22, 1.0), radius=0.09, depth=0.8, location=(-0.45, 0, 1.5), rotation=(0, 0, 0.12))
    part("cylinder_add", (0.5, 0.32, 0.22, 1.0), radius=0.09, depth=0.8, location=(0.45, 0, 1.5), rotation=(0, 0, -0.12))
    part("uv_sphere_add", (0.05, 0.05, 0.05, 1.0), radius=0.05, location=(-0.11, 0.26, 2.28))
    part("uv_sphere_add", (0.05, 0.05, 0.05, 1.0), radius=0.05, location=(0.11, 0.26, 2.28))

    if total_frames > 2:
        root.rotation_euler = (0, 0, -0.12)
        root.keyframe_insert(data_path="rotation_euler", frame=1)
        root.rotation_euler = (0, 0, 0.12)
        root.keyframe_insert(data_path="rotation_euler", frame=max(2, total_frames // 2))
        root.rotation_euler = (0, 0, -0.12)
        root.keyframe_insert(data_path="rotation_euler", frame=total_frames)

    log("WARNING: no FBX assets found - using procedural placeholder character")
    return root


def animation_frame_range():
    hi = 0
    for o in bpy.data.objects:
        if o.animation_data and o.animation_data.action:
            a, b = o.animation_data.action.frame_range
            hi = max(hi, int(b))
    return hi


def setup_camera():
    center, radius = scene_bounds()
    if center is None:
        log("WARNING: no geometry found, camera uses a fixed angle")
        return

    cam_data = bpy.data.cameras.new("Cam")
    cam_data.lens = 50.0
    cam = bpy.data.objects.new("Cam", cam_data)
    bpy.context.collection.objects.link(cam)
    bpy.context.scene.camera = cam

    target = bpy.data.objects.new("CameraTarget", None)
    bpy.context.collection.objects.link(target)
    target.location = (center.x, center.y, center.z + radius * 0.4)

    direction = Vector((0.9, -0.9, 0.55)).normalized()
    cam.location = target.location + direction * (radius * 3.4)
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()

    tc = cam.constraints.new("TRACK_TO")
    tc.target = target
    tc.track_axis = "TRACK_NEGATIVE_Z"
    tc.up_axis = "UP_Y"
    log(f"camera placed at radius {radius:.2f} tracking scene centre")


def animate_camera(total_frames):
    """Slow push-in + gentle rise so scenes stay alive even if the
    animation clip is shorter than the narration."""
    if total_frames <= 2:
        return
    cam = bpy.context.scene.camera
    if cam is None:
        return
    target = next((o for o in bpy.data.objects if o.name == "CameraTarget"), None)

    cam.keyframe_insert(data_path="location", frame=1)
    if target is not None:
        target.keyframe_insert(data_path="location", frame=1)

    direction = (cam.location - target.location).normalized() if target is not None else Vector((0.9, -0.9, 0.55)).normalized()
    cam.location += direction * 0.6
    cam.location.z += 0.2
    if target is not None:
        target.location.z += 0.4

    cam.keyframe_insert(data_path="location", frame=total_frames)
    if target is not None:
        target.keyframe_insert(data_path="location", frame=total_frames)
    log(f"camera drift over {total_frames} frames")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--story", required=True)
    ap.add_argument("--scene", required=True, type=int)
    ap.add_argument("--out", required=True)
    ap.add_argument("--fps", type=int, default=24)
    ap.add_argument("--resolution-x", type=int, default=1920)
    ap.add_argument("--resolution-y", type=int, default=1080)
    ap.add_argument("--engine", default="CYCLES")
    ap.add_argument("--samples", type=int, default=64)
    ap.add_argument("--max-seconds", type=int, default=30)

    # Blender puts its own CLI (blender -b --python render_scene.py -- ...)
    # into sys.argv untouched, so the script's own args have to be split
    # out manually at the "--" separator.
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else argv[1:]
    args = ap.parse_args(argv)

    if bpy is None:
        sys.exit("[render] bpy is not available - run this inside Blender (see docstring)")

    with open(args.story) as fh:
        story = json.load(fh)
    scene = story["scenes"][args.scene]

    cfg = {"samples": args.samples, "engine": args.engine,
           "ffmpeg_crf": "HIGH", "device": "CPU"}

    clear_scene()
    build_world(scene.get("mood", "neutral"))
    build_ground()
    build_lights(scene.get("mood", "neutral"))

    character_file = scene.get("character_file") or "assets/characters/hero.fbx"
    anim_dir = os.path.join("assets", "animations", story.get("id", "story"))
    animation_file = scene.get("animation_file") or os.path.join(anim_dir, f"scene{scene['id']}.fbx")

    duration = int(scene.get("duration_seconds", 20))
    duration = min(duration, args.max_seconds)
    frame_end = int(duration * args.fps)

    loaded = load_fbx(animation_file)
    if loaded is None:
        loaded = load_fbx(character_file)
    if loaded is None:
        build_placeholder_character(frame_end)

    clip_end = animation_frame_range()
    if clip_end > 1:
        frame_end = min(frame_end, clip_end)
        log(f"clip length = {clip_end} frames, scene capped to {frame_end}")

    setup_camera()
    setup_render(bpy.context.scene, args, cfg)
    bpy.context.scene.frame_start = 1
    bpy.context.scene.frame_end = max(frame_end, 2)
    animate_camera(bpy.context.scene.frame_end)

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    log(f"rendering frames 1..{frame_end} -> {args.out}")
    bpy.ops.render.render(animation=True)
    log("done")


if __name__ == "__main__":
    main()

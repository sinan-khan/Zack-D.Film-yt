#!/usr/bin/env python3
"""Fast headless Blender renderer for one story scene."""
import argparse
import json
import os
import shutil
import subprocess
import sys

try:
    import bpy
    from mathutils import Vector
except ImportError:
    bpy = None
    Vector = None


def log(msg):
    print(f"[render] {msg}", flush=True)


def clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.render.threads_mode = "AUTO"


def build_world(mood):
    world = bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.use_nodes = True
    nodes = world.node_tree.nodes
    links = world.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputWorld")
    bg = nodes.new("ShaderNodeBackground")
    sky = nodes.new("ShaderNodeTexSky")
    try:
        sky.sky_type = "SINGLE_SCATTERING"
    except Exception:
        pass
    sky.sun_elevation = -0.15 if any(x in mood.lower() for x in ("night", "storm", "rain")) else 0.35
    bg.inputs["Strength"].default_value = 0.35
    links.new(sky.outputs["Color"], bg.inputs["Color"])
    links.new(bg.outputs["Background"], out.inputs["Surface"])


def build_ground():
    bpy.ops.mesh.primitive_plane_add(size=60, location=(0, 0, 0))
    plane = bpy.context.object
    mat = bpy.data.materials.new("GroundMat")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (0.18, 0.16, 0.15, 1)
    bsdf.inputs["Roughness"].default_value = 0.9
    plane.data.materials.append(mat)


def build_lights(mood):
    night = any(x in mood.lower() for x in ("night", "storm", "rain"))
    sun_data = bpy.data.lights.new("Sun", "SUN")
    sun = bpy.data.objects.new("Sun", sun_data)
    bpy.context.collection.objects.link(sun)
    sun.rotation_euler = (0.7, -0.3, -0.6)
    sun_data.energy = 1.0 if night else 2.5
    sun_data.angle = 1.0
    fill_data = bpy.data.lights.new("Fill", "AREA")
    fill = bpy.data.objects.new("Fill", fill_data)
    bpy.context.collection.objects.link(fill)
    fill.location = (-5, 4, 5)
    fill_data.energy = 120 if night else 220
    fill_data.size = 6


def load_fbx(path):
    if not path or not os.path.exists(path):
        return False
    try:
        bpy.ops.import_scene.fbx(filepath=path, axis_forward="-Z", axis_up="Y")
        log(f"loaded FBX: {path}")
        return True
    except Exception as exc:
        log(f"WARNING: failed to import {path}: {exc}")
        return False


def build_placeholder(total_frames):
    root = bpy.data.objects.new("CharacterRoot", None)
    bpy.context.collection.objects.link(root)

    def part(kind, location, scale, material_color):
        op = getattr(bpy.ops.mesh, f"primitive_{kind}_add")
        op(location=location)
        obj = bpy.context.object
        obj.scale = scale
        obj.parent = root
        mat = bpy.data.materials.new(f"Mat_{obj.name}")
        mat.diffuse_color = material_color
        obj.data.materials.append(mat)
        return obj

    part("cylinder", (0, 0, 1.2), (0.32, 0.32, 0.65), (0.65, 0.38, 0.22, 1))
    part("uv_sphere", (0, 0, 2.15), (0.30, 0.30, 0.30), (0.9, 0.7, 0.5, 1))
    part("cylinder", (-0.14, 0, 0.45), (0.10, 0.10, 0.5), (0.15, 0.15, 0.18, 1))
    part("cylinder", (0.14, 0, 0.45), (0.10, 0.10, 0.5), (0.15, 0.15, 0.18, 1))
    part("cylinder", (-0.42, 0, 1.45), (0.08, 0.08, 0.4), (0.45, 0.28, 0.18, 1))
    part("cylinder", (0.42, 0, 1.45), (0.08, 0.08, 0.4), (0.45, 0.28, 0.18, 1))
    if total_frames > 2:
        for frame, angle in ((1, -0.08), (total_frames // 2, 0.08), (total_frames, -0.08)):
            root.rotation_euler.z = angle
            root.keyframe_insert(data_path="rotation_euler", frame=frame)
    log("WARNING: no character/animation FBX; using procedural fallback")


def bounds():
    points = []
    for obj in bpy.data.objects:
        if obj.type == "MESH":
            points.extend(obj.matrix_world @ Vector(c) for c in obj.bound_box)
    if not points:
        return Vector((0, 0, 1)), 2.0
    lo = Vector((min(p.x for p in points), min(p.y for p in points), min(p.z for p in points)))
    hi = Vector((max(p.x for p in points), max(p.y for p in points), max(p.z for p in points)))
    center = (lo + hi) / 2
    radius = max((p - center).length for p in points)
    return center, max(radius, 1.0)


def setup_camera(camera_type):
    center, radius = bounds()
    cam_data = bpy.data.cameras.new("Camera")
    cam = bpy.data.objects.new("Camera", cam_data)
    bpy.context.collection.objects.link(cam)
    bpy.context.scene.camera = cam
    target = bpy.data.objects.new("CameraTarget", None)
    bpy.context.collection.objects.link(target)
    target.location = center + Vector((0, 0, radius * 0.15))
    kind = (camera_type or "medium shot").lower()
    if "close" in kind:
        distance, height, lens = radius * 2.0, radius * 0.45, 65
    elif "low" in kind:
        distance, height, lens = radius * 3.0, -radius * 0.15, 50
    elif "over-the-shoulder" in kind:
        distance, height, lens = radius * 2.8, radius * 0.35, 55
    elif "wide" in kind:
        distance, height, lens = radius * 5.0, radius * 0.8, 42
    else:
        distance, height, lens = radius * 3.2, radius * 0.55, 52
    cam_data.lens = lens
    cam.location = target.location + Vector((distance * 0.85, -distance, height))
    cam.rotation_euler = (target.location - cam.location).to_track_quat("-Z", "Y").to_euler()
    constraint = cam.constraints.new("TRACK_TO")
    constraint.target = target
    constraint.track_axis = "TRACK_NEGATIVE_Z"
    constraint.up_axis = "UP_Y"
    return cam, target


def setup_render(args, frame_dir):
    sc = bpy.context.scene
    requested = args.engine.upper()
    candidates = ["BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"] if requested in ("BLENDER_EEVEE_NEXT", "EEVEE_NEXT", "EEVEE") else [requested]
    engine = None
    last_error = None
    for candidate in candidates:
        try:
            sc.render.engine = candidate
            engine = candidate
            break
        except TypeError as exc:
            last_error = exc
    if engine is None:
        raise RuntimeError(f"No compatible Blender render engine for {requested}: {last_error}")
    if engine == "CYCLES":
        sc.cycles.device = "CPU"
        sc.cycles.samples = args.samples
    sc.render.resolution_x = args.resolution_x
    sc.render.resolution_y = args.resolution_y
    sc.render.resolution_percentage = 100
    sc.render.fps = args.fps
    # Fast CI path: JPEG frames drastically reduce disk I/O versus PNG.
    sc.render.image_settings.file_format = "JPEG"
    sc.render.image_settings.quality = 90
    sc.render.filepath = os.path.join(frame_dir, "frame")
    if engine == "BLENDER_EEVEE":
        try:
            sc.eevee.taa_render_samples = args.samples
        except AttributeError:
            pass
    log(f"engine={engine} {args.resolution_x}x{args.resolution_y}@{args.fps}; samples={args.samples}")


def animate_camera(cam, target, total_frames):
    if total_frames < 2:
        return
    cam.keyframe_insert(data_path="location", frame=1)
    target.keyframe_insert(data_path="location", frame=1)
    cam.location = cam.location * 0.94
    target.location.z += 0.15
    cam.keyframe_insert(data_path="location", frame=total_frames)
    target.keyframe_insert(data_path="location", frame=total_frames)


def encode_video(frame_dir, out, fps):
    frames = sorted(name for name in os.listdir(frame_dir) if name.lower().endswith((".jpg", ".jpeg")))
    if not frames:
        raise RuntimeError(f"Blender produced no JPEG frames in {frame_dir}")
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg is required to encode the rendered JPEG sequence")
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-framerate", str(fps),
        "-i", os.path.join(frame_dir, "frame%04d.jpg"),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", out,
    ]
    log(f"encoding {len(frames)} frames to {out}")
    subprocess.run(cmd, check=True)
    if not os.path.exists(out) or os.path.getsize(out) < 100000:
        raise RuntimeError(f"ffmpeg output missing or suspiciously small: {out}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--story", required=True)
    ap.add_argument("--scene", required=True, type=int)
    ap.add_argument("--out", required=True)
    ap.add_argument("--fps", type=int, default=15)
    ap.add_argument("--resolution-x", type=int, default=540)
    ap.add_argument("--resolution-y", type=int, default=960)
    ap.add_argument("--engine", default="BLENDER_EEVEE")
    ap.add_argument("--samples", type=int, default=8)
    ap.add_argument("--max-seconds", type=int, default=90)
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else argv[1:]
    args = ap.parse_args(argv)
    if bpy is None:
        sys.exit("[render] bpy is not available; run inside Blender")
    with open(args.story) as fh:
        story = json.load(fh)
    scene = story["scenes"][args.scene]
    duration = max(1, min(int(scene.get("duration_seconds", 20)), args.max_seconds))
    total_frames = max(2, int(duration * args.fps))
    clear_scene()
    mood = scene.get("mood", "neutral")
    build_world(mood)
    build_ground()
    build_lights(mood)
    anim_dir = os.path.join("assets", "animations", story.get("id", "story"))
    animation_file = scene.get("animation_file") or os.path.join(anim_dir, f"scene{scene['id']}.fbx")
    character_file = scene.get("character_file") or "assets/characters/hero.fbx"
    loaded_animation = load_fbx(animation_file)
    loaded_character = loaded_animation or load_fbx(character_file)
    if not loaded_character:
        build_placeholder(total_frames)
    bpy.context.scene.frame_start = 1
    bpy.context.scene.frame_end = total_frames
    cam, target = setup_camera(scene.get("camera", "medium shot"))
    animate_camera(cam, target, total_frames)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    frame_dir = os.path.join(os.path.dirname(args.out) or ".", f".frames_scene{scene['id']}")
    if os.path.isdir(frame_dir):
        shutil.rmtree(frame_dir)
    os.makedirs(frame_dir, exist_ok=True)
    try:
        setup_render(args, frame_dir)
        log(f"rendering scene {scene['id']} for {duration}s ({total_frames} low-res frames; final upscale happens later)")
        bpy.ops.render.render(animation=True)
        encode_video(frame_dir, args.out, args.fps)
    finally:
        shutil.rmtree(frame_dir, ignore_errors=True)
    log(f"done: {args.out} ({os.path.getsize(args.out)} bytes)")


if __name__ == "__main__":
    main()

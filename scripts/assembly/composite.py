#!/usr/bin/env python3
"""Assemble the final video.

Steps (all via ffmpeg):
  1. For each scene: trim the rendered mp4 to the exact planned length,
     mux in the narration mp3 (with a short lead-in and silence padding),
     and re-encode to a common format so scenes can be concatenated losslessly.
  2. Concatenate all scenes with the concat demuxer.
  3. Optional: loop background music underneath at low volume, plus gentle
     audio/video fade in and out.
  4. Write output/final.mp4.

Usage:
  python scripts/assembly/composite.py --story content/stories/story-001.json \
      --audio output/audio --scenes output/scenes --out output/final.mp4 \
      --config config/settings.yaml
"""

import argparse
import json
import os
import subprocess
import sys

FFMPEG = "ffmpeg"
FFPROBE = "ffprobe"


def load_config(path):
    import yaml
    with open(path) as fh:
        return yaml.safe_load(fh) or {}


def run(cmd):
    print("[composite]", " ".join(cmd))
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        print("[composite] ffmpeg stderr:\n" + (e.stderr or "(empty)"))
        raise


def probe_duration(path):
    out = subprocess.run(
        [FFPROBE, "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", path],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


def has_audio_stream(path):
    out = subprocess.run(
        [FFPROBE, "-v", "error", "-select_streams", "a",
         "-show_entries", "stream=index", "-of", "csv=p=0", path],
        capture_output=True, text=True, check=True,
    )
    return bool(out.stdout.strip())


def build_scene_segment(scene, scenes_dir, audio_dir, seg_dir):
    sid = scene["id"]
    raw = os.path.join(scenes_dir, f"scene{sid}.mp4")
    mp3 = scene.get("mp3") or os.path.join(audio_dir, f"scene{sid}.mp3")
    target = os.path.join(seg_dir, f"seg{sid}.mp4")
    if not os.path.exists(raw):
        sys.exit(f"[composite] missing rendered scene {raw}")
    dur = scene.get("duration_seconds", 20)
    probe_and_log("source scene", raw)

    if os.path.exists(mp3):
        run([
            FFMPEG, "-y",
            "-i", raw, "-i", mp3,
            "-filter_complex",
            f"[1:a]adelay=400|400,apad=whole_dur={dur},aformat=channel_layouts=stereo[na];"
            f"[0:v]fps=24,format=yuv420p,trim=duration={dur},setpts=PTS-STARTPTS[v];"
            f"[na]atrim=duration={dur},asetpts=PTS-STARTPTS[a]",
            "-map", "[v]", "-map", "[a]",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
            "-c:a", "aac", "-b:a", "128k", "-ar", "48000",
            "-movflags", "+faststart", target,
        ])
    else:
        run([
            FFMPEG, "-y",
            "-i", raw,
            "-filter_complex",
            f"[0:v]fps=24,format=yuv420p,trim=duration={dur},setpts=PTS-STARTPTS[v]",
            "-map", "[v]",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
            "-an", target,
        ])
    probe_and_log("built segment", target)
    return target


def probe_and_log(label, path):
    try:
        d = probe_duration(path)
        s = os.path.getsize(path)
        print(f"[composite] {label}: {path} -> {d:.2f}s, {s / 1024:.0f} KB")
        return d
    except Exception as exc:
        print(f"[composite] {label}: {path} -> probe failed: {exc}")
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--story", required=True)
    ap.add_argument("--audio", required=True, help="dir with sceneN.mp3 files")
    ap.add_argument("--scenes", required=True, help="dir with rendered sceneN.mp4 files")
    ap.add_argument("--out", required=True)
    ap.add_argument("--config", default="config/settings.yaml")
    args = ap.parse_args()

    cfg = load_config(args.config)
    with open(args.story) as fh:
        story = json.load(fh)

    seg_dir = os.path.join(os.path.dirname(args.out), "_segments")
    os.makedirs(seg_dir, exist_ok=True)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)

    segs = []
    for scene in sorted(story["scenes"], key=lambda s: s["id"]):
        segs.append(build_scene_segment(scene, args.scenes, args.audio, seg_dir))

    list_file = os.path.join(seg_dir, "concat.txt")
    with open(list_file, "w") as fh:
        for s in segs:
            fh.write(f"file '{os.path.abspath(s)}'\n")

    timeline = os.path.join(os.path.dirname(args.out), "_timeline.mp4")
    run([FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", list_file,
         "-c", "copy", "-movflags", "+faststart", timeline])
    total = probe_and_log("concatenated timeline", timeline)
    if total is None:
        total = 0.0

    expected = sum(float(s.get("duration_seconds", 20)) for s in story["scenes"])
    if total < expected * 0.5:
        sys.exit(
            f"[composite] ERROR: concatenated timeline is {total:.2f}s but "
            f"segments summed to ~{expected:.1f}s - the concat step (-c copy) "
            "silently truncated the output, most likely because the segment "
            "files aren't stream-copy-compatible (mismatched codec params "
            "between scene renders). Re-encoding instead of stream-copying "
            "the concat step is the likely fix."
        )

    fade_out_start = max(0.0, total - 0.8)
    narration = has_audio_stream(timeline)

    music = cfg.get("video", {}).get("music_file", "")
    if music and os.path.exists(music):
        mv = float(cfg.get("video", {}).get("music_volume", 0.12))
        if narration:
            run([
                FFMPEG, "-y",
                "-i", timeline, "-i", music,
                "-filter_complex",
                f"[0:a]afade=t=in:st=0:d=0.3,afade=t=out:st={fade_out_start}:d=0.8[a0];"
                f"[1:a]volume={mv},aloop=loop=-1:size=2e9,atrim=duration={total}[mu];"
                f"[a0][mu]amix=inputs=2:duration=first:normalize=0[aout];"
                f"[0:v]fade=t=in:st=0:d=0.4,fade=t=out:st={fade_out_start}:d=0.8[vout]",
                "-map", "[vout]", "-map", "[aout]",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
                "-c:a", "aac", "-b:a", "128k", args.out,
            ])
        else:
            # no narration track to mix in - music alone carries the audio
            run([
                FFMPEG, "-y",
                "-i", timeline, "-i", music,
                "-filter_complex",
                f"[1:a]volume={mv},aloop=loop=-1:size=2e9,atrim=duration={total},"
                f"afade=t=in:st=0:d=0.3,afade=t=out:st={fade_out_start}:d=0.8[aout];"
                f"[0:v]fade=t=in:st=0:d=0.4,fade=t=out:st={fade_out_start}:d=0.8[vout]",
                "-map", "[vout]", "-map", "[aout]",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
                "-c:a", "aac", "-b:a", "128k", args.out,
            ])
    elif narration:
        run([
            FFMPEG, "-y",
            "-i", timeline,
            "-filter_complex",
            f"[0:a]afade=t=in:st=0:d=0.3,afade=t=out:st={fade_out_start}:d=0.8[aout];"
            f"[0:v]fade=t=in:st=0:d=0.4,fade=t=out:st={fade_out_start}:d=0.8[vout]",
            "-map", "[vout]", "-map", "[aout]",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
            "-c:a", "aac", "-b:a", "128k", args.out,
        ])
    else:
        # no narration, no music - video-only output, no audio stream to map
        run([
            FFMPEG, "-y",
            "-i", timeline,
            "-filter_complex",
            f"[0:v]fade=t=in:st=0:d=0.4,fade=t=out:st={fade_out_start}:d=0.8[vout]",
            "-map", "[vout]",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
            "-an", args.out,
        ])

    out_size = os.path.getsize(args.out) if os.path.exists(args.out) else 0
    print(f"[composite] final video -> {args.out} ({total:.1f}s, {out_size / 1024:.0f} KB)")
    if out_size < 100_000:
        sys.exit(
            f"[composite] ERROR: {args.out} is only {out_size} bytes - ffmpeg "
            "exited cleanly but produced a near-empty file. Not treating this "
            "as success; check the segment/timeline files above for the real "
            "problem instead of letting a broken video reach upload."
        )


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Generate voice-over narration for every scene using edge-tts.

edge-tts is free, needs no API key, and produces natural neural voices
via Microsoft Edge's online voices. After generating each mp3 it
measures the real duration and rewrites the story JSON so the render
and composite steps know exactly how long each scene must be
(narration length + padding from config/settings.yaml).

Usage:
  python scripts/assembly/generate_tts.py --story content/stories/story-001.json \
      --out output/audio --config config/settings.yaml
"""

import argparse
import asyncio
import json
import math
import os
import subprocess
import sys

try:
    import edge_tts
except ImportError:
    edge_tts = None


def load_config(path):
    import yaml
    with open(path) as fh:
        return yaml.safe_load(fh) or {}


def probe_duration(path):
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", path],
            capture_output=True, text=True, timeout=60, check=True,
        )
        return float(out.stdout.strip())
    except Exception:
        return None


def estimate_duration(text):
    return len(text) / 13.0 + 0.6


async def synth(text, voice, rate, out_path):
    comm = edge_tts.Communicate(text, voice=voice, rate=rate)
    await comm.save(out_path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--story", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--config", default="config/settings.yaml")
    args = ap.parse_args()

    if edge_tts is None:
        sys.exit("[tts] edge-tts is not installed (pip install edge-tts)")

    cfg = load_config(args.config)
    tts_cfg = cfg.get("tts", {})
    padding = float(cfg.get("video", {}).get("scene_padding_seconds", 1.5))

    with open(args.story) as fh:
        story = json.load(fh)

    os.makedirs(args.out, exist_ok=True)
    transcript_path = os.path.join(args.out, "transcript.txt")
    with open(transcript_path, "w") as transcript:
        for scene in story["scenes"]:
            mp3 = os.path.join(args.out, f"scene{scene['id']}.mp3")
            asyncio.run(synth(scene["narration"], tts_cfg.get("voice", "en-US-ChristopherNeural"), tts_cfg.get("rate", "+0%"), mp3))
            dur = probe_duration(mp3) or estimate_duration(scene["narration"])
            scene["narration_duration"] = round(dur, 2)
            scene["duration_seconds"] = max(8, int(math.ceil(dur + padding)))
            scene["mp3"] = mp3
            transcript.write(f"[{scene['id']:02d}] {scene['narration']}\n")
            print(f"[tts] scene {scene['id']}: narration={dur:.2f}s -> scene={scene['duration_seconds']}s")

    with open(args.story, "w") as fh:
        json.dump(story, fh, indent=2, ensure_ascii=False)

    print(f"[tts] wrote {len(story['scenes'])} mp3 files into {args.out}")
    print(f"[tts] transcript: {transcript_path}")


if __name__ == "__main__":
    main()

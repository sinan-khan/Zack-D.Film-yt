#!/usr/bin/env python3
"""Pick a Mixamo animation for a scene and download it.

Used by fetch_animations.py (the pipeline) and runnable standalone.

Resolution order:
  1. scene["animation_name"]     explicit clip chosen by the story
  2. catalog keyword match       keywords from animation_prompt + mood
  3. default_animation           fallback

Requires:
  MIXAMO_TOKEN (env) and config/mixamo_animations.yaml -> character_id

Example:
  python scripts/animation/select_mixamo.py --story content/stories/story-001.json --scene 0 \
      --out assets/animations/story-001/scene0.fbx
"""

import argparse
import json
import os
import sys

from download_mixamo import download_animation


def load_catalog(path="config/mixamo_animations.yaml"):
    import yaml
    if not os.path.exists(path):
        return {"character_id": "", "default_animation": "Idle", "catalog": []}
    with open(path) as fh:
        return yaml.safe_load(fh) or {}


def pick_animation(scene, catalog):
    name = scene.get("animation_name")
    if name:
        return name

    text = " ".join(filter(None, [
        scene.get("animation_prompt", ""),
        scene.get("mood", ""),
        scene.get("camera", ""),
    ])).lower()

    for entry in catalog.get("catalog", []):
        if any(kw in text for kw in entry.get("keywords", [])):
            return entry["animation"]
    return catalog.get("default_animation", "Idle")


def fetch_scene_animation(story, scene, out_path, character_id=None, catalog=None):
    catalog = catalog or load_catalog()
    character_id = character_id or catalog.get("character_id", "")
    if not character_id:
        print("[select_mixamo] no character_id configured; skipping mixamo fetch")
        return False
    if not os.environ.get("MIXAMO_TOKEN", ""):
        print("[select_mixamo] MIXAMO_TOKEN not set; skipping mixamo fetch")
        return False

    name = pick_animation(scene, catalog)
    print(f"[select_mixamo] scene {scene['id']}: animation '{name}'")
    download_animation(name, character_id, out_path)
    scene["animation_name"] = name
    scene["animation_source"] = "mixamo"
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--story", required=True)
    ap.add_argument("--scene", required=True, type=int)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    with open(args.story) as fh:
        story = json.load(fh)
    scene = story["scenes"][args.scene]
    ok = fetch_scene_animation(story, scene, args.out)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

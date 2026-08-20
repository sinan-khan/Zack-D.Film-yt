#!/usr/bin/env python3
"""Build a deterministic visual plan from the story JSON.

The renderer consumes this plan so narration, shot timing, camera language,
and asset requirements stay tied to the same scene IDs. No external model is
required; the plan is intentionally deterministic for reproducible CI runs.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

CAMERAS = {
    "wide establishing shot": {"distance": 5.0, "height": 1.0, "lens": 42},
    "medium shot": {"distance": 3.2, "height": 0.55, "lens": 52},
    "close-up": {"distance": 2.0, "height": 0.45, "lens": 65},
    "over-the-shoulder": {"distance": 2.8, "height": 0.35, "lens": 55},
    "low angle": {"distance": 3.0, "height": -0.15, "lens": 50},
}


def shot_text(scene: dict, index: int) -> str:
    narration = scene.get("narration", "").strip()
    words = narration.split()
    if not words:
        return scene.get("animation_prompt", "a character moving naturally")
    chunk = max(1, len(words) // 3)
    start = min(index * chunk, len(words) - 1)
    end = len(words) if index == 2 else min(len(words), start + chunk)
    return " ".join(words[start:end])


def build(scene: dict) -> dict:
    duration = float(scene.get("duration_seconds", 20))
    camera_name = scene.get("camera", "medium shot").lower()
    camera = CAMERAS.get(camera_name, CAMERAS["medium shot"])
    # Three shots keep the visual rhythm readable while preserving the exact
    # scene duration used by TTS and final assembly.
    weights = [0.30, 0.40, 0.30]
    shots = []
    cursor = 0.0
    for i, weight in enumerate(weights):
        length = duration * weight
        shots.append({
            "id": i,
            "start": round(cursor, 3),
            "duration": round(length, 3),
            "camera": camera_name if i == 1 else ("wide establishing shot" if i == 0 else "close-up"),
            "camera_move": ["slow_push_in", "gentle_track", "slow_push_in"][i],
            "narration_anchor": shot_text(scene, i),
            "visual_prompt": scene.get("animation_prompt", "a character moving naturally"),
        })
        cursor += length
    return {
        "scene_id": int(scene.get("id", 0)),
        "duration": duration,
        "mood": scene.get("mood", "neutral studio"),
        "animation_source": scene.get("animation_source", "mixamo"),
        "animation_name": scene.get("animation_name"),
        "character_file": scene.get("character_file", "assets/characters/hero.fbx"),
        "animation_file": scene.get("animation_file"),
        "shots": shots,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--story", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    story = json.loads(Path(args.story).read_text(encoding="utf-8"))
    story["visual_plan_version"] = 1
    story["visual_plan"] = [build(scene) for scene in story["scenes"]]
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(story, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[visual-plan] wrote {args.out} ({len(story['visual_plan'])} scenes)")


if __name__ == "__main__":
    main()

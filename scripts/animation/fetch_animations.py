#!/usr/bin/env python3
"""Fetch animation clips for every scene of a production plan.

This is the single entry point the CI prepare job calls. For each scene
it decides which motion source to use:

  animation_source == "text2motion" and TEXT2MOTION_API_KEY set
      -> Text2Motion API (text prompt -> FBX)
  otherwise MIXAMO_TOKEN + character_id configured
      -> Mixamo library (keyword-mapped clip baked onto your character)
  otherwise
      -> skip; the render step will use the default character or the
         procedural placeholder, so the pipeline never hard-fails.

Files land at staging/animations/{story_id}/scene{id}.fbx, which is the
exact location the render step looks for.

Usage:
  python scripts/animation/fetch_animations.py --story staging/story.json --out staging/animations
"""

import argparse
import json
import os
import sys

from download_mixamo import download_animation
from select_mixamo import fetch_scene_animation, load_catalog
from text2motion import generate as text2motion_generate


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--story", required=True, help="path to the production plan JSON")
    ap.add_argument("--out", required=True, help="directory to write FBX clips into")
    args = ap.parse_args()

    with open(args.story) as fh:
        story = json.load(fh)

    has_text2motion = bool(os.environ.get("TEXT2MOTION_API_KEY", ""))
    catalog = load_catalog()

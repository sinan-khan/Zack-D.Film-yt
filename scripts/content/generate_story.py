#!/usr/bin/env python3
"""Expand a story idea into a scene-by-scene production plan.
 
Two modes:
  1. LLM mode (default if STORY_LLM_API_KEY is set): calls any
     OpenAI-compatible chat-completions API to write the story.
  2. Offline mode (--no-llm or no key): uses a built-in rotating set of
     pre-written micro-stories so the channel runs with zero API keys.
 
Output: a JSON plan consumed by the render/tts/assembly steps.
"""
 
import argparse
import json
import os
import re
import sys
import urllib.request
 
SCHEMA_PROMPT = """You are the head writer for a 3D animated YouTube channel
called "Zack d. Films" that publishes short cinematic stories (45-80 seconds).
 
Turn the story idea into a complete production plan. Return ONLY valid JSON,
no markdown, no commentary. The JSON must match exactly this shape:
 
{
  "title": "Short catchy title",
  "description": "2-3 sentence YouTube description",
  "tags": ["3danimation", "shorts"],
  "narration_style": "warm, gentle, cinematic",
  "scenes": [
    {
      "id": 0,
      "narration": "The exact voice-over line for this scene.",
      "duration_seconds": 20,
      "camera": "wide establishing shot",
      "mood": "sunset over a lighthouse",
      "animation_prompt": "a man walking slowly along a cliff edge",
      "animation_source": "text2motion"
    }
  ]
}
 
Rules:
- 3 scenes per story, each 15-30 seconds, total 60-90 seconds.
- narration must read naturally out loud (voice-over for TTS).
- camera: use one of wide establishing shot / medium shot / close-up / over-the-shoulder / low angle.
- animation_prompt: describe a single continuous humanoid motion for one
  character, present tense, no names, e.g. "a figure standing under a lamp post turning to look up".
- animation_source: "mixamo" when the motion can be matched by a common
  animation clip (walk, run, sit, talk, wave, climb, write, point, look,
  think, etc.), otherwise "text2motion" for novel motions. Optionally add
  "animation_name" with a Mixamo clip name (e.g. "Walking", "Talking").
"""
 
 
def read_config(path):
    if not os.path.exists(path):
        return {}
    try:
        import yaml
    except ImportError:
        return {}
    with open(path) as fh:
        return yaml.safe_load(fh) or {}
 
 
def llm_call(prompt_text):
    key = os.environ.get("STORY_LLM_API_KEY", "").strip()
    if not key:
        return None
    base = os.environ.get("STORY_LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.environ.get("STORY_LLM_MODEL", "gpt-4o-mini")
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SCHEMA_PROMPT},
            {"role": "user", "content": prompt_text},
        ],
        "temperature": 0.9,
    }
    req = urllib.request.Request(
        f"{base}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
        },
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    content = data["choices"][0]["message"]["content"]
    start = content.find("{")
    end = content.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("LLM did not return JSON")
    return json.loads(content[start : end + 1])
 
 
OFFLINE_STORIES = [
    {
        "title": "The Last Lighthouse",
        "description": "One keeper, one light, one stormy night. A short 3D animated story about the quiet promise of keeping the light on.",
        "tags": ["3danimation", "shorts", "story"],
        "narration_style": "warm, gentle, cinematic",
        "scenes": [
            {
                "id": 0,
                "narration": "Every night, Elias climbed the old stone stairs and lit the great lamp. It was the only light for miles, and he never once skipped a step. The ocean stretched out below him like a dark, patient animal, waiting.",
                "duration_seconds": 22,
                "camera": "wide establishing shot",
                "mood": "dusk, ocean, lighthouse",
                "animation_prompt": "a figure climbing wooden stairs, then stopping at a window",
                "animation_name": "Climbing",
                "animation_source": "mixamo",
            },
            {
                "id": 1,
                "narration": "Tonight the storm came in hard, and the lamp flickered in the wind. The glass rattled and the rain hammered the roof, but Elias shielded the flame with both hands and lifted it high. He never once thought of giving up.",
                "duration_seconds": 25,
                "camera": "medium shot",
                "mood": "storm night, warm lamp glow",
                "animation_prompt": "a figure shielding a flame with both hands, then lifting it high",
                "animation_name": "Stretching",
                "animation_source": "mixamo",
            },
            {
                "id": 2,
                "narration": "And somewhere far below, a small boat turned toward home, guided home by a single steady light. Elias watched it slide safely into the harbor, and for the first time that night, he smiled.",
                "duration_seconds": 23,
                "camera": "close-up",
                "mood": "dawn breaking over calm water",
                "animation_prompt": "a figure standing still, looking out at the horizon",
                "animation_name": "Looking Around",
                "animation_source": "mixamo",
            },
        ],
    },
    {
        "title": "The Paper Boat",
        "description": "A rainy window, a folded boat, and a wish carried downstream. A tiny 3D animated story.",
        "tags": ["3danimation", "shorts", "story"],
        "narration_style": "soft, curious, warm",
        "scenes": [
            {
                "id": 0,
                "narration": "Milo folded a paper boat on a rainy afternoon, creasing every edge with the patience of a boy who had nowhere else to be. When he was done, he carried it out to the gutter and set it gently on the water.",
                "duration_seconds": 23,
                "camera": "wide establishing shot",
                "mood": "rainy city street, blue-grey light",
                "animation_prompt": "a figure sitting on a curb, hands folding something carefully",
                "animation_name": "Sitting On Ground",
                "animation_source": "mixamo",
            },
            {
                "id": 1,
                "narration": "The little boat sailed past doors and drains, dodging every current, as if it knew the way. It spun through puddles and slipped under parked cars, and Milo walked beside it, watching the whole world move around a single piece of paper.",
                "duration_seconds": 24,
                "camera": "low angle",
                "mood": "raindrops, reflections, motion",
                "animation_prompt": "a figure walking slowly beside a stream, watching it flow",
                "animation_name": "Walking",
                "animation_source": "mixamo",
            },
            {
                "id": 2,
                "narration": "And when it finally reached the river, Milo let it go. The boat carried his wish all the way to the sea, and he stood there a long time, believing that somewhere out there, it would arrive.",
                "duration_seconds": 23,
                "camera": "close-up",
                "mood": "river mouth, golden light",
                "animation_prompt": "a figure releasing something from an open palm and waving",
                "animation_name": "Waving",
                "animation_source": "mixamo",
            },
        ],
    },
    {
        "title": "The Night Clerk",
        "description": "A 24-hour shop, a night clerk, and one customer who always pays with a story.",
        "tags": ["3danimation", "shorts", "story"],
        "narration_style": "dry, warm, film-noir",
        "scenes": [
            {
                "id": 0,
                "narration": "The shop never closed, and neither did Sam. At midnight, when the street went quiet, the same customer always appeared, the bell above the door ringing like a small alarm clock for his thoughts.",
                "duration_seconds": 23,
                "camera": "medium shot",
                "mood": "late night corner shop, neon glow",
                "animation_prompt": "a figure standing behind a counter, looking up at a door",
                "animation_name": "Leaning On Wall",
                "animation_source": "mixamo",
            },
            {
                "id": 1,
                "narration": "He never bought anything, but he always left something behind. A story about the town, or the weather, or the moon. Sam would lean on the counter and listen, and the hours would slip away like coins from a pocket.",
                "duration_seconds": 25,
                "camera": "over-the-shoulder",
                "mood": "warm shop interior, blue street outside",
                "animation_prompt": "a figure leaning on a counter, talking with open hands",
                "animation_name": "Talking",
                "animation_source": "mixamo",
            },
            {
                "id": 2,
                "narration": "And Sam kept a book of every single one, written in his careful handwriting. Years later, when the shop closed for good, he opened the book and read them all again. This is the last story he ever wrote down.",
                "duration_seconds": 24,
                "camera": "close-up",
                "mood": "dim warm light, dust in the air",
                "animation_prompt": "a figure writing in a small notebook, then closing it gently",
                "animation_name": "Writing",
                "animation_source": "mixamo",
            },
        ],
    },
]
 
 
def offline_story(prompt_text, story_id):
    # Rotate by 12-hour window so each scheduled run (2/day) picks a
    # different template, cycling through all of them. With an LLM key
    # the offline mode is never used anyway.
    import time
    window = int(time.time()) // 43200
    index = window % len(OFFLINE_STORIES)
    story = json.loads(json.dumps(OFFLINE_STORIES[index]))
    story["id"] = story_id
    story["source"] = "offline-template"
    return story
 
 
def validate(plan):
    assert isinstance(plan.get("title"), str) and plan["title"], "missing title"
    assert isinstance(plan.get("scenes"), list) and len(plan["scenes"]) >= 1, "no scenes"
    for scene in plan["scenes"]:
        scene["id"] = int(scene.get("id", 0))
        assert scene.get("narration"), f"scene {scene['id']} missing narration"
        scene.setdefault("duration_seconds", 20)
        scene.setdefault("camera", "medium shot")
        scene.setdefault("mood", "neutral studio")
        scene.setdefault("animation_prompt", "a figure standing and looking at the camera")
        scene.setdefault("animation_source", "mixamo")
    total = sum(s["duration_seconds"] for s in plan["scenes"])
    if total > 240:
        scale = 240.0 / total
        for s in plan["scenes"]:
            s["duration_seconds"] = max(12, int(s["duration_seconds"] * scale))
    return plan
 
 
def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40]
 
 
def main():
    ap = argparse.ArgumentParser(description="Generate a production plan JSON")
    ap.add_argument("--prompt", required=True, help="path to the story idea text file")
    ap.add_argument("--out", required=True, help="output JSON path")
    ap.add_argument("--no-llm", action="store_true", help="force offline template mode")
    args = ap.parse_args()
 
    with open(args.prompt) as fh:
        prompt_text = fh.read().strip()
 
    story_id = os.path.splitext(os.path.basename(args.prompt))[0]
 
    plan = None
    if not args.no_llm:
        try:
            plan = llm_call(prompt_text)
        except Exception as exc:  # pragma: no cover - depends on external API
            print(f"[generate_story] LLM failed ({exc}); using offline template", file=sys.stderr)
            plan = None
 
    if plan is None:
        plan = offline_story(prompt_text, story_id)
 
    plan = validate(plan)
    plan["id"] = story_id
    plan.setdefault("source", "llm")
 
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w") as fh:
        json.dump(plan, fh, indent=2, ensure_ascii=False)
 
    for scene in plan["scenes"]:
        print(f"scene {scene['id']:>2}: {scene['duration_seconds']:>3}s  [{scene['camera']}] {scene['narration']}")
 
    print(f"[generate_story] wrote {args.out} (source={plan.get('source')}, scenes={len(plan['scenes'])})")
 
 
if __name__ == "__main__":
    main()

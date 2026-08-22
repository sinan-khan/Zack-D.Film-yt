#!/usr/bin/env python3
"""Generate a deterministic, scene-by-scene production plan."""
import argparse, hashlib, json, os, re, sys, urllib.request

SCHEMA_PROMPT = """You are the head writer for a 3D animated YouTube channel called Zack d. Films. Return ONLY valid JSON with title, description, tags, narration_style and scenes. Use 3 scenes, 15-30 seconds each. Every scene must be visually distinct and include id, narration, duration_seconds, camera, mood, setting, animation_prompt, animation_source and optionally animation_name. Match the visuals and motion to the narration exactly."""


def llm_call(prompt_text):
    key = os.environ.get("STORY_LLM_API_KEY", "").strip()
    if not key: return None
    base = os.environ.get("STORY_LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.environ.get("STORY_LLM_MODEL", "gpt-4o-mini")
    payload = {"model": model, "messages": [{"role": "system", "content": SCHEMA_PROMPT}, {"role": "user", "content": prompt_text}], "temperature": 0.9}
    req = urllib.request.Request(f"{base}/chat/completions", data=json.dumps(payload).encode(), headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=120) as resp: data = json.loads(resp.read().decode())
    content = data["choices"][0]["message"]["content"]
    a, b = content.find("{"), content.rfind("}")
    if a < 0 or b < 0: raise ValueError("LLM did not return JSON")
    return json.loads(content[a:b + 1])


OFFLINE_STORIES = [
 {"title":"The Last Lighthouse","description":"One keeper, one light, one stormy night.","tags":["3danimation","shorts","story"],"narration_style":"warm cinematic","scenes":[
  {"id":0,"narration":"Every night, the lighthouse keeper climbed the old stone stairs and lit the great lamp. The ocean stretched below him, dark and patient.","duration_seconds":22,"camera":"wide establishing shot","mood":"dusk ocean lighthouse","setting":"stone lighthouse interior and ocean horizon","animation_prompt":"a figure climbing stone stairs and stopping at a lighthouse window","animation_name":"Climbing","animation_source":"mixamo"},
  {"id":1,"narration":"Tonight the storm came hard. Rain struck the glass and the lamp flickered, but he shielded the flame and kept it burning.","duration_seconds":24,"camera":"medium shot","mood":"storm night warm lamp","setting":"lighthouse lantern room during heavy rain","animation_prompt":"a figure shielding a small flame with both hands and lifting it carefully","animation_name":"Stretching","animation_source":"mixamo"},
  {"id":2,"narration":"Far below, a small boat turned toward home, guided by the steady light. The keeper watched it reach the harbor and finally smiled.","duration_seconds":23,"camera":"close-up","mood":"dawn calm harbor","setting":"lighthouse balcony overlooking a harbor","animation_prompt":"a figure standing at a railing and looking toward a distant boat","animation_name":"Looking Around","animation_source":"mixamo"}]},
 {"title":"The Paper Boat","description":"A rainy window, a folded boat, and a wish carried downstream.","tags":["3danimation","shorts","story"],"narration_style":"soft curious warm","scenes":[
  {"id":0,"narration":"Milo folded a paper boat on a rainy afternoon, creasing every edge with patience. He carried it outside and set it gently on flowing gutter water.","duration_seconds":23,"camera":"wide establishing shot","mood":"rainy city street blue grey","setting":"small apartment beside a rain-soaked street","animation_prompt":"a figure sitting on a doorstep folding a paper boat carefully","animation_name":"Sitting On Ground","animation_source":"mixamo"},
  {"id":1,"narration":"The little boat sailed past doors and drains, dodging every current. Milo walked beside it, watching the world move around one tiny piece of paper.","duration_seconds":24,"camera":"low angle","mood":"rain reflections puddles","setting":"rainy street gutter with puddles and parked cars","animation_prompt":"a figure walking slowly beside flowing rainwater while watching a paper boat","animation_name":"Walking","animation_source":"mixamo"},
  {"id":2,"narration":"When it reached the river, Milo let it go. The boat carried his wish toward the sea, and he stood there believing it would arrive.","duration_seconds":23,"camera":"close-up","mood":"river mouth golden light","setting":"riverbank at sunset","animation_prompt":"a figure releasing a small boat from an open palm and waving goodbye","animation_name":"Waving","animation_source":"mixamo"}]},
 {"title":"The Night Clerk","description":"A 24-hour shop, a night clerk, and one customer who always pays with a story.","tags":["3danimation","shorts","story"],"narration_style":"dry warm film noir","scenes":[
  {"id":0,"narration":"The shop never closed, and neither did Sam. At midnight, when the street went quiet, the same customer appeared and the bell rang above the door.","duration_seconds":23,"camera":"medium shot","mood":"late night corner shop neon","setting":"small convenience shop with neon windows","animation_prompt":"a figure standing behind a shop counter and looking up as the door opens","animation_name":"Leaning On Wall","animation_source":"mixamo"},
  {"id":1,"narration":"The customer never bought anything, but always left a story. Sam leaned on the counter and listened while the hours slipped away.","duration_seconds":25,"camera":"over-the-shoulder","mood":"warm shop interior blue street","setting":"shop counter with shelves and rainy neon street outside","animation_prompt":"a figure leaning on a counter and talking with open hand gestures","animation_name":"Talking","animation_source":"mixamo"},
  {"id":2,"narration":"Sam kept every story in a notebook. Years later, when the shop closed, he opened it again and read every page.","duration_seconds":24,"camera":"close-up","mood":"dim warm light dust","setting":"closed shop with an old wooden desk","animation_prompt":"a figure writing in a notebook and then closing it gently","animation_name":"Writing","animation_source":"mixamo"}]}
]


def offline_story(prompt_text, story_id):
    # Prompt content, not wall-clock time, selects the fallback story.
    index = int(hashlib.sha256(prompt_text.encode()).hexdigest()[:8], 16) % len(OFFLINE_STORIES)
    story = json.loads(json.dumps(OFFLINE_STORIES[index]))
    story["id"], story["source"] = story_id, "offline-template"
    return story


def slugify(text): return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40]


def validate(plan):
    assert isinstance(plan.get("title"), str) and plan["title"], "missing title"
    assert isinstance(plan.get("scenes"), list) and plan["scenes"], "no scenes"
    for scene in plan["scenes"]:
        scene["id"] = int(scene.get("id", 0))
        assert scene.get("narration"), f"scene {scene['id']} missing narration"
        scene.setdefault("duration_seconds", 20); scene.setdefault("camera", "medium shot")
        scene.setdefault("mood", "neutral studio"); scene.setdefault("setting", scene["mood"])
        scene.setdefault("animation_prompt", "a figure standing and looking around")
        scene.setdefault("animation_source", "mixamo")
        # Mixamo has no public API, so per-scene motion comes from a fixed
        # library of animations named after Mixamo's own clip names,
        # pre-downloaded once and hosted as GitHub Release assets (see
        # scripts/animation/README - download step in the render job).
        # animation_name -> assets/animations/mixamo/<slug>.fbx
        if scene["animation_source"] == "mixamo" and scene.get("animation_name") and not scene.get("animation_file"):
            scene["animation_file"] = f"assets/animations/mixamo/{slugify(scene['animation_name'])}.fbx"
    total = sum(float(s["duration_seconds"]) for s in plan["scenes"])
    if total > 240:
        scale = 240.0 / total
        for s in plan["scenes"]: s["duration_seconds"] = max(12, int(s["duration_seconds"] * scale))
    return plan


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--prompt", required=True); ap.add_argument("--out", required=True); ap.add_argument("--no-llm", action="store_true"); args = ap.parse_args()
    with open(args.prompt, encoding="utf-8") as fh: prompt_text = fh.read().strip()
    prompt_hash = hashlib.sha1(prompt_text.encode()).hexdigest()[:8]
    story_id = f"{slugify(os.path.splitext(os.path.basename(args.prompt))[0])}-{prompt_hash}"
    plan = None
    if not args.no_llm:
        try: plan = llm_call(prompt_text)
        except Exception as exc: print(f"[generate_story] LLM failed ({exc}); using offline template", file=sys.stderr)
    if plan is None: plan = offline_story(prompt_text, story_id)
    plan = validate(plan); plan["id"] = story_id; plan.setdefault("source", "llm")
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh: json.dump(plan, fh, indent=2, ensure_ascii=False)
    for s in plan["scenes"]: print(f"scene {s['id']}: {s['duration_seconds']}s [{s['camera']}] {s['narration']}")
    print(f"[generate_story] wrote {args.out} (id={story_id}, source={plan.get('source')})")

if __name__ == "__main__": main()

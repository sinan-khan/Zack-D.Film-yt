#!/usr/bin/env python3
"""Build a provider-independent animation manifest from a story plan."""
from __future__ import annotations
import argparse, json, re
from pathlib import Path

COMMON = {"walk":"mixamo","walking":"mixamo","run":"mixamo","running":"mixamo","sit":"mixamo","sitting":"mixamo","wave":"mixamo","waving":"mixamo","talk":"mixamo","talking":"mixamo","write":"mixamo","writing":"mixamo","climb":"mixamo","climbing":"mixamo","point":"mixamo","think":"mixamo","look":"mixamo","looking":"mixamo","idle":"mixamo"}
MOVES = ("slow_push_in", "gentle_track", "slow_pull_out", "static_drift")
CAMERAS = ("wide establishing shot", "medium shot", "close-up", "over-the-shoulder", "low angle")

def words(text): return re.findall(r"\S+", text or "")
def anchor(text, start, end):
    w=words(text)
    if not w: return "visual beat"
    a=round(start*len(w)); b=round(end*len(w)); return " ".join(w[a:max(a+1,b)])
def provider(scene):
    source=str(scene.get("animation_source","" )).lower().strip()
    name=str(scene.get("animation_name",scene.get("animation_prompt",""))).lower()
    if source in {"mixamo","text2motion","procedural","remotion"}: return source
    for key,value in COMMON.items():
        if key in name: return value
    return "text2motion"
def build_scene(scene):
    duration=float(scene.get("duration_seconds",20)); narration=scene.get("narration","").strip(); p=provider(scene); shots=[]; cur=0.0
    weights=(.28,.36,.36)
    for i,weight in enumerate(weights):
        d=round(duration*weight,3); start=sum(weights[:i]); end=start+weight
        shots.append({"shot_id":f"s{int(scene.get('id',0)):02d}-{i:02d}","start_seconds":round(cur,3),"duration_seconds":d,"camera":CAMERAS[(i+int(scene.get('id',0)))%len(CAMERAS)],"camera_move":MOVES[i],"narration_anchor":anchor(narration,start,end),"animation_provider":p,"animation_name":scene.get("animation_name",""),"animation_prompt":scene.get("animation_prompt","natural character movement"),"character_id":scene.get("character_id","hero-v1"),"setting":scene.get("setting",scene.get("mood","neutral environment"))})
        cur+=d
    return {"scene_id":int(scene.get("id",0)),"duration_seconds":duration,"character_id":scene.get("character_id","hero-v1"),"animation_provider":p,"shots":shots}
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--story",required=True); ap.add_argument("--out",required=True); args=ap.parse_args()
    story=json.loads(Path(args.story).read_text(encoding="utf-8")); manifest={"version":1,"story_id":story.get("id",Path(args.story).stem),"character_identity":"hero-v1","narration_locked":True,"regeneration":{"scope":"shot","preserve_character":True,"preserve_audio":True},"scenes":[build_scene(s) for s in story.get("scenes",[])]}
    out=Path(args.out); out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding="utf-8"); print(f"[animation-manifest] wrote {out}")
if __name__=="__main__": main()

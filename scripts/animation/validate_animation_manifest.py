#!/usr/bin/env python3
"""Validate animation manifests before expensive Blender rendering."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--manifest",required=True); args=ap.parse_args(); m=json.loads(Path(args.manifest).read_text(encoding="utf-8")); errors=[]; warnings=[]
    if m.get("version") != 1: warnings.append("unknown animation manifest version")
    if not m.get("character_identity"): errors.append("missing character identity")
    if not m.get("narration_locked"): errors.append("manifest is not narration-locked")
    scenes=m.get("scenes",[])
    if not scenes: errors.append("no scenes")
    seen=set()
    for s in scenes:
        sid=s.get("scene_id")
        if sid in seen: errors.append(f"duplicate scene {sid}")
        seen.add(sid); shots=s.get("shots",[])
        if not shots: errors.append(f"scene {sid}: no shots")
        total=0.0
        for sh in shots:
            q=sh.get("shot_id")
            if q in seen: errors.append(f"duplicate shot {q}")
            seen.add(q); d=float(sh.get("duration_seconds",0))
            if d<=0: errors.append(f"shot {q}: non-positive duration")
            if not sh.get("narration_anchor"): warnings.append(f"shot {q}: empty narration anchor")
            if not sh.get("character_id"): errors.append(f"shot {q}: missing character")
            total+=d
        target=float(s.get("duration_seconds",0))
        if abs(total-target)>0.15: errors.append(f"scene {sid}: shot duration {total:.2f}s != scene {target:.2f}s")
    for e in errors: print(f"ERROR: {e}")
    for w in warnings: print(f"WARNING: {w}")
    if errors: sys.exit(1)
    print(f"[animation-qc] PASS: {len(scenes)} scenes, {sum(len(s.get('shots',[])) for s in scenes)} shots")
if __name__=="__main__": main()

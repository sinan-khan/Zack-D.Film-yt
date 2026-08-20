#!/usr/bin/env python3
"""Create a deterministic, narration-anchored shot plan."""
from __future__ import annotations
import argparse,json
from pathlib import Path
CAMERAS=('wide establishing shot','medium shot','close-up','over-the-shoulder','low angle')
MOVES=('slow_push_in','gentle_track','slow_pull_out','static_drift')
def anchor(text,index,total):
 w=text.split();
 if not w:return 'visual beat'
 a=round(index*len(w)/total); b=round((index+1)*len(w)/total)
 return ' '.join(w[a:max(a+1,b)])
def build(scene):
 d=float(scene.get('duration_seconds',20)); narration=scene.get('narration','').strip(); base=scene.get('animation_prompt','a character moving naturally'); shots=[]; cur=0
 for i,weight in enumerate((.28,.36,.36)):
  length=round(d*weight,3); cam=CAMERAS[(i+scene.get('id',0))%len(CAMERAS)]
  shots.append({'id':i,'start':round(cur,3),'duration':length,'camera':cam,'camera_move':MOVES[i],'narration_anchor':anchor(narration,i,3),'visual_prompt':f'{base}; shot {i+1}; visual action must match narration anchor'})
  cur+=length
 return {'scene_id':int(scene.get('id',0)),'duration':d,'mood':scene.get('mood','neutral'),'setting':scene.get('setting',scene.get('visual_style','neutral environment')),'character_file':scene.get('character_file','assets/characters/hero.fbx'),'animation_file':scene.get('animation_file'),'animation_source':scene.get('animation_source','mixamo'),'shots':shots}
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--story',required=True); ap.add_argument('--out',required=True); args=ap.parse_args(); story=json.loads(Path(args.story).read_text()); story['visual_plan_version']=2; story['visual_plan']=[build(s) for s in story['scenes']]; Path(args.out).parent.mkdir(parents=True,exist_ok=True); Path(args.out).write_text(json.dumps(story,indent=2,ensure_ascii=False)); print(f"[visual-plan] wrote {args.out}")
if __name__=='__main__': main()

#!/usr/bin/env python3
"""Convert narration into semantic visual beats consumed by the renderer."""
from __future__ import annotations
import argparse,json
from pathlib import Path
CAMERAS=['wide establishing shot','medium shot','over-the-shoulder','close-up','low angle']
MOVES=['slow_push_in','gentle_track','slow_pull_out','static_hold','arc_left']
RULES=[('enter',['enter','entered','walked into','opened the door','arrived'],'entering a location'),('walk',['walk','walking','climbed','ran','running','followed'],'moving through the environment'),('look',['look','looked','watch','watched','stared','saw','noticed'],'looking toward an important subject'),('talk',['said','says','spoke','talked','asked','replied'],'speaking or reacting to another person'),('hold',['held','holding','picked up','grabbed','carried','lifted'],'handling an important object'),('write',['write','wrote','writing','notebook','letter','book'],'writing or reading an important object'),('open',['opened','unlock','unlocked','door','lid'],'opening something important'),('react',['smiled','cried','laughed','shocked','afraid','surprised','realized'],'emotional reaction'),('release',['released','dropped','let go','threw','sent'],'releasing or throwing an object')]
def classify(text):
 t=text.lower()
 for k,words,d in RULES:
  if any(w in t for w in words): return k,d
 return 'observe','observing the story environment'
def chunks(words,n):
 size=max(1,(len(words)+n-1)//n); return [' '.join(words[i:i+size]) for i in range(0,len(words),size)][:n]
def build(scene):
 narration=scene.get('narration','').strip(); duration=float(scene.get('duration_seconds',20)); parts=chunks(narration.split(),max(3,min(6,round(duration/5)))) or ['the scene']; shots=[]; cursor=0
 for i,part in enumerate(parts):
  kind,desc=classify(part); length=duration/len(parts)
  shots.append({'id':i,'start':round(cursor,3),'duration':round(length,3),'beat_type':kind,'narration_anchor':part,'visual_prompt':f'{desc}; {scene.get("mood","neutral")}; story-specific cinematic 3D shot based on: {part}','camera':CAMERAS[i%len(CAMERAS)],'camera_move':MOVES[i%len(MOVES)],'required_action':kind,'asset_focus':part}); cursor+=length
 shots[-1]['duration']=round(duration-sum(x['duration'] for x in shots[:-1]),3)
 return {'scene_id':int(scene.get('id',0)),'duration':duration,'mood':scene.get('mood','neutral'),'shots':shots,'character_file':scene.get('character_file','assets/characters/hero.fbx'),'animation_file':scene.get('animation_file')}
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--story',required=True); ap.add_argument('--out',required=True); a=ap.parse_args(); story=json.loads(Path(a.story).read_text()); story['visual_plan_version']=2; story['visual_plan']=[build(s) for s in story['scenes']]; Path(a.out).parent.mkdir(parents=True,exist_ok=True); Path(a.out).write_text(json.dumps(story,indent=2,ensure_ascii=False)); print(f'[visual-plan] v2: {sum(len(x["shots"]) for x in story["visual_plan"])} semantic shots')
if __name__=='__main__': main()

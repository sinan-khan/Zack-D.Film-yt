#!/usr/bin/env python3
"""Generate narration and lock each scene to the real narration duration."""
import argparse, asyncio, json, math, os, subprocess, sys
try: import edge_tts
except ImportError: edge_tts=None

def load_config(path):
 import yaml
 with open(path) as f: return yaml.safe_load(f) or {}
def probe_duration(path):
 try:
  out=subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","default=nw=1:nk=1",path],capture_output=True,text=True,timeout=60,check=True); return float(out.stdout.strip())
 except Exception: return None
async def synth(text,voice,rate,out_path): await edge_tts.Communicate(text,voice=voice,rate=rate).save(out_path)
def main():
 ap=argparse.ArgumentParser(); ap.add_argument("--story",required=True); ap.add_argument("--out",required=True); ap.add_argument("--config",default="config/settings.yaml"); args=ap.parse_args()
 if edge_tts is None: sys.exit("[tts] edge-tts is not installed")
 cfg=load_config(args.config); tts=cfg.get("tts",{}); padding=float(cfg.get("video",{}).get("scene_padding_seconds",1.5)); max_d=float(cfg.get("video",{}).get("max_duration_seconds",90))
 with open(args.story,encoding="utf-8") as f: story=json.load(f)
 os.makedirs(args.out,exist_ok=True); transcript=os.path.join(args.out,"transcript.txt")
 with open(transcript,"w",encoding="utf-8") as tr:
  for scene in story["scenes"]:
   mp3=os.path.join(args.out,f"scene{scene['id']}.mp3"); asyncio.run(synth(scene["narration"],tts.get("voice","en-US-ChristopherNeural"),tts.get("rate","+0%"),mp3)); dur=probe_duration(mp3)
   if not dur: sys.exit(f"[tts] ffprobe could not measure {mp3}; refusing to guess duration")
   scene["narration_duration"]=round(dur,2); scene["duration_seconds"]=max(8,int(math.ceil(dur+padding))); scene["mp3"]=mp3; tr.write(f"[{scene['id']:02d}] {scene['narration']}\n"); print(f"[tts] scene {scene['id']}: narration={dur:.2f}s -> scene={scene['duration_seconds']}s")
 total=sum(float(s["duration_seconds"]) for s in story["scenes"])
 if total > max_d:
  scale=max_d/total
  for s in story["scenes"]: s["duration_seconds"]=max(8,round(s["duration_seconds"]*scale,2))
  print(f"[tts] scaled total scene duration to {sum(s['duration_seconds'] for s in story['scenes']):.2f}s")
 with open(args.story,"w",encoding="utf-8") as f: json.dump(story,f,indent=2,ensure_ascii=False)
 print(f"[tts] wrote {len(story['scenes'])} mp3 files into {args.out}")
if __name__=="__main__": main()

#!/usr/bin/env python3
"""Headless Blender scene renderer with deterministic visual variation."""
import argparse,json,os,shutil,sys,math
try:
 import bpy
 from mathutils import Vector
except ImportError:
 bpy=None; Vector=None

def log(msg): print(f"[render] {msg}",flush=True)
def clear_scene(): bpy.ops.wm.read_factory_settings(use_empty=True); bpy.context.scene.render.threads_mode="AUTO"
def build_world(mood):
 w=bpy.data.worlds.new("World"); bpy.context.scene.world=w; w.use_nodes=True
 n=w.node_tree.nodes; l=w.node_tree.links; n.clear(); out=n.new("ShaderNodeOutputWorld"); bg=n.new("ShaderNodeBackground"); sky=n.new("ShaderNodeTexSky")
 try: sky.sky_type="SINGLE_SCATTERING"
 except Exception: pass
 m=(mood or "").lower(); sky.sun_elevation=-0.15 if any(x in m for x in ("night","storm","rain")) else 0.35; bg.inputs["Strength"].default_value=0.35; l.new(sky.outputs["Color"],bg.inputs["Color"]); l.new(bg.outputs["Background"],out.inputs["Surface"])
def mat(name,color,rough=0.8):
 m=bpy.data.materials.new(name); m.use_nodes=True; b=m.node_tree.nodes.get("Principled BSDF"); b.inputs["Base Color"].default_value=(*color,1); b.inputs["Roughness"].default_value=rough; return m
def build_ground(setting):
 bpy.ops.mesh.primitive_plane_add(size=60,location=(0,0,0)); p=bpy.context.object; p.data.materials.append(mat("Ground",(0.12,0.14,0.17)))
 # A simple setting-dependent landmark prevents every fallback scene from being the same.
 s=(setting or "").lower()
 if "lighthouse" in s:
  bpy.ops.mesh.primitive_cylinder_add(vertices=32,radius=1.8,depth=5,location=(4,2,2.5)); bpy.context.object.data.materials.append(mat("Lighthouse",(0.65,0.65,0.68)))
  bpy.ops.mesh.primitive_cylinder_add(vertices=32,radius=2.1,depth=.35,location=(4,2,5.1)); bpy.context.object.data.materials.append(mat("Lantern",(0.9,0.55,0.12)))
 elif "shop" in s or "street" in s:
  bpy.ops.mesh.primitive_cube_add(location=(4,3,1.8),scale=(3,.8,1.8)); bpy.context.object.data.materials.append(mat("Building",(0.18,0.22,0.28)))
  bpy.ops.mesh.primitive_cube_add(location=(4,2.15,1.8),scale=(1.1,.08,.7)); bpy.context.object.data.materials.append(mat("Window",(0.75,0.45,0.12)))
 elif "river" in s or "rain" in s:
  bpy.ops.mesh.primitive_cube_add(location=(4,3,.05),scale=(5,1.2,.03)); bpy.context.object.data.materials.append(mat("Water",(0.08,0.22,0.32),.2))
def build_lights(mood):
 night=any(x in (mood or "").lower() for x in ("night","storm","rain")); sd=bpy.data.lights.new("Sun","SUN"); so=bpy.data.objects.new("Sun",sd); bpy.context.collection.objects.link(so); so.rotation_euler=(.7,-.3,-.6); sd.energy=1.0 if night else 2.5; sd.angle=1.0
 fd=bpy.data.lights.new("Fill","AREA"); f=bpy.data.objects.new("Fill",fd); bpy.context.collection.objects.link(f); f.location=(-5,4,5); fd.energy=120 if night else 220; fd.size=6
def load_fbx(path):
 if not path or not os.path.exists(path): return False
 try: bpy.ops.import_scene.fbx(filepath=path,axis_forward="-Z",axis_up="Y"); log(f"loaded FBX: {path}"); return True
 except Exception as e: log(f"WARNING: failed to import {path}: {e}"); return False
def build_placeholder(total_frames,scene_id,setting):
 root=bpy.data.objects.new("CharacterRoot",None); bpy.context.collection.objects.link(root)
 def part(kind,loc,scale,color,name):
  getattr(bpy.ops.mesh,f"primitive_{kind}_add")(location=loc); o=bpy.context.object; o.scale=scale; o.parent=root; o.name=name; o.data.materials.append(mat(name+"Mat",color))
 # Slightly different body proportions per scene plus a visible prop.
 k=1.0+0.08*(scene_id%3); part("cylinder",(0,0,1.2),(0.32*k,.32*k,.65),(0.45,.25,.16),"Body"); part("uv_sphere",(0,0,2.15),(.3,.3,.3),(.82,.62,.42),"Head")
 part("cylinder",(-.14,0,.45),(.1,.1,.5),(.1,.1,.12),"LegL"); part("cylinder",(.14,0,.45),(.1,.1,.5),(.1,.1,.12),"LegR"); part("cylinder",(-.42,0,1.45),(.08,.08,.4),(.3,.16,.1),"ArmL"); part("cylinder",(.42,0,1.45),(.08,.08,.4),(.3,.16,.1),"ArmR")
 s=(setting or "").lower()
 if "boat" in s or "river" in s:
  bpy.ops.mesh.primitive_cube_add(location=(1.2,-.2,.18),scale=(.45,.18,.05)); bpy.context.object.data.materials.append(mat("Boat",(.5,.22,.08))); bpy.context.object.parent=root
 elif "shop" in s or "notebook" in s:
  bpy.ops.mesh.primitive_cube_add(location=(.55,-.15,1.0),scale=(.35,.06,.25)); bpy.context.object.data.materials.append(mat("Prop",(.12,.22,.55))); bpy.context.object.parent=root
 elif "lighthouse" in s or "lamp" in s:
  bpy.ops.mesh.primitive_uv_sphere_add(location=(.5,-.1,1.5),segments=16,ring_count=8); bpy.context.object.scale=(.12,.12,.12); bpy.context.object.data.materials.append(mat("Lamp",(1.0,.55,.08))); bpy.context.object.parent=root
 for frame,angle in ((1,-.08),(max(2,total_frames//2),.08),(total_frames,-.08)): root.rotation_euler.z=angle; root.keyframe_insert(data_path="rotation_euler",frame=frame)
 log("WARNING: no animation/character FBX; using deterministic procedural fallback")
def bounds():
 pts=[]
 for o in bpy.data.objects:
  if o.type=="MESH": pts.extend(o.matrix_world@Vector(c) for c in o.bound_box)
 if not pts:return Vector((0,0,1)),2.0
 lo=Vector((min(p.x for p in pts),min(p.y for p in pts),min(p.z for p in pts))); hi=Vector((max(p.x for p in pts),max(p.y for p in pts),max(p.z for p in pts))); c=(lo+hi)/2; return c,max(max((p-c).length for p in pts),1.0)
def setup_camera(kind,scene_id,total):
 c,r=bounds(); cd=bpy.data.cameras.new("Camera"); cam=bpy.data.objects.new("Camera",cd); bpy.context.collection.objects.link(cam); bpy.context.scene.camera=cam; t=bpy.data.objects.new("CameraTarget",None); bpy.context.collection.objects.link(t); t.location=c+Vector((0,0,r*.15)); k=(kind or "medium shot").lower()
 if "close" in k:d,h,l=r*2.0,r*.45,65
 elif "low" in k:d,h,l=r*3.0,-r*.15,50
 elif "over-the-shoulder" in k:d,h,l=r*2.8,r*.35,55
 elif "wide" in k:d,h,l=r*5.0,r*.8,42
 else:d,h,l=r*3.2,r*.55,52
 side=-1 if scene_id%2 else 1; cd.lens=l; cam.location=t.location+Vector((d*.85,side*d*.65,h)); con=cam.constraints.new("TRACK_TO"); con.target=t; con.track_axis="TRACK_NEGATIVE_Z"; con.up_axis="UP_Y"; return cam,t
def setup_render(args,frame_dir):
 sc=bpy.context.scene; req=args.engine.upper(); candidates=["BLENDER_EEVEE","BLENDER_EEVEE_NEXT"] if req in ("BLENDER_EEVEE_NEXT","EEVEE_NEXT","EEVEE") else [req]; err=None
 for e in candidates:
  try: sc.render.engine=e; break
  except TypeError as x: err=x
 else: raise RuntimeError(f"No compatible Blender render engine for {req}: {err}")
 if sc.render.engine=="CYCLES": sc.cycles.device="CPU"; sc.cycles.samples=args.samples
 sc.render.resolution_x=args.resolution_x; sc.render.resolution_y=args.resolution_y; sc.render.resolution_percentage=100; sc.render.fps=args.fps; sc.render.image_settings.file_format="JPEG"; sc.render.image_settings.quality=90; sc.render.filepath=os.path.join(frame_dir,"frame")
 try: sc.eevee.taa_render_samples=args.samples
 except Exception: pass
 log(f"engine={sc.render.engine} {args.resolution_x}x{args.resolution_y}@{args.fps}; samples={args.samples}")
def main():
 ap=argparse.ArgumentParser(); ap.add_argument("--story",required=True); ap.add_argument("--scene",required=True,type=int); ap.add_argument("--out",required=True); ap.add_argument("--fps",type=int,default=15); ap.add_argument("--resolution-x",type=int,default=540); ap.add_argument("--resolution-y",type=int,default=960); ap.add_argument("--engine",default="BLENDER_EEVEE"); ap.add_argument("--samples",type=int,default=8); ap.add_argument("--max-seconds",type=int,default=90); ap.add_argument("--no-encode",action="store_true"); a=sys.argv; a=a[a.index("--")+1:] if "--" in a else a[1:]; args=ap.parse_args(a)
 if bpy is None: sys.exit("[render] bpy is not available; run inside Blender")
 with open(args.story,encoding="utf-8") as f: story=json.load(f)
 scene=story["scenes"][args.scene]; duration=max(1,min(int(scene.get("duration_seconds",20)),args.max_seconds)); total=max(2,int(duration*args.fps)); clear_scene(); build_world(scene.get("mood","")); build_ground(scene.get("setting",scene.get("mood",""))); build_lights(scene.get("mood",""))
 aid=os.path.join("assets","animations",story.get("id","story")); af=scene.get("animation_file") or os.path.join(aid,f"scene{scene['id']}.fbx"); cf=scene.get("character_file") or "assets/characters/hero.fbx"
 loaded=load_fbx(af) or load_fbx(cf)
 if not loaded: build_placeholder(total,scene["id"],scene.get("setting",scene.get("mood","")))
 bpy.context.scene.frame_start=1; bpy.context.scene.frame_end=total; cam,t=setup_camera(scene.get("camera","medium shot"),scene["id"],total); cam.keyframe_insert(data_path="location",frame=1); t.keyframe_insert(data_path="location",frame=1); cam.location=cam.location*.94; t.location.z+=.15; cam.keyframe_insert(data_path="location",frame=total); t.keyframe_insert(data_path="location",frame=total)
 os.makedirs(os.path.dirname(args.out) or ".",exist_ok=True); fd=os.path.join(os.path.dirname(args.out) or ".",f".frames_scene{scene['id']}"); shutil.rmtree(fd,ignore_errors=True); os.makedirs(fd); setup_render(args,fd); log(f"rendering scene {scene['id']} for {duration}s ({total} frames)"); bpy.ops.render.render(animation=True)
 try:
  os.chmod(fd,0o777)
  for name in os.listdir(fd):
   try: os.chmod(os.path.join(fd,name),0o666)
   except OSError: pass
 except OSError as e: log(f"WARNING: could not relax frame permissions: {e}")
 if args.no_encode: log(f"frames ready: {fd}")
 else: raise RuntimeError("Direct encoding is disabled in CI; use --no-encode and host FFmpeg")
if __name__=="__main__": main()

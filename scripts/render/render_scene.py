#!/usr/bin/env python3
"""Render story scenes as distinct semantic visual beats."""
import argparse,json,os,shutil,sys
try:
 import bpy
 from mathutils import Vector
except ImportError: bpy=None; Vector=None

def log(x): print('[render] '+x,flush=True)
def clear(): bpy.ops.wm.read_factory_settings(use_empty=True); bpy.context.scene.render.threads_mode='AUTO'
def mat(name,c,rough=.8):
 m=bpy.data.materials.new(name); m.use_nodes=True; b=m.node_tree.nodes.get('Principled BSDF'); b.inputs['Base Color'].default_value=(*c,1); b.inputs['Roughness'].default_value=rough; return m
def prop(kind,loc,scale,c,name):
 getattr(bpy.ops.mesh,f'primitive_{kind}_add')(location=loc); o=bpy.context.object; o.name=name; o.scale=scale; o.data.materials.append(mat(name+'Mat',c)); return o
def world(mood):
 w=bpy.data.worlds.new('World'); bpy.context.scene.world=w; w.use_nodes=True; n=w.node_tree.nodes; l=w.node_tree.links; n.clear(); out=n.new('ShaderNodeOutputWorld'); bg=n.new('ShaderNodeBackground'); sky=n.new('ShaderNodeTexSky'); sky.sky_type='SINGLE_SCATTERING'; sky.sun_elevation=-.2 if any(k in mood.lower() for k in ('night','storm','rain')) else .35; bg.inputs['Strength'].default_value=.28; l.new(sky.outputs['Color'],bg.inputs['Color']); l.new(bg.outputs['Background'],out.inputs['Surface'])
def environment(scene):
 text=' '.join(str(scene.get(k,'')) for k in ('mood','setting','visual_style','animation_prompt')).lower(); prop('cube',(0,5,3),(8,.2,3),(.08,.1,.13),'Backdrop'); prop('cube',(0,0,-.08),(8,5,.08),(.1,.09,.08),'Floor')
 if any(k in text for k in ('city','street','urban')):
  for i,x in enumerate((-6,-3,3,6)): prop('cube',(x,3,2),(1,1,2),(.15,.17,.2),f'Building{i}')
 if any(k in text for k in ('room','office','house','home','interior')): prop('cube',(-5,1,2.5),(.12,4,2.5),(.12,.13,.15),'Wall'); prop('cube',(0,2.4,1),(2,.4,1),(.24,.2,.14),'Desk')
 if any(k in text for k in ('car','vehicle','truck')): prop('cube',(2,1,.65),(1.5,.7,.35),(.16,.18,.2),'VehicleBody'); prop('cube',(2,1,1.1),(1,.55,.3),(.22,.24,.28),'VehicleCab')
def beat_props(kind,text):
 t=text.lower()
 if kind in ('hold','write'): 
  p=prop('cube',(.45,-.25,1.15),(.38,.5,.06),(.75,.58,.2),'StoryObject'); p.rotation_euler.z=.18
 if kind in ('open','enter'): prop('cube',(2.2,2.6,1.5),(.08,.9,1.5),(.28,.18,.1),'StoryDoor')
 if kind=='release': prop('uv_sphere',(.55,-.1,1.0),(.16,.16,.16),(.8,.8,.8),'ReleasedObject')
 if kind in ('observe','look','react'): prop('cube',(0,3.2,1.6),(1.1,.08,1.1),(.12,.14,.18),'FocusPanel')
 if any(k in t for k in ('boat','ship','ocean','river','water')): prop('cube',(0,2,.15),(3,1.2,.08),(.05,.15,.22),'Water')
def lights(mood):
 night=any(k in mood.lower() for k in ('night','storm','rain')); ld=bpy.data.lights.new('Key','AREA'); lo=bpy.data.objects.new('Key',ld); bpy.context.collection.objects.link(lo); lo.location=(-4,-4,6); ld.energy=160 if night else 360; ld.size=5
def load(path):
 if not path or not os.path.exists(path): return []
 try: bpy.ops.import_scene.fbx(filepath=path,axis_forward='-Z',axis_up='Y'); return list(bpy.context.selected_objects)
 except Exception as e: log(f'FBX import failed: {e}'); return []
def placeholder():
 root=bpy.data.objects.new('CharacterRoot',None); bpy.context.collection.objects.link(root)
 for kind,loc,scale,c in [('cylinder',(0,0,1.2),(.32,.32,.65),(.55,.3,.18)),('uv_sphere',(0,0,2.15),(.3,.3,.3),(.85,.68,.5)),('cylinder',(-.14,0,.45),(.1,.1,.5),(.12,.12,.14)),('cylinder',(.14,0,.45),(.1,.1,.5),(.12,.12,.14))]:
  getattr(bpy.ops.mesh,f'primitive_{kind}_add')(location=loc); o=bpy.context.object; o.scale=scale; o.parent=root; o.data.materials.append(mat('CharacterMat',c))
 return [root]
def bounds():
 pts=[]
 for o in bpy.data.objects:
  if o.type=='MESH': pts += [o.matrix_world@Vector(c) for c in o.bound_box]
 if not pts:return Vector((0,0,1)),2
 lo=Vector((min(p.x for p in pts),min(p.y for p in pts),min(p.z for p in pts))); hi=Vector((max(p.x for p in pts),max(p.y for p in pts),max(p.z for p in pts))); c=(lo+hi)/2; return c,max(max((p-c).length for p in pts),1)
def camera():
 cd=bpy.data.cameras.new('Camera'); cam=bpy.data.objects.new('Camera',cd); bpy.context.collection.objects.link(cam); bpy.context.scene.camera=cam; t=bpy.data.objects.new('CameraTarget',None); bpy.context.collection.objects.link(t); return cam,t
def configure(cam,t,shot,c,r):
 k=(shot.get('camera') or 'medium shot').lower(); d=r*(5 if 'wide' in k else 2 if 'close' in k else 2.8); h=r*(-.15 if 'low' in k else .35 if 'over-the-shoulder' in k else .5); cam.data.lens=42 if 'wide' in k else 65 if 'close' in k else 52; t.location=c+Vector((0,0,r*.12)); cam.location=t.location+Vector((d*.85,-d,h)); return shot.get('camera_move','')
def key(cam,t,s,e,move):
 cam.keyframe_insert(data_path='location',frame=s); t.keyframe_insert(data_path='location',frame=s)
 if 'push' in move: cam.location*=.88
 elif 'pull' in move: cam.location*=1.12
 elif 'track' in move: cam.location.x+=.7
 elif 'arc' in move: cam.location.x+=.45; cam.location.y+=.45
 t.location.x+=.12; cam.keyframe_insert(data_path='location',frame=e); t.keyframe_insert(data_path='location',frame=e)
def setup(a,fd):
 sc=bpy.context.scene; sc.render.engine='BLENDER_EEVEE'; sc.render.resolution_x=a.resolution_x; sc.render.resolution_y=a.resolution_y; sc.render.resolution_percentage=100; sc.render.fps=a.fps; sc.render.image_settings.file_format='JPEG'; sc.render.image_settings.quality=90; sc.render.filepath=os.path.join(fd,'frame')
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--story',required=True); ap.add_argument('--scene',required=True,type=int); ap.add_argument('--out',required=True); ap.add_argument('--fps',type=int,default=15); ap.add_argument('--resolution-x',type=int,default=540); ap.add_argument('--resolution-y',type=int,default=960); ap.add_argument('--engine',default='BLENDER_EEVEE'); ap.add_argument('--samples',type=int,default=8); ap.add_argument('--max-seconds',type=int,default=90); ap.add_argument('--no-encode',action='store_true'); argv=sys.argv; argv=argv[argv.index('--')+1:] if '--' in argv else argv[1:]; a=ap.parse_args(argv)
 if bpy is None: sys.exit('[render] bpy unavailable')
 story=json.load(open(a.story)); scene=story['scenes'][a.scene]; duration=max(1,min(int(scene.get('duration_seconds',20)),a.max_seconds)); total=max(2,int(duration*a.fps)); clear(); world(scene.get('mood','neutral')); environment(scene); lights(scene.get('mood','neutral')); aid=os.path.join('assets','animations',story.get('id','story')); load(scene.get('animation_file') or os.path.join(aid,f"scene{scene['id']}.fbx")) or load(scene.get('character_file') or 'assets/characters/hero.fbx') or placeholder(); c,r=bounds(); cam,t=camera(); plans=[p for p in story.get('visual_plan',[]) if int(p.get('scene_id',-1))==int(scene['id'])]; shots=plans[0].get('shots',[]) if plans else []
 if not shots: shots=[{'start':0,'duration':duration,'beat_type':'observe','camera':scene.get('camera','medium shot'),'camera_move':'slow_push_in','narration_anchor':scene.get('narration','')}]
 for shot in shots:
  start=max(0,float(shot.get('start',0))); end=min(duration,start+float(shot.get('duration',duration))); sf=max(1,int(start*a.fps)+1); ef=max(sf+1,int(end*a.fps)); beat_props(shot.get('beat_type','observe'),shot.get('asset_focus',shot.get('narration_anchor',''))); move=configure(cam,t,shot,c,r); key(cam,t,sf,ef,move); log(f"beat {shot.get('id',0)} {start:.2f}-{end:.2f}s type={shot.get('beat_type')} action={shot.get('required_action')} :: {shot.get('narration_anchor','')[:100]}")
 bpy.context.scene.frame_start=1; bpy.context.scene.frame_end=total; fd=os.path.join(os.path.dirname(a.out) or '.',f'.frames_scene{scene["id"]}'); shutil.rmtree(fd,ignore_errors=True); os.makedirs(fd); setup(a,fd); log(f'rendering scene {scene["id"]}: {len(shots)} semantic beats'); bpy.ops.render.render(animation=True)
 try:
  os.chmod(fd,0o777)
  for n in os.listdir(fd): os.chmod(os.path.join(fd,n),0o666)
 except OSError: pass
 if not a.no_encode: raise RuntimeError('CI requires --no-encode')
if __name__=='__main__': main()

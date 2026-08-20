#!/usr/bin/env python3
"""Deterministic story-driven Blender scene renderer."""
import argparse,json,os,shutil,sys
try:
 import bpy
 from mathutils import Vector
except ImportError:
 bpy=None; Vector=None

def log(msg): print(f"[render] {msg}",flush=True)
def clear_scene(): bpy.ops.wm.read_factory_settings(use_empty=True); bpy.context.scene.render.threads_mode="AUTO"
def mat(name,color,rough=.8):
 m=bpy.data.materials.new(name); m.use_nodes=True; b=m.node_tree.nodes.get('Principled BSDF'); b.inputs['Base Color'].default_value=(*color,1); b.inputs['Roughness'].default_value=rough; return m
def prop(kind,loc,scale,color,name):
 getattr(bpy.ops.mesh,f"primitive_{kind}_add")(location=loc); o=bpy.context.object; o.name=name; o.scale=scale; o.data.materials.append(mat(name+'Mat',color)); return o
def build_world(mood):
 w=bpy.data.worlds.new('World'); bpy.context.scene.world=w; w.use_nodes=True; n=w.node_tree.nodes; l=w.node_tree.links; n.clear(); out=n.new('ShaderNodeOutputWorld'); bg=n.new('ShaderNodeBackground'); sky=n.new('ShaderNodeTexSky'); sky.sky_type='SINGLE_SCATTERING'; sky.sun_elevation=-.18 if any(x in mood.lower() for x in ('night','storm','rain')) else .35; bg.inputs['Strength'].default_value=.3; l.new(sky.outputs['Color'],bg.inputs['Color']); l.new(bg.outputs['Background'],out.inputs['Surface'])
def build_environment(mood,scene):
 s=(scene.get('setting') or scene.get('visual_style') or mood or 'neutral').lower(); prop('cube',(0,5,3),(8,.2,3),(.09,.11,.14),'Backdrop'); prop('cube',(0,0,-.08),(8,5,.08),(.11,.10,.09),'Floor')
 if any(x in s for x in ('street','city','urban')):
  for i,x in enumerate((-6,-3,3,6)): prop('cube',(x,3,2),(1,1,2),(.16,.18,.22),f'Building{i}')
 elif any(x in s for x in ('room','office','interior')):
  prop('cube',(-5,1,2.5),(.12,4,2.5),(.12,.13,.15),'SideWall'); prop('cube',(0,2.5,1),(2,.4,1),(.24,.20,.14),'Desk')
def build_lights(mood):
 night=any(x in mood.lower() for x in ('night','storm','rain')); ld=bpy.data.lights.new('Key','AREA'); lo=bpy.data.objects.new('Key',ld); bpy.context.collection.objects.link(lo); lo.location=(-4,-3,6); ld.energy=180 if night else 350; ld.size=5

def load_fbx(path):
 if not path or not os.path.exists(path): return None
 try: bpy.ops.import_scene.fbx(filepath=path,axis_forward='-Z',axis_up='Y'); log(f'loaded FBX: {path}'); return bpy.context.selected_objects[:]
 except Exception as e: log(f'WARNING: FBX import failed: {e}'); return None
def placeholder():
 root=bpy.data.objects.new('CharacterRoot',None); bpy.context.collection.objects.link(root)
 for kind,loc,scale,c in [('cylinder',(0,0,1.2),(.32,.32,.65),(.55,.30,.18)),('uv_sphere',(0,0,2.15),(.3,.3,.3),(.85,.68,.5)),('cylinder',(-.14,0,.45),(.1,.1,.5),(.12,.12,.14)),('cylinder',(.14,0,.45),(.1,.1,.5),(.12,.12,.14))]:
  getattr(bpy.ops.mesh,f'primitive_{kind}_add')(location=loc); o=bpy.context.object; o.scale=scale; o.parent=root; o.data.materials.append(mat('CharacterMat',c))
 return [root]
def bounds():
 pts=[]
 for o in bpy.data.objects:
  if o.type=='MESH': pts.extend(o.matrix_world@Vector(c) for c in o.bound_box)
 if not pts:return Vector((0,0,1)),2
 lo=Vector((min(p.x for p in pts),min(p.y for p in pts),min(p.z for p in pts))); hi=Vector((max(p.x for p in pts),max(p.y for p in pts),max(p.z for p in pts))); c=(lo+hi)/2; return c,max(max((p-c).length for p in pts),1)
def camera(kind):
 c,r=bounds(); cd=bpy.data.cameras.new('Camera'); cam=bpy.data.objects.new('Camera',cd); bpy.context.collection.objects.link(cam); bpy.context.scene.camera=cam; t=bpy.data.objects.new('CameraTarget',None); bpy.context.collection.objects.link(t); t.location=c+Vector((0,0,r*.15)); k=(kind or 'medium').lower(); d=r*(5 if 'wide' in k else 2.4 if 'close' in k else 3.2); h=r*(.75 if 'low' in k else .45); cd.lens=42 if 'wide' in k else 55; cam.location=t.location+Vector((d*.85,-d,h)); con=cam.constraints.new('TRACK_TO'); con.target=t; con.track_axis='TRACK_NEGATIVE_Z'; con.up_axis='UP_Y'; return cam,t
def animate(cam,t,shot,frames):
 cam.keyframe_insert(data_path='location',frame=1); t.keyframe_insert(data_path='location',frame=1); s=(shot or '').lower(); cam.location*=.91 if any(x in s for x in ('push','close')) else 1.08 if 'wide' in s else 1; cam.location.x+=.3; t.location.x+=.08; cam.keyframe_insert(data_path='location',frame=frames); t.keyframe_insert(data_path='location',frame=frames)
def setup_render(args,fd):
 sc=bpy.context.scene; sc.render.engine='BLENDER_EEVEE' if args.engine.upper()!='CYCLES' else 'BLENDER_EEVEE'; sc.render.resolution_x=args.resolution_x; sc.render.resolution_y=args.resolution_y; sc.render.resolution_percentage=100; sc.render.fps=args.fps; sc.render.image_settings.file_format='JPEG'; sc.render.image_settings.quality=90; sc.render.filepath=os.path.join(fd,'frame')
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--story',required=True); ap.add_argument('--scene',required=True,type=int); ap.add_argument('--out',required=True); ap.add_argument('--fps',type=int,default=15); ap.add_argument('--resolution-x',type=int,default=540); ap.add_argument('--resolution-y',type=int,default=960); ap.add_argument('--engine',default='BLENDER_EEVEE'); ap.add_argument('--samples',type=int,default=8); ap.add_argument('--max-seconds',type=int,default=90); ap.add_argument('--no-encode',action='store_true'); a=sys.argv; a=a[a.index('--')+1:] if '--' in a else a[1:]; args=ap.parse_args(a)
 if bpy is None: sys.exit('[render] bpy unavailable')
 story=json.load(open(args.story)); scene=story['scenes'][args.scene]; duration=max(1,min(int(scene.get('duration_seconds',20)),args.max_seconds)); frames=max(2,int(duration*args.fps)); clear_scene(); mood=scene.get('mood','neutral'); build_world(mood); build_environment(mood,scene); build_lights(mood)
 aid=os.path.join('assets','animations',story.get('id','story')); af=scene.get('animation_file') or os.path.join(aid,f"scene{scene['id']}.fbx"); cf=scene.get('character_file') or 'assets/characters/hero.fbx'; objs=load_fbx(af) or load_fbx(cf) or placeholder()
 cam,t=camera(scene.get('camera','medium shot')); animate(cam,t,scene.get('camera_motion',''),frames); bpy.context.scene.frame_start=1; bpy.context.scene.frame_end=frames
 fd=os.path.join(os.path.dirname(args.out) or '.',f".frames_scene{scene['id']}"); shutil.rmtree(fd,ignore_errors=True); os.makedirs(fd); setup_render(args,fd); log(f"scene={scene['id']} duration={duration}s frames={frames} visual={scene.get('visual_prompt','')[:120]}"); bpy.ops.render.render(animation=True)
 try:
  os.chmod(fd,0o777)
  for n in os.listdir(fd): os.chmod(os.path.join(fd,n),0o666)
 except OSError: pass
 if not args.no_encode: raise RuntimeError('CI requires --no-encode')
if __name__=='__main__': main()

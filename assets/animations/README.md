# Animations

Drop animation/clip FBX files here, or let the pipeline fetch them.

Expected layout used by the render step:
  assets/animations/{story_id}/scene{id}.fbx

The pipeline can fetch these automatically when you configure the keys:
  * Text2Motion (text prompt -> animation): set TEXT2MOTION_API_KEY in
    your GitHub Actions secrets. Files land in the layout above.
  * Mixamo: use scripts/animation/download_mixamo.py with MIXAMO_TOKEN,
    or download clips manually from https://www.mixamo.com and place the
    FBX here.

If a scene has no animation file, the render step uses the default
character from assets/characters/hero.fbx in an idle pose, so the
pipeline never hard-fails on a missing clip.

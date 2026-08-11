# Characters

Drop Mixamo character FBX files here. The render pipeline looks for the
default character at `assets/characters/hero.fbx` when a scene does not
specify its own `character_file`.

Downloading a character from Mixamo (auto-rigged):
  1. Log in at https://www.mixamo.com
  2. Pick a character, select your animation (or "No animation"),
     choose FBX for Unity (.fbx), format: FBX 7.4 binary.
  3. Download and rename it to `hero.fbx`.
  Or automate it with: scripts/animation/download_mixamo.py character

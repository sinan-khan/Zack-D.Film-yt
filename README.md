# Zack d. Films - Automated 3D Short Story Pipeline

A review-first 3D short-story production pipeline. It writes a story, generates narration, creates a narration-locked animation manifest, renders scenes in Blender, assembles the final 1080x1920 video, creates a thumbnail, and can upload the finished video to YouTube as **private**.

```text
story idea
  -> story plan
  -> TTS + real duration lock
  -> animation director / shot manifest
  -> animation QC
  -> Mixamo / Text2Motion / procedural provider
  -> Blender scene render
  -> FFmpeg assembly
  -> thumbnail + final QC
  -> preview artifact (recommended)
  -> private YouTube upload
```

## Recommended first run: Preview only

Use **Actions -> Preview Video - No YouTube Upload -> Run workflow**.

This workflow builds the complete video and uploads it as a downloadable GitHub Actions artifact. It does **not** call the YouTube API. Watch the resulting `output/final.mp4` before enabling regular production uploads.

The preview also publishes `animation_manifest.json`, so you can inspect exactly what the animation director planned for every shot.

## Production workflow

`Daily Short Production` keeps the existing two scheduled production slots and manual trigger. The production workflow uploads the final video using the repository's configured YouTube privacy status; the default is `private` so you can review it in YouTube Studio before making it public.

## Animation providers

- **Mixamo**: preferred for common humanoid motions such as walking, running, sitting, talking, waving, climbing and writing. Mixamo has no official public API; automated downloading is optional and should be used only if permitted by its current terms.
- **Text2Motion**: fallback for novel humanoid movements when `TEXT2MOTION_API_KEY` is configured. Free-tier attribution is included in the channel description configuration.
- **Procedural**: renderer fallback when no FBX asset is available. This keeps the pipeline runnable without animation API keys, but a real character FBX is strongly recommended for production quality.
- **Remotion**: reserved as a future motion-graphics provider for titles, overlays and 2D animated elements.

## Character setup

For the best Blender output, add a rigged humanoid FBX at:

`assets/characters/hero.fbx`

The pipeline uses a stable logical character identity (`hero-v1`) across the animation manifest so future shot-level regeneration can preserve character consistency.

## Required / optional secrets

Required only for the features you use:

- `STORY_LLM_API_KEY` — optional; offline stories work without it.
- `STORY_LLM_BASE_URL` / `STORY_LLM_MODEL` — optional OpenAI-compatible endpoint settings.
- `TEXT2MOTION_API_KEY` — optional; needed for Text2Motion generation.
- `MIXAMO_TOKEN` — optional; only for the Mixamo downloader.
- `YOUTUBE_CLIENT_SECRET_JSON` and `YOUTUBE_TOKEN_JSON` — needed only for YouTube upload.

Narration uses `edge-tts`, so it does not require a TTS API key.

## Local checks

```bash
pip install -r requirements.txt
bash scripts/check_local.sh
```

The local check runs offline story generation, builds and validates the animation manifest, compiles Python files, and validates workflow YAML without requiring Blender, API keys, or YouTube credentials.

## Important quality note

The pipeline is intentionally **review-first**. A successful render only proves that the technical pipeline completed; it does not guarantee cinematic quality. Always watch the preview artifact first. If the character, animation, scene composition or narration synchronization is poor, fix/regenerate before publishing.

# Zack d. Films - Automated 3D Short Story Pipeline

A free, fully-automated pipeline that writes, animates, renders, narrates,
and uploads short 3D animated stories to YouTube every day - using only
free tiers: GitHub Actions (public repo), Blender in Docker, edge-tts,
and the YouTube Data API.

```
story idea -> AI/offline story plan -> narration (TTS)
   -> AI animation (Text2Motion/Mixamo) -> Blender render per scene (parallel)
   -> ffmpeg composite + thumbnail -> YouTube upload
```

## The honest bottom line

| Piece | Free tier | Real limits |
|-------|-----------|-------------|
| GitHub Actions | Unlimited minutes for **public** repos | 2000 min/mo if private; no free larger runners |
| Blender | Free, open source | Runs in Docker (`blendergrid/blender`), CPU only |
| Text2Motion | Free tier, CC BY 4.0 | Attribution required in description; API may change |
| Mixamo | Free library | No official API; automate at your own ToS risk |
| edge-tts (narration) | Free, no key | Needs internet; voice model is fixed per config |
| YouTube Data API | 10,000 units/day | `videos.insert` = 1600 units, so ~6/day max |
| Story writing | Optional LLM key | Offline templates work with zero keys |

## Quick start

1. **Clone & make public.** This repo must be public to keep renders free.
2. **Add your Blender character** -> `assets/characters/hero.fbx`
   (a placeholder figure is used automatically until you add one).
3. **YouTube credentials** (one time):
   - Enable YouTube Data API v3 in Google Cloud, download OAuth desktop JSON.
   - Run `python scripts/upload/oauth_setup.py --client-secret secrets/client_secret.json`
   - base64-encode both JSON files and add them as repo secrets
     `YOUTUBE_CLIENT_SECRET_JSON` and `YOUTUBE_TOKEN_JSON`.
4. **Optional keys** as repo secrets: `STORY_LLM_API_KEY` (better stories),
   `TEXT2MOTION_API_KEY` (AI animations), `MIXAMO_TOKEN`.
5. **Trigger a run.** Go to the Actions tab -> *Daily Short Production* ->
   *Run workflow*. Watch it produce a video and upload it (private by
   default; flip to public when you are ready).

## Layout

```
.github/workflows/   daily.yml (production) + test.yml (CI)
scripts/
  content/generate_story.py    story plan (LLM or offline templates)
  animation/text2motion.py     text -> animation FBX
  animation/download_mixamo.py optional Mixamo downloader
  render/render_scene.py       Blender headless per-scene render
  assembly/generate_tts.py     narration + exact scene timings
  assembly/composite.py        ffmpeg assembly, music, fades
  assembly/thumbnail.py        auto thumbnail from title
  upload/oauth_setup.py        one-time YouTube OAuth token
  upload/upload_youtube.py     upload video + thumbnail
config/settings.yaml           channel, timing, quality
content/prompts/               drop story ideas here
assets/                        characters / animations / music
docs/PIPELINE_GUIDE.md         full step-by-step walkthrough
```

## Local development

```bash
pip install -r requirements.txt
bash scripts/check_local.sh          # fast, no Blender/keys needed
act -W .github/workflows/test.yml    # run CI locally
```

## Privacy defaults

Videos upload as **private** (`config/settings.yaml` ->
`youtube.privacy_status`). Review the first few in your YouTube Studio
before switching to `unlisted` or `public`.

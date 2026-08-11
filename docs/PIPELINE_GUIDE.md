# Zack d. Films - The Complete Step-by-Step Guide

This is the word-by-word guide to the whole system. It covers:

1. What the original "free pipeline" chat got right and wrong
2. What you are building (the 5 stages)
3. Every file in the repo and what it does
4. One-time setup, step by step
5. What happens during one automated run (job by job)
6. How to test locally without burning minutes
7. Going live and growing the channel
8. Troubleshooting

---

## 1. Checking the chat you pasted (the honest analysis)

Your chat with the other AI is mostly correct. Here is the accurate version,
because a few numbers were wrong.

**GitHub Actions - correct, with nuance**
- Public repos: unlimited free minutes and 500 MB of artifact storage. True.
  There is no credit-card requirement for free Actions - the "credit card on
  file" claim is wrong.
- One thing it missed: free accounts get at most **5 concurrent jobs**, so the
  pipeline renders scenes in parallel but never more than a handful at once.
- Private repos: 2000 minutes/month. Renders take 5-30 min each, so keep the
  repo public, as the chat said.

**Blender in Docker - correct**
- `blendergrid/blender` pulls in seconds and runs Blender headlessly. The
  chat's suggestion is exactly what this repo does.

**Text2Motion - correct**
- Free tier exists, animations are CC BY 4.0, and attribution must appear in
  the video description. This pipeline **adds that attribution automatically**
  when a scene uses Text2Motion.

**Mixamo - correct with a big asterisk**
- The library is free, but there is **no official public API**. The chat's
  suggestion (grab a token from your browser) works but technically violates
  Mixamo's terms. Do it for your own convenience at your own risk, or just
  download the few clips you need in the browser. Both paths are documented.

**BlenderKit - half true**
- 50%+ of assets are free, but downloading them requires logging in, which is
  awkward to automate headlessly. This pipeline does **not** depend on
  BlenderKit. You can still grab free materials/models and drop them into your
  Blender scene files later if you want richer sets.

**YouTube Data API - the chat got the price wrong**
- `videos.insert` costs **1600** quota units, not ~100. Even so, at 1-2 uploads
  per day you use 1600-3200 of the 10,000 daily units. You are fine.
- `search.list` costs **100 units per call** (that's why the chat said ~100
  searches/day). `videos.list` costs 1 unit.

**The biggest thing the chat missed: narration**
- A "short story" needs a voice-over. None of the tools in your chat produce
  speech. This pipeline adds **edge-tts** - free, no key, natural neural
  voices from Microsoft Edge - so every story is narrated automatically.

**What the chat got right overall**
- The full stack can be built with zero monthly cost, and your specific plan
  (2 uploads/day on a public repo) stays inside every free tier.

---

## 2. What you are building (the 5 stages)

```
Stage 1  Content     story idea  ->  scene-by-scene plan JSON
Stage 2  Assets      text prompt -> animation FBX  (Text2Motion/Mixamo)
Stage 3  Render      FBX + plan  -> one mp4 per scene (Blender, parallel)
Stage 4  Assembly    scenes + narration -> final.mp4 + thumbnail.jpg
Stage 5  Publish     final.mp4  ->  private video on YouTube
```

Every stage is a plain Python script that can also run on your laptop. The
GitHub Actions workflow just runs them in the right order, in parallel where
possible, every day on a schedule.

---

## 3. Every file, what it does, and why

### Configuration

| File | Purpose |
|------|---------|
| `config/settings.yaml` | Channel name, YouTube category & privacy, fps, resolution, TTS voice, music volume, render quality, attribution text. Everything you might want to tune lives here. |
| `.env.example` | Copy to `.env` for local runs. Lists every optional key. Real values go into GitHub secrets for CI. |
| `requirements.txt` | Python packages for all stages except render (render only needs Blender). |

### Stage 1 - Content (`scripts/content/`)

| File | Purpose |
|------|---------|
| `generate_story.py` | Reads a story idea from `content/prompts/*.txt`. If `STORY_LLM_API_KEY` is set it asks any OpenAI-compatible API to write a 3-scene plan. Without a key it rotates built-in templates, so the channel runs even at zero keys. Outputs `story.json` with title, description, tags, and one object per scene (narration text, camera, mood, animation prompt). |
| `content/prompts/story-001.txt` | Your story idea file. Edit it any time - each run picks one `.txt` from the folder. |

### Stage 2 - Animation assets (`scripts/animation/`)

| File | Purpose |
|------|---------|
| `text2motion.py` | Sends the scene's animation prompt to Text2Motion, polls the job, downloads an FBX clip. Output lands at `assets/animations/{story_id}/scene{id}.fbx` which is exactly where the render step looks. |
| `download_mixamo.py` | Optional. Downloads a Mixamo character or animation given your `v7` cookie token. Used only if you choose to automate Mixamo. |

### Stage 3 - Render (`scripts/render/`)

| File | Purpose |
|------|---------|
| `render_scene.py` | The only Blender-dependent script. Renders **one scene** to an mp4: builds a sky + ground + lights based on the scene's mood, imports the character FBX (and its embedded animation), frames the character with a tracking camera, and renders H.264 frames at your chosen resolution/fps. If no FBX exists it builds a procedural placeholder figure so the pipeline never hard-fails. |

### Stage 4 - Assembly (`scripts/assembly/`)

| File | Purpose |
|------|---------|
| `generate_tts.py` | Speaks each scene's narration with edge-tts, measures the real mp3 length, and **rewrites `story.json`** so every scene is exactly "narration + padding" seconds. This is what keeps voice and picture in sync. |
| `composite.py` | For each scene: trims the render to the planned length, muxes the narration mp3 (400 ms lead-in, silence to fill), re-encodes scenes to a common format, concatenates them, loops optional background music at low volume, adds fades, and writes `final.mp4`. |
| `thumbnail.py` | Grabs a mid-video frame and overlays the story title on a gradient bar. Writes `thumbnail.jpg`. |

### Stage 5 - Publish (`scripts/upload/`)

| File | Purpose |
|------|---------|
| `oauth_setup.py` | One-time helper you run **on your own machine**. Opens a browser, you approve, and it saves `secrets/token.json` (your refresh token). |
| `upload_youtube.py` | Reads the credentials, uploads `final.mp4` via the resumable API (1600 units), sets title/description/tags/category/privacy, appends the CC BY 4.0 attribution when Text2Motion was used, and sets the thumbnail. |

### Orchestration (`.github/workflows/`)

| File | Purpose |
|------|---------|
| `daily.yml` | The production pipeline. 5 jobs: `prepare` -> `render` (matrix, one job per scene) -> `assemble` -> `upload`. Runs on a schedule (twice daily) plus manual trigger and a webhook event. |
| `test.yml` | CI. Runs on every push: syntax-checks every script, generates an offline story, validates the schema, checks the YAML. This is the workflow you run with `act`. |

### Supporting

| File | Purpose |
|------|---------|
| `assets/characters/hero.fbx` | Your main character. The render step uses it for every scene that has no specific animation clip. |
| `assets/animations/{story}/scene{id}.fbx` | Per-scene animation clips (fetched automatically when keys are set). |
| `assets/music/` | Drop a royalty-free track here and set `video.music_file` to enable background music. |
| `scripts/check_local.sh` | Fast local sanity check (no Blender/keys). |
| `output/` | Where every stage writes results. Gitignored. |
| `secrets/` | Local OAuth files. Gitignored. |
| `docs/PIPELINE_GUIDE.md` | This document. |

---

## 4. One-time setup, step by step

### Step 4.1 - Make the repository public

1. Create a GitHub repo (e.g. `zackd-films`) and push this code to it.
2. Keep it **public**. This is what makes the renders free and unlimited.

### Step 4.2 - Add a character (once)

The pipeline can run with zero assets (placeholder figure), but for a real
channel you want a proper character:

1. Go to https://www.mixamo.com and log in.
2. In **Characters**, pick one (e.g. "Y Bot" or "Enkof"). It is already
   auto-rigged.
3. Choose format **FBX for Unity (.fbx)**, **FBX 7.4 binary**.
4. Pick an animation in the dropdown or choose "No animation" first.
5. Download and save it as `assets/characters/hero.fbx` in the repo.
6. Commit and push.

### Step 4.3 - YouTube credentials (the only fiddly part)

You need two JSON files. Do this once, on your own computer.

1. Go to https://console.cloud.google.com and create a project.
2. Go to **APIs & Services -> Library**, search **YouTube Data API v3**, enable it.
3. Go to **APIs & Services -> OAuth consent screen**:
   - User type: **External**, app name "Zack d. Films", your email.
   - Under **Test users**, add your own Gmail.
4. Go to **APIs & Services -> Credentials -> Create credentials ->
   OAuth client ID**:
   - Application type: **Desktop app**.
   - Download the JSON. Save it as `secrets/client_secret.json`.
5. Install Python deps and get the refresh token:

   ```bash
   pip install -r requirements.txt
   python scripts/upload/oauth_setup.py --client-secret secrets/client_secret.json
   ```

   A browser opens. Log in as your channel account and approve. A file
   `secrets/token.json` is created.

6. Encode both files to base64 (this is how they travel to CI safely):

   ```bash
   base64 -w0 secrets/client_secret.json
   base64 -w0 secrets/token.json
   ```

7. In GitHub: **Settings -> Secrets and variables -> Actions -> New
   repository secret**:
   - `YOUTUBE_CLIENT_SECRET_JSON` = output of the first base64 command
   - `YOUTUBE_TOKEN_JSON` = output of the second

### Step 4.4 - Optional keys (each makes the channel better)

| Secret | What it adds | Where to get it |
|--------|--------------|-----------------|
| `STORY_LLM_API_KEY` | Original stories instead of rotating templates | Any OpenAI-compatible API; set `STORY_LLM_BASE_URL` / `STORY_LLM_MODEL` too |
| `TEXT2MOTION_API_KEY` | Real AI animation per scene | https://text2motion.cc free tier |
| `MIXAMO_TOKEN` | Automate Mixamo downloads | Your `v7` cookie from mixamo.com (see script docstring) |

None are required. The pipeline degrades gracefully without them.

### Step 4.5 - Set your channel identity

Edit `config/settings.yaml`:
- `channel.name` -> "Zack d. Films"
- `youtube.privacy_status` -> keep `private` for now
- `video.fps` / `resolution` -> 24 fps / 1920x1080
- `tts.voice` -> try a few voices, e.g. `en-US-ChristopherNeural`,
  `en-US-AriaNeural`, `en-GB-RyanNeural`

---

## 5. What happens during one automated run

Trigger the workflow (Actions tab -> *Daily Short Production* -> Run
workflow, or let the schedule fire). Job by job:

### Job `prepare` (writes the story, narrates it, fetches animations)

1. `checkout` clones the repo.
2. Python deps install.
3. It picks the first `content/prompts/*.txt` as today's idea.
4. `generate_story.py` writes `staging/story.json`. With an LLM key you get
   a fresh story; without one it rotates the 3 built-in templates every
   12 hours so repeated runs never produce the same video.
5. `generate_tts.py` speaks every narration line into
   `staging/audio/scene*.mp3` and rewrites the plan with exact timings.
6. If `TEXT2MOTION_API_KEY` is set, each scene's animation prompt becomes an
   FBX file in `staging/animations/{story_id}/scene{id}.fbx`.
7. It publishes two things for the next jobs: the list of scene ids (used to
   build the render matrix) and an artifact called `story-assets`
   (the plan + audio + animations).

### Job `render` (runs once per scene, in parallel)

This is a **matrix** job: GitHub starts one copy per scene, up to your
concurrency limit.

1. Restores the plan and animation files.
2. Runs Blender inside Docker:

   ```bash
   docker run --rm -v "$PWD:/work" -w /work \
     --entrypoint blender blendergrid/blender:latest \
     -b --python scripts/render/render_scene.py -- \
     --story content/stories/{story_id}.json \
     --scene {N} --out output/scenes/scene{N}.mp4 --fps 24
   ```

3. The script builds sky/ground/lights from the scene mood, imports the
   character (and its animation clip), frames it with a tracking camera,
   and renders H.264.
4. Each rendered `scene{N}.mp4` is uploaded as its own artifact.

Rendering scenes in parallel is the single biggest time-saver: a 60-90 second
video at 1080p on CPU can take 10-40 minutes per scene, and parallel jobs
overlap that.

### Job `assemble` (joins everything into one video)

1. Downloads the story plan, the audio, and **all** scene artifacts.
2. `composite.py` trims each scene to its planned length, muxes the
   narration, concatenates the scenes, loops optional music underneath,
   and fades in/out. Result: `output/final.mp4`.
3. `thumbnail.py` extracts a frame and overlays the title.
4. The final package (video + thumbnail + plan JSON) is uploaded as the
   `final` artifact.

### Job `upload` (publishes to YouTube)

1. Decodes `YOUTUBE_CLIENT_SECRET_JSON` and `YOUTUBE_TOKEN_JSON` from
   secrets into local files.
2. `upload_youtube.py` calls `videos.insert` (1600 units):
   - Title, description, tags from the story plan
   - Category and privacy from `config/settings.yaml`
   - CC BY 4.0 attribution appended automatically when Text2Motion was used
   - Thumbnail attached via `thumbnails.set`
3. Prints the video id and watch URL into the run log.

Because `privacy_status` is `private`, nothing goes live until you say so.

### Total cost of one run

- GitHub minutes: unlimited (public repo).
- YouTube quota: 1600 units of 10,000 per day.
- Text2Motion/LLM: 0 if no keys configured.
- Money spent: **$0.00**.

---

## 6. Testing locally (without burning cloud minutes)

Two levels of local testing.

### Level 1 - Fast sanity check (no Blender, no keys)

```bash
pip install -r requirements.txt
bash scripts/check_local.sh
```

This runs: Python syntax check on every script, an offline story
generation, a schema validation, and a YAML check of both workflows.

### Level 2 - The full CI workflow with `act`

Install `act` (https://github.com/nektos/act) then:

```bash
act -W .github/workflows/test.yml
```

This runs the same `test.yml` CI locally, so you can iterate on code without
ever spending a cloud minute.

### Level 3 - Assemble a real video on your laptop

If you have Blender + ffmpeg installed locally you can run the entire chain:

```bash
# 1. story plan (offline)
python3 scripts/content/generate_story.py --prompt content/prompts/story-001.txt \
  --out content/stories/story-001.json --no-llm

# 2. narration + timings
python3 scripts/assembly/generate_tts.py --story content/stories/story-001.json \
  --out output/audio

# 3. render each scene (Blender installed locally, replace 0 with 1, 2, ...)
mkdir -p output/scenes
blender -b --python scripts/render/render_scene.py -- \
  --story content/stories/story-001.json --scene 0 --out output/scenes/scene0.mp4 --fps 24

# 4. composite + thumbnail
python3 scripts/assembly/composite.py --story content/stories/story-001.json \
  --audio output/audio --scenes output/scenes --out output/final.mp4
python3 scripts/assembly/thumbnail.py --video output/final.mp4 \
  --story content/stories/story-001.json --out output/thumbnail.jpg

# 5. inspect
ffprobe output/final.mp4
```

---

## 7. Going live and growing the channel

1. **First uploads.** Let the pipeline run a few times with `private`.
   Open YouTube Studio and watch the first videos: check narration sync,
   framing, lighting. Iterate on `config/settings.yaml` and the render
   script until you are happy.
2. **Flip to public.** Set `youtube.privacy_status: "unlisted"` or
   `"public"`. Unlisted is a good middle step while you build a back-catalog.
3. **Better stories.** Add an `STORY_LLM_API_KEY`. The LLM writes a fresh
   3-scene story every run and sets real `animation_prompt`s, so animations
   match the narration instead of the template poses.
4. **Richer animation.** The templates all use `animation_source:
   text2motion`. Once you have Text2Motion working, experiment with more
   expressive prompts. For clips Text2Motion can't do, download Mixamo
   animations and drop them at `assets/animations/{story_id}/scene{id}.fbx`
   with `"animation_source": "assets"`.
5. **Music.** Add a royalty-free track as `assets/music/ambient.mp3` and set
   `video.music_file`. This lifts perceived quality a lot.
6. **Shorts vs long-form.** The default plan targets 60-90 seconds (Shorts
   territory). For long-form, edit the story prompt to ask for 6-8 scenes of
   30-45s and the render matrix will simply scale up (renders take longer,
   but public-repo minutes are free).
7. **Thumbnails.** The auto thumbnail overlays the title on a real frame.
   As you grow, you can replace `thumbnail.py` with something fancier or
   use YouTube's manual upload.
8. **Attribution.** Keep the CC BY 4.0 line for Text2Motion in the
   description - it is legally required by their free tier and the pipeline
   adds it automatically.

---

## 8. Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Upload job fails with "invalid_grant" | Refresh token expired/revoked | Re-run `oauth_setup.py`, re-add the `YOUTUBE_TOKEN_JSON` secret |
| Upload job: quota exceeded | Too many uploads / API calls in one day | At most 1-2 uploads/day on free quota |
| Render job fails with "no geometry" | The story.json wasn't restored into `content/stories/` | Check the "Restore plan" step; artifact names must match |
| Render uses placeholder figure | No FBX at the expected path | Add `assets/characters/hero.fbx` or configure `TEXT2MOTION_API_KEY` |
| Text2Motion step skipped | Secret not set | Add `TEXT2MOTION_API_KEY` to repo secrets |
| "no character found, camera fixed angle" | Empty scene in render | Look at the Blender log; check FBX axis settings in `load_fbx` |
| Scenes out of sync with narration | TTS step didn't run / durations stale | Re-run `generate_tts.py`; it rewrites durations in the plan |
| `videos.insert` says the video is invalid | Resolution/bitrate not acceptable | Check `config` resolution; re-encode with ffmpeg |
| GitHub shows 5 concurrent jobs max | Free-tier concurrency limit | Normal; scenes queue and finish in turn |

---

## 9. Your one remaining "free" gotcha

The whole thing is genuinely free **as long as the repo stays public**.
If you ever make it private, renders start burning 2000 minutes/month and a
30-minute render will exhaust the budget in ~2 weeks. Keep the scripts open
source - that is the price of free rendering.

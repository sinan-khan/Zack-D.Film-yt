#!/usr/bin/env bash
# Fast local sanity check. No Blender, no API keys, no YouTube needed.
set -euo pipefail

echo "==> syntax check"
for f in scripts/**/*.py; do python3 -m py_compile "$f"; done
echo "    OK"

echo "==> offline story generation"
rm -rf /tmp/zackd-preview && mkdir -p /tmp/zackd-preview
python3 scripts/content/generate_story.py --prompt content/prompts/story-001.txt --out /tmp/zackd-preview/story.json --no-llm

echo "==> animation manifest"
python3 scripts/animation/build_animation_manifest.py --story /tmp/zackd-preview/story.json --out /tmp/zackd-preview/animation_manifest.json
python3 scripts/animation/validate_animation_manifest.py --manifest /tmp/zackd-preview/animation_manifest.json

echo "==> plan schema"
python3 - <<'PY'
import json
story = json.load(open('/tmp/zackd-preview/story.json'))
assert story['title'] and story['scenes']
for s in story['scenes']:
    assert s['narration'] and s['duration_seconds'] > 0 and s['camera'] and s['animation_prompt']
total=sum(s['duration_seconds'] for s in story['scenes'])
assert 40 <= total <= 240
print(f"    OK: '{story['title']}' {len(story['scenes'])} scenes, {total}s")
PY

echo "==> workflow YAML"
python3 - <<'PY'
import glob, yaml
for f in glob.glob('.github/workflows/*.yml'):
    yaml.safe_load(open(f))
    print(f"    OK: {f}")
PY

echo "ALL LOCAL CHECKS PASSED"

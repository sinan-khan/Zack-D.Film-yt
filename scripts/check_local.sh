#!/usr/bin/env bash
# Fast local sanity check. No Blender, no API keys, no YouTube needed.
# Use this during development; run the same checks in CI via act:
#   act -W .github/workflows/test.yml
set -euo pipefail

echo "==> syntax check"
for f in scripts/**/*.py; do
  python3 -m py_compile "$f"
done
echo "    OK"

echo "==> offline story generation"
python3 scripts/content/generate_story.py --prompt content/prompts/story-001.txt \
  --out /tmp/zackd-story.json --no-llm

echo "==> plan schema"
python3 - <<'EOF'
import json
story = json.load(open("/tmp/zackd-story.json"))
assert story["title"], "no title"
assert len(story["scenes"]) >= 1, "no scenes"
for s in story["scenes"]:
    assert s["narration"], "missing narration"
    assert s["duration_seconds"] > 0, "bad duration"
    assert s["camera"], "missing camera"
total = sum(s["duration_seconds"] for s in story["scenes"])
assert 40 <= total <= 240, f"total {total}s out of range"
print(f"    OK: '{story['title']}' {len(story['scenes'])} scenes, {total}s")
EOF

echo "==> workflow YAML"
python3 - <<'EOF'
import glob, yaml
for f in glob.glob(".github/workflows/*.yml"):
    yaml.safe_load(open(f))
    print(f"    OK: {f}")
EOF

echo "ALL LOCAL CHECKS PASSED"

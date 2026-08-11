#!/usr/bin/env python3
"""Generate a humanoid animation from a text prompt via Text2Motion.

Free tier animations are released under CC BY 4.0; the pipeline adds the
required attribution to the YouTube description automatically.

NOTE: Text2Motion's public API may change. The script uses a job-based
flow (submit -> poll -> download) with configurable base URL so you can
adapt it without touching the rest of the pipeline.

Usage:
  python scripts/animation/text2motion.py \
      --prompt "a figure walking slowly along a cliff edge" \
      --out assets/animations/story-001/scene0.fbx

Environment:
  TEXT2MOTION_API_KEY   required
  TEXT2MOTION_BASE_URL  optional, default https://api.text2motion.cc/v1
"""

import argparse
import json
import os
import sys
import time
import urllib.request

BASE_URL = os.environ.get("TEXT2MOTION_BASE_URL", "https://api.text2motion.cc/v1")


def _request(method, path, payload=None, timeout=120):
    key = os.environ.get("TEXT2MOTION_API_KEY", "").strip()
    if not key:
        sys.exit("[text2motion] ERROR: TEXT2MOTION_API_KEY is not set")
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        f"{BASE_URL.rstrip('/')}/{path.lstrip('/')}",
        data=body,
        method=method,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def generate(prompt, out_path):
    job = _request("POST", "animations", {"prompt": prompt, "format": "fbx"})
    job_id = job.get("id") or job.get("job_id") or job.get("animationId")
    if not job_id:
        sys.exit(f"[text2motion] Unexpected response, no job id: {job}")

    print(f"[text2motion] job {job_id} submitted, polling...")
    deadline = time.time() + 300
    result_url = None
    while time.time() < deadline:
        time.sleep(10)
        status = _request("GET", f"animations/{job_id}")
        state = status.get("status") or status.get("state") or "processing"
        if state in ("done", "succeeded", "completed"):
            result_url = status.get("result_url") or status.get("url") or status.get("download_url")
            break
        if state in ("failed", "error", "cancelled"):
            sys.exit(f"[text2motion] job failed: {status}")
        print(f"[text2motion] status={state}, waiting...")

    if not result_url:
        sys.exit("[text2motion] timed out waiting for the job")

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    req = urllib.request.Request(result_url, method="GET")
    with urllib.request.urlopen(req, timeout=300) as resp:
        data = resp.read()
    with open(out_path, "wb") as fh:
        fh.write(data)
    print(f"[text2motion] downloaded animation -> {out_path} ({len(data)} bytes)")


def main():
    ap = argparse.ArgumentParser(description="Generate animation via Text2Motion")
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    generate(args.prompt, args.out)


if __name__ == "__main__":
    main()

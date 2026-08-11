#!/usr/bin/env python3
"""Download a character and/or an animation clip from Mixamo.

Mixamo's web app has no official public API. This script reproduces the
requests the browser makes, which means you must supply your own session
token. Please check Mixamo's terms of service before automating downloads
- if you prefer, simply download FBX files manually in the browser and
drop them into assets/characters and assets/animations instead.

Getting your token:
  1. Log in at https://www.mixamo.com in your browser.
  2. Open DevTools (F12) -> Application -> Cookies -> mixamo.com.
  3. Copy the value of the `v7` cookie. That is your token.

Usage:
  python scripts/animation/download_mixamo.py character --name "Y Bot" --out assets/characters/hero.fbx
  python scripts/animation/download_mixamo.py animation --name "Walking" --character assets/characters/hero.fbx --out assets/animations/story-001/scene0.fbx

Environment:
  MIXAMO_TOKEN   your `v7` cookie value (required)
"""

import argparse
import json
import os
import re
import sys
import urllib.request

API = "https://www.mixamo.com"
COOKIE = "XSRF-TOKEN"


def _token():
    tok = os.environ.get("MIXAMO_TOKEN", "").strip()
    if not tok:
        sys.exit("[mixamo] ERROR: MIXAMO_TOKEN is not set (see script docstring)")
    return tok


def _session():
    token = _token()
    # The web app uses an XSRF cookie; we just need the header value.
    return {
        "Cookie": f"{COOKIE}={token}",
        "X-XSRF-TOKEN": token,
        "Referer": f"{API}/",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
    }


def _get(url, headers):
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read()


def _search(kind, name, headers):
    page = 1
    while page <= 50:
        url = f"{API}/api/v1/{kind}?page={page}&limit=96&query={urllib.parse.quote(name)}"
        data = json.loads(_get(url, headers).decode("utf-8"))
        for item in data.get("results", []):
            if name.lower() in item.get("name", "").lower():
                return item
        if page >= (data.get("pagination") or {}).get("total_pages", 1):
            break
        page += 1
    return None


def _download(url, out_path):
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    data = _get(url, _session())
    with open(out_path, "wb") as fh:
        fh.write(data)
    print(f"[mixamo] saved -> {out_path} ({len(data)} bytes)")


def main():
    import urllib.parse

    ap = argparse.ArgumentParser(description="Mixamo asset downloader")
    sub = ap.add_subparsers(dest="command", required=True)

    pc = sub.add_parser("character")
    pc.add_argument("--name", required=True)
    pc.add_argument("--out", required=True)

    pa = sub.add_parser("animation")
    pa.add_argument("--name", required=True)
    pa.add_argument("--character-id", help="character id (taken from a downloaded character file)")
    pa.add_argument("--out", required=True)

    args = ap.parse_args()

    if args.command == "character":
        item = _search("characters", args.name, _session())
        if not item:
            sys.exit(f"[mixamo] character '{args.name}' not found")
        url = f"{API}/api/v1/characters/{item['id']}/download"
        _download(url, args.out)
        print(f"[mixamo] character id for reuse: {item['id']}")

    elif args.command == "animation":
        if not args.character_id:
            sys.exit("[mixamo] animation requires --character-id")
        item = _search("animations", args.name, _session())
        if not item:
            sys.exit(f"[mixamo] animation '{args.name}' not found")
        url = (
            f"{API}/api/v1/animations/{item['id']}/download"
            f"?character_id={args.character_id}"
        )
        _download(url, args.out)


if __name__ == "__main__":
    main()

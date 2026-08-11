#!/usr/bin/env python3
"""Upload the finished video to YouTube.

Quota note: videos.insert costs 1600 of the 10000 daily API units, so a
single scheduled upload per day is comfortably inside the free tier.

Credentials are read from (in order):
  1. Env vars YOUTUBE_CLIENT_SECRET_JSON / YOUTUBE_TOKEN_JSON (base64)
  2. Files secrets/client_secret.json / secrets/token.json

Usage:
  python scripts/upload/upload_youtube.py --video output/final.mp4 \
      --story content/stories/story-001.json --thumbnail output/thumbnail.jpg \
      --config config/settings.yaml
"""

import argparse
import base64
import json
import os
import sys


def load_config(path):
    import yaml
    with open(path) as fh:
        return yaml.safe_load(fh) or {}


def write_secret_file(env_name, fallback_path):
    value = os.environ.get(env_name, "").strip()
    if not value:
        return fallback_path if os.path.exists(fallback_path) else None
    try:
        data = base64.b64decode(value)
    except Exception as exc:
        sys.exit(f"[upload] {env_name} is not valid base64: {exc}")
    os.makedirs(os.path.dirname(fallback_path) or ".", exist_ok=True)
    with open(fallback_path, "wb") as fh:
        fh.write(data)
    return fallback_path


def build_credentials():
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    SCOPES = [
        "https://www.googleapis.com/auth/youtube.upload",
        "https://www.googleapis.com/auth/youtube.force-ssl",
    ]

    secret = write_secret_file("YOUTUBE_CLIENT_SECRET_JSON", "secrets/client_secret.json")
    token = write_secret_file("YOUTUBE_TOKEN_JSON", "secrets/token.json")

    if not secret:
        sys.exit("[upload] YOUTUBE_CLIENT_SECRET_JSON not set and no secrets/client_secret.json")
    if not token:
        sys.exit("[upload] YOUTUBE_TOKEN_JSON not set and no secrets/token.json")

    with open(secret) as fh:
        client_config = json.load(fh)
    with open(token) as fh:
        token_json = json.load(fh)

    creds = Credentials.from_authorized_user_info(token_json, SCOPES)
    if creds.refresh_token:
        from google.auth.transport.requests import Request
        creds.refresh(Request())

    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    flow.oauth2session.token = creds.token
    flow.oauth2session.refresh_token = creds.refresh_token
    flow.oauth2session.token_uri = creds.token_uri
    flow.oauth2session.client_id = creds.client_id
    flow.oauth2session.client_secret = creds.client_secret
    return flow.credentials


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--story", required=True)
    ap.add_argument("--thumbnail", default="")
    ap.add_argument("--config", default="config/settings.yaml")
    args = ap.parse_args()

    if not os.path.exists(args.video):
        sys.exit(f"[upload] video not found: {args.video}")

    cfg = load_config(args.config)
    with open(args.story) as fh:
        story = json.load(fh)

    title = story.get("title") or "Zack d. Films"
    description = story.get("description") or ""
    tags = story.get("tags") or ["3danimation", "shorts"]

    # Required CC-BY-4.0 attribution when Text2Motion was used.
    sources = {s.get("animation_source") for s in story["scenes"]}
    if "text2motion" in sources and story.get("source") != "offline-template":
        description += "\n\n" + cfg.get("credits", {}).get("text2motion", "")

    youtube_cfg = cfg.get("youtube", {})
    snippet = {
        "title": title,
        "description": description,
        "tags": tags,
        "categoryId": str(cfg.get("channel", {}).get("category_id", 22)),
    }
    status = {
        "privacyStatus": youtube_cfg.get("privacy_status", "private"),
        "selfDeclaredMadeForKids": bool(youtube_cfg.get("made_for_kids", False)),
    }

    creds = build_credentials()
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)
    media = MediaFileUpload(args.video, chunksize=8 * 1024 * 1024, resumable=True)

    request = youtube.videos().insert(
        part="snippet,status",
        body={"snippet": snippet, "status": status},
        media_body=media,
    )

    response = None
    while response is None:
        _status, response = request.next_chunk()

    video_id = response.get("id")
    print(f"[upload] uploaded video id={video_id}")
    print(f"[upload] https://www.youtube.com/watch?v={video_id}")
    print(f"[upload] privacyStatus={response.get('status', {}).get('privacyStatus')}")

    if args.thumbnail and os.path.exists(args.thumbnail):
        try:
            youtube.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(args.thumbnail),
            ).execute()
            print(f"[upload] thumbnail set -> {args.thumbnail}")
        except Exception as exc:
            print(f"[upload] WARNING: thumbnail failed ({exc}); video still uploaded")

    return video_id


if __name__ == "__main__":
    main()

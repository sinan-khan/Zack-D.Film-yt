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
import traceback


def load_config(path):
    import yaml
    with open(path) as fh:
        return yaml.safe_load(fh) or {}


def write_secret_file(env_name, fallback_path):
    value = os.environ.get(env_name, "").strip()
    if not value:
        return fallback_path if os.path.exists(fallback_path) else None
    try:
        data = base64.b64decode(value, validate=True)
    except Exception as exc:
        sys.exit(
            f"[upload] {env_name} is not valid base64: {exc}\n"
            "[upload] check the secret was pasted as one unbroken line with "
            "no extra characters (e.g. PEM headers, line wraps)."
        )
    try:
        json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        sys.exit(
            f"[upload] {env_name} decoded from base64 but is not valid JSON "
            f"({exc}).\n[upload] this usually means the base64 string was "
            "corrupted when copied into the GitHub secret - re-copy the "
            "single-line output directly from the terminal (not a "
            "line-wrapped display) and re-paste it as the secret value."
        )
    os.makedirs(os.path.dirname(fallback_path) or ".", exist_ok=True)
    with open(fallback_path, "wb") as fh:
        fh.write(data)
    return fallback_path


def build_credentials():
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request

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

    # client_config isn't needed for the credential object itself (token.json
    # already embeds client_id/client_secret/token_uri from the original
    # consent flow), but we still require the secret to exist/parse so a
    # broken client_secret.json is caught early with a clear error.
    with open(secret) as fh:
        json.load(fh)
    with open(token) as fh:
        token_json = json.load(fh)

    creds = Credentials.from_authorized_user_info(token_json, SCOPES)
    if creds.expired and creds.refresh_token:
        print("[upload] Token expired, refreshing...")
        try:
            creds.refresh(Request())
            print("[upload] Token refreshed successfully")
        except Exception as exc:
            print(f"[upload] ERROR: Token refresh failed: {exc}")
            traceback.print_exc()
            sys.exit(f"[upload] Cannot refresh YouTube credentials: {exc}")
    return creds


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--story", required=True)
    ap.add_argument("--thumbnail", default="")
    ap.add_argument("--config", default="config/settings.yaml")
    args = ap.parse_args()

    if not os.path.exists(args.video):
        sys.exit(f"[upload] video not found: {args.video}")

    print(f"[upload] Starting upload for video: {args.video}")
    print(f"[upload] Video size: {os.path.getsize(args.video) / (1024*1024):.1f} MB")

    cfg = load_config(args.config)
    with open(args.story) as fh:
        story = json.load(fh)

    title = story.get("title") or "Zack d. Films"
    description = story.get("description") or ""
    tags = story.get("tags") or ["3danimation", "shorts"]

    # Required CC-BY-4.0 attribution whenever Text2Motion was actually used,
    # regardless of whether the story text itself came from an LLM or the
    # offline template - those are independent things.
    sources = {s.get("animation_source") for s in story["scenes"]}
    if "text2motion" in sources:
        description += "\n\n" + cfg.get("credits", {}).get("text2motion", "")

    youtube_cfg = cfg.get("youtube", {})
    snippet = {
        "title": title,
        "description": description,
        "tags": tags,
        "categoryId": str(cfg.get("channel", {}).get("category_id", 22)),
    }
    status = {
        "privacyStatus": youtube_cfg.get("privacy_status", "public"),
        "selfDeclaredMadeForKids": bool(youtube_cfg.get("made_for_kids", False)),
    }

    print(f"[upload] Title: {title}")
    print(f"[upload] Privacy: {status['privacyStatus']}")

    try:
        creds = build_credentials()
        print("[upload] Credentials loaded successfully")
    except Exception as exc:
        print(f"[upload] FATAL: Failed to build credentials: {exc}")
        traceback.print_exc()
        sys.exit(1)

    try:
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload

        youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)
        media = MediaFileUpload(args.video, chunksize=8 * 1024 * 1024, resumable=True)

        print("[upload] Uploading to YouTube...")
        request = youtube.videos().insert(
            part="snippet,status",
            body={"snippet": snippet, "status": status},
            media_body=media,
        )

        response = None
        while response is None:
            try:
                _status, response = request.next_chunk()
                if _status:
                    print(f"[upload] Upload progress: {int(_status.progress() * 100)}%")
            except Exception as chunk_error:
                print(f"[upload] ERROR during upload chunk: {chunk_error}")
                traceback.print_exc()
                raise

        video_id = response.get("id")
        print(f"[upload] SUCCESS: uploaded video id={video_id}")
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

    except Exception as exc:
        print(f"[upload] FATAL ERROR: {exc}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

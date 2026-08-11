#!/usr/bin/env python3
"""One-time setup: obtain a YouTube OAuth refresh token.

Run this ONCE on your own machine (not in CI), then upload the resulting
token file to GitHub as an encrypted secret.

Steps before running:
  1. Create a Google Cloud project: console.cloud.google.com
  2. Enable the "YouTube Data API v3".
  3. Create OAuth client credentials of type "Desktop app".
  4. Download the JSON and pass its path below.

Usage:
  python scripts/upload/oauth_setup.py --client-secret secrets/client_secret.json
  -> writes secrets/token.json

To put the token in GitHub Actions (see .github/workflows/daily.yml):
  base64 -w0 secrets/token.json   # paste into the YOUTUBE_TOKEN_JSON secret
"""

import argparse
import json
import os
import sys

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--client-secret", required=True, help="path to the downloaded OAuth client secret JSON")
    ap.add_argument("--token-out", default="secrets/token.json")
    args = ap.parse_args()

    if not os.path.exists(args.client_secret):
        sys.exit(f"[oauth] client secret not found: {args.client_secret}")

    from google_auth_oauthlib.flow import InstalledAppFlow

    flow = InstalledAppFlow.from_client_secrets_file(args.client_secret, SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent")

    os.makedirs(os.path.dirname(args.token_out) or ".", exist_ok=True)
    with open(args.token_out, "w") as fh:
        fh.write(creds.to_json())
    print(f"[oauth] token saved -> {args.token_out}")
    print("[oauth] keep this file private; it is gitignored.")


if __name__ == "__main__":
    main()

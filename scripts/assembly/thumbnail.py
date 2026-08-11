#!/usr/bin/env python3
"""Generate a YouTube thumbnail from the final video.

Extracts a mid-video frame with ffmpeg and overlays the story title with
a semi-transparent gradient bar using Pillow.

Usage:
  python scripts/assembly/thumbnail.py --video output/final.mp4 \
      --story content/stories/story-001.json --out output/thumbnail.jpg
"""

import argparse
import json
import os
import subprocess
import sys

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    Image = None


def grab_frame(video, out_png, at_frac=0.35):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", video],
        capture_output=True, text=True, check=True,
    )
    total = float(out.stdout.strip())
    t = total * at_frac
    subprocess.run(
        ["ffmpeg", "-y", "-ss", str(t), "-i", video, "-frames:v", "1", out_png],
        check=True, capture_output=True, text=True,
    )


def overlay_title(img_path, title, out_path):
    img = Image.open(img_path).convert("RGB")
    w, h = img.size
    draw = ImageDraw.Draw(img, "RGBA")

    bar_h = int(h * 0.30)
    for y in range(bar_h):
        alpha = int(180 * (y / bar_h))
        draw.line([(0, h - bar_h + y), (w, h - bar_h + y)], fill=(0, 0, 0, alpha))

    font = None
    for name in ["DejaVuSans-Bold.ttf", "Arial Bold.ttf", "arialbd.ttf"]:
        try:
            font = ImageFont.truetype(name, int(w * 0.05))
            break
        except OSError:
            continue
    if font is None:
        font = ImageFont.load_default()

    words = title.split()
    lines, cur = [], ""
    for word in words:
        probe = f"{cur} {word}".strip()
        if draw.textlength(probe, font=font) <= w * 0.9:
            cur = probe
        else:
            lines.append(cur)
            cur = word
    lines.append(cur)

    y = h - bar_h + int(bar_h * 0.15)
    for line in lines:
        lw = draw.textlength(line, font=font)
        draw.text(((w - lw) / 2, y), line, fill=(255, 255, 255, 255), font=font)
        y += int(font.size * 1.25)

    img.save(out_path, quality=90)
    print(f"[thumbnail] wrote {out_path} ({img.size[0]}x{img.size[1]})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--story", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    if Image is None:
        sys.exit("[thumbnail] Pillow is not installed (pip install Pillow)")

    with open(args.story) as fh:
        story = json.load(fh)

    png = os.path.splitext(args.out)[0] + "_raw.png"
    grab_frame(args.video, png)
    overlay_title(png, story.get("title", "Zack d. Films"), args.out)
    if os.path.exists(png):
        os.remove(png)


if __name__ == "__main__":
    main()

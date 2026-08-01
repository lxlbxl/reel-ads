#!/usr/bin/env python3
"""
contact_sheet.py -- montage representative frames from a rendered scene or
finished MP4 into one image for fast visual QC (see SKILL.md step 9 and
references/vo_sync.md step 6).

Always write path-touching Python to a FILE and run it, never pass paths
inside a `python -c "..."` string -- see the "Windows/git-bash" note in
references/scene_architecture.md for why a multi-path one-liner can fail
unpredictably on this platform (one path converts correctly, another in
the same string doesn't).

Two modes:

1. From an already-rendered PNG frame sequence:
   python3 contact_sheet.py --frames frames/ --out contact_sheet.jpg [--cols 5]
   (samples up to --max frames evenly spaced across the sequence)

2. From a finished MP4, at specific timestamps (fractions of duration or
   absolute seconds) -- pulls frames straight from the encode for QC that
   reflects exactly what will ship, not the raw PNGs:
   python3 contact_sheet.py --video final.mp4 --duration 48.03 \
       --at 0.1,0.3,0.5,0.7,0.9 --out contact_sheet.jpg
"""
import argparse
import glob
import subprocess
import sys
from pathlib import Path

from PIL import Image


def extract_from_video(video, duration, fractions, tmp_dir):
    tmp_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for frac in fractions:
        t = round(duration * frac, 3) if frac <= 1 else frac  # <=1 treated as fraction, else absolute seconds
        out = tmp_dir / f"t_{frac}.jpg"
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-ss", str(t), "-i", str(video),
             "-frames:v", "1", str(out)],
            check=True,
        )
        paths.append(out)
    return paths


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", help="dir of f%05d.png frames (mode 1)")
    ap.add_argument("--video", help="finished MP4 to sample from (mode 2)")
    ap.add_argument("--duration", type=float, help="video duration in seconds (required with --video)")
    ap.add_argument("--at", default="0.1,0.3,0.5,0.7,0.9",
                     help="comma-separated fractions (0-1) or absolute seconds (>1) to sample (mode 2)")
    ap.add_argument("--max", type=int, default=12, help="max frames to sample (mode 1)")
    ap.add_argument("--cols", type=int, default=5)
    ap.add_argument("--out", required=True)
    ap.add_argument("--thumb-w", type=int, default=260)
    ap.add_argument("--thumb-h", type=int, default=462)
    args = ap.parse_args()

    if args.video:
        if not args.duration:
            sys.exit("--duration is required with --video")
        fractions = [float(x) for x in args.at.split(",")]
        tmp_dir = Path(args.out).resolve().parent / "_contact_sheet_tmp"
        files = extract_from_video(Path(args.video), args.duration, fractions, tmp_dir)
    elif args.frames:
        all_files = sorted(glob.glob(str(Path(args.frames) / "f*.png")))
        if not all_files:
            sys.exit(f"no frames found in {args.frames}")
        n = min(args.max, len(all_files))
        step = max(1, len(all_files) // n)
        files = all_files[::step][:n]
    else:
        sys.exit("pass either --frames or --video")

    print(f"{len(files)} frames sampled")
    cols = args.cols
    rows = (len(files) + cols - 1) // cols
    tw, th = args.thumb_w, args.thumb_h
    sheet = Image.new("RGB", (tw * cols, th * rows), (24, 24, 24))
    for i, f in enumerate(files):
        thumb = Image.open(f).convert("RGB").resize((tw, th))
        sheet.paste(thumb, ((i % cols) * tw, (i // cols) * th))
    sheet.save(args.out, quality=88)
    print("saved", args.out)


if __name__ == "__main__":
    main()

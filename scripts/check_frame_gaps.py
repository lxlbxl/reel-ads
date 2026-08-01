#!/usr/bin/env python3
"""
check_frame_gaps.py -- verify a rendered frame sequence has no missing
indices before encoding.

ffmpeg's image2 demuxer (`-i frames/f%05d.png`) reads sequential frames
and STOPS SILENTLY at the first missing index -- no error, no warning,
just a shorter output video. A plain `ls frames | wc -l` can look right
(the total count is close to correct) while one frame in the middle is
missing, e.g. dropped at a chunk boundary during a resumed/retried
render. This script checks the actual index set, not just the count.

Usage:
    python3 check_frame_gaps.py <frames_dir> <total_frames>

Exits 0 with "no gaps" if the sequence is complete. Exits 1 and prints
the missing indices (and ready-to-run render commands to fill them) if
not.
"""
import argparse
import os
import sys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("frames_dir")
    ap.add_argument("total_frames", type=int, help="expected frame count, e.g. round(duration*fps)")
    ap.add_argument("--html", default="scene.html", help="scene HTML path, for the suggested fix command")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--duration", type=float, default=None, help="duration in seconds, for the suggested fix command")
    args = ap.parse_args()

    present = set()
    for f in os.listdir(args.frames_dir):
        if f.startswith("f") and f.endswith(".png") and len(f) == 10:
            try:
                present.add(int(f[1:6]))
            except ValueError:
                pass

    missing = [i for i in range(args.total_frames) if i not in present]

    print(f"expected: {args.total_frames}  present: {len(present)}  missing: {len(missing)}")

    if not missing:
        print("no gaps -- safe to encode")
        sys.exit(0)

    print(f"MISSING INDICES: {missing}")

    # collapse into contiguous ranges for compact re-render commands
    ranges = []
    start = prev = missing[0]
    for i in missing[1:]:
        if i == prev + 1:
            prev = i
            continue
        ranges.append((start, prev))
        start = prev = i
    ranges.append((start, prev))

    dur = args.duration if args.duration else "<duration>"
    print("\nrender the gaps before encoding:")
    for lo, hi in ranges:
        print(f"  python3 capture_frames.py {args.html} {args.fps} {dur} {args.frames_dir}/ --start {lo} --end {hi+1}")

    sys.exit(1)


if __name__ == "__main__":
    main()

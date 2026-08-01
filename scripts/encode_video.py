#!/usr/bin/env python3
"""
encode_video.py -- turn a folder of f%05d.png frames (+ optional audio) into
a delivery-ready MP4, with optional aspect-ratio crops for feed/square posting.

Usage:
    python3 encode_video.py --frames DIR --fps 30 --out out.mp4 \
        [--audio master_vo.wav] [--crop 1080x1350+0+285 --crop-out feed.mp4]

If --audio is omitted, a silent AAC track is muxed in anyway -- Reels/TikTok/
IG both upload video-only files awkwardly or downrank them; a null audio
track avoids that with no audible difference.

If --audio is given, -shortest trims the tiny (<1 frame) rounding mismatch
between video length (frames/fps) and audio length so they end together
cleanly.

--crop takes ffmpeg crop filter syntax WxH+X+Y (e.g. 1080x1350+0+285 to pull
a centered 4:5 crop out of a 1080x1920 master -- no re-render needed).
"""
import argparse
import subprocess


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", required=True, help="dir containing f%05d.png")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--out", required=True)
    ap.add_argument("--audio", default=None)
    ap.add_argument("--crf", type=int, default=19)
    ap.add_argument("--preset", default="slow")
    ap.add_argument("--crop", default=None, help="WxH+X+Y, e.g. 1080x1350+0+285")
    ap.add_argument("--crop-out", default=None)
    args = ap.parse_args()

    cmd = ["ffmpeg", "-y", "-loglevel", "error",
           "-framerate", str(args.fps), "-i", f"{args.frames}/f%05d.png"]

    if args.audio:
        cmd += ["-i", args.audio]
    else:
        cmd += ["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100"]

    cmd += [
        "-c:v", "libx264", "-profile:v", "high", "-level", "4.1",
        "-pix_fmt", "yuv420p", "-crf", str(args.crf), "-preset", args.preset,
        "-x264-params", "keyint=60:min-keyint=30:scenecut=0",
        "-c:a", "aac", "-b:a", "160k", "-ar", "44100",
        "-shortest", "-movflags", "+faststart",
        args.out,
    ]
    subprocess.run(cmd, check=True)
    print(f"wrote {args.out}")

    if args.crop:
        if not args.crop_out:
            raise SystemExit("--crop requires --crop-out")
        w, rest = args.crop.split("x")
        h, x, y = rest.replace("+", " ").split()
        vf = f"crop={w}:{h}:{x}:{y}"
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", args.out,
             "-vf", vf,
             "-c:v", "libx264", "-profile:v", "high", "-pix_fmt", "yuv420p",
             "-crf", str(args.crf), "-preset", args.preset,
             "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart",
             args.crop_out],
            check=True,
        )
        print(f"wrote {args.crop_out}")


if __name__ == "__main__":
    main()

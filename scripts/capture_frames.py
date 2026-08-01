#!/usr/bin/env python3
"""
capture_frames.py -- render a deterministic window.render(t) HTML scene to PNG frames.

The target HTML must define a global `window.render(t)` that is a PURE function
of t (seconds) -- it should not rely on CSS animations, transitions, or
requestAnimationFrame. Headless capture is slower than real time, so anything
driven by the wall clock will drift and stutter. See references/scene_architecture.md.

Usage:
    python3 capture_frames.py <html_path> <fps> <duration_seconds> <out_dir> \
        [--start N] [--end N] [--width W] [--height H]

If --start/--end are omitted, renders the full [0, duration*fps) frame range.
Always chunk long renders (call this repeatedly with --start/--end) to stay
under any single-tool-call time limit -- ~250-350 frames per call is a safe
chunk size regardless of scene complexity.

Frames are written as f00000.png, f00001.png, ... in out_dir, at native
resolution (no upscaling), ready for ffmpeg's `-framerate FPS -i f%05d.png`.
"""
import argparse
import time
from pathlib import Path
from playwright.sync_api import sync_playwright


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("html_path")
    ap.add_argument("fps", type=int)
    ap.add_argument("duration", type=float)
    ap.add_argument("out_dir")
    ap.add_argument("--start", type=int, default=None)
    ap.add_argument("--end", type=int, default=None)
    ap.add_argument("--width", type=int, default=1080)
    ap.add_argument("--height", type=int, default=1920)
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    total_frames = round(args.duration * args.fps)
    start = args.start if args.start is not None else 0
    end = args.end if args.end is not None else total_frames

    html_path = Path(args.html_path).resolve()
    url = f"file://{html_path}"

    t0 = time.time()
    with sync_playwright() as p:
        browser = p.chromium.launch(args=[
            "--force-color-profile=srgb",
            "--font-render-hinting=none",
            "--disable-lcd-text",
        ])
        page = browser.new_page(
            viewport={"width": args.width, "height": args.height},
            device_scale_factor=1,
        )
        page.goto(url)
        # Wait for any @font-face fonts to finish loading before the first
        # screenshot -- otherwise early frames render in a fallback font.
        page.wait_for_function("document.fonts.status === 'loaded'", timeout=20000)
        page.wait_for_timeout(300)

        for i in range(start, end):
            t = i / args.fps
            page.evaluate("t => window.render(t)", t)
            page.screenshot(path=str(out_dir / f"f{i:05d}.png"))

        browser.close()

    print(f"frames {start}-{end-1} in {time.time()-t0:.0f}s -> {out_dir}")


if __name__ == "__main__":
    main()

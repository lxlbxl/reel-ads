#!/usr/bin/env python3
"""
build_vo_track.py -- turn a set of per-scene TTS clips into one clean,
scene-accurate voice-over track, and hand back the numbers needed to
retime the video's scene-cut table (SC array).

Two modes per segment:
  "natural" -- trim leading AND trailing silence (small post-roll kept).
               The scene's on-screen duration should be SET TO MATCH this
               clip's resulting length. Use this when building fresh visuals
               around already-recorded VO (the usual case).
  "pad"     -- trim only leading silence, then pad the tail with silence so
               the clip is exactly `target_duration` seconds. Use this when
               retrofitting VO onto a video whose scene cut points already
               exist and must not move (e.g. adding narration to a silent
               cut you already approved). If target_duration is shorter than
               the natural spoken length, the script refuses to truncate
               mid-word and falls back to the natural length instead --
               widen that scene rather than clip audio.

Also detects internal silence gaps within each clip (the pauses between
sentences/phrases already in the read) and reports them, offset into the
clip's own trimmed timeline. Use these as anchor points to stagger on-screen
elements (list items, words, rows) so they land on the beat they're spoken on
-- see references/vo_sync.md for the retiming pattern.

Usage:
    python3 build_vo_track.py <manifest.json> <out_dir>

manifest.json:
[
  {"name": "scene1_hook", "mp3": "raw/scene1_hook.mp3", "mode": "natural"},
  {"name": "scene2_cta",  "mp3": "raw/scene2_cta.mp3",  "mode": "pad", "target_duration": 3.7}
]

Writes to out_dir:
  <name>_final.wav      per-segment trimmed/padded clip
  master_vo.wav         all segments concatenated, in manifest order
  vo_summary.json       per-segment duration, cumulative t0/t1, internal_gaps
                         -- t0/t1 are ready to paste straight into the SC array
"""
import json
import subprocess
import sys
from pathlib import Path


def ffprobe_duration(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    return float(out)


def detect_silences(path, noise_db=-40, min_dur=0.08):
    proc = subprocess.run(
        ["ffmpeg", "-i", str(path), "-af",
         f"silencedetect=noise={noise_db}dB:d={min_dur}", "-f", "null", "-"],
        capture_output=True, text=True,
    )
    starts, ends = [], []
    for line in proc.stderr.splitlines():
        line = line.strip()
        if "silence_start:" in line:
            starts.append(float(line.split("silence_start:")[1].strip()))
        elif "silence_end:" in line:
            # format: "silence_end: 1.234 | silence_duration: 0.567"
            val = line.split("silence_end:")[1].split("|")[0].strip()
            ends.append(float(val))
    blocks = list(zip(starts, ends))
    # A silence_start with no matching end means it runs to EOF.
    if len(starts) > len(ends):
        blocks.append((starts[-1], None))
    return blocks


def build_segment(mp3, mode, target_duration, out_wav, lead_pad=0.03, tail_pad=0.08, sr=44100):
    dur = ffprobe_duration(mp3)
    blocks = detect_silences(mp3)

    leading = 0.0
    trailing_start = dur
    internal = list(blocks)

    if internal and internal[0][0] <= 0.05:
        s, e = internal.pop(0)
        leading = max(0.0, (e if e is not None else dur) - lead_pad)

    if internal:
        s, e = internal[-1]
        if e is None or e >= dur - 0.05:
            internal.pop(-1)
            trailing_start = s + tail_pad

    natural_len = max(0.05, trailing_start - leading)

    if mode == "natural":
        target = natural_len
    elif mode == "pad":
        if target_duration is None:
            raise ValueError(f"{mp3}: mode 'pad' requires target_duration")
        target = target_duration
        if target < natural_len:
            print(f"WARNING: {mp3}: target_duration {target:.3f}s is shorter than the "
                  f"natural spoken length {natural_len:.3f}s. Refusing to cut off words -- "
                  f"using {natural_len:.3f}s instead. Widen this scene's on-screen duration to match.",
                  file=sys.stderr)
            target = natural_len
    else:
        raise ValueError(f"unknown mode: {mode}")

    if abs(target - natural_len) < 1e-6:
        af = f"atrim=start={leading}:end={leading+natural_len},asetpts=PTS-STARTPTS"
    elif target > natural_len:
        af = f"atrim=start={leading},asetpts=PTS-STARTPTS,apad=whole_dur={target}"
    else:
        # target < natural_len but mode == "natural" can't happen; guard anyway
        af = f"atrim=start={leading}:end={leading+target},asetpts=PTS-STARTPTS"

    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp3), "-af", af,
         "-ar", str(sr), "-ac", "2", "-c:a", "pcm_s16le", str(out_wav)],
        check=True,
    )

    internal_gaps = []
    for s, e in internal:
        s2 = round(s - leading, 3)
        e2 = round((e if e is not None else dur) - leading, 3)
        if e2 > 0 and s2 < target:
            internal_gaps.append([max(0.0, s2), min(target, e2)])

    return {
        "duration": round(target, 6),
        "natural_length": round(natural_len, 6),
        "leading_trim": round(leading, 6),
        "internal_gaps": internal_gaps,
    }


def main():
    manifest_path, out_dir = sys.argv[1], Path(sys.argv[2])
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(Path(manifest_path).read_text())

    summary = []
    t_cursor = 0.0
    concat_lines = []

    for seg in manifest:
        name = seg["name"]
        out_wav = out_dir / f"{name}_final.wav"
        info = build_segment(
            seg["mp3"], seg.get("mode", "natural"), seg.get("target_duration"),
            out_wav,
        )
        info["name"] = name
        info["t0"] = round(t_cursor, 6)
        info["t1"] = round(t_cursor + info["duration"], 6)
        t_cursor = info["t1"]
        summary.append(info)
        concat_lines.append(f"file '{out_wav.resolve()}'")
        print(f"{name}: duration={info['duration']:.3f}s  t0={info['t0']:.3f}  t1={info['t1']:.3f}"
              f"  internal_gaps={info['internal_gaps']}")

    concat_list = out_dir / "concat_list.txt"
    concat_list.write_text("\n".join(concat_lines) + "\n")
    master = out_dir / "master_vo.wav"
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
         "-i", str(concat_list), "-c", "copy", str(master)],
        check=True,
    )
    total = ffprobe_duration(master)
    print(f"\nmaster_vo.wav duration: {total:.6f}s ({out_dir / 'master_vo.wav'})")

    (out_dir / "vo_summary.json").write_text(json.dumps(
        {"total_duration": total, "segments": summary}, indent=2))
    print(f"wrote {out_dir / 'vo_summary.json'}")


if __name__ == "__main__":
    main()

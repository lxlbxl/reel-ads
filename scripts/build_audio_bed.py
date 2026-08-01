#!/usr/bin/env python3
"""
build_audio_bed.py -- mix a spoken VO track with a subtle synthesized ambient
pad plus whoosh/chime SFX, sidechain-ducked under the voice, loudness-normalized.

Nothing here is fetched from the internet -- the pad is synthesized from sine
oscillators and the whoosh/chime one-shots ship as static assets in
assets/whoosh.wav and assets/chime.wav (generated once, reused for every
video). This sidesteps any stock-music licensing question entirely and keeps
the whole pipeline offline and deterministic.

Usage:
    python3 build_audio_bed.py --vo master_vo.wav --out master_mix.wav \
        --cuts 3.829,7.936,11.787,... \
        --accents 16.938,33.706,... \
        [--chord 130.81,164.81,196.00] [--lufs -16] [--pad-db -24]

--cuts     comma list of scene-cut timestamps (t0 of every scene after the
           first) -- gets a whoosh from assets/whoosh.wav.
--accents  comma list of timestamps for a softer accent moment (logo reveal,
           a step landing, a CTA button pop) -- gets a chime from
           assets/chime.wav. Optional.
--chord    three (or more) frequencies in Hz for the ambient pad, comma
           separated. Default is a soft major-ish triad. Pick a different
           chord per video if you want the background beds to feel distinct
           across a batch (e.g. shift up a whole tone for a brighter angle).
--lufs     integrated loudness target for the final mix. -16 matches the
           existing maids-ad brand convention; keep consistent across a
           campaign unless there's a reason to diverge.
--pad-db   overall level of the synthesized pad+SFX layer before ducking.
           -24dB is "subtle" per the production brief; go louder only if
           asked for a more energetic bed.

Output duration is hard-locked to the VO's duration (via atrim/apad), so it
is always frame-exact with a video whose SC table was built from the same
master_vo.wav via build_vo_track.py.
"""
import argparse
import subprocess
from pathlib import Path

SKILL_ASSETS = Path(__file__).resolve().parent.parent / "assets"


def ffprobe_duration(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    return float(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vo", required=True, help="path to master_vo.wav (from build_vo_track.py)")
    ap.add_argument("--out", required=True, help="output path, e.g. master_mix.wav")
    ap.add_argument("--cuts", default="", help="comma-separated whoosh timestamps (seconds)")
    ap.add_argument("--accents", default="", help="comma-separated chime timestamps (seconds)")
    ap.add_argument("--chord", default="130.81,164.81,196.00", help="comma-separated pad frequencies (Hz)")
    ap.add_argument("--lufs", type=float, default=-16.0)
    ap.add_argument("--pad-db", type=float, default=-24.0)
    ap.add_argument("--whoosh", default=str(SKILL_ASSETS / "whoosh.wav"))
    ap.add_argument("--chime", default=str(SKILL_ASSETS / "chime.wav"))
    ap.add_argument("--workdir", default=None, help="scratch dir for intermediates (default: alongside --out)")
    args = ap.parse_args()

    vo_dur = ffprobe_duration(args.vo)
    work = Path(args.workdir) if args.workdir else Path(args.out).resolve().parent / "_audio_bed_tmp"
    work.mkdir(parents=True, exist_ok=True)

    freqs = [f.strip() for f in args.chord.split(",") if f.strip()]
    cuts = [float(x) for x in args.cuts.split(",") if x.strip()]
    accents = [float(x) for x in args.accents.split(",") if x.strip()]

    pad_dur = vo_dur + 2.0
    pad_raw = work / "pad_raw.wav"
    pad_inputs = []
    for f in freqs:
        pad_inputs += ["-f", "lavfi", "-i", f"sine=frequency={f}:sample_rate=44100:duration={pad_dur}"]
    weights = " ".join(["1"] + ["0.7"] * (len(freqs) - 1)) if freqs else "1"
    n = len(freqs)
    labels = "".join(f"[{i}:a]" for i in range(n))
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error"] + pad_inputs + [
            "-filter_complex",
            f"{labels}amix=inputs={n}:weights={weights}:normalize=0[mix];"
            f"[mix]lowpass=f=1800,tremolo=f=0.12:d=0.25,volume={args.pad_db}dB,"
            f"afade=t=in:st=0:d=2,afade=t=out:st={pad_dur-2.5}:d=2.5,"
            "aformat=channel_layouts=stereo[out]",
            "-map", "[out]", str(pad_raw),
        ],
        check=True,
    )
    pad = work / "pad.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(pad_raw), "-t", str(vo_dur), str(pad)], check=True)

    # place whoosh/chime one-shots at their timestamps onto a silent canvas
    sfx_layer = work / "sfx_layer.wav"
    inputs = ["-f", "lavfi", "-i", f"anullsrc=channel_layout=stereo:sample_rate=44100", "-t", str(vo_dur)]
    filters = []
    labels2 = ["[0:a]"]
    idx = 1
    for t in cuts:
        inputs += ["-i", args.whoosh]
        ms = round(t * 1000)
        filters.append(f"[{idx}:a]adelay={ms}|{ms}[s{idx}]")
        labels2.append(f"[s{idx}]")
        idx += 1
    for t in accents:
        inputs += ["-i", args.chime]
        ms = round(t * 1000)
        filters.append(f"[{idx}:a]adelay={ms}|{ms}[s{idx}]")
        labels2.append(f"[s{idx}]")
        idx += 1
    mix_expr = "".join(labels2) + f"amix=inputs={len(labels2)}:normalize=0,volume=6dB,atrim=0:{vo_dur}[out]"
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error"] + inputs +
        ["-filter_complex", ";".join(filters + [mix_expr]) if filters else mix_expr,
         "-map", "[out]", str(sfx_layer)],
        check=True,
    )

    bg_bed = work / "bg_bed.wav"
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(pad), "-i", str(sfx_layer),
         "-filter_complex", "[0:a][1:a]amix=inputs=2:normalize=0[out]", "-map", "[out]", str(bg_bed)],
        check=True,
    )

    bg_ducked = work / "bg_ducked.wav"
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(bg_bed), "-i", args.vo,
         "-filter_complex",
         "[0:a][1:a]sidechaincompress=threshold=0.05:ratio=8:attack=15:release=250:makeup=1[out]",
         "-map", "[out]", str(bg_ducked)],
        check=True,
    )

    raw_mix = work / "raw_mix.wav"
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", args.vo, "-i", str(bg_ducked),
         "-filter_complex", "[0:a]volume=1.0[vo];[1:a]apad[bg];[vo][bg]amix=inputs=2:duration=first:normalize=0[out]",
         "-map", "[out]", str(raw_mix)],
        check=True,
    )

    normed = work / "normed.wav"
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(raw_mix),
         "-af", f"loudnorm=I={args.lufs}:TP=-1.5:LRA=11", "-ar", "44100", "-ac", "2", str(normed)],
        check=True,
    )

    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(normed), "-af", "apad", "-t", str(vo_dur), args.out],
        check=True,
    )

    final_dur = ffprobe_duration(args.out)
    print(f"wrote {args.out}  duration={final_dur:.3f}s  (vo was {vo_dur:.3f}s)")


if __name__ == "__main__":
    main()

# Background music + SFX bed (synthesized, no stock-music sourcing)

For a spot that needs "subtle background music and sound effects" alongside
VO, the fastest and safest option is to **synthesize the bed with ffmpeg**
rather than pull a stock track from the web. It sidesteps licensing entirely
(nothing downloaded, nothing to attribute or clear), it's fully controllable
in timing (whooshes land exactly on scene cuts, not "close enough"), and it's
one script call.

Use `scripts/build_audio_bed.py`. It expects `master_vo.wav` and
`vo_summary.json` from `build_vo_track.py` (see `vo_sync.md`) to already
exist -- the bed is built *around* the locked VO timing, never the other
way around.

```bash
python3 scripts/build_audio_bed.py \
  --vo vo_out/master_vo.wav \
  --out sfx/master_mix.wav \
  --cuts "3.829,7.936,11.787,16.638,19.002,25.010,32.309,33.206,36.142,41.363,47.350,52.077" \
  --accents "16.938,33.706,36.642,41.863,52.827"
```

- `--cuts` -- every scene-cut timestamp after the first (i.e. every `t0` in
  the `SC` table except `SC[0]`). Each gets a soft whoosh transient.
- `--accents` -- a handful of extra moments worth a softer chime: a logo
  reveal, a number landing, a CTA button pop. Don't use more than ~5-6 in a
  60s spot or the ear stops noticing them as distinct beats.
- `--chord` -- optional, three-or-more comma-separated Hz values for the
  ambient pad (default is a soft low triad: `130.81,164.81,196.00` = C3, E3,
  G3). **Vary this across a multi-video campaign** -- shifting the chord up
  a whole tone or to a different inversion per video is a cheap way to give
  each spot a slightly different sonic identity without touching the
  narration or visuals.
- `--pad-db` -- default `-24` is deliberately subtle (measured around -22dB
  peak / -44dB RMS in isolation, near-inaudible under continuous VO). Only
  raise it if the brief specifically wants a more energetic bed.

## What it does internally (skip this section if the script already covers your case)

1. Synthesizes a pad from layered sine oscillators at the given chord,
   `lowpass`'d for warmth, `tremolo`'d for slow movement, faded in/out.
2. Places the pre-baked `assets/whoosh.wav` at every `--cuts` timestamp and
   `assets/chime.wav` at every `--accents` timestamp on a silent canvas
   (`adelay` per instance, then `amix`).
3. Mixes pad + SFX into one background layer.
4. **Sidechain-ducks** that background layer under the VO
   (`sidechaincompress`, main=background, sidechain=VO) so it dips
   automatically whenever there's speech -- no manual per-segment volume
   automation needed, even though in practice VO covers nearly the entire
   runtime in a script-driven explainer.
5. Mixes the (now ducked) background back in with the VO at full level.
6. `loudnorm`s the result to `--lufs` (default -16, matching this brand's
   established convention -- keep consistent across a campaign so spots
   don't jump in loudness back-to-back in a Reels feed).
7. Hard-trims/pads to the VO's exact duration, so the output is always
   frame-exact with a video built from the same `master_vo.wav`.

## QC before encoding

Same checks as `vo_sync.md` step 6, run on the *mixed* output, not the raw
VO:

```bash
ffmpeg -i master_mix.wav -filter_complex showwavespic=s=1600x300 waveform.png
ffmpeg -i master_mix.wav -af astats -f null - 2>&1 | grep -E "Peak level|RMS level"
```

Expect Peak around `-1.5dB` (the `TP=-1.5` true-peak ceiling in the
`loudnorm` call) and RMS in the high -teens to -20s given a continuous VO
track. If Peak is clipping (`0dB` or positive) or RMS is buried below -30,
something upstream changed -- check the VO's own level first with the same
`astats` command before touching this script's gain stages.

## Regenerating whoosh/chime assets (rarely needed)

`assets/whoosh.wav` and `assets/chime.wav` are generic, brand-agnostic SFX
-- they don't need regenerating per project. Only redo them if a brief
specifically wants a different SFX character (e.g. a harder cut sound, a
brighter chime):

```bash
# whoosh: filtered pink-noise burst
ffmpeg -y -f lavfi -i "anoisesrc=color=pink:duration=0.35:sample_rate=44100" \
  -af "bandpass=f=1400:width_type=h:w=1800,afade=t=in:st=0:d=0.02,afade=t=out:st=0.12:d=0.23,volume=-15dB,aformat=channel_layouts=stereo" \
  assets/whoosh.wav

# chime: two-tone soft ding
ffmpeg -y -f lavfi -i "sine=frequency=880:duration=0.4:sample_rate=44100" \
       -f lavfi -i "sine=frequency=1760:duration=0.4:sample_rate=44100" \
  -filter_complex "[0:a]volume=1[a];[1:a]volume=0.5[b];[a][b]amix=inputs=2:normalize=0,afade=t=out:st=0.05:d=0.35,volume=-17dB,aformat=channel_layouts=stereo" \
  assets/chime.wav
```

# reel-ads

A Claude Code skill for building short vertical video ads (Reels/TikTok/
Shorts) as deterministic HTML/CSS/JS animations, captured frame-by-frame
with headless Chromium and encoded to MP4 — with optional ElevenLabs
voice-over synced to scene cuts and words, a synthesized background
music/SFX bed, and optional publishing straight to Instagram/Facebook.

Brand-agnostic: written to work for whichever brand is named in a given
request, not one specific venture.

**Start here: [SKILL.md](SKILL.md)** — the entry point and full workflow.
It links out to the reference docs (`references/`) as each becomes
relevant, and the pipeline scripts live in `scripts/`.

## Layout

```
SKILL.md                        entry point / workflow
references/
  scene_architecture.md         render(t) pattern, safe area, logo/font handling
  kinetic_typography.md         font pairing, motion primitives, line-width budgeting
  vo_sync.md                    ElevenLabs voice-over workflow
  audio_design.md               synthesized background music/SFX bed
  url_hosting.md                getting a finished file to a public URL
  publishing.md                 posting to Instagram/Facebook via Composio
  brand_claims.md                claims/compliance check before locking copy
assets/
  scene_template.html           starting point for a new scene build
  whoosh.wav, chime.wav         reusable SFX one-shots for the audio bed
scripts/
  capture_frames.py             render(t) HTML -> PNG frame sequence (Playwright)
  build_vo_track.py             per-scene TTS clips -> timed VO track
  build_audio_bed.py            VO + pad + SFX -> mixed, ducked, normalized track
  check_frame_gaps.py           verify a frame sequence before encoding
  contact_sheet.py              QC montage from frames or a finished MP4
  encode_video.py               frames (+audio) -> final MP4
```

## Requirements

- Python 3 with `playwright` (`pip install playwright && playwright install chromium`) and `Pillow`
- `ffmpeg`/`ffprobe` on PATH
- An ElevenLabs-compatible TTS tool, only if a video needs voice-over

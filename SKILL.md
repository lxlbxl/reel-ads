# Reel Ads

Builds short vertical video ads as deterministic HTML/CSS/JS animations,
captured frame-by-frame with headless Chromium and encoded to MP4 --
optionally with ElevenLabs voice-over synced to the scene cuts and to
individual words/phrases within each scene, plus a synthesized background
music/SFX bed, and optional publishing straight to Instagram/Facebook.

This skill is written for **any brand the user runs**, not one specific
venture. The user may run several -- always work from whichever brand is
named in the current request, pull that brand's real assets (site,
uploaded logo, given copy), and never carry over a previous project's
colors, fonts, or claims into a new one.

## Before starting: read the reference files

- `references/scene_architecture.md` -- the render(t) pattern, safe area,
  a real markup bug worth knowing about up front, logo handling, fonts,
  brand tokens.
- `references/kinetic_typography.md` -- read this whenever text carries
  the spot (explainers, offer/list/step ads): font pairing, line-width
  budgeting so headlines don't wrap mid-word, mask-reveal/letter-slam/
  highlight-swipe/counter motion primitives, a living background, and the
  live `?play` preview mode. For a silent b-roll cut with two words on
  screen, the base template in `scene_architecture.md` is enough on its
  own.
- `references/vo_sync.md` -- only if this ad has voice-over. Covers the
  ElevenLabs workflow including a download-link caveat that is
  environment-dependent (test whether your environment can fetch
  `storage.googleapis.com` directly before assuming you need the
  upload/re-download workaround).
- `references/audio_design.md` -- only if the brief asks for background
  music/SFX under the VO. Covers `scripts/build_audio_bed.py`, which
  synthesizes a subtle ambient bed plus whoosh/chime transients and
  sidechain-ducks them under the narration -- no stock-music sourcing or
  licensing question involved.
- `references/brand_claims.md` -- read while drafting copy, not after.
- `references/url_hosting.md` -- only if a finished video/audio file needs
  to reach a public URL (e.g. for publishing, or a VO tool that returns a
  presigned download link). Covers a verified working temp-host and a
  redirect pitfall in another common one.
- `references/publishing.md` -- only if asked to post the finished video
  to Instagram/Facebook. Covers account discovery, a default-account
  pitfall worth knowing before the first call, the two-step Reel publish
  flow, and verifying what actually posted.

Also check `/mnt/skills/public/frontend-design/SKILL.md` for general
design-token and styling guidance if it's relevant to the visual
direction, and use `image_search` if you want reference images of the
brand's existing look before designing.

## Workflow

### 1. Establish the brand

If the user names a live site, `web_fetch` it (and any linked
offers/pricing/case-study pages) for: accent color (check the
`theme-color` meta tag first), logo, wordmark, tagline, real offers, and
proof points. If a logo file is attached instead of/in addition to a
site, use that as the source of truth for color and mark (see
`scene_architecture.md` for cropping/embedding it).

If nothing is fetchable and no logo is provided, ask for a link or a
logo upload rather than inventing brand colors/fonts from a guess --
proceed with a clearly-labeled placeholder only if the user explicitly
wants to move forward without real assets.

**Producing multiple videos for the same brand in one batch?** Stage the
brand's cropped/base64 logo and embedded font CSS *once* in a shared
location, and have every video reference those files rather than
re-cropping the logo or re-fetching fonts per video -- identical output,
faster, and avoids redundant npm/font-fetch work.

### 2. Nail down the ask

Sensible defaults if the user doesn't specify: 9:16 (1080x1920), 20-35s
if silent / whatever the VO naturally runs if scripted, 5-8 scenes (more
for a detailed 45-60s+ explainer -- 10-13 is normal there), hard cuts
with a brand-colored wipe transition. Confirm anything that isn't
a sensible default -- platform (Reels/TikTok/Shorts all use the same
9:16 master; ask if they specifically need a native square or 4:5 too),
whether voice-over is wanted now or this is a silent pass first, and
what the single most important thing to say is (the hook and the CTA
matter far more than the middle).

**Producing several videos on different angles for the same brand?**
Give each one a genuinely distinct pain point/scenario/proof mechanism --
not just reworded copy over the same structure. Draw on whatever angle
inventory the brand already has (an existing ad library, prior campaign
briefs) so each video targets a different buyer hesitation rather than
overlapping ground.

### 3. Script and storyboard before building

Sketch scene beats in plain language first (hook / problem or context /
brand reveal / offer or mechanism / proof or differentiators / guarantee
or urgency / CTA -- adapt freely, this isn't a fixed template). Run the
claims check (`references/brand_claims.md`) against any stat or outcome
you're tempted to use. If VO is wanted, write the per-scene script now
too (`references/vo_sync.md` step 1) -- get the words approved before
generating anything, since regenerating costs ElevenLabs credits and time.

### 4. Build the scene HTML

Copy `assets/scene_template.html` into the working directory and extend
it -- don't write the render loop from scratch. Set the brand tokens,
add/duplicate scene `<div>`s for each beat, write the copy, embed the
logo. Read `references/scene_architecture.md` fully before this step;
it documents a markup bug in the word-reveal helper that's easy to
reintroduce if you're not aware of it, plus the logo crop/embed steps.
If text carries the spot, read `references/kinetic_typography.md` too --
it has a DOM-building text helper that sidesteps the markup bug's whole
class of failure, plus the motion vocabulary.

### 5. Preview before committing to a full render

Render a handful of representative frames (one per scene, plus one from
the *middle* of any text-reveal animation, not just t=0 -- markup bugs
in word reveals often only show up mid-animation) and look at them
before spending the time on a full frame-by-frame render:

```bash
python3 scripts/capture_frames.py scene.html 30 <duration> preview/ --start 0 --end 1
# then call window.render(t) at spot-check times via a small inline script,
# or just render a few full chunks and montage a handful of frames from them
```
In practice: render the full frame set in chunks (step 6), then pull a
handful of frames from the finished chunks with `ffmpeg -ss <t> -i
video.mp4 -frames:v 1` once step 7 has run once -- catching a bug after
one full pass and fixing it before final QC is normal and cheap; the
expensive mistake is skipping frame inspection entirely and only
watching the finished video once at the end.

### 6. Render frames

```bash
python3 scripts/capture_frames.py scene.html <fps> <duration> frames/ --start 0 --end 300
python3 scripts/capture_frames.py scene.html <fps> <duration> frames/ --start 300 --end 600
# ...continue in ~250-350 frame chunks until the full duration is covered
```
Chunk regardless of scene complexity -- this keeps each call well under
any single-tool-call time limit. Frames are deterministic, so chunk
boundaries don't affect output; if one scene's timing changes later,
only that scene's frame range needs re-rendering. **Producing multiple
videos in parallel?** Each video's chunks can render as separate
background processes/agents simultaneously -- they don't share state.

**Before encoding, verify the frame sequence has no gaps -- not just a
correct total count.** A chunk boundary picked up by a different process
(a resumed agent, a manually-issued `--start`/`--end` that's off by one
from where the last chunk actually stopped) can silently drop exactly one
frame. The total file count still looks *close* to right, so a plain
`ls frames | wc -l` can pass a sanity check while one index is missing.
`encode_video.py`'s `ffmpeg -i frames/f%05d.png` uses the image2
demuxer's sequential-numbering mode, which **stops at the first missing
index** with no error or warning -- the encode "succeeds" and produces a
shorter, truncated video with no indication anything went wrong. This is
a real failure mode, not a hypothetical: a batch run hit it and silently
produced a 30-second file from a script that should have run 48 seconds,
because frame 900 alone was missing at a resume boundary. Check for gaps
explicitly before every encode, especially after any resume/retry of a
partial render -- `scripts/check_frame_gaps.py` does this and prints
ready-to-run commands for exactly the missing indices:
```bash
python3 scripts/check_frame_gaps.py frames/ <total_frames> --html scene.html --duration <duration>
```
Exit code 0 means safe to encode; exit code 1 prints the gaps and the
render commands to fill them -- run those before encoding, don't just
re-run a whole chunk and hope.

### 7. Voice-over (if wanted)

Full workflow in `references/vo_sync.md` -- read it before generating
any audio. Short version: generate per-scene lines via ElevenLabs, get
the files back (see `vo_sync.md` for the environment-dependent download
step), trim/pad/concat with `scripts/build_vo_track.py`, use its output
durations as the scene cut points, then optionally retime individual
on-screen elements to the words/phrases within each scene using the
detected internal gaps.

If VO changes the scene durations (the normal case when building fresh
around a script), update the `SC` array in the HTML and re-render only
the frames whose timing changed before moving to step 8.

### 8. Background music/SFX (if wanted)

Full workflow in `references/audio_design.md`. Short version: once
`master_vo.wav` and its scene-cut timestamps exist, one call to
`scripts/build_audio_bed.py` produces a subtle synthesized ambient pad
plus whoosh/chime transients, sidechain-ducked under the VO and
loudness-normalized, frame-exact with the video.

### 9. Encode and deliver

```bash
python3 scripts/encode_video.py --frames frames/ --fps 30 --out reel.mp4 \
  [--audio vo_out/master_vo.wav  # or sfx/master_mix.wav if step 8 ran] \
  [--crop 1080x1350+0+285 --crop-out reel_4x5.mp4]
```
QC before delivering: a contact-sheet montage with one frame per scene
(`scripts/contact_sheet.py --video reel.mp4 --duration <duration> --out contact_sheet.jpg`
-- sampling from the *encoded MP4*, not the raw PNGs, catches anything
the encode step itself broke), and, if there's VO, the waveform/level
checks in `vo_sync.md` step 6 (run them on the *final mixed* track if
step 8 ran, not just the raw VO). Deliver the final MP4(s) directly to
the user, consolidated into a single delivery folder if producing more
than one -- clear sequential names (`01_Angle_45s.mp4`, ...) beat leaving
each video buried in its own working directory. Include the scene HTML
itself as a deliverable alongside the video(s) -- it's the editable
source if the person wants copy or timing tweaks without a full
re-render from scratch. If `kinetic_typography.md`'s live `?play` mode
is wired up, mention it -- it lets the person watch the exact cut with
sound before deciding on changes, with no re-render needed.

### 10. Publish (only if asked)

Full workflow in `references/publishing.md`. Confirm the exact caption
with the user before publishing -- this is a public, effectively
irreversible action every time, not just the first time in a campaign.

## Common follow-up requests

- **"Add voice-over to this"** -- if the video already exists silently,
  go to `references/vo_sync.md` and use `"pad"` mode to fit VO to the
  existing cuts, or offer to let the cuts move to match natural VO pacing
  instead (their choice -- flag the tradeoff).
- **"Make the same thing for [other brand]"** -- treat as a new brand
  from step 1. Do not reuse the previous brand's colors, fonts, logo, or
  claims; do reuse the scene structure/pacing approach if it fits.
- **"Give me a square/4:5 version too"** -- use `--crop` on the existing
  master; no need to re-render frames unless the safe-area framing
  genuinely doesn't work at the new aspect (call this out if so, rather
  than delivering a badly-cropped version).
- **"Make N more videos, different angles"** -- stage shared brand
  assets once (step 1's note), write N distinct scripts up front, then
  produce each video as an independent background task/agent so they run
  concurrently rather than one at a time. Keep each video in its own
  working directory; only the brand asset files (logo, font CSS) should
  be shared.
- **"Post this to Instagram/Facebook"** -- `references/publishing.md`.
  Always verify the target account explicitly rather than trusting a
  connection's default, and read the caption back after publishing to
  confirm it matches what was approved.

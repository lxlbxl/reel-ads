# Voice-over sync (ElevenLabs)

Voice-over is optional -- many Reels ship silent (with a null audio track,
see `encode_video.py`). Only go through this when the person asks for VO,
narration, or "add a voiceover."

## 1. Write the script broken into per-scene lines

One line per scene/beat, matched to what that scene shows. Read it out
loud (mentally) for pace -- ad VO runs faster and punchier than
conversational speech. Show the person the full script before generating
audio; regenerating costs ElevenLabs credits and time, so get the words
right first.

## 2. Generate audio via the ElevenLabs tool

Call `ElevenLabs:text_to_speech` once per line (not one giant multi-scene
call) -- separate calls give you a clean per-scene duration to retime
against, and a slight prosodic reset between clips is fine, even
desirable, for a hard-cut ad style.

There is no tool available to browse the account's voice library from
here. Omit `voice_id` to use the default voice, and say plainly that
you're doing so -- if the person has a specific `voice_id` they use
elsewhere for this brand, ask, and pass it explicitly next time.

## 3. THE GOTCHA: you cannot fetch the audio bytes automatically

The tool returns a presigned download link on `storage.googleapis.com`.
In this environment, that domain is blocked both ways:
- `web_fetch` refuses it (`PERMISSIONS_ERROR` -- not a prior search/fetch result)
- the bash sandbox's network egress also refuses it (`x-deny-reason:
  host_not_allowed`)

There is no way to pull the mp3 bytes into the sandbox directly. Don't
spend turns retrying this -- go straight to one of:

- **Ask the person to allow `storage.googleapis.com`** in this chat's
  network settings, if they want a fully hands-off flow next time.
- **Give them the download links and have them re-upload the files.**
  This is the reliable default. The links expire ~15 minutes after
  generation, so generate all of them and post all the links in the
  same message, and ask for all files back in one upload.

Once the files land in `/mnt/user-data/uploads/`, map them back to
scenes **by filename** -- ElevenLabs names the file after its own
history-item ID, which is unique and was already in the link you posted,
so matching is exact (no need to rely on upload order or ask which is
which).

## 4. Build the VO track with build_vo_track.py

Write a manifest and run the script:

```json
[
  {"name": "scene1_hook", "mp3": "raw/scene1_hook.mp3", "mode": "natural"},
  {"name": "scene2_offer", "mp3": "raw/scene2_offer.mp3", "mode": "natural"}
]
```
```bash
python3 scripts/build_vo_track.py manifest.json vo_out/
```

**Choosing "natural" vs "pad":**
- Building a fresh video around the VO (normal case): `"natural"` for
  every segment. The script trims leading and trailing silence and hands
  back each clip's actual spoken length -- use those durations as the
  scene's `t0`/`t1` directly. Don't force speech into a duration you
  picked before recording; let the read set the pace and give scenes the
  time they need. A 20s silent storyboard commonly becomes ~28-32s once
  real VO is added -- that's normal, say so, don't fight it by speeding
  up the read.
- Retrofitting VO onto a video whose cuts are already locked (e.g. the
  person approved a silent cut and now wants narration added without
  changing edit points): `"pad"` with `target_duration` set to each
  scene's existing length. If a line is naturally longer than the scene
  it's being fit into, the script refuses to truncate mid-word and falls
  back to the natural length -- when that happens, widen that scene
  rather than cut the audio.

The script's output `vo_summary.json` gives per-segment `t0`/`t1` --
paste these straight into the HTML's `SC` array. It also gives
`internal_gaps`: the pauses already present between phrases within each
clip (e.g. between "AI receptionist." and "AI sales rep." in a spoken
list), offset into that clip's own trimmed timeline. Use these as anchor
points for word/phrase-level retiming (step 5) rather than guessing.

## 5. Word/phrase-level retiming (the polish pass)

Overall scene-cut sync (step 4) gets the cuts right. For a tighter feel,
sync individual on-screen elements to the words that name them:

- A list read as "AI receptionist. AI sales rep. AI support agent." with
  `internal_gaps` at, say, `[[0.97,1.14],[1.94,2.34]]` means phrase 2
  starts at 1.14s and phrase 3 at 2.34s -- set those three list rows'
  reveal-start times to `[~0, 1.14, 2.34]` instead of an evenly-spaced
  guess.
- A CTA line that says the URL near the end of the sentence should have
  the on-screen button/URL appear at the proportional word position in
  the clip, not at scene-start -- e.g. if "us dot example dot com" is the
  last 5 of 12 words, place it at roughly 58% into the clip's duration.
- If on-screen caption text doesn't word-for-word match the VO line
  (common when the visual copy is punchier/shorter), that's fine as
  reinforcement rather than a caption -- but reword it to not contradict
  or duplicate awkwardly, and retime its appearance to roughly when the
  VO reaches that idea.

This step is what separates "the video has narration" from "the video
was made for this narration" -- worth the extra pass whenever the person
asks for VO to be *synced*, not just present.

## 6. Mux and QC

`encode_video.py --audio vo_out/master_vo.wav` mutes in the real track
with `-shortest` so any sub-frame rounding mismatch between video length
(`frames/fps`) and audio length resolves cleanly at the end rather than
leaving a gap or truncating a word.

Before delivering, check:
- **Contact sheet**: grab a frame from inside every scene (not just at
  cuts) and montage them -- catches both timing and rendering bugs at
  once (see `scene_architecture.md`'s tag-splitting gotcha, which only
  shows up mid-reveal, not at t=0).
- **Waveform sanity**: `ffmpeg -i master_vo.wav -filter_complex
  showwavespic=s=1200x200 waveform.png` -- should show one clear speech
  burst per scene, no long dead-air stretches, no abrupt clipped-looking
  cutoffs at segment boundaries.
- **Levels**: `ffmpeg -i master_vo.wav -af astats -f null -` and check
  `Peak level dB` (should be well under 0, no clipping) and `RMS level
  dB` (should be in a reasonable -20 to -30 range for spoken VO, not
  buried at -40+ or slammed near 0).

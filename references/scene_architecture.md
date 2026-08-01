# Scene architecture

Start from `assets/scene_template.html` and extend it. Don't build the
render loop from scratch each time -- copy the template, then add scenes,
brand tokens, and copy.

## The one rule that matters: render(t) must be a pure function

Never use CSS `@keyframes`/`transition`, and never use
`requestAnimationFrame`. Headless screenshot capture runs slower than real
time (roughly 0.15-0.3s per frame depending on scene complexity), so
anything driven by the wall clock or by CSS transitions will drift,
stutter, or simply not have finished animating when the frame is captured.

Instead, every visual property must be computed directly from the `t`
argument passed into `window.render(t)`. `capture_frames.py` calls
`render(i/fps)` for each frame index `i` and screenshots the result --
this makes the render fully deterministic: the same `t` always produces
pixel-identical output, so frames can be re-rendered individually if one
scene's timing changes, without re-rendering the whole video.

## Scene table (SC) and scene switching

```js
const SC = [
  {el:'s1', t0:0.0, t1:3.0},
  {el:'s2', t0:3.0, t1:6.0},
];
```
`render(t)` finds which scene's `[t0,t1)` contains `t`, toggles an `.on`
class that shows/hides that scene's `<div>` (all scenes are absolutely
positioned and stacked; only `.on` ones display), and computes `lt = t -
t0` -- elapsed seconds within the current scene -- which every animation
inside that scene block is keyed off of.

**If this ad has voice-over**, `t0`/`t1` should come directly from
`build_vo_track.py`'s `vo_summary.json`, not be hand-picked. See
`references/vo_sync.md`.

## Safe area

1080x1920 is the full canvas, but Reels/TikTok/Shorts UI (captions,
profile chip, like/comment/share buttons, caption text) covers roughly the
top 150px and bottom 260px. Keep all real content inside `.safe` (already
scoped to a safe box in the template). For a square (1:1) or 4:5 delivery,
the safe area shrinks proportionally -- if a client needs those natively
rather than as a crop, ask, and adjust `.safe`'s box accordingly rather
than just changing canvas width.

## Word-by-word text reveal -- the tag-splitting gotcha

The `words()` helper in the template splits a line into per-word `<span>`s
so each word can animate in independently. If you need one word colored
(brand accent, a number, etc.), **do not** embed a raw HTML tag with a
space in its attributes directly in the source string:

```
// BROKEN -- do not do this:
words(el, 'Called back at <b style="color:#FF3300">7:42 PM</b> last night')
```

`split(' ')` will cut `<b style="color:#FF3300">` in half at the space
between `<b` and `style=`, producing two `.w` spans that each contain a
fragment of broken markup -- the raw tag text becomes visible on screen
(`STYLE="COLOR:#FF3300">7:42` etc.). This is easy to miss in a quick
preview and easy to catch by rendering one frame from the middle of the
reveal, not just t=0.

Use the `**word**` marker instead (already implemented in the template's
`words()`): wrap each accented word in double-asterisks, one word at a
time, e.g. `'Called back at **7:42** **PM** last night'`. Each marker only
ever wraps a single space-free token so the split can never land inside
a tag.

For a real brand mark/logo that includes its own colored lettering,
skip `words()` entirely for that element -- render it as a single `<img>`
(see Logo handling below), not as reconstructed text.

## Logo handling

If the user uploads a raster logo (PNG/JPG), two things almost always
need doing before it looks right on screen:

1. **Auto-crop the padding.** App-icon exports (the square rounded-corner
   tile format) nearly always ship with generous white/transparent margin
   around the actual mark. Crop to content before placing it, or it'll
   look like a small icon floating in a big white box that doesn't match
   either a light or dark scene background:

   ```python
   from PIL import Image, ImageChops
   im = Image.open(src).convert('RGB')
   bg = Image.new('RGB', im.size, (255,255,255))
   diff = ImageChops.difference(im, bg).point(lambda p: 255 if p>18 else 0)
   bbox = diff.getbbox()
   pad = 6
   l,t,r,b = bbox
   im.crop((max(0,l-pad), max(0,t-pad), min(im.width,r+pad), min(im.height,b+pad))).save(out)
   ```

2. **Downscale before embedding, then base64-embed it.** A source logo is
   often 1000px+ on a side; the largest it'll ever render in a 1080-wide
   scene is a few hundred px, so resize down to ~800px on the long edge
   first (keeps the final HTML file's size sane -- a few hundred KB
   instead of multiple MB). Embed as a `data:` URI so the scene HTML stays
   a single self-contained file with no relative-path dependency:

   ```python
   import base64
   b64 = base64.b64encode(open(resized_png,'rb').read()).decode()
   # in JS: document.getElementById('logoEl').src = 'data:image/png;base64,' + b64
   ```
   Set the base64 string via a JS constant assigned once at the top of
   the script (`const LOGO_SRC = 'data:image/png;base64,...'; el.src =
   LOGO_SRC;`), not inlined twice in the HTML `src=` attributes -- keeps
   the file from carrying two multi-hundred-KB copies of the same string
   if the logo appears in more than one scene.

Verify the logo actually rendered (not a broken-image icon) before
spending a full render pass on it -- screenshot the scene and sample a
pixel where the logo should be; if it doesn't match the expected brand
color, the `src` didn't load.

## Windows/git-bash: don't embed Unix-style paths in `python -c`

If the shell is git-bash on Windows (check for a Bash tool description
mentioning "Git Bash (POSIX sh)" or paths like `/c/Users/...`), MSYS
auto-converts path-like substrings in command-line arguments to Windows
paths -- and this conversion is unreliable across a multi-path
`python -c "..."` string. A `glob.glob('/c/Users/.../qc_check/*.jpg')`
inside such a string can read files fine (that occurrence got converted)
while a second path a few lines later (`open('/c/Users/.../out.jpg')`)
fails with `FileNotFoundError`, because the same string wasn't converted
consistently. It's a real failure mode, not a hypothetical -- it happened
mid-batch on this project.

The fix: never pass a Python script containing filesystem paths via
`-c`. Write it to a small `.py` file with the `Write` tool (paths as
plain string literals inside the file are never touched by shell argv
conversion) and run `python script.py [args]`. This applies to any
one-liner in this workflow that touches multiple paths -- logo cropping,
contact-sheet montages, the frame-gap check in `SKILL.md` step 6, etc.

Pull the brand's real fonts via `@fontsource` on npm rather than
guessing a lookalike, when the brand's actual typeface is identifiable
(from the site's CSS, a shared brand-guideline doc, or by asking):

```bash
npm install @fontsource/<font-name>
```
Font files land in `node_modules/@fontsource/<name>/files/*.woff2` --
reference them with relative `@font-face src: url(...)` paths, or read
the file and base64-embed it the same way as the logo if the HTML needs
to be portable outside this working directory.

If the exact brand font can't be identified or sourced, pick a
comparable pairing (e.g. a bold grotesque for display + a plain sans for
body) and say so plainly rather than presenting a guess as the confirmed
brand font.

## Brand tokens (CSS variables)

Keep every brand-specific value in the `:root { --ink; --paper; --signal;
--mute; }` block (or add more as needed -- a second accent, a specific
gray, etc.). Nothing else in the file should hardcode a hex color or a
font name directly -- this is what makes re-skinning the same scene
structure for a different brand a quick edit instead of a rewrite.

Pull the accent color from the brand's actual site when there is one --
`meta theme-color` in the page head is a fast, reliable source; failing
that, sample it from a provided logo or ask.

## Marquee / ticker (optional pattern)

A horizontally-scrolling text ticker (used in the ai20 spot for
"Revenue. / Speed. / Done-For-You. / 30 Days.") reads well as a
recurring background element in a features/offer-list scene. Drive its
position from the *global* `t` (not the per-scene `lt`), so it scrolls
continuously across cuts rather than resetting:

```js
$('mq').style.transform = `translateX(${-((t*185)%SCROLL_WIDTH)}px)`;
```

## Claims and copy -- check before locking the script

Before finalizing on-screen copy or VO lines, check whether any number,
stat, or result claim on the brand's own site is labeled illustrative,
modeled, hypothetical, or a placeholder ("Illustrative Scenario" is a
real example seen in the wild). If so, do not present it as a real,
unqualified outcome in paid ad copy -- that's an FTC substantiation
problem in the US and a rejection risk on Meta/TikTok ad review, whoever
the client is. Lead with something the client can actually stand behind:
a stated guarantee, a named offer, a generic capability claim, or a
qualified statement ("modeled outcome" / "illustrative"). See
`references/brand_claims.md`.

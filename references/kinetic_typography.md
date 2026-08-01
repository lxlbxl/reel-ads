# Kinetic typography

Text that fades in is not kinetic. Text that *arrives* is. This file is the
motion vocabulary that turns a slideshow of captions into something that
reads as designed -- and the layout rules that keep it from wrapping or
floating in dead space.

Read this whenever text is the primary visual (explainers, offer spots,
list/step ads). For a silent b-roll cut with two words on screen, the base
template is enough.

Every technique here is still a **pure function of `t`** -- no CSS
transitions, no keyframes, no rAF. That constraint is what lets you
re-render frame 900 alone after a timing tweak.

## Fonts: pair a face with attitude and a face that reads

Two families is the sweet spot. One does the shouting, one does the
talking:

- **Display/hero** -- a heavy condensed face for the words that carry the
  spot (`STRANGER`, `VERIFIED`, `₦20,000`, `48 HOURS`). Condensed matters
  in 9:16: it fits far more characters per line at a huge size. Anton is a
  reliable default.
- **Headline/body** -- a geometric sans at 700-800 for sentences. Poppins,
  Plus Jakarta Sans, Manrope.

Pick the body face to sit *with* the brand's wordmark, not to fight it. A
rounded geometric logo next to a hard grotesque reads as a mismatch.

```bash
npm install @fontsource/anton @fontsource/poppins
```

Base64-embed the woff2 files so the scene HTML stays one portable file
(the whole set above is ~40KB -- negligible next to the logo):

```python
import base64
def b64(p): return base64.b64encode(open(p,'rb').read()).decode()
css = f"@font-face{{font-family:'Anton';font-weight:400;font-display:block;" \
      f"src:url(data:font/woff2;base64,{b64(path)}) format('woff2')}}"
```

Use `font-display:block`, not `swap`. `capture_frames.py` waits on
`document.fonts.status === 'loaded'`, but `swap` can still paint a
fallback for the first frames of a chunk.

**Glyph coverage bites.** Latin subsets routinely omit currency signs --
`₦` (U+20A6) is missing from both Anton and Poppins. Always end the stack
with a system fallback (`'Anton','Poppins',Arial,sans-serif`) so the glyph
renders from Arial instead of tofu, and *look at a rendered frame* of any
scene with an unusual character before committing to a full pass. Check
coverage up front if fontTools is available:

```python
from fontTools.ttLib import TTFont
print(0x20A6 in TTFont(path).getBestCmap())
```

## Budget your line widths before you render

Wrapping is the single most common way a kinetic layout falls apart -- a
hero line breaking mid-word (`MORE TIME BAC / K`) looks broken, not
stylish. At 1080 wide with 76px margins you have **928px**.

Rough advance per character (multiply by font-size):

| Face | weight | ~advance |
|---|---|---|
| Poppins | 800 | 0.58em |
| Anton | 400 | 0.45em |

So Poppins 800 at 86px fits ~18 characters; Anton at 240px fits ~8. Count
the characters in every line while writing copy, and **split long lines in
the source** rather than letting the browser wrap them:

```js
// wraps unpredictably -- 25 chars at 86px = 1247px
line(el, 'with their ~National_I-D~', 'h2');
// deliberate, fits
line(el, 'with their', 'h2');
line(el, '~National_I-D~', 'h2');
```

## Use the vertical, don't just centre in it

The base template's safe box leaves the bottom third empty. For a
text-driven spot:

```css
.safe{position:absolute;left:76px;right:76px;top:230px;height:1430px;
  display:flex;flex-direction:column;justify-content:center;align-items:flex-start}
```

A workable scale for 1080x1920 (go bigger than instinct says -- these are
read at thumbnail size on a phone):

```css
.kick{font:800 34px/1.2}      /* eyebrow, letter-spacing .22em, uppercase */
.h1  {font:800 118px/1.06}    /* primary headline */
.h2  {font:800 86px/1.13}     /* secondary headline */
.hero{font:400 240px/0.86}    /* Anton impact word; .sm 178px, .xl 300px */
.body{font:700 54px/1.42}
```

Then fill the leftover frame with structure rather than air:

- **Ghosted step numerals** -- `01/02/03` in the display face at ~380px,
  `color:rgba(255,255,255,.09)`, `z-index:-1`, bled off the right edge.
- **A progress bar** at the bottom of the safe band. It anchors the lower
  third, and a visible "how much is left" measurably helps retention.
  ```js
  $('progfill').style.transform = `scaleX(${t/DURATION})`;
  ```
- **A living background** (below).

## Build text as DOM, never as parsed markup

The base template's `words()` helper splits a string on spaces and
re-emits HTML, which is why `<b style="...">` explodes (see
`scene_architecture.md`). Sidestep the entire bug class: build spans with
`textContent` and set colour via `style`, so a marker can never land
inside a tag.

```js
function tokens(str){
  return str.split(' ').filter(Boolean).map(w=>{
    if(w.length>2 && w[0]==='*' && w[w.length-1]==='*') return {t:w.slice(1,-1).replace(/_/g,' '), s:'a'};
    if(w.length>2 && w[0]==='~' && w[w.length-1]==='~') return {t:w.slice(1,-1).replace(/_/g,' '), s:'h'};
    return {t:w.replace(/_/g,' '), s:'p'};
  });
}
function line(parent, str, cls){
  const tks=tokens(str);
  const ln=document.createElement('div'); ln.className='ln';
  const inner=document.createElement('div'); inner.className='lni '+cls;
  tks.forEach((tk,i)=>{
    const w=document.createElement('span'); w.className='w';
    if(tk.s==='h'){
      const hl=document.createElement('span'); hl.className='hl'; w.appendChild(hl);
      const tx=document.createElement('span'); tx.className='tx hlx'; tx.textContent=tk.t; w.appendChild(tx);
    }else{
      const tx=document.createElement('span'); tx.className='tx'; tx.textContent=tk.t;
      if(tk.s==='a') tx.style.color='var(--signal)';
      w.appendChild(tx);
    }
    inner.appendChild(w);
    if(i<tks.length-1) inner.appendChild(document.createTextNode(' '));
  });
  ln.appendChild(inner); parent.appendChild(ln);
  return [...inner.querySelectorAll('.w')];
}
```

`_` becomes a space *inside* a token, so a multi-word phrase can still be
one highlighted unit (`~National_I-D~`) while every marker still wraps a
single space-free token.

**A marker must never span a space.** `**No background check.**` produces
literal asterisks on screen, because the split lands between `**No` and
`check.**` and neither fragment matches the marker regex. Mark each word:
`No **background** **check.**` This is the same failure the base template
warns about, in a new costume -- and it only shows up mid-reveal, so it
survives a t=0 preview.

## The motion library

```css
.ln {display:block;overflow:hidden;padding:0 .06em .12em 0}  /* the mask */
.lni{display:block;white-space:pre-wrap}
.w  {display:inline-block;position:relative;will-change:transform,opacity}
.lt {display:inline-block;will-change:transform,opacity}
```

**Mask reveal (the workhorse).** Words rise out of a clipped box, stagger
per word, overshoot slightly, with a touch of rotation:

```js
function showWords(ws, lt, o){
  o=o||{};
  const start=o.start||0, stag=(o.stag===undefined?0.062:o.stag), dur=o.dur||0.46,
        dy=(o.dy===undefined?118:o.dy), rot=(o.rot===undefined?4:o.rot);
  ws.forEach((w,i)=>{
    const q=cl((lt-start-i*stag)/dur,0,1), e=outBack(q);
    w.style.opacity = q<=0?0:cl(q*2.6,0,1);
    const fl = Math.sin(lt*1.6 + i*0.7)*2.2*q;          // settle float
    w.style.transform = `translateY(${(1-e)*dy + fl}%) rotate(${(1-e)*rot}deg)`;
    const hl=w.querySelector('.hl');
    if(hl){
      const hq=cl((lt-start-i*stag-0.16)/0.36,0,1);
      hl.style.transform=`scaleX(${outExpo(hq)})`;
      const tx=w.querySelector('.hlx'); if(tx) tx.style.color = hq>0.5 ? '#08302E' : '#fff';
    }
  });
}
```

`dy` is in **percent of the word's own height**, so it works at any type
size without retuning.

**The settle float is what sells it.** That `Math.sin(lt*1.6 + i*0.7)*2.2`
term keeps each word breathing on a slightly different phase after it
lands. Without it, a scene that holds for 6 seconds is a still image for
5.5 of them. It is the cheapest possible upgrade and the one people
actually notice.

**Per-letter slam** for hero words -- scale up from 0.55 with an overshoot,
tighter stagger, plus a micro-breath once settled:

```js
function showLetters(ls, lt, o){
  o=o||{};
  const start=o.start||0, stag=(o.stag===undefined?0.026:o.stag), dur=o.dur||0.4;
  ls.forEach((s,i)=>{
    const q=cl((lt-start-i*stag)/dur,0,1), e=outBack(q);
    s.style.opacity = q<=0?0:cl(q*3,0,1);
    const br = q>=1 ? 1+Math.sin(lt*2.4+i*0.5)*0.012 : 1;
    s.style.transform = `translateY(${(1-e)*70}px) scale(${(0.55+e*0.45)*br})`;
  });
}
```

Build the letters with one span per character (`textContent`, never
`innerHTML`), preserving spaces.

**Highlight bar swipe** -- a brand-coloured bar wipes left-to-right behind
a phrase and the text flips to the dark brand colour as it passes. Handled
inline in `showWords` above; the CSS:

```css
.hl{position:absolute;left:-.09em;right:-.09em;top:.08em;bottom:.12em;
  background:var(--signal);border-radius:14px;
  transform-origin:left center;transform:scaleX(0);z-index:0}
.tx{position:relative;z-index:1;display:inline-block}
```

Use it on at most one phrase per scene -- it's the loudest move in the set.

**Strikethrough draw** for negatives ("No I-D checks"), timed just after
the word lands:

```js
S3N1.strike.style.transform = `scaleX(${outExpo(cl((lt-0.44)/0.3,0,1))})`;
```

**Counters** for any number the VO says aloud. Far more alive than a static
figure, and it gives the eye something to track:

```js
function counter(el, lt, from, to, start, dur, prefix){
  const q=cl((lt-start)/dur,0,1), e=outCubic(q);
  el.textContent=(prefix||'')+Math.round(from+(to-from)*e).toLocaleString('en-US');
  const done=cl((lt-start-dur)/0.34,0,1);
  el.style.transformOrigin='left center';
  el.style.transform=`scale(${q>=1 ? 1+0.09*(1-outBack(done)) : 1})`;   // land-pop
  el.style.opacity = lt<start ? 0 : 1;
}
```

Time the counter off `internal_gaps` so the number **finishes on the
spoken word**, then verify it holds long enough to read -- 1s+ after
settling. A counter that completes 0.3s before the cut is wasted; shorten
`dur` and start it earlier rather than letting it run to the edge.

**Scene exits.** Hard-cutting from fully-present text is the tell of a
template. Lift and fade the whole scene in its last ~0.3s:

```js
function exitSafe(el, lt, exitAt, dur){
  dur=dur||0.32;
  const q=cl((lt-exitAt)/dur,0,1);
  if(q<=0){ el.style.opacity=1; el.style.marginTop='0px'; return; }
  el.style.opacity=1-q;
  el.style.marginTop=(-outCubic(q)*54)+'px';
}
// call with: exitSafe($('s1s'), lt, len-0.34)
```

Drive it off `len = cur.t1 - cur.t0` so it stays correct when VO retiming
moves the cut.

## A background that is never still

Put one background layer *behind all scenes* rather than a `.bg` div per
scene, and drive it from **global `t`** so the motion carries across cuts
instead of resetting:

```html
<div id="bgbase"></div>
<div id="bgfx"><div class="blob" id="b1"></div><div class="blob" id="b2"></div></div>
<div id="vig"></div>
```
```js
$('bgbase').style.background = cur.bg==='paper' ? 'var(--paper)' : 'var(--ink)';
$('b1').style.transform = `translate(${Math.sin(t*0.23)*170}px, ${Math.cos(t*0.17)*150}px) scale(${1+Math.sin(t*0.31)*0.09})`;
$('b2').style.transform = `translate(${Math.cos(t*0.19)*190}px, ${Math.sin(t*0.26)*160}px) scale(${1+Math.cos(t*0.28)*0.10})`;
```

Blobs are large `radial-gradient` circles at low opacity. Use the gradient's
own falloff for softness -- **never `filter:blur()`**, which is expensive on
every one of ~1800 frames. Scenes then declare only a `bg` token in the
`SC` table (`{el:'s6', t0:19.002, t1:25.010, bg:'paper'}`), and a vignette
on top keeps the centre readable.

Give the cut wipe a little skew so it reads as designed rather than default:

```js
W.style.transform=`translateY(${y}%) skewY(${(0.5-Math.abs(ph-0.5))*-7}deg)`;
```

## Live playback mode

Add a guarded playback path so the same file can be watched at full speed
with audio, without ever interfering with capture (`capture_frames.py`
loads the bare path, so the query string is absent and the loop never
arms):

```js
if(location.search.indexOf('play')>=0){
  const s=Math.min(innerWidth/1080, innerHeight/1920);
  $('stage').style.transformOrigin='top left';
  $('stage').style.transform=`scale(${s})`;      // fit the window
  const a=new Audio('mix.m4a');
  // click-to-start gate (browsers block autoplay), then:
  const tick=()=>{ window.render(a.currentTime||0); requestAnimationFrame(tick); };
}
```

Driving `render()` off `audio.currentTime` rather than a wall clock makes
the preview **frame-accurate to the final encode** -- what they approve is
what ships. Keep a `performance.now()` fallback for when audio fails to
load. Ship this alongside the MP4: it is the fastest way for someone to
request a copy or timing change without a re-render.

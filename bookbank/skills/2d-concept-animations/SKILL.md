---
name: 2d-concept-animations
description: >
  Use this skill whenever the task is to explain a concept with an animated,
  interactive 2D visualization — educational animations, concept explainers,
  music theory / math / physics / algorithm visualizations, step-by-step
  animated lessons, or "show me how X works" requests. Triggers include:
  "explain X with an animation", "visualize", "animated lesson", "interactive
  demo of a concept", "2D animation", "canvas animation". Do NOT use for 3D/WebGL
  scenes (use a WebGL skill), video production, or plain static diagrams.
---

# 2D Concept Animations

Build single-file HTML lessons that teach ONE concept through animation the learner
can control. The animation is the explanation — text only supports it.

## Design the lesson before the code

Answer these first, in one or two lines each:

1. **The one concept.** One idea per animation (e.g. "the major scale is a fixed
   recipe of whole/half steps", not "music theory"). If the user asks for a broad
   topic, pick the single most foundational concept and say so.
2. **The domain object.** Animate the real object from the learner's world — a
   guitar fretboard, a number line, a unit circle, an array of boxes — not abstract
   shapes. Recognition is half the teaching.
3. **The "aha".** What should the learner realize? Build the interaction so they
   can trigger the realization themselves (e.g. a key selector proving the same
   recipe works from any root).
4. **The narration beat.** Each animation step gets a short caption update. Plan
   the caption text alongside the motion, not after.

## Technology decision

| Need | Use |
|---|---|
| Default: shapes, motion, step-through lessons | **Canvas 2D** |
| Crisp resolution-independent diagrams, morphing paths | **SVG + JS** (or SMIL-free CSS transitions on SVG attributes) |
| Thousands of moving sprites | **PixiJS** (cdnjs) |
| Pure UI/state transitions, no drawing | **CSS animations/transitions** |
| Sequenced multi-element choreography in DOM/SVG | **GSAP** (cdnjs) if allowed; otherwise a tiny promise-based tween (see below) |

Single self-contained HTML file, no build step, unless the project has one.
In Claude.ai artifacts only `https://cdnjs.cloudflare.com` scripts load.

**Targeting a BookBank book? (offline, `file://`)** Books render with no network,
so a CDN `<script>` (PixiJS, GSAP) and `<script type="module">` both fail — the
latter is CORS-blocked from the null `file://` origin in WKWebView. Good news:
everything this skill actually needs is **inline and dependency-free** — Canvas 2D,
the promise-based `tween`, the WebAudio `pluck`, HiDPI sizing — so a lesson built
from the patterns here is already offline-safe with **no external JS at all**.
Prefer that for books. Only if a lesson genuinely needs PixiJS/GSAP, **vendor it**
into one classic IIFE bundle the same way the `write-book` skill's "3D figures"
section vendors three.js (esbuild `--format=iife` → `assets/vendor/<lib>.iife.js`,
loaded with a plain relative `<script>`) — never a CDN or a module import. Also
follow the book layout rules: `<meta charset="utf-8">` as the page's first line,
lock the canvas to a capped aspect box (`break-inside:avoid`, `max-height`), and
make Play/parameter controls avoid the reader's ← → ↑ page-turn keys.

## Structure of a lesson file

```
<header>   title + 2–3 sentence framing of the concept (plain words, bold the key terms)
<controls> the learner's levers: play button, parameter selectors, "show all" reveal
<canvas>   the animation stage
<caption>  large live label for the current step + one supporting line
<footer>   optional: formula chips / legend that light up in sync with the animation
```

Every lesson must have a **Play** button (never autoplay the teaching sequence)
and at least one **parameter the learner can change** to test the idea themselves.

## Canvas 2D essentials

```js
// HiDPI-correct sizing — blurry canvas is the #1 quality killer
function layout() {
  const dpr = Math.min(devicePixelRatio, 2);
  const w = cv.clientWidth, h = /* derive from w, clamp */;
  cv.style.height = h + 'px';
  cv.width = w * dpr; cv.height = h * dpr;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);   // draw in CSS pixels from here on
}
addEventListener('resize', () => { layout(); draw(); });
```

- **One `draw()` renders the whole frame from state.** Never mutate the canvas
  incrementally; clear and redraw. State drives pixels.
- Redraw only while animating; a settled scene needs no rAF loop.
- Precompute layout geometry (positions of frets, ticks, cells) in `layout()`,
  not per frame.

## Sequenced animation pattern (async/await)

Step-through lessons read best as a linear async function — one `await` per beat:

```js
const wait = ms => new Promise(r => setTimeout(r, reducedMotion ? 40 : ms));

function tween(dur, onFrame) {          // promise-based tween
  return new Promise(res => {
    const t0 = performance.now();
    (function frame(now) {
      const t = Math.min(1, (now - t0) / (reducedMotion ? 1 : dur));
      onFrame(t * t * (3 - 2 * t));     // smoothstep ease
      draw();
      t < 1 ? requestAnimationFrame(frame) : res();
    })(t0);
  });
}

async function playLesson() {
  if (animating) return; animating = true;
  setCaption('Step 1: …');
  await tween(550, e => { marker.x = lerp(x0, x1, e); });
  playSound(note); landMarker();
  await wait(500);
  // …next beats…
  animating = false;
}
```

Rules:
- Guard against double-starts (`if (animating) return`).
- Ease everything the eye follows (smoothstep minimum); linear motion reads as robotic.
- Hop/arc motion (sin bump on y) communicates "discrete jump" better than sliding.
- Leave a **trail** of completed steps visible — the learner should see the whole
  construction at the end, not just the last state.
- 400–700 ms per beat, with 400–600 ms pauses between beats. Faster feels frantic
  for teaching; slower feels broken.

## Sound (when the concept is audible)

Music/rhythm/frequency concepts should be heard. Minimal pluck, no libraries:

```js
let ac = null;
function pluck(midi) {
  ac = ac || new (window.AudioContext || window.webkitAudioContext)();
  const f = 440 * Math.pow(2, (midi - 69) / 12), t = ac.currentTime;
  const o = ac.createOscillator(), g = ac.createGain();
  o.type = 'triangle'; o.frequency.value = f;
  g.gain.setValueAtTime(0.0001, t);
  g.gain.exponentialRampToValueAtTime(0.5, t + 0.01);
  g.gain.exponentialRampToValueAtTime(0.0001, t + 0.9);
  o.connect(g); g.connect(ac.destination); o.start(t); o.stop(t + 1);
}
```

Create the AudioContext lazily inside a user-gesture handler (autoplay policy).

## Visual language for teaching

- **Semantic color, 2–3 max**: one color per meaning (root vs scale note, whole vs
  half step) and keep it consistent between the canvas, the caption, and the legend
  chips. Sync = comprehension.
- Big live caption (20–26px) that names what is happening RIGHT NOW; a smaller
  supporting line explains why.
- Legend/formula chips below the canvas that light up as their step plays —
  connects the animation to the abstract notation.
- Draw the domain object with enough fidelity to be recognized (fret dots, string
  thickness, axis ticks) but no more; decoration competes with the concept.
- Theme the palette to the subject's world (rosewood browns for guitar, chalkboard
  for math) rather than a generic dashboard look.

## Accessibility & robustness checklist

- [ ] `prefers-reduced-motion`: collapse tweens to near-instant, keep the sequence
      and captions (the lesson still works as a step-through).
- [ ] HiDPI canvas sizing (pattern above) + resize handler that recomputes layout.
- [ ] Focus styles on all controls; controls are real `<button>`/`<select>`.
- [ ] Touch-friendly hit targets (≥40px) for interactive canvas elements; use
      pointer events and map `clientX/Y` through `getBoundingClientRect()`.
- [ ] Changing a parameter mid-animation either queues or resets cleanly — never
      corrupts state.
- [ ] Ends with a takeaway caption restating the concept in one sentence.

## Quality bar / self-review

1. Could a beginner say what the concept is after one Play, without reading the header?
2. Does changing the parameter visibly prove the concept generalizes?
3. Is every color doing one job, matched across canvas/caption/legend?
4. Does it read well at 380px wide (phone) and does text stay ≥11px?
5. Is the final frame a complete picture of what was built, not a blank stage?

## Files in this skill

- `assets/lesson-template.html` — skeleton implementing this structure: HiDPI canvas,
  promise tween, caption sync, legend chips, reduced-motion, pluck sound.

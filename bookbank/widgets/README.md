# BookBank shared widget runtime — `book-widgets.js`

The verified interactive-canvas machinery from `fun-with-calculus` (calc.js)
and `spacetime` (spacetime.js), promoted into one runtime every book can
vendor. A book's topic script only writes the *widgets* — the draw/update
functions that make the subject move — and gets the lifecycle for free:

| Concern | Handled by the runtime |
|---|---|
| Boot | DOM scan for `[data-widget]`, one `try/catch` per widget — a broken widget flags its box `widget-failed` and never breaks the page |
| Animation | one shared dt-clamped rAF loop; a widget ticks only while **running** and **on the visible spread** (IntersectionObserver); the loop stops entirely when nothing animates |
| Reduced motion | `prefers-reduced-motion` → animations don't autostart, static first frames still render; an explicit Play press (`start(true)`) overrides |
| Canvas sizing | DPR-correct (capped 2×), refit on `resize` **and** the pager's `bookbank:relayout` event |
| Theming | colors resolved from the book's CSS custom properties (`--ink`, `--accent`, `--rule`, …) — widgets match any theme skin without hardcoding |
| Interaction | `drag()` pointer capture that stops propagation (never reaches nav links); **widgets must not bind arrow keys** — those belong to the pager |

## Vendoring (per book — books stay self-contained)

```bash
mkdir -p "<book-dir>/assets/vendor"
cp "$CLAUDE_PLUGIN_ROOT/widgets/book-widgets.js" "<book-dir>/assets/vendor/"
```

Load order on every page that uses widgets (classic scripts — works from `file://`):

```html
<script src="../assets/vendor/book-widgets.js"></script>
<script src="../assets/widgets.js"></script>   <!-- the book's own widget definitions -->
```

## Markup contract

```html
<figure class="figbox" data-widget="secant" data-fn="square" data-a="1" data-anchor="deriv-fig1">
  <canvas></canvas>
  <div class="controls">
    <input class="h" type="range" min="0.01" max="1.5" step="0.01" value="1">
    <button type="button" class="btn play">▶ Play</button>
  </div>
  <p class="readout"></p>
  <figcaption>The secant sweeps into the tangent as h → 0.</figcaption>
</figure>
```

- `data-widget` names the registered init; other `data-*` are free parameters
  (read them with `W.params(box)` — numbers arrive as numbers).
- The book's CSS must size the canvas with an aspect box + hard cap, exactly
  like images/3D figures (pages are fixed-height spreads that cannot scroll):
  ```css
  .figbox{ break-inside:avoid; }
  .figbox canvas{ width:100%; aspect-ratio:16/9; height:auto; max-height:52vh; display:block; }
  .figbox.widget-failed canvas, .figbox.widget-failed .controls{ display:none; }
  ```
  The `widget-failed` rule keeps a broken widget readable: the figcaption
  (and any static fallback content) stays, the dead canvas goes.

## Writing a widget

```js
BookWidgets.register('secant', function(box, W){
  var cv = box.querySelector('canvas'); if(!cv) return;
  var p = W.params(box);                       // {fn:"square", a:1}
  var C = W.theme();                           // {ink, soft, accent, grid, paper, code}
  var P = W.Plot(cv, { xr:[-0.5,3], yr:[-1,9] });
  var h = 1;
  function draw(){
    if(!P.fit()) return;                       // rect can be 0 mid-relayout
    P.clear(); P.axes({});
    P.curve(function(x){ return x*x; }, C.accent, 2.6);
    // ... seg/dot/label in world coordinates ...
  }
  W.drag(cv, function(sx){ h = Math.max(0.01, P.ix(sx)); draw(); });
  var eng = W.anim(box, function(dt){ h *= Math.pow(0.5, dt); draw(); });
  var btn = box.querySelector('.btn.play');
  if(btn) btn.addEventListener('click', function(){ eng.toggle(true); });
  W.onRelayout(draw);
  draw();                                      // static first frame, always
  eng.start();                                 // no-op under reduced motion
});
```

Rules the runtime expects widgets to follow:

1. **Always draw a static first frame** before starting any animation — that's
   the reduced-motion (and screenshot/print) rendering.
2. **`tick(dt)` is time-based**, not frame-based: `angle += speed * dt`, so a
   paused-and-resumed widget doesn't jump.
3. **Redraw on `W.onRelayout(draw)`** — the spread re-columns on resize and
   after fonts settle; `Plot.fit()` returning false (zero rect) is normal
   mid-relayout, just skip the frame.
4. **No arrow-key bindings, no wheel hijacking** — keys turn pages. Pointer
   interaction inside the canvas only (`W.drag` handles capture+propagation).
5. **Deterministic decoration** — use `W.rng(seed)`, never `Math.random`, so
   every load renders identically (verifiable by screenshot diff).

## Full API

`window.BookWidgets` (also passed as the second init argument):

- `register(name, init)` / `boot(root?)` — registry + scan (auto-boots on
  DOMContentLoaded; late registration re-scans).
- `Plot(canvas, {xr, yr, pad?, colors?})` — world-coordinate plotter:
  `fit clear axes curve seg dot label px py ix iy setXR setYR`, getters
  `W H xr yr ctx`.
- `makeCanvas(host, aspect)` — create+size a canvas from the host width
  (auto-refits); or `fitCanvas(cv)` for a CSS-sized canvas.
- `anim(el, tick)` → `{start(force?), stop(), toggle(force?), running()}`.
- `onRelayout(fn)` — resize + `bookbank:relayout` (the pager must dispatch
  this after `layout()` — the write-book pager reference does).
- `theme()` / `colors(map)` / `cssVar(name, fallback)` — theme-token colors;
  map values are `'--var|fallback'` or literal colors.
- `drag(canvas, onMove(x, y, event))` — pointer-capture drag, local coords.
- `params(box)` — `data-*` attributes as a typed object.
- `fmt(v, d?)`, `niceStep([min,max])`, `rng(seed)`, `reduced`, `version`.

## Verifying

`widgets/demo.html` next to this file exercises the runtime standalone
(plot + animation + drag + params + failure isolation) and reports
PASS/FAIL per check into `#status`. Re-verify it after any change to the
runtime — in a **WKWebView harness or a real browser**, not headless Chrome:
headless Chrome throttles `requestAnimationFrame` on unfocused pages
(`--virtual-time-budget` delivers exactly one frame), so its "anim: dt ticks
arrived" check false-fails there while everything real passes. The 10-line
WKWebView driver pattern (load `file://`, wait ~4s, read `#status`) is the
reference harness — it's the same engine the BookBank app renders with.

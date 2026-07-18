/* ============================================================
   book-widgets.js — BookBank's shared interactive-widget runtime.
   Vendored per book (assets/vendor/book-widgets.js). No network,
   no dependencies; works from file://. Extracted from the proven
   engines in `fun-with-calculus` (calc.js) and `spacetime`
   (spacetime.js), so every book gets the same verified lifecycle:

     - DOM-scan boot:  <figure class="figbox" data-widget="name">
       is wired to the init registered for "name"; one widget
       throwing never breaks the page (per-widget try/catch).
     - One shared requestAnimationFrame loop, dt-clamped; each
       widget animates only while its element is on the visible
       spread (IntersectionObserver) AND its engine is running.
     - prefers-reduced-motion: animations don't autostart; every
       widget still renders its static first frame.
     - DPR-correct canvas sizing (capped 2x), re-fit on `resize`
       and on the pager's `bookbank:relayout` event.
     - Theme-aware colors read from the book's CSS custom
       properties (--ink, --accent, ...), so widgets match the
       book's skin without hardcoding a palette.

   The book's own topic script defines the widgets:

     BookWidgets.register('pendulum', function(box, W){ ... });

   and the runtime does the rest. See widgets/README.md in the
   bookbank plugin for the full API and markup contract.
   ============================================================ */
(function(){
"use strict";
if(window.BookWidgets) return;                 // vendored once per page

var REDUCE = !!(window.matchMedia &&
  window.matchMedia('(prefers-reduced-motion: reduce)').matches);

/* ---------------- theme colors from CSS custom properties ---------------- */
function cssVar(name, fallback){
  var v = getComputedStyle(document.documentElement).getPropertyValue(name);
  v = (v || '').trim();
  return v || fallback || '';
}
/* Resolve {key: '--var' | '--var|fallback' | '#literal'} to concrete colors. */
function colors(map){
  var out = {}, k, spec, parts;
  for(k in map){
    spec = map[k];
    if(spec.charAt(0) === '-'){
      parts = spec.split('|');
      out[k] = cssVar(parts[0], parts[1] || '#888');
    } else out[k] = spec;
  }
  return out;
}
/* The default palette every theme token set provides (see write-book's
   theme contract): enough for most plots without a custom map. */
function theme(){
  return colors({
    ink:   '--ink|#1c1a17',
    soft:  '--ink-soft|#6b6459',
    accent:'--accent|#b45309',
    grid:  '--rule|#d8d2c6',
    paper: '--bg|#faf7f1',
    code:  '--code-bg|#f0ece3'
  });
}

/* ---------------- shared animation loop (pause offscreen) ---------------- */
var anims = [];            // {el, tick(dt), visible, running}
var looping = false;
function loop(t){
  loop.last = loop.last == null ? t : loop.last;
  var dt = Math.min(0.05, (t - loop.last) / 1000);   // clamp long gaps
  loop.last = t;
  var any = false;
  for(var i = 0; i < anims.length; i++){
    var a = anims[i];
    if(a.running && a.visible){ any = true; try{ a.tick(dt); }catch(e){ a.running = false; } }
  }
  if(any){ requestAnimationFrame(loop); }
  else { looping = false; loop.last = null; }        // idle: stop the loop entirely
}
function wake(){ if(!looping){ looping = true; loop.last = null; requestAnimationFrame(loop); } }
var io = ('IntersectionObserver' in window) ? new IntersectionObserver(function(es){
  es.forEach(function(e){
    for(var i = 0; i < anims.length; i++){
      if(anims[i].el === e.target){
        anims[i].visible = e.isIntersecting;
        if(anims[i].visible && anims[i].running) wake();
      }
    }
  });
}, { threshold: [0, 0.01] }) : null;

/* anim(el, tick) -> engine. tick(dt) runs only while running AND el is on
   the visible spread. Under reduced motion start() is a no-op (widgets keep
   their static frame) unless called as start(true) by an explicit user
   gesture — a person pressing Play trumps the ambient preference. */
function anim(el, tick){
  var rec = { el: el, tick: tick, visible: true, running: false };
  anims.push(rec);
  if(io) io.observe(el);
  return {
    start: function(force){ if(REDUCE && !force) return; rec.running = true; wake(); },
    stop: function(){ rec.running = false; },
    toggle: function(force){ if(rec.running) this.stop(); else this.start(force); return rec.running; },
    running: function(){ return rec.running; }
  };
}

/* ---------------- canvas fitting (DPR-correct, relayout-aware) ------------ */
var relayoutFns = [];
function onRelayout(fn){ relayoutFns.push(fn); }
function fireRelayout(){
  for(var i = 0; i < relayoutFns.length; i++){ try{ relayoutFns[i](); }catch(e){} }
}
window.addEventListener('resize', fireRelayout);
window.addEventListener('bookbank:relayout', fireRelayout);   // the pager fires this after layout()

/* Fit a canvas's backing store to its CSS box (rect-based; the CSS decides
   the size — aspect-ratio box + max-height cap, per the skill's sizing
   rules). Returns false while the rect is 0 (e.g. display:none). */
function fitCanvas(cv){
  var r = cv.getBoundingClientRect();
  if(!r.width || !r.height) return false;
  var dpr = Math.min(window.devicePixelRatio || 1, 2);
  var w = Math.round(r.width * dpr), h = Math.round(r.height * dpr);
  if(cv.width !== w || cv.height !== h){ cv.width = w; cv.height = h; }
  cv.getContext('2d').setTransform(dpr, 0, 0, dpr, 0, 0);
  cv.__w = r.width; cv.__h = r.height;
  return true;
}

/* makeCanvas(host, aspect) — create + append a canvas sized from the host's
   width (spacetime.js model), refit automatically on relayout. The caller
   still redraws (subscribe via onRelayout). */
function makeCanvas(host, aspect){
  var cv = document.createElement('canvas');
  host.appendChild(cv);
  var ctx = cv.getContext('2d');
  function fit(){
    var w = host.clientWidth || 480;
    var h = Math.round(w * (aspect || 0.5));
    var dpr = Math.min(window.devicePixelRatio || 1, 2);
    cv.style.width = w + 'px'; cv.style.height = h + 'px';
    cv.width = Math.round(w * dpr); cv.height = Math.round(h * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    cv.__w = w; cv.__h = h;
  }
  fit();
  onRelayout(fit);
  return { cv: cv, ctx: ctx, fit: fit,
           W: function(){ return cv.__w; }, H: function(){ return cv.__h; } };
}

/* ---------------- number formatting + deterministic randomness ------------ */
function niceStep(r){
  var span = r[1] - r[0], raw = span / 6;
  var p = Math.pow(10, Math.floor(Math.log(raw) / Math.LN10)), n = raw / p;
  return (n < 1.5 ? 1 : n < 3 ? 2 : n < 7 ? 5 : 10) * p;
}
function fmt(v, d){
  if(!isFinite(v)) return '∞';
  if(d != null) return v.toFixed(d);
  if(Math.abs(v) < 1e-9) return '0';
  return String(Math.abs(v) < 10 ? Math.round(v * 100) / 100 : Math.round(v * 10) / 10);
}
/* Seeded LCG in [0,1) — repeatable decoration (starfields, jitter) without
   Math.random, so every load of the page looks identical. */
function rng(seed){
  var s = (seed || 7) >>> 0;
  return function(){ s = (s * 9301 + 49297) % 233280; return s / 233280; };
}

/* ---------------- the world-coordinate plotter (calc.js model) ------------ */
/* Plot(canvas, {xr:[min,max], yr:[min,max], pad?, colors?}) — axes, grid,
   curves, segments, dots and labels in world coordinates, with screen<->world
   mapping for pointer interaction. Colors default to the theme tokens. */
function Plot(canvas, opts){
  var ctx = canvas.getContext('2d');
  var W = 0, H = 0;
  var xr = opts.xr.slice(), yr = opts.yr.slice();
  var pad = opts.pad || { l: 34, r: 12, t: 12, b: 26 };
  var C = opts.colors || theme();
  var mono = '10px "SF Mono",Menlo,Consolas,monospace';
  function fit(){
    if(!fitCanvas(canvas)) return false;
    W = canvas.__w; H = canvas.__h;
    return true;
  }
  function px(x){ return pad.l + (x - xr[0]) / (xr[1] - xr[0]) * (W - pad.l - pad.r); }
  function py(y){ return H - pad.b - (y - yr[0]) / (yr[1] - yr[0]) * (H - pad.t - pad.b); }
  function ix(sx){ return xr[0] + (sx - pad.l) / (W - pad.l - pad.r) * (xr[1] - xr[0]); }
  function iy(sy){ return yr[0] + (H - pad.b - sy) / (H - pad.t - pad.b) * (yr[1] - yr[0]); }
  function clear(){ ctx.clearRect(0, 0, W, H); }
  function axes(o){
    o = o || {};
    ctx.lineWidth = 1; ctx.strokeStyle = o.grid || C.grid; ctx.fillStyle = o.labelColor || C.soft;
    ctx.font = mono; ctx.textAlign = 'center'; ctx.textBaseline = 'top';
    var gx = o.gx || niceStep(xr), gy = o.gy || niceStep(yr), x, y;
    for(x = Math.ceil(xr[0] / gx) * gx; x <= xr[1] + 1e-9; x += gx){
      ctx.globalAlpha = .55; ctx.beginPath(); ctx.moveTo(px(x), pad.t); ctx.lineTo(px(x), H - pad.b); ctx.stroke(); ctx.globalAlpha = 1;
      if(o.labels !== false) ctx.fillText(fmt(x), px(x), H - pad.b + 4);
    }
    ctx.textAlign = 'right'; ctx.textBaseline = 'middle';
    for(y = Math.ceil(yr[0] / gy) * gy; y <= yr[1] + 1e-9; y += gy){
      ctx.globalAlpha = .55; ctx.beginPath(); ctx.moveTo(pad.l, py(y)); ctx.lineTo(W - pad.r, py(y)); ctx.stroke(); ctx.globalAlpha = 1;
      if(o.labels !== false && Math.abs(y) > 1e-9) ctx.fillText(fmt(y), pad.l - 4, py(y));
    }
    ctx.strokeStyle = o.axis || C.soft; ctx.lineWidth = 1.4;
    if(yr[0] < 0 && yr[1] > 0){ ctx.beginPath(); ctx.moveTo(pad.l, py(0)); ctx.lineTo(W - pad.r, py(0)); ctx.stroke(); }
    if(xr[0] < 0 && xr[1] > 0){ ctx.beginPath(); ctx.moveTo(px(0), pad.t); ctx.lineTo(px(0), H - pad.b); ctx.stroke(); }
  }
  function curve(f, color, width){
    ctx.strokeStyle = color || C.accent; ctx.lineWidth = width || 2.4; ctx.lineJoin = 'round'; ctx.beginPath();
    var started = false, N = Math.max(120, Math.round(W)), i, x, y;
    for(i = 0; i <= N; i++){
      x = xr[0] + (xr[1] - xr[0]) * i / N; y = f(x);
      if(!isFinite(y) || y < yr[0] - 6 * (yr[1] - yr[0]) || y > yr[1] + 6 * (yr[1] - yr[0])){ started = false; continue; }
      var sy = Math.max(-1e4, Math.min(1e4, py(y)));
      if(!started){ ctx.moveTo(px(x), sy); started = true; } else ctx.lineTo(px(x), sy);
    }
    ctx.stroke();
  }
  function seg(x1, y1, x2, y2, color, width, dash){
    ctx.strokeStyle = color || C.soft; ctx.lineWidth = width || 1.6; ctx.setLineDash(dash || []);
    ctx.beginPath(); ctx.moveTo(px(x1), py(y1)); ctx.lineTo(px(x2), py(y2)); ctx.stroke(); ctx.setLineDash([]);
  }
  function dot(x, y, color, r){
    ctx.fillStyle = color || C.accent; ctx.beginPath(); ctx.arc(px(x), py(y), r || 4.5, 0, 7); ctx.fill();
    ctx.lineWidth = 1.5; ctx.strokeStyle = C.paper; ctx.stroke();
  }
  function label(x, y, text, color, dx, dy){
    ctx.fillStyle = color || C.ink; ctx.font = '11px "SF Mono",Menlo,Consolas,monospace';
    ctx.textAlign = 'left'; ctx.textBaseline = 'middle';
    ctx.fillText(text, px(x) + (dx || 6), py(y) + (dy || -8));
  }
  return {
    ctx: ctx, fit: fit, clear: clear, axes: axes, curve: curve, seg: seg, dot: dot, label: label,
    px: px, py: py, ix: ix, iy: iy, pad: pad,
    get W(){ return W; }, get H(){ return H; },
    setXR: function(v){ xr = v.slice(); }, setYR: function(v){ yr = v.slice(); },
    get xr(){ return xr; }, get yr(){ return yr; }
  };
}

/* ---------------- pointer drag (doesn't fight the pager) ------------------ */
/* drag(canvas, onMove) — pointer-capture drag reporting canvas-local coords.
   Stops propagation so a drag never reaches nav links; arrow keys stay with
   the pager (widgets must not bind them — see the skill's runtime rules). */
function drag(cv, onMove){
  cv.addEventListener('pointerdown', function(e){
    e.stopPropagation();
    var r = cv.getBoundingClientRect();
    onMove(e.clientX - r.left, e.clientY - r.top, e);
    cv.setPointerCapture(e.pointerId);
    cv.onpointermove = function(ev){
      var rr = cv.getBoundingClientRect();
      onMove(ev.clientX - rr.left, ev.clientY - rr.top, ev);
    };
    cv.onpointerup = function(){ cv.onpointermove = null; cv.onpointerup = null; };
  });
}

/* ---------------- registry + boot ----------------------------------------- */
var REG = {};        // widget name -> init(box, BookWidgets)
function initBox(box){
  if(box.__bwDone) return;
  var init = REG[box.getAttribute('data-widget')];
  if(!init) return;                       // registered later → boot() re-scans
  box.__bwDone = true;
  try{ init(box, api); }
  catch(e){
    /* one broken widget must never take the page down; flag the box so the
       book's CSS can reveal a static fallback (figcaption stays visible) */
    box.className += ' widget-failed';
  }
}
function boot(root){
  var boxes = (root || document).querySelectorAll('[data-widget]');
  for(var i = 0; i < boxes.length; i++) initBox(boxes[i]);
}
function register(name, init){
  REG[name] = init;
  if(document.readyState !== 'loading') boot();   // late registration: wire now
}
if(document.readyState === 'loading') document.addEventListener('DOMContentLoaded', function(){ boot(); });
else boot();

/* ---------------- data-* params -------------------------------------------- */
/* params(box) — every data-* attribute except data-widget, numbers coerced:
   <figure data-widget="orbit" data-mass="5.2" data-fn="sin"> →
   { mass: 5.2, fn: "sin" } */
function params(box){
  var out = {}, at = box.attributes, i, n, v;
  for(i = 0; i < at.length; i++){
    n = at[i].name;
    if(n.indexOf('data-') !== 0 || n === 'data-widget' || n === 'data-anchor') continue;
    v = at[i].value;
    out[n.slice(5).replace(/-([a-z])/g, function(_, c){ return c.toUpperCase(); })] =
      (v !== '' && isFinite(v)) ? parseFloat(v) : v;
  }
  return out;
}

var api = {
  version: 1,
  reduced: REDUCE,
  register: register,
  boot: boot,
  colors: colors,
  cssVar: cssVar,
  theme: theme,
  Plot: Plot,
  makeCanvas: makeCanvas,
  fitCanvas: fitCanvas,
  anim: anim,
  onRelayout: onRelayout,
  drag: drag,
  params: params,
  fmt: fmt,
  niceStep: niceStep,
  rng: rng
};
window.BookWidgets = api;
})();

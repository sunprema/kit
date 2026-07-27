/* book-three.js — the shared 3D-figure runtime for BookBank books.
   Companion to book-widgets.js (2D canvas), same philosophy: the runtime owns
   the lifecycle so a figure cannot get the book rules wrong.

   Load AFTER the vendored three.js IIFE and after book.js:
     <script src="../assets/vendor/three.iife.js"></script>
     <script src="../assets/vendor/book-three.js"></script>
     <script src="../assets/figures.js"></script>   // your BookThree.register calls

   What it guarantees, so each figure doesn't have to:
     • renderer sized to the FIGURE, never the window; DPR clamped to 2
     • a static first frame drawn before any animation (this is what a
       screenshot, a print, and prefers-reduced-motion all see)
     • the rAF loop runs ONLY while the figure is on screen — a figure on
       spread 5 must not burn GPU while the reader is on spread 1
     • time-based ticks with a clamped dt, never frame-counted
     • re-fit on 'bookbank:relayout' (the pager dispatches it after every
       layout()) and on resize
     • context disposed on teardown — browsers cap live WebGL contexts
     • per-figure failure isolation: a thrown init marks .widget-failed so the
       CSS can hide a dead canvas, and the rest of the page still works
     • NO key bindings, ever. ← → ↑ belong to the pager.

   API:
     BookThree.register(name, init)
       init(ctx) runs once. ctx = {THREE, scene, camera, renderer, canvas,
       figure, params, size:{w,h}}. Return {tick(dt, elapsed), resize(w,h),
       dispose()} — every field optional.
     BookThree.params(figure)   data-* attributes, numbers coerced
     BookThree.rng(seed)        deterministic PRNG; never Math.random in a book
*/
(function () {
  'use strict';

  var REGISTRY = {};
  var LIVE = [];
  var MAX_DT = 1 / 20;          // a backgrounded tab must not jump the sim
  var reduced = false;
  try {
    reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  } catch (e) {}

  function params(figure) {
    var out = {};
    if (!figure || !figure.attributes) return out;
    for (var i = 0; i < figure.attributes.length; i++) {
      var a = figure.attributes[i];
      if (a.name.indexOf('data-') !== 0) continue;
      var key = a.name.slice(5).replace(/-([a-z])/g, function (m, c) { return c.toUpperCase(); });
      var n = parseFloat(a.value);
      out[key] = (a.value !== '' && !isNaN(n) && String(n) === a.value.trim()) ? n : a.value;
    }
    return out;
  }

  // Deterministic PRNG (mulberry32). Renders must be reproducible: a book
  // screenshotted twice should look identical.
  function rng(seed) {
    var t = (seed >>> 0) || 1;
    return function () {
      t += 0x6D2B79F5;
      var r = Math.imul(t ^ (t >>> 15), 1 | t);
      r ^= r + Math.imul(r ^ (r >>> 7), 61 | r);
      return ((r ^ (r >>> 14)) >>> 0) / 4294967296;
    };
  }

  function fail(figure, err) {
    figure.classList.add('widget-failed');
    if (window.console && console.warn) {
      console.warn('[book-three] figure failed:', figure.getAttribute('data-three'), err);
    }
  }

  function measure(figure, canvas) {
    // The FIGURE's box is the authority — CSS gives the canvas its aspect
    // ratio and hard max-height, so the renderer must follow the element,
    // never window.innerWidth.
    var w = Math.max(1, Math.round(canvas.clientWidth || figure.clientWidth || 1));
    var h = Math.max(1, Math.round(canvas.clientHeight || Math.round(w * 9 / 16)));
    return { w: w, h: h };
  }

  function boot(figure) {
    var name = figure.getAttribute('data-three');
    var init = REGISTRY[name];
    if (!init) { fail(figure, 'no registered figure named "' + name + '"'); return; }
    if (typeof window.THREE === 'undefined') {
      fail(figure, 'window.THREE missing — is three.iife.js loaded before this file?');
      return;
    }

    var canvas = figure.querySelector('canvas');
    if (!canvas) { fail(figure, 'no <canvas> in the figure'); return; }

    var THREE = window.THREE;
    var entry = null;

    try {
      var size = measure(figure, canvas);
      var renderer = new THREE.WebGLRenderer({ canvas: canvas, antialias: true });
      renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
      renderer.setSize(size.w, size.h, false);     // false: never touch CSS size

      var scene = new THREE.Scene();
      var camera = new THREE.PerspectiveCamera(50, size.w / size.h, 0.1, 100);
      camera.position.set(0, 0, 4);

      var ctx = {
        THREE: THREE, scene: scene, camera: camera, renderer: renderer,
        canvas: canvas, figure: figure, params: params(figure), size: size
      };

      var handle = init(ctx) || {};
      entry = {
        figure: figure, renderer: renderer, scene: scene, camera: camera,
        canvas: canvas, handle: handle, visible: false, last: 0, elapsed: 0, raf: 0
      };

      draw(entry, 0);            // the static first frame — before any motion
      observe(entry);
      LIVE.push(entry);
    } catch (err) {
      fail(figure, err);
      if (entry) dispose(entry);
    }
  }

  function draw(entry, dt) {
    if (entry.handle.tick) entry.handle.tick(dt, entry.elapsed);
    entry.renderer.render(entry.scene, entry.camera);
  }

  function frame(entry) {
    entry.raf = requestAnimationFrame(function (now) {
      if (!entry.visible) { entry.raf = 0; return; }      // stopped, not idling
      var dt = entry.last ? Math.min((now - entry.last) / 1000, MAX_DT) : 0;
      entry.last = now;
      entry.elapsed += dt;
      try { draw(entry, dt); } catch (err) { fail(entry.figure, err); stop(entry); return; }
      frame(entry);
    });
  }

  function start(entry) {
    if (entry.raf || reduced) return;   // reduced motion keeps the static frame
    entry.last = 0;
    frame(entry);
  }

  function stop(entry) {
    if (entry.raf) { cancelAnimationFrame(entry.raf); entry.raf = 0; }
  }

  function observe(entry) {
    if (!('IntersectionObserver' in window)) {   // no observer: draw once, don't loop
      entry.visible = false;
      return;
    }
    var io = new IntersectionObserver(function (es) {
      for (var i = 0; i < es.length; i++) {
        entry.visible = es[i].isIntersecting;
        if (entry.visible) start(entry); else stop(entry);
      }
    }, { threshold: 0.01 });
    io.observe(entry.figure);
    entry.io = io;
  }

  function refit(entry) {
    var s = measure(entry.figure, entry.canvas);
    if (s.w === entry.renderer.domElement.width && s.h === entry.renderer.domElement.height) {
      // still let the figure react (e.g. re-layout labels) on an explicit relayout
    }
    entry.renderer.setSize(s.w, s.h, false);
    if (entry.camera.isPerspectiveCamera) {
      entry.camera.aspect = s.w / s.h;
      entry.camera.updateProjectionMatrix();
    }
    if (entry.handle.resize) {
      try { entry.handle.resize(s.w, s.h); } catch (err) { fail(entry.figure, err); }
    }
    try { draw(entry, 0); } catch (err) { fail(entry.figure, err); }
  }

  function dispose(entry) {
    stop(entry);
    if (entry.io) { try { entry.io.disconnect(); } catch (e) {} }
    if (entry.handle && entry.handle.dispose) { try { entry.handle.dispose(); } catch (e) {} }
    if (entry.scene) {
      entry.scene.traverse(function (o) {
        if (o.geometry && o.geometry.dispose) o.geometry.dispose();
        var m = o.material;
        if (!m) return;
        (Array.isArray(m) ? m : [m]).forEach(function (mm) {
          for (var k in mm) { if (mm[k] && mm[k].isTexture) mm[k].dispose(); }
          if (mm.dispose) mm.dispose();
        });
      });
    }
    if (entry.renderer) {
      try { entry.renderer.dispose(); } catch (e) {}
      try { entry.renderer.forceContextLoss(); } catch (e) {}
    }
  }

  function bootAll() {
    var figures = document.querySelectorAll('figure.three-figure[data-three], .three-figure[data-three]');
    if (figures.length > 1 && window.console && console.warn) {
      console.warn('[book-three] ' + figures.length + ' 3D figures on one page. ' +
        'Browsers cap live WebGL contexts; the book rule is one per concept page.');
    }
    Array.prototype.forEach.call(figures, boot);
  }

  window.addEventListener('bookbank:relayout', function () { LIVE.forEach(refit); });
  window.addEventListener('resize', function () { LIVE.forEach(refit); });
  // Free contexts when the reader leaves the page (page-turns are navigations).
  window.addEventListener('pagehide', function () { LIVE.forEach(dispose); LIVE.length = 0; });

  if (document.readyState !== 'loading') bootAll();
  else document.addEventListener('DOMContentLoaded', bootAll);

  window.BookThree = {
    register: function (name, init) { REGISTRY[name] = init; },
    params: params,
    rng: rng,
    reducedMotion: function () { return reduced; },
    version: 1
  };
})();

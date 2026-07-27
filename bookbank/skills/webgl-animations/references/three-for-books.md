# three.js for BookBank books — API reference

Everything here is written the way a **book** must use three.js: the vendored
IIFE global `window.THREE`, no `import`, no CDN, no external assets. If you copy
an example from the wider three.js ecosystem it will almost certainly start with
`import * as THREE from "three"` — that is an ES module, module scripts are
CORS-blocked from a `file://` null origin in WKWebView, and the result is a book
that works in a browser tab and renders **blank in the BookBank app**. Translate
before you use.

The lifecycle rules (sizing, offscreen pause, reduced motion, disposal) are
owned by `book-three.js`. This file is about what you put *inside* a figure.

---

## The contract

**Build the bundle once per book** (idempotent; `FORCE=1` to rebuild):

```bash
"$CLAUDE_PLUGIN_ROOT/skills/write-book/scripts/build-three-bundle.sh" "<book-dir>" \
  OrbitControls=three/addons/controls/OrbitControls.js
```

**Vendor the runtime** next to it:

```bash
cp "$CLAUDE_PLUGIN_ROOT/skills/webgl-animations/assets/book-three.js" "<book-dir>/assets/vendor/"
```

**Load order matters** — three, then the runtime, then your figures:

```html
<script src="../assets/vendor/three.iife.js"></script>
<script src="../assets/vendor/book-three.js"></script>
<script src="../assets/figures.js"></script>
```

**Markup** — the runtime scans for this:

```html
<figure class="three-figure" data-three="lattice" data-cells="3" data-spin="0.5">
  <canvas></canvas>
  <figcaption>Always present — the fallback when the figure cannot run.</figcaption>
</figure>
```

**CSS** — an aspect box with a hard cap, exactly like an image slot, because the
page cannot scroll:

```css
.three-figure{ margin:0 0 1.2rem; max-width:34em; break-inside:avoid; }
.three-figure canvas{
  width:100%; aspect-ratio:16/9; height:auto; max-height:56vh;
  display:block; border:1px solid var(--rule);
}
.three-figure.widget-failed canvas{ display:none; }
```

**Register a figure.** `init` runs once; return any of `tick`/`resize`/`dispose`:

```js
BookThree.register('lattice', function (ctx) {
  var THREE = ctx.THREE, p = ctx.params;      // data-* attrs, numbers coerced
  ctx.camera.position.set(2.6, 2.0, 3.4);
  ctx.camera.lookAt(0, 0, 0);
  var mesh = new THREE.Mesh(
    new THREE.BoxGeometry(1, 1, 1),
    new THREE.MeshStandardMaterial({ color: 0x6ee7c8, roughness: 0.45 })
  );
  ctx.scene.add(mesh, new THREE.AmbientLight(0xffffff, 0.55));
  var key = new THREE.DirectionalLight(0xffffff, 2.2);
  key.position.set(3, 5, 4);
  ctx.scene.add(key);
  return {
    tick: function (dt, elapsed) { mesh.rotation.y = elapsed * (p.spin || 0.4); },
    dispose: function () { mesh.geometry.dispose(); mesh.material.dispose(); }
  };
});
```

`ctx` = `{THREE, scene, camera, renderer, canvas, figure, params, size}`.
The runtime already made the scene, a `PerspectiveCamera(50, aspect, 0.1, 100)`
at `z = 4`, and a renderer sized to the figure with DPR clamped to 2.

---

## Animation

**Time-based, never frame-based.** `tick(dt, elapsed)` gives seconds; `dt` is
clamped to 1/20s so a backgrounded tab cannot jump the simulation.

```js
tick: function (dt, t) {
  mesh.rotation.y += dt * 0.6;         // per-second rate — frame-rate independent
  mesh.position.y = Math.sin(t * 2) * 0.3;   // absolute time — reproducible
}
```

Prefer `elapsed` for anything a reader might screenshot: it is a pure function of
time, so the same moment always looks the same.

**Frame-rate-independent damping.** The naive `x += (target - x) * 0.1` is
frame-rate dependent. Use:

```js
var k = 1 - Math.exp(-dt * 6);        // 6 = stiffness
x += (target - x) * k;
```

**Keyframe clips** — worth it only when motion is genuinely choreographed:

```js
var track = new THREE.NumberKeyframeTrack('.position[y]', [0, 1, 2], [0, 1, 0]);
var clip  = new THREE.AnimationClip('bounce', 2, [track]);
var mixer = new THREE.AnimationMixer(mesh);
mixer.clipAction(clip).play();
// then, in tick:  mixer.update(dt);
```

Track name is a property path: `.position[y]`, `.material.opacity`, `.quaternion`
(with `QuaternionKeyframeTrack`), `.material.color` (`ColorKeyframeTrack`).
Interpolate rotation with quaternions, never three separate Euler tracks —
Euler interpolation gimbals and wobbles.

---

## Geometry

Use the built-ins; they are cheap and exact.

| Need | Constructor |
|------|-------------|
| Box | `new THREE.BoxGeometry(w, h, d)` |
| Sphere | `new THREE.SphereGeometry(r, widthSeg, heightSeg)` — 32×16 is plenty |
| Faceted ball | `new THREE.IcosahedronGeometry(r, detail)` + `flatShading:true` |
| Cylinder / tube | `new THREE.CylinderGeometry(rTop, rBottom, h, radialSeg)` |
| Plane / ground | `new THREE.PlaneGeometry(w, h)` |
| Arrow / vector | `new THREE.ArrowHelper(dir, origin, length, color)` |
| Axes | `new THREE.AxesHelper(size)` — instant orientation for a coordinate figure |
| Grid | `new THREE.GridHelper(size, divisions, c1, c2)` |

**A line through computed points** (the workhorse for plotting a path, an orbit,
a field line):

```js
var pts = [];
for (var i = 0; i <= 128; i++) {
  var u = i / 128 * Math.PI * 2;
  pts.push(new THREE.Vector3(Math.cos(u), Math.sin(u) * 0.4, Math.sin(u)));
}
var line = new THREE.Line(
  new THREE.BufferGeometry().setFromPoints(pts),
  new THREE.LineBasicMaterial({ color: 0xf08ac0 })
);
```

**Many identical objects → `InstancedMesh`, never a Mesh each.** Above ~200
objects the difference is the whole frame budget:

```js
var im = new THREE.InstancedMesh(geo, mat, count);
var m = new THREE.Matrix4();
for (var i = 0; i < count; i++) {
  m.setPosition(x, y, z);
  im.setMatrixAt(i, m);
}
im.instanceMatrix.needsUpdate = true;     // required after any setMatrixAt
```

---

## Materials

| Material | When | Cost |
|----------|------|------|
| `MeshBasicMaterial` | Flat color, ignores light — diagram-like figures, wireframes | free |
| `MeshLambertMaterial` | Cheap diffuse shading | low |
| `MeshStandardMaterial` | The default for anything solid; `roughness`/`metalness` | medium |
| `MeshNormalMaterial` | Debugging orientation; also a decent stylised look | free |
| `LineBasicMaterial` | Lines (width is always 1 on most platforms — do not rely on it) | free |
| `ShaderMaterial` | Custom GLSL | yours |

Useful flags: `flatShading:true` (faceted, reads well in print), `wireframe:true`,
`transparent:true` + `opacity`, `side: THREE.DoubleSide` (needed for open
surfaces), `depthWrite:false` for additive glows.

**Take colors from the book's theme**, so a figure re-skins with everything else:

```js
function token(name, fallback) {
  var v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return new THREE.Color(v || fallback);
}
var mat = new THREE.MeshStandardMaterial({ color: token('--accent', '#6ee7c8') });
ctx.scene.background = token('--bg-2', '#111830');
```

---

## Lighting

A dependable three-light setup — one bright key, a soft fill, and ambient so
nothing reads pure black:

```js
var key = new THREE.DirectionalLight(0xffffff, 2.2); key.position.set(3, 5, 4);
var fill = new THREE.DirectionalLight(0xffffff, 0.6); fill.position.set(-4, 1, -2);
ctx.scene.add(key, fill, new THREE.AmbientLight(0xffffff, 0.5));
```

`HemisphereLight(sky, ground, intensity)` is a good single-light substitute for
an object sitting on a surface. **Avoid shadow maps in a book figure** —
`castShadow` costs an extra render pass per light for a detail nobody reads at
figure size. Light intensities changed meaning in three r155 (physically-correct
by default); if a scene from an older tutorial looks black, the intensities are
the reason, not your code.

---

## Shaders

Minimal `ShaderMaterial` with a time uniform:

```js
var mat = new THREE.ShaderMaterial({
  uniforms: { uTime: { value: 0 }, uColor: { value: new THREE.Color(0x6ee7c8) } },
  vertexShader: [
    'varying vec2 vUv;',
    'void main(){ vUv = uv;',
    '  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }'
  ].join('\n'),
  fragmentShader: [
    'uniform float uTime; uniform vec3 uColor; varying vec2 vUv;',
    'void main(){',
    '  float w = 0.5 + 0.5 * sin(vUv.x * 12.0 + uTime * 2.0);',
    '  gl_FragColor = vec4(uColor * w, 1.0); }'
  ].join('\n')
});
// in tick:  mat.uniforms.uTime.value = elapsed;
```

`uv`, `position`, `normal`, `projectionMatrix`, `modelViewMatrix`, `normalMatrix`
are injected by three — do not redeclare them. Keep GLSL in arrays joined by
`\n` rather than template literals if you want the file to stay ES5-safe for the
oldest WebView you care about.

---

## Interaction

**OrbitControls only, and constrain it.** A figure that can be flung into empty
space or flipped upside down is worse than a static image:

```js
var c = new THREE.OrbitControls(ctx.camera, ctx.renderer.domElement);
c.enableDamping = true; c.dampingFactor = 0.08;
c.enablePan = false; c.enableZoom = false;      // zoom fights page scroll
c.minPolarAngle = Math.PI * 0.15;
c.maxPolarAngle = Math.PI * 0.85;
c.autoRotate = false;
// in tick:  c.update();
// in dispose:  c.dispose();
```

**Never bind arrow keys** — they belong to the pager, and OrbitControls binds
them by default, so either leave `enableKeys`/`listenToKeyEvents` unset (the
default in current versions is not to listen) or explicitly avoid calling
`listenToKeyEvents`. Test it: with the canvas focused, ← and → must still turn
pages.

Picking, when a figure is genuinely clickable:

```js
var ray = new THREE.Raycaster(), ptr = new THREE.Vector2();
ctx.canvas.addEventListener('pointerdown', function (e) {
  var r = ctx.canvas.getBoundingClientRect();
  ptr.x = ((e.clientX - r.left) / r.width) * 2 - 1;
  ptr.y = -((e.clientY - r.top) / r.height) * 2 + 1;
  ray.setFromCamera(ptr, ctx.camera);
  var hit = ray.intersectObjects(ctx.scene.children, true)[0];
  if (hit) { /* … */ }
  e.stopPropagation();          // never let it reach a nav link
});
```

---

## Budget for a book figure

A figure is one illustration on one page, not a demo reel:

- **≤ ~20k triangles.** A 32×16 sphere is 1k; you will not miss the rest.
- **≤ 3 lights, no shadow maps.**
- **One WebGL context per page.** Browsers cap live contexts; the runtime warns
  if it finds more than one figure.
- **No external assets** — no GLTF, no HDRI, no texture files. Books are
  self-contained and offline. Generate geometry procedurally; if you truly need
  a texture, draw it into a canvas and use `new THREE.CanvasTexture(canvas)`.
- **Bundle size:** three + OrbitControls is ~730 KB minified, per book. That is
  acceptable once; it is not acceptable to also pull in postprocessing,
  loaders, and controls you never call.

---

## Verifying a figure

WebGL **does not work in default headless Chrome** — you get "Error creating
WebGL context" and a blank figure that looks like your bug. Force software
rendering:

```bash
CH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
GL="--enable-unsafe-swiftshader --use-gl=angle --use-angle=swiftshader"
"$CH" --headless $GL --hide-scrollbars --window-size=900,700 \
  --virtual-time-budget=5000 --screenshot=/tmp/fig.png \
  "file://$PWD/concepts/07-page.html"
```

Then read the PNG. Checklist:

1. **It draws at all** — a static first frame must exist before any animation,
   which is also what print and reduced-motion readers get.
2. **It stays in its box** across a spread reflow and below the 900px breakpoint.
3. **Arrow keys still turn pages** with the canvas focused.
4. **It pauses offscreen** — put a counter in `tick` and confirm a figure below
   the fold is not counting. (Note that under `--virtual-time-budget` the
   absolute frame counts are small and jumpy; compare *relative* counts, don't
   read them as a frame rate.)
5. `/book-visual-qa` passes — an over-tall canvas shoves the whole spread.

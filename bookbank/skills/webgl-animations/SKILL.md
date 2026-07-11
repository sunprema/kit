---
name: webgl-animations
description: >
  Use this skill whenever the task involves creating WebGL animations, 3D scenes,
  interactive visualizations, shaders, particle systems, or Three.js code — whether
  as standalone HTML files, embedded components, or educational/data visualizations.
  Triggers include: "WebGL", "Three.js", "3D animation", "shader", "particle effect",
  "3D visualization", "rotating/orbiting scene", or any request to animate something
  in the browser with GPU rendering. Do NOT use for 2D canvas, CSS animations, or
  SVG animation unless the user explicitly wants WebGL.
---

# WebGL Animations

Build WebGL animations that are smooth, mobile-friendly, and leak-free. Default to
Three.js unless the user asks for raw WebGL or a specific library. Prefer a single
self-contained HTML file unless the project has an existing build system.

## Targeting a BookBank book? (offline, `file://`) — read this first

If the output is a **BookBank book** (a page under `<root>/books/<id>/`), the CDN
and ES-module/import-map advice below does **not** apply — books render from
`file://` with no network, and module scripts are CORS-blocked from a null origin
in WKWebView. **Do not** load three.js from a CDN or via `<script type="module">`.
Instead, bundle three.js + the addons you need into one classic IIFE that sets
`window.THREE`, vendor it in the book, and load it with a plain `<script>`. Use the
helper in the write-book skill (it handles the install/bundle and is idempotent):

```bash
"$CLAUDE_PLUGIN_ROOT/skills/write-book/scripts/build-three-bundle.sh" "<book-dir>" \
  OrbitControls=three/addons/controls/OrbitControls.js
```

It writes `<book>/assets/vendor/three.iife.js`. Load it relatively (concept pages
are one level down) with `<meta charset="utf-8">` as the page's first line:

```html
<script src="../assets/vendor/three.iife.js"></script>
```

Then follow the BookBank layout/runtime rules — lock the canvas to a capped
aspect box (`break-inside:avoid`, `max-height:56vh`), size the renderer to the
figure not the window, pause the rAF loop offscreen with an `IntersectionObserver`,
keep interaction to mouse-drag/wheel so it doesn't fight the reader's arrow-key
page-turns, and dispose the context on teardown. The **`write-book` skill's "3D
figures (three.js)"** section is the authoritative spec — defer to it. The rest of
this skill (scene setup, animation techniques, performance, shaders) still applies;
only the *loading* mechanism changes for books.

## Decision tree

1. **3D scene / objects / lighting** → Three.js (`three.min.js` from a CDN for a
   standalone/artifact page, or npm `three` in a build; **for a BookBank book, the
   vendored IIFE** — see the offline callout above).
2. **Full-screen shader effect** (plasma, noise, ray-march) → raw WebGL2 with a fullscreen
   triangle, or Three.js `ShaderMaterial` on a plane. See `assets/shader-quad.html`.
3. **Existing React project** → `@react-three/fiber` if available; otherwise mount a
   plain Three.js renderer in a `useEffect` with cleanup.
4. **Thousands of similar objects** → `InstancedMesh`, never one Mesh per object.
5. **Millions of points** → `THREE.Points` with a `BufferGeometry` and custom shader.

## Non-negotiable checklist

Every WebGL deliverable must have:

- [ ] `renderer.setPixelRatio(Math.min(devicePixelRatio, 2))` — uncapped DPR kills mobile GPUs.
- [ ] A resize handler that updates renderer size AND `camera.aspect` + `updateProjectionMatrix()`.
- [ ] `touch-action: none` on the canvas container if pointer/touch controls exist.
- [ ] Pointer Events (`pointerdown/move/up`), not mouse events — they cover touch for free.
- [ ] `prefers-reduced-motion` respected: skip autoplaying camera drift/loops; keep user-initiated animation.
- [ ] Disposal on teardown or rebuild: `geometry.dispose()`, `material.dispose()`, `texture.dispose()`,
      and `renderer.dispose()` when unmounting (critical in React/SPA contexts).
- [ ] Time-based animation (`clock.getDelta()` or timestamp deltas), never per-frame `+= constant`
      (frame-rate dependent speed breaks on 120 Hz and slow devices).
- [ ] A graceful fallback message if `WebGLRenderingContext` is unavailable.

## Environment constraints (read carefully)

**Claude.ai artifacts:** only `https://cdnjs.cloudflare.com` scripts load. Three.js there is
**r128** — old API. In r128:
- `OrbitControls` is NOT bundled and the examples path won't load → write minimal custom
  orbit controls (spherical coords + pointer drag + wheel/pinch). Template in `assets/orbit-controls.js`.
- No `CapsuleGeometry` (r142+). Use Cylinder + Sphere caps or LatheGeometry.
- Geometry classes are already Buffer-based; `Geometry` (legacy) still exists but never use it.
- No `localStorage`/`sessionStorage` in artifacts — keep state in memory.

**Modern npm `three` (r150+):** import from `three` and `three/addons/controls/OrbitControls.js`.
Color management and `outputColorSpace = THREE.SRGBColorSpace` are defaults to be aware of.
Check the installed version in package.json before writing imports.

## Scene setup pattern (Three.js)

```js
const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
container.appendChild(renderer.domElement);

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 100);

// Lighting default: ambient fill + warm key + cool rim reads well on almost anything
scene.add(new THREE.AmbientLight(0xffffff, 0.5));
const key = new THREE.DirectionalLight(0xfff2dd, 0.9); key.position.set(3, 5, 4);
const rim = new THREE.DirectionalLight(0xbcd9ff, 0.35); rim.position.set(-4, -2, -3);
scene.add(key, rim);

function resize() {
  const w = container.clientWidth, h = container.clientHeight;
  renderer.setSize(w, h, false);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
}
addEventListener('resize', resize); resize();

const clock = new THREE.Clock();
renderer.setAnimationLoop(() => {          // r128: use requestAnimationFrame instead
  const dt = clock.getDelta();
  // update(dt)
  renderer.render(scene, camera);
});
```

## Animation techniques, in order of preference

1. **Transform animation** (position/rotation/scale in the render loop) — cheapest, start here.
2. **Vertex displacement in a shader** (`ShaderMaterial` / `onBeforeCompile`) — for waves,
   terrain, flags; keeps all work on the GPU.
3. **Rebuilding geometry per frame** — avoid. If shape must change each frame, either
   morph targets, update `position` attribute in place (`attribute.needsUpdate = true`
   with `setUsage(THREE.DynamicDrawUsage)`), or parameterize a shader instead.
4. **InstancedMesh matrix updates** — for crowds/particles with per-instance transforms;
   set `instanceMatrix.needsUpdate = true` after writing matrices.

Easing: use `t = t*t*(3-2*t)` (smoothstep) or an easing function; never animate UI-visible
motion linearly unless it's constant rotation.

## Performance rules

- Target 60 fps on a mid-range phone: < 100 draw calls, < 500k triangles as a rough budget.
- Reuse geometries/materials across meshes; clone only when parameters differ.
- One `requestAnimationFrame` loop for everything. Never nest loops or start a second
  loop on user interaction.
- Pause rendering when the tab is hidden (`document.visibilitychange`) for long-running pages.
- For post-processing keep it to 1–2 passes on mobile; bloom is the usual budget-buster.
- Text: use CSS/HTML overlays positioned over the canvas, not `TextGeometry`, unless
  text must exist inside the 3D scene.

## Shaders (GLSL) quick rules

- Declare precision in fragment shaders: `precision highp float;` (mediump breaks on iOS
  for large coordinates/time values — pass time as `mod(time, 3600.)` to avoid precision drift).
- Pass `uTime`, `uResolution` uniforms; update `uTime` from the clock each frame.
- Noise: include a hash/simplex snippet inline; there is no `#include` in WebGL1.
  A compact 2D/3D simplex implementation is in `assets/shader-quad.html`.
- Debug by rendering intermediate values to color: `gl_FragColor = vec4(vec3(value), 1.0);`

## Interaction defaults

- Orbit: drag rotates (spherical θ/φ), wheel + two-finger pinch zooms, clamp φ to
  (0.1, π−0.1) and distance to a sane range. See `assets/orbit-controls.js`.
- Picking: `THREE.Raycaster` from normalized pointer coords; throttle to pointer events,
  never raycast every frame if nothing moved.
- Show a brief "drag to orbit" hint that fades on first interaction.

## Quality bar / self-review

Before delivering, verify mentally or in a browser:
1. Does it resize correctly (rotate a phone / drag window edge)?
2. Is motion frame-rate independent?
3. Any per-frame allocations (`new Vector3()` in the loop)? Hoist them.
4. Does interaction work with touch (pointer events + touch-action)?
5. Are colors/lighting readable on the chosen background, not washed out?
6. Reduced motion respected?
7. Memory: does toggling parameters that rebuild geometry dispose the old one?

## Files in this skill

- `assets/orbit-controls.js` — dependency-free orbit controls (drag/wheel/pinch), works on r128+.
- `assets/shader-quad.html` — minimal fullscreen-shader template (raw WebGL2) with simplex noise.
- `assets/template.html` — single-file Three.js starter implementing the full checklist.

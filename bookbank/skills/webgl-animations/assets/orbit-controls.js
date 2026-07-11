/**
 * MiniOrbit — dependency-free orbit controls for Three.js (works on r128+).
 * Drag to rotate, wheel to zoom, two-finger pinch to zoom on touch.
 *
 * Usage:
 *   const controls = MiniOrbit(camera, rendererDomElementOrContainer, {
 *     target: new THREE.Vector3(0, 0, 0),
 *     distance: 6, minDistance: 2, maxDistance: 20,
 *     theta: 0.9, phi: 1.1,            // initial angles (rad)
 *     autoRotate: 0.05,                 // rad/sec, 0 to disable
 *   });
 *   // in the render loop: controls.update(dt);
 */
function MiniOrbit(camera, el, opts = {}) {
  const target = opts.target || new THREE.Vector3();
  let theta = opts.theta ?? 0.8;
  let phi = opts.phi ?? 1.1;
  let dist = opts.distance ?? 6;
  const minD = opts.minDistance ?? 1.5;
  const maxD = opts.maxDistance ?? 30;
  const autoRotate = opts.autoRotate ?? 0;
  const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;

  let dragging = false, px = 0, py = 0, pinchDist = 0, interacted = false;

  function apply() {
    phi = Math.max(0.1, Math.min(Math.PI - 0.1, phi));
    dist = Math.max(minD, Math.min(maxD, dist));
    camera.position.set(
      target.x + dist * Math.sin(phi) * Math.sin(theta),
      target.y + dist * Math.cos(phi),
      target.z + dist * Math.sin(phi) * Math.cos(theta)
    );
    camera.lookAt(target);
  }

  el.style.touchAction = 'none';
  el.addEventListener('pointerdown', e => {
    if (!e.isPrimary) return;
    dragging = true; interacted = true; px = e.clientX; py = e.clientY;
    el.setPointerCapture && el.setPointerCapture(e.pointerId);
  });
  el.addEventListener('pointermove', e => {
    if (!dragging || !e.isPrimary) return;
    theta -= (e.clientX - px) * 0.006;
    phi   -= (e.clientY - py) * 0.006;
    px = e.clientX; py = e.clientY;
    apply();
  });
  el.addEventListener('pointerup',   () => { dragging = false; });
  el.addEventListener('pointercancel', () => { dragging = false; });
  el.addEventListener('wheel', e => {
    e.preventDefault(); interacted = true;
    dist *= 1 + Math.sign(e.deltaY) * 0.08;
    apply();
  }, { passive: false });
  el.addEventListener('touchmove', e => {
    if (e.touches.length !== 2) { pinchDist = 0; return; }
    dragging = false; interacted = true;
    const d = Math.hypot(
      e.touches[0].clientX - e.touches[1].clientX,
      e.touches[0].clientY - e.touches[1].clientY
    );
    if (pinchDist) { dist *= pinchDist / d; apply(); }
    pinchDist = d;
  }, { passive: true });
  el.addEventListener('touchend', () => { pinchDist = 0; });

  apply();

  return {
    update(dt) {
      if (autoRotate && !dragging && !reducedMotion && !interacted) {
        theta += autoRotate * (dt || 0.016);
        apply();
      }
    },
    get target() { return target; },
    set distance(d) { dist = d; apply(); },
    apply,
  };
}

// Export for module contexts; global otherwise.
if (typeof module !== 'undefined') module.exports = MiniOrbit;

import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { CONFIG } from './config.js';
import { clamp, protectsInput, wheelState } from './control-state.js';

export function createCamera(canvas, onPick) {
  const camera = new THREE.PerspectiveCamera(CONFIG.camera.fov, 1, .1, 2200);
  camera.position.setFromSpherical(new THREE.Spherical(CONFIG.camera.distance, CONFIG.camera.phi, CONFIG.camera.theta));
  const orbit = new OrbitControls(camera, canvas);
  orbit.enableZoom = false; orbit.enablePan = false; orbit.enableDamping = true; orbit.dampingFactor = .09;
  orbit.minPolarAngle = .12; orbit.maxPolarAngle = Math.PI - .12; orbit.rotateSpeed = .42;
  const keys = new Set(), state = { speed: CONFIG.motion.initial, selected: null, movedFrames: 0 };
  const right = new THREE.Vector3(), up = new THREE.Vector3(), delta = new THREE.Vector3();
  function zoom(factor) {
    const offset = camera.position.clone().sub(orbit.target), distance = clamp(offset.length() * factor, CONFIG.camera.min, CONFIG.camera.max);
    camera.position.copy(orbit.target).add(offset.setLength(distance));
  }
  window.addEventListener('keydown', event => {
    if (protectsInput(event)) { keys.clear(); return; }
    const key = event.key.toLowerCase();
    if ('wasdqe'.includes(key) && key.length === 1) { event.preventDefault(); keys.add(key); }
  });
  window.addEventListener('keyup', event => keys.delete(event.key.toLowerCase()));
  window.addEventListener('blur', () => keys.clear());
  document.addEventListener('visibilitychange', () => { if (document.hidden) keys.clear(); });
  document.addEventListener('focusin', event => { if (protectsInput(event)) keys.clear(); });
  canvas.addEventListener('wheel', event => {
    if (protectsInput(event)) return;
    event.preventDefault();
    const multiplier = event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? canvas.clientHeight : 1;
    const distance = camera.position.distanceTo(orbit.target);
    const next = wheelState(state.speed, distance, state.selected, event.deltaY * multiplier);
    state.speed = next.speed; zoom(next.distance / distance);
  }, { passive: false });
  let pointer = null;
  canvas.addEventListener('pointerdown', event => { if (event.button === 0) pointer = { x: event.clientX, y: event.clientY, id: event.pointerId, moved: false }; });
  canvas.addEventListener('pointermove', event => {
    if (pointer?.id === event.pointerId && Math.hypot(event.clientX - pointer.x, event.clientY - pointer.y) >= 5) pointer.moved = true;
  });
  canvas.addEventListener('pointerup', event => {
    if (pointer?.id === event.pointerId && !pointer.moved && Math.hypot(event.clientX - pointer.x, event.clientY - pointer.y) < 5) {
      const rect = canvas.getBoundingClientRect(); onPick(event.clientX - rect.left, event.clientY - rect.top);
    }
    pointer = null;
  });
  canvas.addEventListener('pointercancel', () => { pointer = null; });
  return { camera, orbit, state,
    update(dt) {
      if (keys.size) {
        camera.updateMatrixWorld(); right.setFromMatrixColumn(camera.matrixWorld, 0); up.setFromMatrixColumn(camera.matrixWorld, 1);
        delta.set(0, 0, 0).addScaledVector(right, Number(keys.has('d')) - Number(keys.has('a'))).addScaledVector(up, Number(keys.has('w')) - Number(keys.has('s')));
        if (delta.lengthSq()) {
          delta.normalize().multiplyScalar(camera.position.distanceTo(orbit.target) * CONFIG.camera.panRate * dt);
          const target = orbit.target.clone().add(delta).clampLength(0, CONFIG.radius * 2);
          delta.copy(target).sub(orbit.target); orbit.target.copy(target); camera.position.add(delta);
        }
        zoom(Math.exp((Number(keys.has('e')) - Number(keys.has('q'))) * CONFIG.camera.zoomRate * dt));
        state.movedFrames++;
      }
      orbit.update();
    },
  };
}

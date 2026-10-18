import { test } from 'node:test';
import assert from 'node:assert/strict';
import * as THREE from 'three';
import { createDust } from '../src/particles.js';

function fixture(mode) {
  const scene = new THREE.Scene(), dust = createDust(scene, mode);
  return { scene, dust, read: () => scene.children.map(p => ({ opacity: p.material.uniforms.opacity.value, cap: p.material.uniforms.maxPixels.value })),
    dispose: () => scene.children.forEach(p => { p.geometry.dispose(); p.material.dispose(); }) };
}

// Catches zoom mutating the fallback or an adaptive branch accidentally enabled by default.
test('default, explicit baseline and invalid modes preserve original uniforms at every distance', () => {
  for (const mode of [undefined, 'baseline', 'unknown']) {
    const f = fixture(mode);
    try {
      f.dust.resize(900, 1.5); const original = f.read();
      for (const distance of [520, 245, 150, 43, 24, 245]) { f.dust.update(0, distance, 43); assert.deepEqual(f.read(), original); }
    } finally { f.dispose(); }
  }
});

// Catches all-layer dimming, reversed zoom response, and lost full-view restoration.
test('adaptive reduces discrete stars first, preserves mist, and exactly restores the panorama', () => {
  const f = fixture('adaptive');
  try {
    f.dust.resize(900, 1); f.dust.update(0, 245, 43); const full = f.read();
    f.dust.update(0, 115, 43); const mid = f.read();
    f.dust.update(0, 43, 43); const near = f.read();
    assert.deepEqual(near[1], full[1]);
    for (const i of [0, 2, 3, 4]) {
      assert.ok(near[i].opacity > 0 && near[i].opacity < mid[i].opacity && mid[i].opacity < full[i].opacity);
      assert.ok(near[i].cap > .7 && near[i].cap < mid[i].cap && mid[i].cap < full[i].cap);
    }
    assert.ok(near[3].opacity / full[3].opacity < near[0].opacity / full[0].opacity);
    f.dust.update(0, 245, 43); assert.deepEqual(f.read(), full);
  } finally { f.dispose(); }
});

// Catches cutoff/discard transitions, stale DPR caps, and per-zoom geometry regeneration.
test('adaptive is continuous, FOV aware and reuses every particle buffer through zoom and resize', () => {
  const f = fixture('adaptive');
  try {
    const geometry = f.scene.children.map(p => p.geometry), positions = geometry.map(g => g.getAttribute('position').array);
    f.dust.resize(900, 1);
    let previous;
    for (let distance = 24; distance <= 520; distance += .25) {
      f.dust.update(0, distance, 43); const current = f.read();
      if (previous) current.forEach((v, i) => { assert.ok(Math.abs(v.opacity - previous[i].opacity) < .003); assert.ok(Math.abs(v.cap - previous[i].cap) < .02); });
      previous = current;
    }
    f.dust.update(0, 100, 43); const normal = f.read();
    const wide = 2 * Math.atan(2 * Math.tan(43 * Math.PI / 360)) * 180 / Math.PI;
    f.dust.update(0, 50, wide); f.read().forEach((v, i) => assert.ok(Math.abs(v.opacity - normal[i].opacity) < 1e-10));
    f.dust.resize(640, 2); f.dust.update(0, 100, 43);
    f.read().forEach((v, i) => { assert.equal(v.opacity, normal[i].opacity); assert.equal(v.cap, 2 * normal[i].cap); });
    f.scene.children.forEach((p, i) => { assert.equal(p.geometry, geometry[i]); assert.equal(p.geometry.getAttribute('position').array, positions[i]); });
    assert.equal(f.dust.count, 214200);
  } finally { f.dispose(); }
});

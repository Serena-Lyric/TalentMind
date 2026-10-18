import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { generateParticles, generateDemo } from '../src/generate.js';
import { CONFIG, spiralPoint } from '../src/config.js';
import * as THREE from 'three';
import { createDust } from '../src/particles.js';

test('P1-A.2 preserves demo identities, camera and exposure for paired evidence', () => {
  assert.equal(createHash('sha256').update(JSON.stringify(generateDemo())).digest('hex'), '75c49b6d419c1de569049ae7aa167aec430dcd60a63f2921a34efd6dd6ad6fae');
  assert.deepEqual(CONFIG.camera, { distance: 245, min: 24, max: 520, phi: .86, theta: .18, fov: 43, panRate: .32, zoomRate: .65 });
  assert.deepEqual(CONFIG.render, { dpr: 1.5, bloomStrength: .34, bloomRadius: .45, bloomThreshold: .85, exposure: 1.05 });
});

test('discrete particles retain arm contrast with a limited inter-arm star population', () => {
  const { position, count } = generateParticles('stars');
  let interArm = 0, sampled = 0;
  for (let i = 0; i < count; i++) {
    const x = position[i * 3], z = position[i * 3 + 2], r = Math.hypot(x, z);
    if (r < 25 || r > 90) continue;
    let nearest = Math.PI;
    for (let arm = 0; arm < 4; arm++) {
      const [sx, , sz] = spiralPoint(r, arm), angle = Math.atan2(z, x) - Math.atan2(sz, sx);
      nearest = Math.min(nearest, Math.abs(Math.atan2(Math.sin(angle), Math.cos(angle))));
    }
    if (nearest > .45) interArm++; sampled++;
  }
  assert.ok(interArm / sampled > .035 && interArm / sampled < .14, `inter-arm ${interArm / sampled}`);
  assert.equal(Object.values(CONFIG.particles).reduce((a, b) => a + b), 214200);
});

test('all five layers draw once at full resolution with the original P1-A sprite bounds', () => {
  const scene = new THREE.Scene(), dust = createDust(scene); dust.resize(900, 1.5);
  assert.equal(scene.children.length, 5);
  let total = 0;
  scene.children.forEach((points, index) => {
    const g = points.geometry;
    total += g.getAttribute('position').count;
    assert.equal(points.layers.mask, 1); assert.equal(points.material.uniforms.pixels.value, 1350);
    assert.equal(points.material.uniforms.maxPixels.value, [7.5, 15, 9, 7.5, 4.5][index]);
    assert.ok(g.getAttribute('position').array.every(Number.isFinite));
    g.dispose(); points.material.dispose();
  });
  assert.equal(total, 214200);
});
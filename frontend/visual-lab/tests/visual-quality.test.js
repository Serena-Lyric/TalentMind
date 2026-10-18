import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { generateParticles, generateDemo } from '../src/generate.js';
import { CONFIG, spiralPoint } from '../src/config.js';
import * as THREE from 'three';
import { createDust } from '../src/particles.js';
import { createHazePass } from '../src/haze-pass.js';

test('P1-A seed, camera, demo positions, identities and relationships stay unchanged', () => {
  assert.equal(createHash('sha256').update(JSON.stringify(generateDemo())).digest('hex'), '75c49b6d419c1de569049ae7aa167aec430dcd60a63f2921a34efd6dd6ad6fae');
  assert.deepEqual(CONFIG.camera, { distance: 245, min: 24, max: 520, phi: .86, theta: .18, fov: 43, panRate: .32, zoomRate: .65 });
  assert.deepEqual(CONFIG.render, { dpr: 1.5, bloomStrength: .34, bloomRadius: .45, bloomThreshold: .85, exposure: 1.05 });
});

test('mist spans inter-arm space while the majority still follows four arms, without adding particles', () => {
  const { position, count } = generateParticles('mist');
  let interArm = 0, sampled = 0;
  for (let i = 0; i < count; i++) {
    const x = position[i * 3], z = position[i * 3 + 2], r = Math.hypot(x, z);
    if (r < 25 || r > 90) continue;
    let nearest = Math.PI;
    for (let arm = 0; arm < 4; arm++) {
      const [sx, , sz] = spiralPoint(r, arm);
      const angle = Math.atan2(z, x) - Math.atan2(sz, sx);
      nearest = Math.min(nearest, Math.abs(Math.atan2(Math.sin(angle), Math.cos(angle))));
    }
    if (nearest > .45) interArm++;
    sampled++;
  }
  assert.ok(interArm / sampled > .15, `inter-arm coverage ${interArm / sampled}`);
  assert.ok(interArm / sampled < .4, 'keep the spiral density contrast');
  assert.equal(Object.values(CONFIG.particles).reduce((a, b) => a + b), 214200);
  assert.equal(CONFIG.seed, 261018);
});

test('core separates faint unresolved light from fine resolved particles', () => {
  const data = generateParticles('core');
  assert.ok(data.alpha instanceof Float32Array && data.haze instanceof Float32Array);
  let haze = 0, fine = 0;
  for (let i = 0; i < data.count; i++) {
    assert.ok(data.alpha[i] > 0 && data.alpha[i] < 1);
    if (data.haze[i]) { haze++; assert.ok(data.alpha[i] < .04); }
    else { fine++; assert.ok(data.scale[i] < .15); }
  }
  assert.ok(haze / data.count > .08 && haze / data.count < .25);
  assert.ok(fine / data.count > .75);
});

test('only unresolved haze uses the reduced resolution; every particle is drawn once', () => {
  const scene = new THREE.Scene(), dust = createDust(scene); dust.resize(900, 1.5);
  let total = 0;
  for (const points of scene.children) {
    const geometry = points.geometry, haze = geometry.getAttribute('ahaze');
    const indices = geometry.index?.array ?? Array.from({ length: haze.count }, (_, i) => i);
    const isHaze = points.layers.mask === 2;
    for (const index of indices) assert.equal(Boolean(haze.array[index]), isHaze);
    assert.equal(points.material.uniforms.pixels.value, 1350 * (isHaze ? .5 : 1));
    total += indices.length;
    geometry.dispose(); points.material.dispose();
  }
  assert.equal(total, 214200);
});

test('haze compositor samples the live render-target texture', () => {
  const haze = createHazePass({}, new THREE.Scene(), new THREE.PerspectiveCamera());
  assert.equal(haze.pass.uniforms.hazeTexture.value?.isRenderTargetTexture, true);
  haze.pass.dispose();
});

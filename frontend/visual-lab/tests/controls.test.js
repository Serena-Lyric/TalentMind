import { test } from 'node:test';
import assert from 'node:assert/strict';

test('wheel changes only dust when unselected, only distance when selected; both clamp', async () => {
  const { wheelState } = await import('../src/control-state.js');
  assert.deepEqual(wheelState(0.15, 260, null, -100), { speed: 0.25, distance: 260 });
  assert.deepEqual(wheelState(0, 260, null, 10000), { speed: 0, distance: 260 });
  assert.equal(wheelState(0, 260, null, -10000).speed, 2);
  assert.equal(wheelState(0.2, 260, 'demo', -10000).distance, 24);
  assert.deepEqual(wheelState(0.2, 260, 'demo', 10000), { speed: 0.2, distance: 520 });
});

test('input and composition/modifier protection excludes editing without blocking ordinary keys', async () => {
  const { protectsInput } = await import('../src/control-state.js');
  for (const tagName of ['INPUT', 'TEXTAREA', 'SELECT']) assert.equal(protectsInput({ target: { tagName } }), true);
  assert.equal(protectsInput({ target: { isContentEditable: true } }), true);
  for (const flag of ['isComposing', 'ctrlKey', 'metaKey', 'altKey']) assert.equal(protectsInput({ [flag]: true }), true);
  assert.equal(protectsInput({ target: { tagName: 'CANVAS' } }), false);
});

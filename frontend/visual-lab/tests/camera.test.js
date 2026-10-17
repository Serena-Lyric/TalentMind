import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createCamera } from '../src/camera.js';

test('dragging out and back never selects; a click selects without moving the camera', () => {
  globalThis.window = new EventTarget(); globalThis.document = new EventTarget();
  const canvas = new EventTarget();
  Object.assign(canvas, { style: {}, clientWidth: 1600, clientHeight: 900, getRootNode: () => document,
    setPointerCapture() {}, releasePointerCapture() {}, getBoundingClientRect: () => ({ left: 0, top: 0 }) });
  let picks = 0;
  const control = createCamera(canvas, () => picks++);
  const pointer = (type, x, y) => {
    const event = new Event(type, { cancelable: true });
    Object.assign(event, { pointerType: 'mouse', pointerId: 1, button: 0, clientX: x, clientY: y, pageX: x, pageY: y,
      ctrlKey: false, metaKey: false, shiftKey: false, altKey: false });
    canvas.dispatchEvent(event);
  };
  pointer('pointerdown', 400, 400); pointer('pointermove', 700, 400); control.update(.016);
  pointer('pointermove', 400, 400); control.update(.016); pointer('pointerup', 400, 400);
  assert.equal(picks, 0, '往返拖动不可触发点选');
  for (let i = 0; i < 100; i++) control.update(.016);
  const camera = control.camera.position.toArray();
  pointer('pointerdown', 400, 400); pointer('pointerup', 400, 400);
  assert.equal(picks, 1); assert.deepEqual(control.camera.position.toArray(), camera);
  control.orbit.dispose(); delete globalThis.window; delete globalThis.document;
});

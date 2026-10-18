import { test } from 'node:test'
import assert from 'node:assert/strict'
import { graphShortcut } from '../src/graph/graphShortcut.ts'

const key = (key: string, extra = {}) => ({ key, ...extra }) as KeyboardEvent
test('Y/H 是独立单键，长按、组合键和 IME 不触发', () => {
  assert.equal(graphShortcut(key('y')), 'immersive')
  assert.equal(graphShortcut(key('H')), 'panels')
  assert.equal(graphShortcut(key('x')), null)
  for (const field of ['ctrlKey', 'altKey', 'metaKey', 'shiftKey', 'repeat', 'isComposing', 'defaultPrevented']) {
    for (const letter of ['h', 'y']) assert.equal(graphShortcut(key(letter, { [field]: true })), null)
  }
  assert.equal(graphShortcut(key('y', { keyCode: 229 })), null)
  assert.equal(graphShortcut(key('h'), true), null)
})
test('输入元素以及 contenteditable 的子节点不触发', () => {
  for (const letter of ['h', 'y']) {
    const target = { closest: () => ({ tagName: 'INPUT' }) }
    assert.equal(graphShortcut(key(letter, { target })), null)
    assert.equal(graphShortcut(key(letter, { composedPath: () => [target] })), null)
  }
})

import { test } from 'node:test'
import assert from 'node:assert/strict'
import { Group, Points } from 'three'
import { createDust } from '../src/graph/galaxy/particles.js'

test('异步粒子首次不占用主线程构建，刷新和卸载拒收旧回包', async t => {
  const workers: FakeWorker[] = []
  class FakeWorker {
    onmessage: ((event: any) => void) | null = null
    onerror: (() => void) | null = null
    terminated = false
    input: any
    constructor() { workers.push(this) }
    postMessage(input: any) { this.input = input }
    terminate() { this.terminated = true }
  }
  const original = Object.getOwnPropertyDescriptor(globalThis, 'Worker')
  Object.defineProperty(globalThis, 'Worker', { configurable: true, value: FakeWorker })
  t.after(() => {
    if (original) Object.defineProperty(globalThis, 'Worker', original)
    else delete (globalThis as any).Worker
  })
  const scene = new Group()
  const dust = createDust(scene, true, { asynchronous: true })
  t.after(() => {
    dust.dispose()
    for (const layer of scene.children as Points[]) { layer.geometry.dispose(); (layer.material as any).dispose() }
  })
  const layer = scene.children[0] as Points
  assert.equal(layer.geometry.getAttribute('position').count, 0)
  const input = { positions: [] }
  dust.setField({ input })
  await new Promise(resolve => setTimeout(resolve, 5))
  assert.equal(workers.length, 1, '初始默认分布与同轮字段绑定合并为一次构建')
  assert.equal(workers[0].input.input, input)
  const reply = (value: number) => ({ data: { kind: 'dust', elapsedMs: 5, particles: {
    position: new Float32Array([value, 0, 0]), color: new Float32Array([1, 1, 1]),
    scale: new Float32Array([1]), phase: new Float32Array([0]), count: 1,
  } } })
  workers[0].onmessage!(reply(1))
  assert.equal(layer.geometry.getAttribute('position').getX(0), 1)
  dust.setField({ input: { positions: [] } })
  assert.equal(workers[0].terminated, true)
  workers[0].onmessage!(reply(9))
  assert.equal(layer.geometry.getAttribute('position').getX(0), 1)
  await new Promise(resolve => setTimeout(resolve, 5))
  dust.dispose()
  workers[1].onmessage!(reply(8))
  assert.equal(layer.geometry.getAttribute('position').getX(0), 1)
  assert.equal(workers[1].terminated, true)
})

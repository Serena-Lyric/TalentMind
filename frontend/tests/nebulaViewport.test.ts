import { test } from 'node:test'
import assert from 'node:assert/strict'
import { toScreen, toWorld, hitPoint, focusTransform, searchNodes, visibleInFocus } from '../src/graph/nebulaViewport.ts'
import type { GraphNode } from '../src/api/graph.ts'

test('缩放和平移后的屏幕/世界坐标互逆', () => {
  for (const scale of [.06, .45, 1, 2.7]) {
    const transform = { x: -145, y: 200, scale }
    const point = { x: 320, y: -50 }
    const screen = toScreen(point, { width: 1200, height: 800 }, transform)
    const result = toWorld(screen, { width: 1200, height: 800 }, transform)
    assert.ok(Math.abs(result.x - point.x) < 1e-9 && Math.abs(result.y - point.y) < 1e-9)
  }
})
test('低倍缩放点击半径与绘制最小屏幕半径一致', () => {
  assert.equal(hitPoint({ x: 40, y: 0 }, { x: 0, y: 0 }, 18, .45), true)
  assert.equal(hitPoint({ x: 45, y: 0 }, { x: 0, y: 0 }, 18, .45), false)
  assert.equal(hitPoint({ x: 20, y: 0 }, { x: 0, y: 0 }, 18, 2.7), true)
})
test('聚焦把分散直连放进两侧玻璃面板之间且保留边距', () => {
  const points = [{ x: -2500, y: -1800 }, { x: 2500, y: 1800 }]
  const view = { width: 1278, height: 818 }
  const transform = focusTransform(points, view)
  for (const point of points) {
    const screen = toScreen(point, view, transform)
    assert.ok(screen.x > 280 && screen.x < 878 && screen.y > 24 && screen.y < 794)
  }
  assert.ok(Object.values(focusTransform([], view)).every(Number.isFinite))
  assert.ok(Object.values(focusTransform([{x:0,y:0}], {width: 400, height: 300})).every(Number.isFinite))
})
test('搜索优先精确节点，排除隐藏类型，空白不命中全部图', () => {
  const node = (id: string, label: string, kind: GraphNode['kind']): GraphNode => ({ id, label, kind, size: 12, color: '' })
  const graph = [node('compound', 'Python 和 Matlab', 'skill'), node('python', 'Python', 'skill'), node('hidden', 'Python', 'industry')]
  const result = searchNodes(graph, ' python ', new Set(['job', 'skill']))
  assert.deepEqual(result.map(n=>n.id), ['python', 'compound'])
  assert.deepEqual(searchNodes(graph, ' ', new Set(['skill'])), [])
})

test('聚焦时未绘制的非邻域节点不能进入命中候选', () => {
  assert.equal(visibleInFocus('other', new Set(['selected', 'neighbor'])), false)
  assert.equal(visibleInFocus('neighbor', new Set(['selected', 'neighbor'])), true)
  assert.equal(visibleInFocus('other', new Set()), true)
})

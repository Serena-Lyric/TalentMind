import { test } from 'node:test'
import assert from 'node:assert/strict'
import { toScreen, toWorld, hitPoint, focusTransform, searchNodes, visibleInFocus, resolveSelection, availableGraphArea } from '../src/graph/nebulaViewport.ts'
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
test('LOD 后使用实际屏幕绘制半径命中，低倍和高倍一致', () => {
  assert.equal(hitPoint({ x: 30, y: 0 }, { x: 0, y: 0 }, 8.1, .45), true)
  assert.equal(hitPoint({ x: 40, y: 0 }, { x: 0, y: 0 }, 8.1, .45), false)
  assert.equal(hitPoint({ x: 20, y: 0 }, { x: 0, y: 0 }, 48.6, 2.7), true)
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
test('刷新从新数据恢复选中详情和全部新直连，移除选中节点则清除邻域', () => {
  const node = (id: string, label: string): GraphNode => ({ id, label, kind: 'job', size: 12, color: '' })
  const nodes = [node('a', 'updated'), node('new', 'new neighbor')]
  const refreshed = resolveSelection('a', nodes, [{ source: 'a', target: 'new', kind: 'related_to' }, { source: 'a', target: 'missing', kind: 'requires' }])
  assert.equal(refreshed.node?.label, 'updated')
  assert.deepEqual([...refreshed.ids].sort(), ['a', 'new'])
  const removed = resolveSelection('removed', nodes, [])
  assert.equal(removed.node, null)
  assert.equal(removed.ids.size, 0)
  assert.equal(resolveSelection(undefined, nodes, []).ids.size, 0)
})
test('900px 画布的聚焦避让真实桌面面板，而不按百分比低估面板宽度', () => {
  const points = [{ x: -2500, y: -100 }, { x: 2500, y: 100 }]
  const view = { width: 900, height: 700 }
  const transform = focusTransform(points, view)
  for (const point of points) {
    const screen = toScreen(point, view, transform)
    assert.ok(screen.x > 260 && screen.x < 524)
  }
})
test('聚焦可使用现有 DOM 实测的可用矩形', () => {
  const points = [{ x: -1000, y: -1000 }, { x: 1000, y: 1000 }]
  const view = { width: 900, height: 700 }
  const area = { left: 280, right: 500, top: 30, bottom: 670 }
  const transform = focusTransform(points, view, area)
  for (const point of points) {
    const screen = toScreen(point, view, transform)
    assert.ok(screen.x > area.left && screen.x < area.right && screen.y > area.top && screen.y < area.bottom)
  }
})
test('全览适配全部极端坐标和宽高变化，并避让实际面板矩形', () => {
  const points = [{ x: -1e12, y: -2e12 }, { x: 3e12, y: 4e12 }]
  for (const view of [{width:1277,height:817}, {width:901,height:817}, {width:600,height:350}]) {
    const panel = {left:16,right:260,top:12,bottom:300}
    const area = availableGraphArea(view, [panel])
    assert.ok(area.right <= panel.left || area.left >= panel.right || area.bottom <= panel.top || area.top >= panel.bottom)
    const transform = focusTransform(points, view, area)
    assert.ok(transform.scale > 0 && Number.isFinite(transform.scale))
    for (const point of points) {
      const screen = toScreen(point, view, transform)
      assert.ok(screen.x >= area.left && screen.x <= area.right && screen.y >= area.top && screen.y <= area.bottom)
    }
  }
})
test('可用矩形不与左右/覆盖面板相交，空图和零尺寸仍有限', () => {
  const view = {width:600,height:800}
  const panels = [{left:16,right:260,top:12,bottom:380}, {left:220,right:580,top:12,bottom:500}]
  const area = availableGraphArea(view, panels)
  assert.ok(area.top >= 500)
  assert.deepEqual(area, availableGraphArea(view, [...panels].reverse()))
  assert.ok(Object.values(focusTransform([],view,area)).every(Number.isFinite))
  assert.ok(Object.values(focusTransform([{x:0,y:0}],{width:0,height:0})).every(Number.isFinite))
})

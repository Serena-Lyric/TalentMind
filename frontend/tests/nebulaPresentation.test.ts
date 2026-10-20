import { test } from 'node:test'
import assert from 'node:assert/strict'
import * as presentation from '../src/graph/nebulaPresentation.ts'
const { nodeAppearance } = presentation

test('近景节点有屏幕像素上限，不能盖住标签', () => {
  for (const kind of ['job', 'skill', 'industry'] as const) {
    assert.ok(nodeAppearance(kind, 18, 2.7, true).radius <= 12)
    assert.ok(nodeAppearance(kind, 18, 100).radius <= 12)
  }
})

test('远景减小小节点和行业圆点，降低阴影和标签密度', () => {
  for (const kind of ['job', 'skill', 'industry'] as const) {
    const near = nodeAppearance(kind, 13, 1)
    const far = nodeAppearance(kind, 13, .05)
    assert.ok(far.radius > 0 && far.radius < near.radius / 3)
    assert.equal(far.label, false)
    assert.equal(far.shadow, 0)
    assert.equal(far.outline, false)
  }
})

test('三类型近景标签开启、缩小关闭，中景岗位/匹配和悬停优先', () => {
  for (const kind of ['job', 'skill', 'industry'] as const) {
    assert.equal(nodeAppearance(kind, 8, 1.25).label, true)
    assert.equal(nodeAppearance(kind, 8, .64).label, false)
    assert.equal(nodeAppearance(kind, 8, 1.24).label, kind === 'job')
    assert.equal(nodeAppearance(kind, 8, .1, false, false, true).label, true)
    assert.equal(nodeAppearance(kind, 8, .1, true).label, true)
    assert.equal(nodeAppearance(kind, 8, .65, false, true).label, true)
  }
})
test('全览匹配节点有轻量描边和较大半径，不开启全部匹配标签/阴影', () => {
  for (const kind of ['job', 'skill', 'industry'] as const) {
    const normal = nodeAppearance(kind, 8, .085)
    const match = nodeAppearance(kind, 8, .085, false, true)
    assert.equal(match.outline, true)
    assert.ok(match.radius > normal.radius)
    assert.equal(match.label, false)
    assert.equal(match.shadow, 0)
  }
})
test('标签稳定按优先级避让，排除面板/离屏，允许相邻无碰撞标签', () => {
  assert.equal(typeof presentation.selectLabels, 'function')
  const label = (id: string, left: number, top: number, priority = 0) => ({ id, priority, bounds: { left, right: left + 40, top, bottom: top + 14 } })
  const labels = [label('ordinary', 80, 30), label('selected', 80, 30, 4), label('hovered', 85, 30, 3), label('next', 125, 30), label('panel', 5, 5, 4), label('outside', 280, 20), label('stable-b', 80, 90), label('stable-a', 80, 90)]
  const view = { left: 0, top: 0, right: 300, bottom: 200 }
  const panels = [{ left: 0, right: 60, top: 0, bottom: 100 }]
  const picked = presentation.selectLabels(labels, view, panels)
  assert.deepEqual([...picked].sort(), ['next', 'selected', 'stable-a'])
  assert.deepEqual(picked, presentation.selectLabels([...labels].reverse(), view, panels))
})
test('远景选择节点仍清楚可见，放大恢复岗位/搜索标签', () => {
  const selected = nodeAppearance('skill', 4, .02, true)
  assert.ok(selected.radius >= 3)
  assert.equal(selected.label, true)
  assert.equal(selected.outline, true)
  assert.equal(nodeAppearance('job', 18, 1).label, true)
  assert.equal(nodeAppearance('skill', 4, 1, false, true).label, true)
  assert.equal(nodeAppearance('skill', 4, .05, false, true).label, false)
})

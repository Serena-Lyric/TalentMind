import { test } from 'node:test'
import assert from 'node:assert/strict'
import { nodeAppearance } from '../src/graph/nebulaPresentation.ts'

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
test('远景选择节点仍清楚可见，放大恢复岗位/搜索标签', () => {
  const selected = nodeAppearance('skill', 4, .02, true)
  assert.ok(selected.radius >= 3)
  assert.equal(selected.label, true)
  assert.equal(selected.outline, true)
  assert.equal(nodeAppearance('job', 18, 1).label, true)
  assert.equal(nodeAppearance('skill', 4, 1, false, true).label, true)
  assert.equal(nodeAppearance('skill', 4, .05, false, true).label, false)
})

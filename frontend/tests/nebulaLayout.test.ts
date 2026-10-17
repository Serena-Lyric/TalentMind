import { test } from 'node:test'
import assert from 'node:assert/strict'
import type { GraphNode, GraphEdge } from '../src/api/graph.ts'
import { buildRelationLayout } from '../src/graph/nebulaLayout.ts'

const node = (id: string, kind: GraphNode['kind']): GraphNode => ({ id, kind, label: id, size: 12, color: '' })
const link = (source: string, target: string, kind = 'requires'): GraphEdge => ({ source, target, kind })
const nodes = [node('job:a', 'job'), node('job:b', 'job'), node('job:c', 'job'), node('shared', 'skill'), node('scene', 'industry'), node('private', 'skill')]
const edges = [link('job:a', 'shared'), link('job:b', 'shared'), link('job:c', 'shared'), link('job:a', 'private'), link('job:a', 'scene', 'applies_to'), link('job:b', 'scene', 'applies_to')]

test('共享技能/场景由全部关联岗位决定，私有技能位于岗位附近', async () => {
  const positions = await buildRelationLayout(nodes, edges)
  for (const [id, parents] of [['shared', ['job:a', 'job:b', 'job:c']], ['scene', ['job:a', 'job:b']]] as const) {
    const x = parents.reduce((sum, id) => sum + positions.get(id)!.x, 0) / parents.length
    const y = parents.reduce((sum, id) => sum + positions.get(id)!.y, 0) / parents.length
    assert.ok(Math.hypot(positions.get(id)!.x - x, positions.get(id)!.y - y) < 40)
  }
  assert.ok(Math.hypot(positions.get('private')!.x - positions.get('job:a')!.x, positions.get('private')!.y - positions.get('job:a')!.y) < 200)
})

test('节点/关系枚举顺序不改变坐标，输入不被改写', async () => {
  const before = JSON.stringify({ nodes, edges })
  const a = await buildRelationLayout(nodes, edges)
  const b = await buildRelationLayout([...nodes].reverse(), [...edges].reverse())
  for (const item of nodes) assert.deepEqual(a.get(item.id), b.get(item.id))
  assert.equal(JSON.stringify({ nodes, edges }), before)
})

test('改变真实关联会改变岗位布局', async () => {
  const a = await buildRelationLayout(nodes, edges)
  const b = await buildRelationLayout(nodes, [link('job:a', 'shared'), link('job:a', 'private')])
  assert.notDeepEqual(a.get('job:b'), b.get('job:b'))
})

test('高度共享、孤立场景、坏端点和空图都有有限、紧凑回退', async () => {
  const jobs = Array.from({ length: 120 }, (_, i) => node('j' + i, 'job'))
  const input = [...jobs, node('hub', 'skill'), ...Array.from({ length: 100 }, (_, i) => node('isolated' + i, 'industry'))]
  const positions = await buildRelationLayout(input, [...jobs.map(item => link(item.id, 'hub')), link('missing', 'hub')])
  assert.equal(positions.size, input.length)
  for (const p of positions.values()) assert.ok(Number.isFinite(p.x) && Number.isFinite(p.y) && Math.abs(p.x) < 6000 && Math.abs(p.y) < 6000)
  assert.equal((await buildRelationLayout([], [])).size, 0)
})

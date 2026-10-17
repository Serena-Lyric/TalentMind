import { test } from 'node:test'
import assert from 'node:assert/strict'
import type { GraphNode, GraphEdge } from '../src/api/graph.ts'
import { selectEdges, dashedEdge, type EdgeOptions } from '../src/graph/nebulaEdges.ts'

const node = (id: string, kind: GraphNode['kind']): GraphNode => ({ id, kind, label: id, size: 12, color: '' })
const nodes = [node('j', 'job'), node('k', 'job'), node('s', 'skill'), node('i', 'industry'), node('outside', 'skill')]
const edges = [
  { source: 'j', target: 's', kind: 'requires' },
  { source: 'j', target: 'i', kind: 'applies_to' },
  { source: 'j', target: 'k', kind: 'related_to' },
  { source: 's', target: 'k', kind: 'requires' },
  { source: 'missing', target: 's', kind: 'requires' },
]
const positions = new Map(nodes.map((n, i) => [n.id, { x: i === 4 ? 2000 : i * 25, y: 0 }]))
const options: EdgeOptions = { activeKinds: new Set(['job', 'skill', 'industry']), viewport: { left: -100, right: 100, top: -100, bottom: 100 }, scale: 1 }

test('边选择与输入顺序无关，排除不存在或隐藏端点', () => {
  const a = selectEdges(edges, nodes, positions, options)
  const b = selectEdges([...edges].reverse(), [...nodes].reverse(), positions, options)
  assert.deepEqual(a, b)
  assert.ok(a.every(edge => edge.source !== 'missing'))
  const filtered = selectEdges(edges, nodes, positions, { ...options, activeKinds: new Set(['job', 'skill']) })
  assert.ok(filtered.every(edge => edge.target !== 'i'))
  assert.ok(filtered.every(edge => edges.includes(edge)))
})

test('选中节点的全部可见直连超过 900 也不截断，且不混入邻居间边', () => {
  const leaves = Array.from({ length: 1001 }, (_, i) => node('s' + i, 'skill'))
  const graph = [node('j', 'job'), ...leaves]
  const links: GraphEdge[] = leaves.map(n => ({ source: 'j', target: n.id, kind: 'requires' }))
  links.push({ source: 's0', target: 's1', kind: 'related_to' })
  const points = new Map(graph.map(n => [n.id, { x: 0, y: 0 }]))
  assert.equal(selectEdges(links, graph, points, { ...options, selectedId: 'j' }).length, 1001)
  assert.equal(selectEdges(links, graph, points, { ...options, selectedId: 'j', activeKinds: new Set(['job']) }).length, 0)
})

test('普通模式有稳定预算和类型覆盖，放大后补全视口内真实关系', () => {
  const normal = selectEdges(edges.slice(0, 4), nodes, positions, { ...options, limit: 3 })
  assert.equal(normal.length, 3)
  assert.equal(new Set(normal.map(e => e.kind)).size, 3)
  assert.equal(selectEdges(edges.slice(0, 4), nodes, positions, { ...options, scale: 2, limit: 1 }).length, 4)
})

test('离屏无交点边不抢占预算，穿越视口的边保留', () => {
  const graph = [node('a', 'job'), node('b', 'skill'), node('c', 'job'), node('d', 'skill')]
  const points = new Map([['a', {x: -200, y: 0}], ['b', {x: 200, y: 0}], ['c', {x: -200, y: 300}], ['d', {x: 200, y: 200}]])
  const links = [{source:'c',target:'d',kind:'requires'}, {source:'a',target:'b',kind:'requires'}]
  assert.deepEqual(selectEdges(links, graph, points, { ...options, limit: 1 }), [links[1]])
})

test('RELATED_TO 仅在岗位两端使用虚线，技能与场景关系使用实线', () => {
  const byId = new Map(nodes.map(n => [n.id, n]))
  assert.equal(dashedEdge(edges[2], byId), true)
  assert.equal(dashedEdge(edges[0], byId), false)
  assert.equal(dashedEdge(edges[1], byId), false)
  assert.equal(dashedEdge({ source: 's', target: 'i', kind: 'related_to' }, byId), false)
})

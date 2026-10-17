import { test } from 'node:test'
import assert from 'node:assert/strict'
import type { GraphNode, GraphEdge } from '../src/api/graph.ts'
import { selectEdges, dashedEdge, selectEdgePlan, edgeAppearance, type EdgeOptions } from '../src/graph/nebulaEdges.ts'

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
test('远景减少短线预算、抑制长距离穿屏边，选择时仍完整保留', () => {
  const graph = [node('j','job'),...Array.from({length:500},(_,i)=>node('s'+i,'skill')),node('long','skill')]
  const points = new Map(graph.map((n,i)=>[n.id,{x:i,y:0}]))
  points.set('long',{x:10000,y:0})
  const links = graph.slice(1).map(n=>({source:'j',target:n.id,kind:'requires'}))
  const far = selectEdgePlan(links,graph,points,{...options,scale:.08})
  assert.ok(far.edges.length<=120)
  assert.ok(!far.edges.some(e=>e.target==='long'))
  assert.equal(far.candidates,501)
  const focus = selectEdgePlan(links,graph,points,{...options,scale:.08,selectedId:'j'})
  assert.equal(focus.edges.length,501)
  assert.equal(focus.visibleDirect,501)
})
test('普通模式优先近距离真实边，不让视口中央的长交叉线抢预算', () => {
  const graph = [node('a','job'),node('b','skill'),node('c','job'),node('d','skill')]
  const points = new Map([['a',{x:-80,y:80}],['b',{x:-60,y:80}],['c',{x:-90,y:0}],['d',{x:90,y:0}]])
  const links = [{source:'c',target:'d',kind:'requires'},{source:'a',target:'b',kind:'requires'}]
  assert.deepEqual(selectEdges(links,graph,points,{...options,limit:1}),[links[1]])
  assert.deepEqual(selectEdges([...links].reverse(),graph,points,{...options,limit:1}),[links[1]])
})
test('三种线型克制可辨，远景/长线弱化，聚焦直连重点突出', () => {
  const byId = new Map(nodes.map(n=>[n.id,n]))
  const styles = edges.slice(0,3).map(edge=>edgeAppearance(edge,byId,1,false,100))
  assert.equal(new Set(styles.map(s=>JSON.stringify(s.dash))).size,3)
  for (const edge of edges.slice(0,3)) {
    const far = edgeAppearance(edge,byId,.08,false,100)
    const near = edgeAppearance(edge,byId,1,false,100)
    const long = edgeAppearance(edge,byId,1,false,800)
    const focus = edgeAppearance(edge,byId,.08,true,1000)
    assert.ok(far.alpha<near.alpha && long.alpha<near.alpha)
    assert.ok(focus.alpha>=.6 && focus.width>near.width)
  }
})
test('选中诊断区分原始度数、类型过滤及有坐标的直连，不按视口删掉离屏直连', () => {
  const graph = [node('j','job'),node('inside','skill'),node('off','skill'),node('hidden','industry'),node('unplaced','skill')]
  const points = new Map([['j',{x:0,y:0}],['inside',{x:20,y:0}],['off',{x:2000,y:0}],['hidden',{x:10,y:0}]])
  const links = ['inside','off','hidden','unplaced','missing'].map(target=>({source:'j',target,kind:'requires'}))
  const plan = selectEdgePlan(links,graph,points,{...options,activeKinds:new Set(['job','skill']),selectedId:'j',scale:.085,limit:1})
  assert.equal(plan.dataDegree,5)
  assert.equal(plan.typeFilteredDirect,3)
  assert.equal(plan.visibleDirect,2)
  assert.deepEqual(plan.edges.map(edge=>edge.target),['inside','off'])
})

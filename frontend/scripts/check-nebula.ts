// 只读检查显式 API 快照；不连接服务，不写文件。
import { readFileSync } from 'node:fs'
import { createHash } from 'node:crypto'
import assert from 'node:assert/strict'
import type { GraphData } from '../src/api/graph.ts'
import { buildRelationLayout } from '../src/graph/nebulaLayout.ts'
import { buildLegacyLayout } from '../src/graph/nebulaLegacy.ts'
import { selectEdges, selectEdgePlan } from '../src/graph/nebulaEdges.ts'
import { focusTransform, toScreen, availableGraphArea } from '../src/graph/nebulaViewport.ts'

if (!process.argv[2]) throw new Error('Usage: node --experimental-strip-types scripts/check-nebula.ts <graph-api.json>')
const raw = readFileSync(process.argv[2])
const parsed = JSON.parse(raw.toString('utf8'))
const graph: GraphData = parsed.data || parsed
const before = JSON.stringify(graph)
const start = performance.now()
const positions = await buildRelationLayout(graph.nodes, graph.edges)
const elapsed = performance.now() - start
const reversed = await buildRelationLayout([...graph.nodes].reverse(), [...graph.edges].reverse())
assert.equal(positions.size, graph.nodes.length)
for (const node of graph.nodes) {
  const point = positions.get(node.id)!
  assert.ok(Number.isFinite(point.x) && Number.isFinite(point.y))
  assert.deepEqual(point, reversed.get(node.id))
}
assert.equal(JSON.stringify(graph), before)
const count = (values: string[]) => Object.fromEntries([...new Set(values)].sort().map(key => [key, values.filter(value => value === key).length]))
const extent = (map: typeof positions) => {
  const points = [...map.values()]
  return { width: Math.max(...points.map(p => p.x)) - Math.min(...points.map(p => p.x)), height: Math.max(...points.map(p => p.y)) - Math.min(...points.map(p => p.y)) }
}
const options = { activeKinds: new Set(['job', 'skill', 'industry'] as const), viewport: { left: -639, right: 639, top: -409, bottom: 409 }, scale: 1 }
const view = {width:1277,height:817}
const area = availableGraphArea(view,[{left:16,right:260,top:12,bottom:400}])
const overviewTransform = focusTransform([...positions.values()],view,area)
const outside = [...positions.values()].filter(point => {
  const screen = toScreen(point,view,overviewTransform)
  return screen.x<area.left || screen.x>area.right || screen.y<area.top || screen.y>area.bottom
}).length
assert.equal(outside,0)
const world = (x: number,y: number) => ({x:(x-view.width/2)/overviewTransform.scale-overviewTransform.x,y:(y-view.height/2)/overviewTransform.scale-overviewTransform.y})
const tl=world(0,0); const br=world(view.width,view.height)
const overviewEdges=selectEdgePlan(graph.edges,graph.nodes,positions,{...options,viewport:{left:tl.x,right:br.x,top:tl.y,bottom:br.y},scale:overviewTransform.scale})
assert.ok(overviewEdges.edges.length<=120)
const normal = selectEdges(graph.edges, graph.nodes, positions, options)
const focused = ['skill:pytorch', 'skill:python', 'job:j-f6dd5eb6f9c5c2e4'].map(id => {
  const expected = graph.edges.filter(edge => edge.source === id || edge.target === id)
  const selected = selectEdges(graph.edges, graph.nodes, positions, { ...options, selectedId: id })
  assert.equal(selected.length, expected.length)
  assert.ok(selected.every(edge => expected.includes(edge)))
  const ids = new Set([id, ...expected.flatMap(edge => [edge.source, edge.target])])
  const view = { width: 1278, height: 818 }
  const points = [...ids].map(id => positions.get(id)!)
  const transform = focusTransform(points, view)
  for (const point of points) {
    const screen = toScreen(point, view, transform)
    assert.ok(screen.x > 280 && screen.x < 878 && screen.y > 24 && screen.y < 794)
  }
  return { id, actualDirect: expected.length, selected: selected.length, scale: transform.scale }
})
console.log(JSON.stringify({
  snapshotSha256: createHash('sha256').update(raw).digest('hex'),
  nodes: graph.nodes.length, edges: graph.edges.length,
  nodeTypes: count(graph.nodes.map(node => node.kind)), edgeTypes: count(graph.edges.map(edge => edge.kind)),
  finite: true, orderInvariant: true, inputUnchanged: true, layoutMs: elapsed,
  overview: { transform: overviewTransform, area, fittedNodes:positions.size, outside, candidates:overviewEdges.candidates,drawn:overviewEdges.edges.length },
  legacyExtent: extent(buildLegacyLayout(graph.nodes, graph.edges)), experimentalExtent: extent(positions),
  normal: { drawn: normal.length, types: count(normal.map(edge => edge.kind)) },
  zoomed: selectEdges(graph.edges, graph.nodes, positions, { ...options, scale: 2 }).length,
  focused,
}, null, 2))

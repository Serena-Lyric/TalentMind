import type { GraphNode, GraphEdge } from '../api/graph'
import type { Point } from './nebulaViewport'
import type { SimulationNodeDatum } from 'd3-force'

interface Anchor extends SimulationNodeDatum { id: string; kind: GraphNode['kind'] }

const compare = (a: string, b: string) => a < b ? -1 : a > b ? 1 : 0
const goldenAngle = 2.39996323

export async function buildRelationLayout(nodes: GraphNode[], edges: GraphEdge[]): Promise<Map<string, Point>> {
  const positions = new Map<string, Point>()
  if (!nodes.length) return positions
  const sorted = [...nodes].sort((a, b) => compare(a.id, b.id))
  const byId = new Map(sorted.map(node => [node.id, node]))
  const parents = new Map<string, Set<string>>()
  const validEdges = edges.filter(edge => byId.has(edge.source) && byId.has(edge.target))
    .sort((a, b) => compare(JSON.stringify([a.source, a.target, a.kind]), JSON.stringify([b.source, b.target, b.kind])))
  for (const edge of validEdges) {
    const source = byId.get(edge.source)!
    const target = byId.get(edge.target)!
    const job = source.kind === 'job' ? source : target.kind === 'job' ? target : null
    const leaf = source.kind !== 'job' ? source : target.kind !== 'job' ? target : null
    if (!job || !leaf) continue
    const kind = edge.kind.toLowerCase()
    if (!(kind === 'requires' && leaf.kind === 'skill') && !(kind === 'applies_to' && leaf.kind === 'industry')) continue
    if (!parents.has(leaf.id)) parents.set(leaf.id, new Set())
    parents.get(leaf.id)!.add(job.id)
  }
  const anchors = sorted.filter(node => node.kind === 'job' || (parents.get(node.id)?.size || 0) > 1)
  const anchorIds = new Set(anchors.map(node => node.id))
  const skeleton = validEdges.filter(edge => anchorIds.has(edge.source) && anchorIds.has(edge.target))
  if (anchors.length) {
    const { forceSimulation, forceLink, forceManyBody, forceCenter, forceCollide } = await import('d3-force')
    let seed = 42
    const solver = forceSimulation<Anchor>(anchors.map(node => ({ id: node.id, kind: node.kind }))).stop()
    try {
      solver.randomSource(() => ((seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0) / 4294967296))
        .force('link', forceLink<Anchor, { source: string | Anchor; target: string | Anchor }>(skeleton.map(edge => ({ source: edge.source, target: edge.target })))
          .id(node => node.id).distance(180).strength(.15))
        .force('charge', forceManyBody<Anchor>().strength(-180))
        .force('center', forceCenter(0, 0))
        .force('collision', forceCollide<Anchor>(node => node.kind === 'job' ? 77 : 26))
        .alphaDecay(.05).tick(120)
      solver.nodes().forEach(node => positions.set(node.id, { x: node.x!, y: node.y! }))
    } finally { solver.stop() }
  }
  // 同一邻域使用稳定的局部槽位；共享节点的中心始终由全部不同岗位决定。
  const groups = new Map<string, GraphNode[]>()
  const isolated: GraphNode[] = []
  for (const node of sorted) {
    if (node.kind === 'job') continue
    const ids = [...(parents.get(node.id) || [])].sort(compare)
    if (!ids.length) { isolated.push(node); continue }
    const key = JSON.stringify(ids)
    if (!groups.has(key)) groups.set(key, [])
    groups.get(key)!.push(node)
  }
  for (const [key, group] of groups) {
    const ids: string[] = JSON.parse(key)
    const center = ids.reduce((sum, id) => {
      const point = positions.get(id)!
      return { x: sum.x + point.x / ids.length, y: sum.y + point.y / ids.length }
    }, { x: 0, y: 0 })
    group.forEach((node, index) => {
      const radius = ids.length === 1 ? 55 + 14 * Math.sqrt(index) : 18 * Math.sqrt(index)
      const angle = index * goldenAngle
      positions.set(node.id, { x: center.x + radius * Math.cos(angle), y: center.y + radius * Math.sin(angle) })
    })
  }
  const outerRadius = Math.max(0, ...[...positions.values()].map(point => Math.hypot(point.x, point.y))) + 180
  isolated.forEach((node, index) => {
    const radius = outerRadius + 24 * Math.sqrt(index)
    positions.set(node.id, { x: radius * Math.cos(index * goldenAngle), y: radius * Math.sin(index * goldenAngle) })
  })
  return positions
}

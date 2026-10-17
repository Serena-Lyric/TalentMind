import type { GraphNode, GraphEdge } from '../api/graph'
import type { Point } from './nebulaLegacy'

export interface Bounds { left: number; right: number; top: number; bottom: number }
export interface EdgeOptions {
  activeKinds: Set<GraphNode['kind']>
  selectedId?: string
  viewport: Bounds
  scale: number
  limit?: number
}

export function selectEdges(edges: GraphEdge[], nodes: GraphNode[], positions: Map<string, Point>, options: EdgeOptions): GraphEdge[] {
  const visible = new Set(nodes.filter(node => options.activeKinds.has(node.kind)).map(node => node.id))
  const candidates = edges.filter(edge => visible.has(edge.source) && visible.has(edge.target)
    && positions.has(edge.source) && positions.has(edge.target)
    && (options.selectedId
      ? edge.source === options.selectedId || edge.target === options.selectedId
      : segmentInBounds(positions.get(edge.source)!, positions.get(edge.target)!, options.viewport)))
  const key = (edge: GraphEdge) => JSON.stringify([edge.kind, edge.source, edge.target])
  const center = { x: (options.viewport.left + options.viewport.right) / 2, y: (options.viewport.top + options.viewport.bottom) / 2 }
  const priority = (edge: GraphEdge) => {
    const source = positions.get(edge.source)!
    const target = positions.get(edge.target)!
    const inside = (p: Point) => p.x >= options.viewport.left && p.x <= options.viewport.right && p.y >= options.viewport.top && p.y <= options.viewport.bottom
    return { inside: Number(inside(source)) + Number(inside(target)), distance: Math.hypot((source.x + target.x) / 2 - center.x, (source.y + target.y) / 2 - center.y) }
  }
  const ranked = candidates.map(edge => ({ edge, ...priority(edge), key: key(edge) }))
    .sort((a, b) => b.inside - a.inside || a.distance - b.distance || (a.key < b.key ? -1 : a.key > b.key ? 1 : 0))
  if (options.selectedId || options.scale >= 1.8) return ranked.map(item => item.edge)
  const limit = Math.max(0, options.limit ?? 900)
  const groups = new Map<string, typeof ranked>()
  for (const item of ranked) {
    if (!groups.has(item.edge.kind)) groups.set(item.edge.kind, [])
    groups.get(item.edge.kind)!.push(item)
  }
  // 类型轮转、覆盖新端点优先，然后补足预算；不依赖数据库返回顺序。
  const lists = [...groups].sort(([a], [b]) => a < b ? -1 : a > b ? 1 : 0).map(([, list]) => list)
  const covered = new Set<string>()
  const picked = new Set<GraphEdge>()
  const result: GraphEdge[] = []
  for (const coverageOnly of [true, false]) {
    const cursors = lists.map(() => 0)
    let progress = true
    while (progress && result.length < limit) {
      progress = false
      lists.forEach((list, index) => {
        while (cursors[index] < list.length && result.length < limit) {
          const edge = list[cursors[index]++].edge
          if (picked.has(edge) || (coverageOnly && covered.has(edge.source) && covered.has(edge.target))) continue
          result.push(edge); picked.add(edge); covered.add(edge.source); covered.add(edge.target)
          progress = true
          break
        }
      })
    }
  }
  return result
}

export function dashedEdge(edge: GraphEdge, nodes: Map<string, GraphNode>) {
  return edge.kind.toLowerCase() === 'related_to' && nodes.get(edge.source)?.kind === 'job' && nodes.get(edge.target)?.kind === 'job'
}

export function segmentInBounds(a: Point, b: Point, bounds: Bounds): boolean {
  let start = 0; let end = 1
  const dx = b.x - a.x; const dy = b.y - a.y
  for (const [p, q] of [[-dx, a.x - bounds.left], [dx, bounds.right - a.x], [-dy, a.y - bounds.top], [dy, bounds.bottom - a.y]]) {
    if (p === 0) { if (q < 0) return false; continue }
    const ratio = q / p
    if (p < 0) start = Math.max(start, ratio)
    else end = Math.min(end, ratio)
    if (start > end) return false
  }
  return true
}

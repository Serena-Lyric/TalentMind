import type { GraphNode, GraphEdge } from '../api/graph'
import type { Point } from './nebulaViewport'

export interface Bounds { left: number; right: number; top: number; bottom: number }
export interface EdgeOptions {
  activeKinds: Set<GraphNode['kind']>
  selectedId?: string
  viewport: Bounds
  scale: number
  limit?: number
  preserveLongNear?: boolean
}
export function selectEdges(edges: GraphEdge[], nodes: GraphNode[], positions: Map<string, Point>, options: EdgeOptions): GraphEdge[] {
  return selectEdgePlan(edges,nodes,positions,options).edges
}
export function edgeAppearance(edge: GraphEdge, nodes: Map<string, GraphNode>, scale: number, focused: boolean, length: number) {
  const scene = edge.kind.toLowerCase() === 'applies_to'
  const related = dashedEdge(edge,nodes)
  const base = scale < .18 ? .1 : scene ? .15 : .2
  return {
    color: scene ? '#c77dff' : related ? '#8e89c4' : '#4fa2ff',
    alpha: focused ? .7 : base * Math.min(1, 120 / Math.max(120,length)),
    width: focused ? 1.15 : scale < .18 ? .5 : .65,
    dash: scene ? [1,4] : related ? [6,5] : [],
  }
}

export function selectEdgePlan(edges: GraphEdge[], nodes: GraphNode[], positions: Map<string, Point>, options: EdgeOptions) {
  const visible = new Set(nodes.filter(node => options.activeKinds.has(node.kind)).map(node => node.id))
  const direct = options.selectedId ? edges.filter(edge => edge.source === options.selectedId || edge.target === options.selectedId) : []
  const dataDegree = direct.length
  const typeFilteredDirect = direct.filter(edge => visible.has(edge.source) && visible.has(edge.target)).length
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
    return { inside: Number(inside(source)) + Number(inside(target)), distance: Math.hypot((source.x + target.x) / 2 - center.x, (source.y + target.y) / 2 - center.y), length: Math.hypot(source.x-target.x,source.y-target.y) * options.scale }
  }
  const zoomed = options.scale >= 1.8
  const maxLength = options.scale < .18 ? 72 : options.scale < .5 ? 180 : 480
  const ranked = candidates.map(edge => ({ edge, ...priority(edge), key: key(edge) }))
    .filter(item => options.selectedId || zoomed || (options.preserveLongNear && options.scale>=1.25) || item.length <= maxLength)
    .sort((a, b) => a.length - b.length || b.inside - a.inside || a.distance - b.distance || (a.key < b.key ? -1 : a.key > b.key ? 1 : 0))
  const visibleDirect = options.selectedId ? candidates.length : 0
  const lengthHidden=candidates.length-ranked.length, eligibleCount=ranked.length
  if (options.selectedId || zoomed) return { edges: ranked.map(item => item.edge), candidates: candidates.length, visibleDirect, dataDegree, typeFilteredDirect,lengthHidden,eligibleCount }
  const limit = Math.max(0, Math.min(options.limit ?? 900, options.scale < .18 ? 120 : options.scale < .5 ? 300 : 900))
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
  return { edges: result, candidates: candidates.length, visibleDirect, dataDegree, typeFilteredDirect,lengthHidden,eligibleCount }
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

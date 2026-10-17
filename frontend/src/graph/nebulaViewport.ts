import type { GraphNode, GraphEdge } from '../api/graph'
import type { Point } from './nebulaLegacy'
import type { Bounds } from './nebulaEdges'

export interface Transform { x: number; y: number; scale: number }
export interface Viewport { width: number; height: number }
export function nextSearchIndex(current: number, count: number, direction: 1 | -1): number {
  if (!count) return -1
  if (current < 0 || current >= count) return direction === 1 ? 0 : count - 1
  return (current + direction + count) % count
}
export function availableGraphArea(view: Viewport, panels: Bounds[]): Bounds {
  const full = { left: 0, right: view.width, top: 0, bottom: view.height }
  const obstacles = panels.map(panel => ({
    left: Math.max(0, panel.left), right: Math.min(view.width, panel.right),
    top: Math.max(0, panel.top), bottom: Math.min(view.height, panel.bottom),
  })).filter(panel => panel.left < panel.right && panel.top < panel.bottom)
  const xs = [...new Set([0, view.width, ...obstacles.flatMap(panel => [panel.left, panel.right])])].sort((a,b)=>a-b)
  const ys = [...new Set([0, view.height, ...obstacles.flatMap(panel => [panel.top, panel.bottom])])].sort((a,b)=>a-b)
  let best = full; let bestArea = 0
  // 两块固定面板，枚举其边界形成的空矩形；不估算面板宽度。
  for (let l = 0; l < xs.length - 1; l++) for (let r = l + 1; r < xs.length; r++) {
    for (let t = 0; t < ys.length - 1; t++) for (let b = t + 1; b < ys.length; b++) {
      const rect = { left: xs[l], right: xs[r], top: ys[t], bottom: ys[b] }
      if (obstacles.some(panel => rect.left < panel.right && rect.right > panel.left && rect.top < panel.bottom && rect.bottom > panel.top)) continue
      const size = (rect.right - rect.left) * (rect.bottom - rect.top)
      if (size > bestArea) { best = rect; bestArea = size }
    }
  }
  return best
}
export function visibleInFocus(id: string, focus: Set<string>) {
  return !focus.size || focus.has(id)
}
export function resolveSelection(id: string | undefined, nodes: GraphNode[], edges: GraphEdge[]) {
  const node = nodes.find(node => node.id === id) || null
  const ids = new Set(node ? [node.id] : [])
  if (node) {
    const validIds = new Set(nodes.map(node => node.id))
    for (const edge of edges) {
      if (!validIds.has(edge.source) || !validIds.has(edge.target)) continue
      if (edge.source === node.id) ids.add(edge.target)
      if (edge.target === node.id) ids.add(edge.source)
    }
  }
  return { node, ids }
}
export function toScreen(point: Point, view: Viewport, transform: Transform): Point {
  return { x: view.width / 2 + (point.x + transform.x) * transform.scale, y: view.height / 2 + (point.y + transform.y) * transform.scale }
}
export function toWorld(point: Point, view: Viewport, transform: Transform): Point {
  return { x: (point.x - view.width / 2) / transform.scale - transform.x, y: (point.y - view.height / 2) / transform.scale - transform.y }
}
export function hitPoint(world: Point, center: Point, radius: number, scale: number) {
  return Math.hypot(world.x - center.x, world.y - center.y) * scale <= radius + 7
}
export function focusTransform(points: Point[], view: Viewport, area?: Bounds): Transform {
  if (!points.length) return { x: 0, y: 0, scale: 1 }
  const xs = points.map(point => point.x); const ys = points.map(point => point.y)
  const minX = Math.min(...xs); const maxX = Math.max(...xs)
  const minY = Math.min(...ys); const maxY = Math.max(...ys)
  const bounds = area || { left: 276, right: view.width - 392, top: 24, bottom: view.height - 24 }
  const width = Math.max(1, bounds.right - bounds.left - 40)
  const height = Math.max(1, bounds.bottom - bounds.top - 40)
  const scale = Math.min(1, width / Math.max(1, maxX - minX), height / Math.max(1, maxY - minY))
  return {
    scale,
    x: -(minX / 2 + maxX / 2) + ((bounds.left + bounds.right) / 2 - view.width / 2) / scale,
    y: -(minY / 2 + maxY / 2) + ((bounds.top + bounds.bottom) / 2 - view.height / 2) / scale,
  }
}
export function searchNodes<T extends GraphNode>(nodes: T[], keyword: string, activeKinds: Set<GraphNode['kind']>): T[] {
  const word = keyword.trim().toLowerCase()
  if (!word) return []
  const exact = (node: T) => node.label.toLowerCase() === word || node.id.toLowerCase() === word
  return nodes.filter(node => activeKinds.has(node.kind) && (node.label.toLowerCase().includes(word) || node.id.toLowerCase().includes(word)))
    .sort((a, b) => Number(exact(b)) - Number(exact(a)) || (a.id < b.id ? -1 : a.id > b.id ? 1 : 0))
}

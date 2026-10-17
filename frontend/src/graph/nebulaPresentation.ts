import type { GraphNode } from '../api/graph'
import type { Bounds } from './nebulaEdges'

export function nodeAppearance(kind: GraphNode['kind'], radius: number, scale: number, selected = false, matched = false, hovered = false) {
  const minimum = selected || hovered ? 3.5 : matched ? 1.8 : kind === 'job' ? .9 : kind === 'skill' ? .35 : .6
  return {
    radius: Math.max(minimum, radius * scale),
    label: selected || hovered || scale >= 1.25 || (scale >= .65 && (kind === 'job' || matched)),
    shadow: selected || scale >= .5 ? kind === 'skill' ? 8 : 16 : 0,
    outline: selected || hovered || matched || scale >= .35,
  }
}

export interface LabelCandidate { id: string; bounds: Bounds; priority: number }
export function selectLabels(labels: LabelCandidate[], viewport: Bounds, panels: Bounds[]): Set<string> {
  const overlaps = (a: Bounds, b: Bounds) => a.left < b.right && a.right > b.left && a.top < b.bottom && a.bottom > b.top
  const grid = new Map<string, Bounds[]>()
  const selected = new Set<string>()
  const cells = (box: Bounds) => {
    const keys: string[] = []
    for (let x = Math.floor(box.left / 64); x <= Math.floor(box.right / 64); x++) {
      for (let y = Math.floor(box.top / 64); y <= Math.floor(box.bottom / 64); y++) keys.push(`${x}:${y}`)
    }
    return keys
  }
  for (const label of [...labels].sort((a,b) => b.priority - a.priority || (a.id < b.id ? -1 : a.id > b.id ? 1 : 0))) {
    const box = label.bounds
    if (box.left < viewport.left || box.right > viewport.right || box.top < viewport.top || box.bottom > viewport.bottom || panels.some(panel => overlaps(box, panel))) continue
    const keys = cells(box)
    if (keys.some(key => grid.get(key)?.some(other => overlaps(box, other)))) continue
    selected.add(label.id)
    for (const key of keys) {
      if (!grid.has(key)) grid.set(key, [])
      grid.get(key)!.push(box)
    }
  }
  return selected
}

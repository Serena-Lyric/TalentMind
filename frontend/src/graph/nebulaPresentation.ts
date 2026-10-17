import type { GraphNode } from '../api/graph'

export function nodeAppearance(kind: GraphNode['kind'], radius: number, scale: number, selected = false, matched = false) {
  const minimum = selected ? 3.5 : kind === 'job' ? .9 : kind === 'skill' ? .35 : .6
  return {
    radius: Math.max(minimum, radius * scale),
    label: selected || (scale >= .65 && (kind === 'job' || matched)),
    shadow: selected || scale >= .5 ? kind === 'skill' ? 8 : 16 : 0,
    outline: selected || scale >= .35,
  }
}

import type { GraphNode, GraphEdge } from '../api/graph'

export interface Point { x: number; y: number }

export function buildLegacyLayout(nodes: GraphNode[], edges: GraphEdge[]): Map<string, Point> {
  const layout = new Map<string, Point>()
  const jobs = nodes.filter(node => node.kind === 'job').sort((a, b) => a.id.localeCompare(b.id))
  const industries = nodes.filter(node => node.kind === 'industry').sort((a, b) => a.id.localeCompare(b.id))
  const skills = nodes.filter(node => node.kind === 'skill').sort((a, b) => a.id.localeCompare(b.id))
  const jobIds = new Set(jobs.map(node => node.id))
  const skillIds = new Set(skills.map(node => node.id))
  jobs.forEach((job, index) => {
    const radius = 150 * Math.sqrt(index + .6)
    const angle = index * 2.39996323
    layout.set(job.id, { x: radius * Math.cos(angle), y: radius * Math.sin(angle) })
  })
  industries.forEach((node, index) => layout.set(node.id, { x: -420 + index * 110, y: -280 + (index % 2) * 70 }))

  const skillLinks = new Map<string, string[]>()
  edges.forEach((edge) => {
    const jobId = jobIds.has(edge.source) ? edge.source : jobIds.has(edge.target) ? edge.target : ''
    const skillId = skillIds.has(edge.source) ? edge.source : skillIds.has(edge.target) ? edge.target : ''
    if (jobId && skillId) {
      const list = skillLinks.get(jobId) || []
      list.push(skillId)
      skillLinks.set(jobId, list)
    }
  })
  skillLinks.forEach((skillIds, jobId) => {
    const parent = layout.get(jobId)
    if (!parent) return
    const unique = [...new Set(skillIds)].sort()
    unique.forEach((skillId, index) => {
      if (layout.has(skillId)) return
      const ring = Math.floor(index / 14)
      const slot = index % 14
      const angle = (slot / 14) * Math.PI * 2 + ring * .42
      const distance = 50 + ring * 28
      layout.set(skillId, { x: parent.x + Math.cos(angle) * distance, y: parent.y + Math.sin(angle) * distance })
    })
  })
  skills.forEach((node, index) => {
    if (!layout.has(node.id)) {
      const radius = 520 + (index % 4) * 90
      const angle = index * 2.39996323
      layout.set(node.id, { x: radius * Math.cos(angle), y: radius * Math.sin(angle) })
    }
  })
  nodes.forEach((node, index) => {
    if (!layout.has(node.id)) layout.set(node.id, { x: (index % 10) * 90, y: Math.floor(index / 10) * 90 })
  })
  return layout
}

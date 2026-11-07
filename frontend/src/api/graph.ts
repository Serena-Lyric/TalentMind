
﻿/**
 * 数据图谱模块 API
 */

// ============================================================
// 类型定义
// ============================================================

export interface GraphNode {
  id: string
  label: string
  kind: 'industry' | 'job' | 'skill'
  size: number
  color: string
  status?: string
  jobs?: number
  level?: string
  growth?: string
  desc?: string
  parent?: string
  name_en?: string
  source?: string[]
  platform_label?: string
  core_duties?: string
  required_skills?: string[]
  bonus_skills?: string[]
  scenarios?: string[]
  category?: string
  is_emerging?: boolean
  canonical_name?: string
  evolution?: Record<string, unknown>
  identity_status?: 'verified' | 'pending' | 'unknown'
  content_eligible?: boolean | null
  identity_evidence?: Record<string, any> | null
  formal_statistics_eligible?: boolean
  raw?: Record<string, any>
  sourceIndex?: number
}

export interface GraphEdge {
  source: string
  target: string
  raw?: Record<string, any>
  sourceIndex?: number
  kind: string
}

export interface GraphData {
  nodes: GraphNode[]
  edges: GraphEdge[]
  stats: {
    totalNodes: number
    totalEdges: number
    added: number
    removed: number
    changed: number
  }
}

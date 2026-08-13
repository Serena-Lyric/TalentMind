import { get } from '../utils/request'

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
}

export interface GraphEdge {
  source: string
  target: string
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

// ============================================================
// 接口函数
// ============================================================

/**
 * GET /api/graph/data
 * 获取图谱节点与边数据
 *
 * 入参：{ year?: string, focusJob?: string }
 * 响应示例：
 * {
 *   code: 200,
 *   data: {
 *     nodes: [ { id, label, kind, size, color, status, ... } ],
 *     edges: [ { source, target, kind } ],
 *     stats: { totalNodes, totalEdges, added, removed, changed }
 *   }
 * }
 */
export async function getGraphData(year = '2026', focusJob = 'all'): Promise<GraphData> {
  
  return get<GraphData>('/graph/data', { year, focusJob })
}

/**
 * GET /api/graph/jobs
 * 获取图谱可选岗位列表（用于聚焦筛选）
 *
 * 入参：无
 * 响应示例：{ code: 200, data: [{ value: 'frontend', label: '前端开发工程师' }] }
 */
export async function getGraphJobs() {
  
  return get('/graph/jobs')
}

/**
 * GET /api/graph/years
 * 获取图谱可用年份列表
 *
 * 入参：无
 * 响应示例：{ code: 200, data: ['2024', '2025', '2026'] }
 */
export async function getGraphYears() {
  
  return get('/graph/years')
}

/**
 * GET /api/graph/skill-radar
 * 获取节点技能雷达图数据
 *
 * 入参：{ nodeName: string }
 * 响应示例：
 * {
 *   code: 200,
 *   data: {
 *     dimensions: ['市场需求','技术热度',...],
 *     values: [88,92,85,90,65,82,88,80]
 *   }
 * }
 */
export async function getGraphSkillRadar(nodeName: string) {
  
  return get('/graph/skill-radar', { nodeName })
}
/**
 * 岗位管理模块 API
 */

import { get, post, put, del, USE_MOCK } from '../utils/request'
import { jobs } from '../data/mock'

// ============================================================
// 类型定义
// ============================================================

export interface Job {
  id: string
  title: string
  company: string
  city: string
  type: string
  salary: string
  status: string
  skills: string[]
  updated: string
  track?: string
  kind?: string
  evolution?: {
    added: string[]
    removed: string[]
    changed: string[]
  }
  skillDetails?: { name: string; level: string; requirement: string }[]
  responsibilities?: string[]
  requirements?: string[]
  jdVersions?: { year: number; version: string; publishedAt: string; content: string; skills: string[] }[]
}

export interface JobQuery {
  keyword?: string
  city?: string
  track?: string
  skillStatus?: '新增' | '淘汰' | '变更'
  salaryRange?: string
  startTime?: string
  endTime?: string
  page?: number
  pageSize?: number
}

export interface JobListResult {
  list: Job[]
  total: number
  page: number
  pageSize: number
}

// ============================================================
// 接口函数
// ============================================================

/**
 * GET /api/jobs
 * 岗位列表查询（带筛选 + 分页）
 *
 * 入参：JobQuery
 * 响应示例：
 * {
 *   code: 200,
 *   data: { list: Job[], total: 2468, page: 1, pageSize: 10 },
 *   message: "success"
 * }
 */
export async function getJobList(query: JobQuery = {}): Promise<JobListResult> {
  if (USE_MOCK) {
    let filtered = [...jobs] as Job[]
    if (query.keyword) {
      const kw = query.keyword.toLowerCase()
      filtered = filtered.filter(j => j.title.toLowerCase().includes(kw) || j.company.toLowerCase().includes(kw))
    }
    if (query.city) filtered = filtered.filter(j => j.city === query.city)
    if (query.track) filtered = filtered.filter(j => j.track === query.track)
    const page = query.page || 1
    const pageSize = query.pageSize || 10
    return {
      list: filtered.slice((page - 1) * pageSize, page * pageSize),
      total: filtered.length,
      page,
      pageSize
    }
  }
  return get<JobListResult>('/jobs', query)
}

/**
 * GET /api/jobs/:id
 * 岗位详情
 *
 * 入参：id (路径参数)
 * 响应：Job 完整对象
 */
export async function getJobDetail(id: string): Promise<Job> {
  if (USE_MOCK) {
    return (jobs as Job[]).find(j => j.id === id) || ({} as Job)
  }
  return get<Job>(`/jobs/${id}`)
}

/**
 * POST /api/jobs
 * 新增岗位
 *
 * 入参：Omit<Job, 'id' | 'updated'>
 * 响应：{ id: string }
 */
export async function createJob(data: Partial<Job>) {
  if (USE_MOCK) {
    return { id: 'JD-MOCK-' + Date.now() }
  }
  return post('/jobs', data)
}

/**
 * PUT /api/jobs/:id
 * 编辑岗位
 *
 * 入参：Partial<Job>
 * 响应：{ success: boolean }
 */
export async function updateJob(id: string, data: Partial<Job>) {
  if (USE_MOCK) {
    return { success: true }
  }
  return put(`/jobs/${id}`, data)
}

/**
 * DELETE /api/jobs/:id
 * 删除岗位
 *
 * 入参：id (路径参数)
 * 响应：{ success: boolean }
 */
export async function deleteJob(id: string) {
  if (USE_MOCK) {
    return { success: true }
  }
  return del(`/jobs/${id}`)
}

/**
 * POST /api/jobs/batch-delete
 * 批量删除岗位
 *
 * 入参：{ ids: string[] }
 * 响应：{ deleted: number }
 */
export async function batchDeleteJobs(ids: string[]) {
  if (USE_MOCK) {
    return { deleted: ids.length }
  }
  return post('/jobs/batch-delete', { ids })
}

/**
 * POST /api/jobs/import
 * 批量导入 JD 文本
 *
 * 入参：FormData (file 字段)
 * 响应：{ imported: number, jobs: Job[] }
 */
export async function importJobs(file: File) {
  if (USE_MOCK) {
    return { imported: 3, jobs: [] as Job[] }
  }
  const formData = new FormData()
  formData.append('file', file)
  return post('/jobs/import', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

/**
 * GET /api/jobs/export
 * 批量导出岗位 Excel
 *
 * 入参：{ ids?: string[] }  (不传则导出全部筛选结果)
 * 响应：Blob (Excel 文件)
 */
export async function exportJobs(ids?: string[]) {
  if (USE_MOCK) {
    return null // mock 模式下不实际导出
  }
  return get('/jobs/export', { ids: ids?.join(',') }, { responseType: 'blob' })
}
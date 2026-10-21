import { get, post, put } from '../utils/request'

export interface CollectionCity { name: string; code: string }
export interface CollectionPlatform { platform: string; label: string; supported: boolean; cities: CollectionCity[] }
export interface CollectionTask {
  run_id: string | null
  platform?: string
  status: string
  mode?: 'once' | 'limited' | 'continuous'
  started_at?: string | null
  finished_at?: string | null
  current_keyword?: string | null
  current_city?: string | null
  current_round?: number | null
  total_rounds?: number | null
  listed?: number | null
  detail_attempted?: number | null
  detail_obtained?: number | null
  content_eligible?: number | null
  identity_pending?: number | null
  identity_verified?: number | null
  complete?: number | null
  inserted?: number | null
  updated?: number | null
  skipped?: number | null
  rejected?: number | null
  failed?: number | null
  // 旧日志兼容字段不代表本轮完整性或写入证据。
  details?: number | null
  new?: number | null
  errors?: number | null
  stop_reason?: string | null
  last_error?: string | null
  log_status?: string
  raw_log_tail?: string[]
}

export interface CollectionConfig {
  mode: 'once' | 'limited' | 'continuous'
  platform?: string
  keywords: string[]
  cities: CollectionCity[]
  pages: number
  detail_limit: number
  max_jobs: number
  page_delay_min?: number
  page_delay_max?: number
  settle_min?: number
  settle_max?: number
  switch_interval_min?: number
  switch_interval_max?: number
  rounds?: number
  check_cdp_before_start?: boolean
  cdp_endpoint?: string
  user_data_dir?: string | null
}

export interface CollectionStats {
  available?: boolean
  error?: string | null
  database_total: number | null
  database_boss_total?: number | null
  database_new_count?: number | null
  platform_counts: { platform: string; label: string; count: number | null }[]
  latest_crawled_at?: string | null
  data_quality?: {
    empty_source_detail: number | null
    duplicate_source_detail: number | null
    placeholder_empty_url: number | null
    duties_nonempty: number | null
    status_distribution?: { status: string; count: number }[]
  } | null
}

export interface CollectionAccess {
  access_state: string
  can_collect: boolean
  content_limited?: boolean
  reason?: string
  message?: string
}
export interface CDPStatus {
  endpoint?: string
  reachable: boolean
  platform_access?: Record<string, CollectionAccess>
  platform_pages?: Record<string, number>
  error?: string
}
export interface CollectionPreparation extends CollectionAccess {
  cdp: CDPStatus
  message: string
  target_url?: string
}

export interface CollectionResult {
  source?: string
  job_title: string
  source_detail?: string | null
  crawled_at?: string | null
  raw_text?: string | null
  duties?: string | null
  requirements?: string | null
  structure_source?: string | null
  quality?: number | null
  rejection_reason?: string | null
  outcome?: string | null
  jd_pool_id?: number | null
  identity_status?: 'verified' | 'pending' | 'unknown'
  content_eligible?: boolean | null
  identity_evidence?: Record<string, any> | null
}
export interface CollectionRaw extends CollectionResult { id?: number; content?: string }

export type CollectionBatchStatus = 'queued' | 'running' | 'waiting_next_round' | 'stopping' | 'stopped' | 'completed' | 'blocked' | 'error' | 'interrupted'
export type CollectionBatchItemStatus = 'queued' | 'preparing' | 'running' | 'completed' | 'error' | 'blocked' | 'cancelled' | 'stopped' | 'interrupted'
export interface CollectionBatchItem {
  item_id: string
  keyword: string
  city: CollectionCity
  status: CollectionBatchItemStatus
  run_id: string | null
  started_at: string | null
  finished_at: string | null
  stop_reason: string | null
  listed: number | null
  detail_attempted: number | null
  detail_obtained: number | null
  content_eligible: number | null
  identity_pending: number | null
  identity_verified: number | null
  complete: number | null
  inserted: number | null
  updated: number | null
  skipped: number | null
  rejected: number | null
  failed: number | null
}
export interface CollectionBatch {
  batch_id: string
  platform: string
  status: CollectionBatchStatus
  created_at: string
  started_at: string | null
  finished_at: string | null
  stop_reason: string | null
  total: number
  completed: number
  current_item_id: string | null
  next_run_at: string | null
  items: CollectionBatchItem[]
}
export interface CollectionBatchPlan {
  platform: string
  keywords: string[]
  cities: CollectionCity[]
  pages: 1
  max_jobs: number
  detail_limit: number
}
export interface CollectionBridgeSession {
  run_id: string
  platform: 'boss'
  status: string
  keywords?: string[]
  cities?: CollectionCity[]
  current_keyword?: string | null
  current_city?: string | null
  listed: number
  detail_attempted: number
  detail_obtained: number
  content_eligible: number
  identity_pending: number
  identity_verified: number
  complete: number
  inserted: number
  updated: number
  new?: number
  skipped: number
  rejected: number
  failed: number
  started_at?: string | null
  updated_at?: string | null
  finished_at: string | null
  stop_reason?: string | null
}
export interface CollectionBridgePairing {
  token: string
  extension_id: string
  extension_path: string
  sessions: CollectionBridgeSession[]
}
export interface CollectionBridgeCreate {
  platform: 'boss'
  keyword: string
  city_name: string
  city_code: string
  pages: 1
  detail_limit: number
  max_jobs: number
}
export function createCollectionBatch(data: CollectionBatchPlan) { return post<CollectionBatch>('/collection/batches', data) }
export function getCollectionBatches() { return get<{ items: CollectionBatch[]; total: number }>('/collection/batches') }
export function getCollectionBatch(batch_id: string) { return get<CollectionBatch>(`/collection/batches/${encodeURIComponent(batch_id)}`) }
export function getCollectionBatchItemTask(batch_id: string, item_id: string) { return get<CollectionTask>(`/collection/batches/${encodeURIComponent(batch_id)}/items/${encodeURIComponent(item_id)}/task`) }
export function startCollectionBatch(batch_id: string) { return post<CollectionBatch>(`/collection/batches/${encodeURIComponent(batch_id)}/start`, {}) }
export function stopCollectionBatch(batch_id: string) { return post<CollectionBatch>(`/collection/batches/${encodeURIComponent(batch_id)}/stop`, {}) }

// 浏览器准备可能包含进程启动和页面就绪等待；沿用统一请求与响应解包。
export function prepareCollection(auto_start = false, platform?: string, config: Partial<CollectionConfig> = {}) { return post<CollectionPreparation>('/collection/prepare', { ...config, auto_start, platform }, { timeout: 120000 }) }
export function getCollectionPlatforms() { return get<CollectionPlatform[]>('/collection/platforms') }
export function getCollectionStatus() { return get<CollectionTask>('/collection/status') }
export function getCollectionProgress() { return get<CollectionTask>('/collection/progress') }
export function getCollectionStats() { return get<CollectionStats>('/collection/stats') }
export function getDatabaseStats() { return get<CollectionStats>('/collection/database-stats') }
export function getCDPStatus() { return get<CDPStatus>('/collection/cdp-status') }
export function getCollectionConfig() { return get<CollectionConfig>('/collection/config') }
export function updateCollectionConfig(data: Partial<CollectionConfig>) { return put<CollectionConfig>('/collection/config', data) }
export function getCollectionHistory(params: { page?: number; page_size?: number; status?: string; mode?: string; platform?: string } = {}) {
  return get<{ items: CollectionTask[]; total: number }>('/collection/history', params)
}
export function startCollection(data: Partial<CollectionConfig>) { return post<{ run_id: string; status?: string; message?: string }>('/collection/start', data) }
export function stopCollection(run_id?: string | null) { return post('/collection/stop', { run_id }) }
export function getCollectionResults(run_id: string) { return get<CollectionResult[]>('/collection/results', { run_id }) }
export function getCollectionRaw(id: number) { return get<CollectionRaw>(`/collection/raw/${id}`) }
export function getCollectionRecent(limit = 10) { return get<CollectionRaw[]>('/collection/recent', { limit }) }
export function getBridgePairing() { return get<CollectionBridgePairing>('/collection/bridge/pairing') }
export function createBridgeSession(data: CollectionBridgeCreate) { return post<{ run_id: string; session: CollectionBridgeSession }>('/collection/bridge/sessions', data) }
export function getBridgeSession(run_id: string) { return get<CollectionBridgeSession>(`/collection/bridge/sessions/${encodeURIComponent(run_id)}`) }
export function finishBridgeSession(run_id: string, reason?: string) { return post<CollectionBridgeSession>(`/collection/bridge/sessions/${encodeURIComponent(run_id)}/finish`, reason ? { reason } : {}) }

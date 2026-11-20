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

export interface CollectionReadiness {
  ready: boolean
  reason: string | null
  message: string
  missing_columns: string[]
  next_step: string
}
export interface CollectionFrequency {
  platform: string
  state: 'clear' | 'unfinished' | 'busy' | 'unavailable' | 'legacy_migration_required'
  can_recover: boolean
  recovery_token: string | null
  reason: string | null
  message: string
  next_action_at: number | null
  next_combination_at: number | null
  interruption?: 'exception' | 'unknown' | null
}


export interface CollectionRuntimePlatformState {
  platform: string
  status: 'idle' | 'running' | 'waiting' | 'needs_login' | 'blocked' | 'failed' | 'stopped'
  keyword_index: number
  city_index: number
  page: number
  next_run_at: number | null
  last_saved_identity: string | null
  last_success_at: number | null
  stop_reason: string | null
  stats: Record<string, number | null>
  updated_at: number
}

export interface CollectionRuntimeStatus {
  status: 'running' | 'attention' | 'stopped'
  platforms: Record<string, CollectionRuntimePlatformState>
  scheduler_path?: string
}

export interface CollectionRuntimeConfig {
  reset_checkpoint?: boolean
  keywords?: string[]
  cities?: Record<string, [string, string][]>
  pages?: number
  detail_limit?: number
  max_jobs?: number
  page_delay_min?: number
  page_delay_max?: number
  switch_interval_min?: number
  switch_interval_max?: number
  settle?: number
}

export interface CollectionResult {
  source?: string
  job_title: string
  list_title?: string | null
  detail_title?: string | null
  title_source?: 'list' | 'detail' | null
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

// 浏览器准备可能包含进程启动和页面就绪等待；沿用统一请求与响应解包。
export function prepareCollection(auto_start = false, platform?: string, config: Partial<CollectionConfig> = {}) { return post<CollectionPreparation>('/collection/prepare', { ...config, auto_start, platform }, { timeout: 120000 }) }
export function getCollectionPlatforms() { return get<CollectionPlatform[]>('/collection/platforms') }
export function getCollectionReadiness() { return get<CollectionReadiness>('/collection/readiness') }
export function getCollectionFrequency(platform: string) { return get<CollectionFrequency>(`/collection/frequency/${encodeURIComponent(platform)}`) }
export function recoverCollectionFrequency(platform: string, recovery_token: string) { return post<CollectionFrequency & { recovered: boolean }>(`/collection/frequency/${encodeURIComponent(platform)}/recover`, { recovery_token }) }
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
export function getCollectionResults(run_id: string) { return get<CollectionResult[]>('/collection/results', { run_id }) }
export function getCollectionRaw(id: number) { return get<CollectionRaw>(`/collection/raw/${id}`) }
export function getCollectionRecent(limit = 10) { return get<CollectionRaw[]>('/collection/recent', { limit }) }

export function getCollectionRuntimeStatus() { return get<CollectionRuntimeStatus>('/collection/runtime/status') }
export function startCollectionRuntime(data: CollectionRuntimeConfig = {}) { return post<CollectionRuntimeStatus>('/collection/runtime/start', data) }
export function stopCollectionRuntime() { return post<CollectionRuntimeStatus>('/collection/runtime/stop', {}) }
export function resumeCollectionRuntime(platform: string, confirmed = false) {
  return post<CollectionRuntimeStatus>(`/collection/runtime/resume/${encodeURIComponent(platform)}`, { confirmed })
}

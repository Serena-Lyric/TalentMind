import { get, post, put } from '../utils/request'

export interface CollectionTask {
  run_id: string | null
  platform?: 'boss' | 'zhaopin' | 'liepin' | 'linkedin' | 'hn' | string
  log_path?: string | null
  log_status?: 'parsed' | 'missing' | 'empty' | 'unrecognized' | string
  log_summary?: Record<string, number>
  raw_log_tail?: string[]
  status: string
  mode: 'once' | 'limited' | 'continuous'
  started_at: string | null
  finished_at: string | null
  current_keyword: string | null
  current_city: string | null
  current_round: number
  total_rounds: number | null
  listed: number
  details: number
  new: number
  skipped: number
  errors: number
  last_error: string | null
  next_run_at: string | null
  cdp_status: string
  browser_page_status: string | null
  database_total: number
  database_boss_total: number
  database_new_count: number
}

export interface CollectionConfig {
  mode: 'once' | 'limited' | 'continuous'
  keywords: string[]
  cities: { name: string; code: string }[]
  pages: number
  detail_limit: number
  max_jobs: number
  page_delay_min: number
  page_delay_max: number
  settle_min: number
  settle_max: number
  switch_interval_min: number
  switch_interval_max: number
  rounds: number
  check_cdp_before_start: boolean
  cdp_endpoint: string
  user_data_dir?: string | null
  platform?: 'boss' | 'zhaopin' | 'liepin' | 'linkedin' | 'hn'
}

export interface CollectionStats {
  database_total: number
  database_boss_total: number
  database_new_count: number
  platform_counts: { platform: string; label: string; count: number }[]
  latest_crawled_at: string | null
  data_quality: {
    empty_source_detail: number
    duplicate_source_detail: number
    placeholder_empty_url: number
    duties_nonempty: number
    status_distribution: { status: string; count: number }[]
  }
}

export interface CDPStatus {
  endpoint: string
  reachable: boolean
  boss_page_count: number
  last_checked_at: string
  page_targets: { type: string; url: string; title: string }[]
  error?: string
  login_required?: boolean
  platform_pages?: Record<string, number>
  platform_login_required?: Record<string, boolean>
}

export function prepareCollection(auto_start = false, platform?: string) { return post<{ status: string; message: string }>('/collection/prepare', { auto_start, platform }) }
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
export function startCollection(data: Partial<CollectionConfig>) { return post<{ run_id: string }>('/collection/start', data) }
export function stopCollection(run_id?: string | null) { return post('/collection/stop', { run_id }) }

export interface CollectionRaw {
  id: number
  source: string
  job_title: string
  content: string
  quality: number | null
  crawled_at: string | null
}

export function getCollectionRecent(limit = 10) { return get<CollectionRaw[]>('/collection/recent', { limit }) }
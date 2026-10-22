import { get, post } from '../utils/request'

export interface M2Selection { sources: string[]; id_min: number | null; id_max: number | null; limit: number; cohort: string }
export interface M2Stage { status: string; reason?: string | null; run_id: string | null; version_id?: string; result?: any }
export type M2ReviewDecision = 'accepted' | 'rejected' | 'needs_followup'
export interface M2HumanReview {
  review_id: number; schema_version: 'm2-human-review-1'; run_id: string; ordinal: number; jd_id: number | string
  input_sha256: string; machine_sha256: string; machine_status: string; decision: M2ReviewDecision
  reviewer: string; note: string; reviewed_at: string; sha256: string; formal_truth_claim: false
}
export interface M2Item {
  ordinal: number; jd_id: number | string; source: string | null; title: string | null; final_status: string; reason: string | null
  warnings: string[]; input_sha256: string; formal_statistics_eligible: false; confirmed_demand_eligible?: false
  identity_status?: 'verified' | 'pending' | 'unknown'; content_eligible?: boolean | null
  identity_evidence?: Record<string, any> | null; stages: Record<string, M2Stage>
  evidence: { matched: number; invalid: number }; input?: Record<string, any>; input_provenance?: Record<string, any>
  machine_sha256?: string; human_review?: M2HumanReview | null; reviews?: M2HumanReview[]
}
export interface M2Run {
  run_id: string; status: string; reason: string | null; created_at: string; finished_at: string | null; parent_run_id: string | null
  versions: { revision: string; implementation: string; adapter: string; scope: string; taxonomy: string }
  input_sha256: string; selection: M2Selection; provenance: Record<string, any>; items: M2Item[]
  summary: { input_total: number; finalized: number; stage_complete: number; final_counts: Record<string, number>; b1: Record<string, any>; b2: Record<string, any>; b22: Record<string, any>; b3: Record<string, any>; evidence: Record<string, any>; identity: Record<string, number>; content: Record<string, number>; review: Record<string, number> }
  artifacts: Record<string, string>
}
export interface M2History { run_id: string; status: string; created_at: string; reason?: string | null }
export interface M2Sources { total: number; sources: { source: string | null; total: number; id_min: number; id_max: number }[]; cohorts: { name: string; available: boolean; total: number; sha256?: string }[] }
export interface M2ReviewRequest { decision: M2ReviewDecision; reviewer: string; note: string; machine_sha256: string }
const path = (id: string) => `/m2/runs/${encodeURIComponent(id)}`
export const getM2Sources = () => get<M2Sources>('/m2/sources')
export const getM2Runs = () => get<M2History[]>('/m2/runs')
export const createM2Run = (selection: M2Selection) => post<M2Run>('/m2/runs', selection, { timeout: 60000 })
export const getM2Run = (id: string) => get<M2Run>(path(id))
export const getM2Item = (id: string, ordinal: number) => get<M2Item>(`${path(id)}/items/${ordinal}`)
export const startM2Run = (id: string) => post<M2Run>(`${path(id)}/start`, {})
export const stopM2Run = (id: string) => post<M2Run>(`${path(id)}/stop`, {})
export const replayM2Run = (id: string, revision: string) => post<M2Run>(`${path(id)}/replay`, { revision })
export const getM2Report = (id: string) => get<M2Run>(`${path(id)}/report`, undefined, { timeout: 60000 })
export const reviewM2Item = (id: string, ordinal: number, event: M2ReviewRequest) => post<M2Item>(`${path(id)}/items/${ordinal}/review`, event)
export const exportM2Reviews = (id: string) => get<Record<string, any>>(`${path(id)}/reviews/export`, undefined, { timeout: 60000 })
export const generateM2Graph = (id: string) => post<{run_id:string;url:string}>(`${path(id)}/graph`, {}, { timeout: 60000 })

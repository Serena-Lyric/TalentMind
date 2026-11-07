import { get } from '../utils/request'
export interface EvolutionRecord { id:string; change_type:string; skill_name:string; reason:string; source:string; created_at:string; source_jd_time:string; change_nature:string; before:unknown; after:unknown; comparison_available:boolean; previous_version:string|null; version:string|null; detail:unknown; provenance:unknown }
export interface EvolutionTimeline { job_id: string; job_title: string; records: EvolutionRecord[]; current_version: string|null; total_changes: number }
export interface ComparisonLayer { kind:string; before:unknown; after:unknown; available:boolean; changed:boolean|null; reason:string; before_binding?:unknown; after_binding?:unknown; before_causes?:unknown; after_causes?:unknown }
export interface RunComparison { before_run:string; after_run:string; before_request_sha256:string; after_request_sha256:string; before_created_at:string|null; after_created_at:string|null; items:{namespace:string;jd_id:string;source_comparable:boolean;layers:ComparisonLayer[]}[];research:ComparisonLayer;interpretation:string }
export function getJobEvolutionTimeline(jobId: string) { return get<EvolutionTimeline>(`/evolution/timeline/${jobId}`) }
export function compareDeliveryRuns(beforeRun:string,afterRun:string) { return get<RunComparison>('/m2/delivery/compare',{before_run:beforeRun,after_run:afterRun}) }

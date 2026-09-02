import { get, post, put } from '../utils/request'
export interface EvolutionTimeline { job_id: string; job_title: string; records: any[]; current_version: number; total_changes: number }
export function getJobEvolutionTimeline(jobId: string) { return get<EvolutionTimeline>(`/evolution/timeline/${jobId}`) }
export function getSourceStatistics() { return get<{ name: string; count: number }[]>('/evolution/sources/stats') }
export function createEvolutionRecord(data: Record<string, unknown>) { return post('/evolution/record', data) }
export function updateEvolutionRecord(id: string, data: Record<string, unknown>) { return put(`/evolution/record/${id}`, data) }
export function submitEvolutionForReview(id: string) { return post(`/evolution/record/${id}/submit`) }
export function reviewEvolutionRecord(id: string, data: Record<string, unknown>) { return post(`/evolution/record/${id}/review`, data) }
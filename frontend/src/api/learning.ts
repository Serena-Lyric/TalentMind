import { get, post } from '../utils/request'

export interface LearningJob { requirements_version: string; value: string; label: string; name_en: string; category?: string; source: string[] }
export interface LearningSkill {
  name: string
  display_name?: string
  category?: string
  aliases?: string[]
  priority: 'high' | 'medium' | 'low'
  reason: string
  status?: string
  evidence?: string
  bridge_skills?: string[]
  suggestion?: string
  practice?: string
  completion_criteria?: string
}
export interface LearningStage { stage: number; title: string; description?: string; priority?: string; skills: LearningSkill[] }
export interface LearningOverview {
  mastered_required: number
  mastered_bonus: number
  missing_required: number
  missing_bonus: number
  at_standard: boolean
  requirements_available?: boolean
  needs_verification?: number
}
export interface LearningPath {
  requirements_version: string
  score: number
  job_id: string
  job_title: string
  job_name_en?: string
  category?: string
  mastered_skills: string[]
  missing_skills: LearningSkill[]
  verification_skills?: LearningSkill[]
  core_skills: LearningSkill[]
  bonus_skills: LearningSkill[]
  stages: LearningStage[]
  overview?: LearningOverview
  source: string
}
export function getLearningJobs() { return get<LearningJob[]>('/learning/jobs') }
export function generateLearningPath(data: { job_id: string; resume_skills: string[]; requirements_version: string }) { return post<LearningPath>('/learning/generate-path', data) }

import { get, post } from '../utils/request'

export interface LearningJob { value: string; label: string; name_en: string; category?: string; source: string[] }
export interface LearningSkill { name: string; category: string; priority: 'high' | 'medium' | 'low'; reason: string; status: string }
export interface LearningStage { stage: number; title: string; category: string; skills: LearningSkill[] }
export interface LearningPath { job_id: string; job_title: string; job_name_en?: string; category?: string; mastered_skills: string[]; missing_skills: LearningSkill[]; core_skills: LearningSkill[]; bonus_skills: LearningSkill[]; stages: LearningStage[]; source: string }
export function getLearningJobs() { return get<LearningJob[]>('/learning/jobs') }
export function getJobSkills(jobId: string) { return get(`/learning/job-skills/${jobId}`) }
export function generateLearningPath(data: { job_id: string; resume_skills: string[] }) { return post<LearningPath>('/learning/generate-path', data) }
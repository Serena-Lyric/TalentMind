import { post } from '../utils/request'

﻿/**
 * 简历上传模块 API
 */

// ============================================================
// 类型定义
// ============================================================

export interface ResumeProfile {
  name: string
  role: string
  experience: string
  education: string
  company: string
  skills: string[]
  summary: string
  phone?: string
  email?: string
  location?: string
  gender?: string
  age?: number | null
  experience_years?: number | string
  education_school?: string
  education_major?: string
  education_degree?: string
  education_period?: string
  education_history?: { school?: string; major?: string; degree?: string; start_date?: string; end_date?: string }[]
  work_experience?: { company: string; position: string; start_date: string; end_date: string; description: string[] }[]
}

export interface RecommendedJob {
  requirements_version: string
  id: string
  title: string
  platform: string
  platform_label: string
  score: number
  raw_score?: number
  display_score?: number
  is_score_floor?: boolean
  display_randomized?: boolean
  name_en?: string
  category?: string
  source_jd_count?: number
  matched: string[]
  missing: { name: string; level: string; tip: string }[]
  skills: string[]
  collected_at?: string
}

export interface MatchResult {
  score: number
  raw_score?: number
  display_score?: number
  is_score_floor?: boolean
  display_randomized?: boolean
  name_en?: string
  category?: string
  source_jd_count?: number
  matched: string[]
  missing: { name: string; level: string; tip: string }[]
  strengths: string[]
}

// ============================================================
// 接口函数
// ============================================================

/**
 * POST /api/resume/upload
 * 上传简历文件进行解析
 *
 * 入参：FormData (file 字段，支持 PDF/DOCX/UTF-8 TXT，最大 10MB)
 * 响应示例：
 * {
 *   code: 200,
 *   data: {
 *     profile: { name, role, experience, education, company, skills, summary },
 *     matchResult: { score, matched, missing, strengths }
 *   }
 * }
 */
export async function uploadResume(file: File, targetJobId = '') {
  
  const formData = new FormData()
  formData.append('file', file)
  // 后端按用户选择的目标岗位匹配；为空仅生成推荐，不选择学习目标
  if (targetJobId) formData.append('target_job_id', targetJobId)
  return post('/resume/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

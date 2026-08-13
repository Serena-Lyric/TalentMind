import { get, post } from '../utils/request'

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
}

export interface MatchResult {
  score: number
  matched: string[]
  missing: { name: string; level: string; tip: string }[]
  strengths: string[]
}

export interface SkillDimension {
  name: string
  jobStandard: number
  personalAbility: number
}

// ============================================================
// 接口函数
// ============================================================

/**
 * POST /api/resume/upload
 * 上传简历文件进行解析
 *
 * 入参：FormData (file 字段，支持 PDF/DOC/DOCX)
 * 响应示例：
 * {
 *   code: 200,
 *   data: {
 *     profile: { name, role, experience, education, company, skills, summary },
 *     matchResult: { score, matched, missing, strengths }
 *   }
 * }
 */
export async function uploadResume(file: File) {
  
  const formData = new FormData()
  formData.append('file', file)
  return post('/resume/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

/**
 * GET /api/resume/skill-dimensions
 * 获取技能维度雷达图数据
 *
 * 入参：{ targetJob: string }
 * 响应示例：
 * {
 *   code: 200,
 *   data: {
 *     dimensions: ['基础技能','前端开发框架','组件与工具',...],
 *     jobStandard: [80,85,82,...],
 *     personalAbility: [85,90,88,...]
 *   }
 * }
 */
export async function getSkillDimensions(targetJob: string) {
  
  return get('/resume/skill-dimensions', { targetJob })
}

/**
 * GET /api/resume/target-jobs
 * 获取可选目标岗位列表
 *
 * 入参：无
 * 响应示例：
 * {
 *   code: 200,
 *   data: [
 *     { value: 'frontend', label: '高级前端工程师', score: 87 }
 *   ]
 * }
 */
export async function getTargetJobs() {
  
  return get('/resume/target-jobs')
}
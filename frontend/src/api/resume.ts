/**
 * 简历上传模块 API
 */

import { get, post, USE_MOCK } from '../utils/request'

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
  if (USE_MOCK) {
    return {
      profile: {
        name: '林苑琪',
        role: '前端开发工程师',
        experience: '2026届应届生',
        education: '本科 · 软件工程',
        company: '广州应用科技学院',
        skills: ['HTML', 'CSS', 'JavaScript', 'Vue3', 'TypeScript', 'ECharts', 'Git'],
        summary: 'Vue3 项目开发、数据可视化、组件化设计与跨团队协作。'
      } as ResumeProfile,
      matchResult: {
        score: 82,
        matched: ['Vue3', 'TypeScript', 'ECharts', 'Vite', 'Git'],
        missing: [
          { name: '微前端架构', level: 'high', tip: '大型项目常见的应用拆分与集成方案' },
          { name: 'Node.js 服务端', level: 'medium', tip: '提升全栈协作与 BFF 开发能力' }
        ],
        strengths: ['具备完整的 Vue3 项目经验', '熟悉数据可视化与组件化开发']
      } as MatchResult
    }
  }
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
  if (USE_MOCK) {
    return {
      dimensions: ['基础技能', '前端开发框架', '组件与工具', '跨端开发', '全栈开发', '技术扩展', 'AI应用开发能力', '综合素养'],
      jobStandard: [80, 85, 82, 65, 70, 75, 60, 80],
      personalAbility: [85, 90, 88, 60, 55, 70, 65, 82]
    }
  }
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
  if (USE_MOCK) {
    return [
      { value: 'frontend', label: '高级前端工程师', score: 87 },
      { value: 'data', label: '数据分析师', score: 72 }
    ]
  }
  return get('/resume/target-jobs')
}
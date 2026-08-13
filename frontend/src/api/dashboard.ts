/**
 * 统计看板模块 API
 *
 * 真实后端接口（统一响应 {code,message,data}，request.ts 已解包 data）。
 */

// ============================================================
// 类型定义（与后端 DTO 保持一致）
// ============================================================

/** 统计看板概览 */
export interface DashboardOverview {
  totalJobs: number        // 岗位总数
  totalResumes: number     // 解析简历数
  matchSuccess: number     // 匹配成功数
  skillGaps: number        // 技能缺口数量
  coralBlocks: { label: string; value: number }[]  // 珊瑚色统计块
}

/** 趋势数据点 */
export interface TrendPoint {
  month: string
  value: number
}

/** 技能分布项 */
export interface SkillDistItem {
  name: string
  count: number
  percentage: number
}

// ============================================================
// 接口函数
// ============================================================

/**
 * GET /api/dashboard/overview
 * 获取统计看板概览数据
 *
 * 入参：无
 * 响应示例：
 * {
 *   code: 200,
 *   data: {
 *     totalJobs: 2468,
 *     totalResumes: 8932,
 *     matchSuccess: 1847,
 *     skillGaps: 376,
 *     coralBlocks: [
 *       { label: "新增岗位", value: 28 },
 *       { label: "待面试", value: 24 },
 *       { label: "紧急招聘", value: 4 }
 *     ]
 *   },
 *   message: "success"
 * }
 */
export async function getDashboardOverview(): Promise<DashboardOverview> {
  
  // ---- 真实接口 ----
  return get<DashboardOverview>('/dashboard/overview')
}

/**
 * GET /api/dashboard/trend
 * 获取岗位能力趋势折线图数据
 *
 * 入参：{ range?: 'month' | 'quarter' | 'year' }
 * 响应示例：
 * {
 *   code: 200,
 *   data: {
 *     months: ['2月','3月','4月','5月','6月','7月'],
 *     series: [
 *       { name: 'AI算法', color: '#E07B6D', data: [82,88,91,95,98,105] },
 *       { name: '前端开发', color: '#A8C5B8', data: [75,78,82,86,90,94] }
 *     ]
 *   }
 * }
 */
export async function getDashboardTrend(range = 'month') {
  
  return get('/dashboard/trend', { range })
}

/**
 * GET /api/dashboard/skill-distribution
 * 获取岗位技能分布柱状图数据
 *
 * 入参：无
 * 响应示例：
 * {
 *   code: 200,
 *   data: {
 *     skills: [
 *       { name: 'JavaScript', count: 320, percentage: 85 },
 *       { name: 'Python', count: 280, percentage: 74 }
 *     ]
 *   }
 * }
 */
export async function getSkillDistribution(): Promise<SkillDistItem[]> {
  
  return get<SkillDistItem[]>('/dashboard/skill-distribution')
}

/**
 * GET /api/dashboard/skill-radar
 * 获取技能雷达图数据（8维度）
 *
 * 入参：{ skillName: string }
 * 响应示例：
 * {
 *   code: 200,
 *   data: {
 *     dimensions: ['市场需求','技术热度','岗位覆盖','增长趋势','学习难度','生态成熟','薪资水平','就业广度'],
 *     values: [88,92,85,90,65,82,88,80]
 *   }
 * }
 */
export async function getSkillRadar(skillName: string) {
  
  return get('/dashboard/skill-radar', { skillName })
}

/**
 * GET /api/dashboard/industry-tracks
 * 获取行业赛道列表
 *
 * 入参：无
 * 响应示例：
 * {
 *   code: 200,
 *   data: [
 *     { id: 'ai', name: '人工智能', color: '#7c5cff', description: '大模型、算法与智能体应用' }
 *   ]
 * }
 */
export async function getIndustryTracks() {
  
  return get('/dashboard/industry-tracks')
}
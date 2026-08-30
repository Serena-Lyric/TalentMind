/**
 * 星云布局算法 - 黄金角螺旋布局
 * 从挑战杯项目 graph.py 移植而来
 * 用于岗位-技能图谱的星云可视化布局
 */

// 布局参数配置
export interface NebulaLayoutConfig {
  galaxySpacing: number;      // 相邻星系中心间距
  goldenAngle: number;        // 黄金角（弧度）
  skillOrbitRadius: number;   // 技能相对岗位的轨道半径
  skillLayerGap: number;      // 技能多层的层间径向增量
  skillsPerLayer: number;     // 每层最多技能数
}

// 默认配置
export const DEFAULT_NEBULA_CONFIG: NebulaLayoutConfig = {
  galaxySpacing: 165,
  goldenAngle: 2.399963229728653, // 黄金角 ≈ 137.508°
  skillOrbitRadius: 75,
  skillLayerGap: 30,
  skillsPerLayer: 12
};

// 节点类型
export interface NebulaNode {
  id: string;
  type: 'job' | 'skill';
  name: string;
  importance?: number;
  [key: string]: any;
}

// 边类型
export interface NebulaEdge {
  source: string;
  target: string;
  type: string;
  [key: string]: any;
}

// 布局结果
export interface NebulaLayoutResult {
  [nodeId: string]: { x: number; y: number };
}

/**
 * 计算星云结构化布局坐标（黄金角螺旋 / 向日葵排列，位置固定）
 * 
 * 布局策略：
 * 1. 岗位节点按黄金角螺旋均匀铺满平面：r = S·√(i+0.5)，θ = i·黄金角
 * 2. 每个岗位的技能围绕其圆周均匀分布（多层向外展开），形成独立星系
 * 3. 所有坐标为确定值，节点位置完全固定
 */
export function computeNebulaLayout(
  nodes: NebulaNode[],
  edges: NebulaEdge[],
  config: NebulaLayoutConfig = DEFAULT_NEBULA_CONFIG
): NebulaLayoutResult {
  const jobNodes = nodes.filter(n => n.type === 'job');

  if (jobNodes.length === 0) {
    return {};
  }

  // 1. 岗位螺旋坐标
  const jobPositions: Record<string, { x: number; y: number; angle: number }> = {};
  jobNodes.forEach((job, i) => {
    const r = config.galaxySpacing * Math.sqrt(i + 0.5);
    const theta = i * config.goldenAngle;
    jobPositions[job.id] = {
      x: r * Math.cos(theta),
      y: r * Math.sin(theta),
      angle: theta
    };
  });

  // 2. 技能 → 岗位归属（每个技能只属于一个岗位，形成独立星系）
  const jobSkillMap: Record<string, string[]> = {};
  edges.forEach(e => {
    if (e.type === 'REQUIRES') {
      const src = e.source;
      const tgt = e.target;
      if (jobPositions[src]) {
        if (!jobSkillMap[src]) jobSkillMap[src] = [];
        jobSkillMap[src].push(tgt);
      } else if (jobPositions[tgt]) {
        if (!jobSkillMap[tgt]) jobSkillMap[tgt] = [];
        jobSkillMap[tgt].push(src);
      }
    }
  });

  // 3. 技能坐标（绕岗位圆周多层展开）
  const skillPositions: Record<string, { x: number; y: number }> = {};
  Object.entries(jobSkillMap).forEach(([jobId, skillIds]) => {
    const jx = jobPositions[jobId].x;
    const jy = jobPositions[jobId].y;
    const baseAng = jobPositions[jobId].angle;
    const sortedSkillIds = [...skillIds].sort();
    const nSkills = sortedSkillIds.length;

    sortedSkillIds.forEach((sid, i) => {
      const layer = Math.floor(i / config.skillsPerLayer);
      const idx = i % config.skillsPerLayer;
      const countInLayer = Math.min(config.skillsPerLayer, nSkills - layer * config.skillsPerLayer);
      
      let ang: number;
      if (countInLayer === 1) {
        ang = baseAng;
      } else {
        ang = baseAng + 2 * Math.PI * idx / countInLayer;
      }
      
      // 层间相位错开，避免多层技能径向重叠
      ang += layer * 0.35;
      const dist = config.skillOrbitRadius + layer * config.skillLayerGap + (idx % 3) * 3;
      
      skillPositions[sid] = {
        x: jx + dist * Math.cos(ang),
        y: jy + dist * Math.sin(ang)
      };
    });
  });

  // 合并结果
  const layout: NebulaLayoutResult = {};
  Object.entries(jobPositions).forEach(([jid, pos]) => {
    layout[jid] = { x: pos.x, y: pos.y };
  });
  Object.entries(skillPositions).forEach(([sid, pos]) => {
    layout[sid] = { x: pos.x, y: pos.y };
  });

  return layout;
}

/**
 * 计算节点重要度对应的大小
 */
export function getNodeSizeByImportance(importance: number): number {
  if (importance >= 3) return 22; // 高重要度
  if (importance >= 2) return 15; // 中重要度
  return 11; // 低重要度
}

/**
 * 计算岗位相似度（基于技能重叠）
 */
export function calculateJobSimilarity(
  job1Skills: string[],
  job2Skills: string[]
): number {
  const set1 = new Set(job1Skills);
  const set2 = new Set(job2Skills);
  const intersection = new Set([...set1].filter(x => set2.has(x)));
  const union = new Set([...set1, ...set2]);
  
  if (union.size === 0) return 0;
  return intersection.size / union.size;
}

/**
 * 生成岗位-岗位相似度边
 */
export function buildJobSimilarityEdges(
  jobs: Array<{ id: string; skills: string[] }>,
  threshold: number = 0.25
): NebulaEdge[] {
  const edges: NebulaEdge[] = [];
  
  for (let i = 0; i < jobs.length; i++) {
    for (let j = i + 1; j < jobs.length; j++) {
      const similarity = calculateJobSimilarity(jobs[i].skills, jobs[j].skills);
      if (similarity >= threshold) {
        edges.push({
          source: jobs[i].id,
          target: jobs[j].id,
          type: 'SIMILAR_TO',
          weight: similarity
        });
      }
    }
  }
  
  return edges;
}

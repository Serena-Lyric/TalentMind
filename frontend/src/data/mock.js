/**
 * 统一模拟数据层：字段设计与后端 DTO 保持一致。
 * 接入接口时可直接将 exports 替换为 API 返回值，页面组件无需改动。
 */

export const industryTracks = [
  { id: 'ai', name: '人工智能', color: '#7c5cff', description: '大模型、算法与智能体应用' },
  { id: 'bigdata', name: '大数据', color: '#1d9bf0', description: '数据开发、治理与商业分析' },
  { id: 'iot', name: '物联网', color: '#13a58b', description: '边缘计算、嵌入式与设备连接' },
  { id: 'backend', name: '后端开发', color: '#f08c2e', description: '服务端架构与分布式系统' },
  { id: 'frontend', name: '前端开发', color: '#2f7cf6', description: 'Web 应用、体验与工程化' },
  { id: 'cloud', name: '云计算', color: '#3e9cce', description: '云原生、运维与基础设施' },
  { id: 'testing', name: '测试', color: '#e74c3c', description: '质量保障、自动化测试与效能提升' },
  { id: 'product', name: '产品', color: '#e67e22', description: '产品规划、用户研究与增长运营' }
]

const trackDefinitions = {
  ai: {
    type: '人工智能',
    cities: ['北京', '深圳', '上海'],
    mature: ['Python算法工程师', '机器学习工程师', '深度学习工程师', 'NLP算法工程师', '计算机视觉工程师', 'AI平台工程师', '算法测试工程师', '数据标注平台主管'],
    emerging: ['多模态智能体训练工程师', 'RAG应用开发工程师', 'AI提示词工程师'],
    base: ['Python', 'PyTorch', '机器学习', '深度学习', '数据结构', 'Linux'],
    old: ['TensorFlow 1.x', '传统特征工程'],
    added: ['大模型应用', 'RAG', 'Agent', 'LoRA 微调'],
    responsibilities: [
      '负责公司核心AI算法的研发与优化',
      '参与大模型微调、RAG系统设计与Agent框架搭建',
      '与产品、工程团队协作，推动AI能力落地业务场景',
      '跟踪前沿技术动态，进行技术选型与方案评审'
    ],
    requirements: [
      '计算机科学、人工智能等相关专业本科及以上学历',
      '3年以上算法开发经验，熟悉PyTorch/TensorFlow',
      '具备扎实的数学基础和机器学习理论知识',
      '有大模型应用或RAG系统实战经验者优先'
    ]
  },
  bigdata: {
    type: '大数据',
    cities: ['北京', '杭州', '上海'],
    mature: ['大数据开发工程师', '数据仓库工程师', '数据分析师', '数据治理工程师', 'ETL开发工程师', '实时计算工程师', '商业智能工程师', '数据质量工程师'],
    emerging: ['向量数据库工程师', '数据智能体工程师', '湖仓一体架构师'],
    base: ['SQL', 'Python', 'Spark', 'Flink', 'Hive', '数据建模'],
    old: ['MapReduce', 'Excel VBA'],
    added: ['湖仓一体', 'DataOps', '向量检索', '实时特征'],
    responsibilities: [
      '负责数据平台架构设计与核心模块开发',
      '构建数据仓库体系，保障数据质量与一致性',
      '开发ETL流程，支撑业务数据分析与决策',
      '持续优化数据处理性能与系统稳定性'
    ],
    requirements: [
      '计算机、统计学等相关专业本科及以上学历',
      '3年以上大数据开发经验，精通SQL和至少一门编程语言',
      '熟悉Spark/Flink等分布式计算框架',
      '有湖仓一体或实时计算项目经验者优先'
    ]
  },
  iot: {
    type: '物联网',
    cities: ['深圳', '上海', '苏州'],
    mature: ['物联网开发工程师', '嵌入式软件工程师', '边缘计算工程师', '硬件测试工程师', '设备云平台工程师', '通信协议工程师', '智能制造工程师', '车联网工程师'],
    emerging: ['边缘AI部署工程师', '数字孪生工程师', '低代码AI开发工程师'],
    base: ['C/C++', 'MQTT', 'Linux', '嵌入式开发', 'TCP/IP', '传感器'],
    old: ['串口通信', '传统PLC'],
    added: ['边缘AI', '数字孪生', '5G RedCap', '容器化部署'],
    responsibilities: [
      '负责物联网平台核心功能开发与维护',
      '设计设备接入方案，保障设备连接稳定性',
      '开发边缘计算节点程序，实现端侧智能',
      '与硬件团队协作，完成固件联调与测试'
    ],
    requirements: [
      '电子工程、通信、计算机等相关专业本科及以上学历',
      '2年以上嵌入式或物联网开发经验',
      '精通C/C++，熟悉Linux系统和常用通信协议',
      '有MQTT、边缘计算或数字孪生项目经验者优先'
    ]
  },
  backend: {
    type: '后端开发',
    cities: ['上海', '北京', '成都'],
    mature: ['Java后端开发', 'Go后端开发', 'Python后端开发', '分布式系统工程师', '中间件开发工程师', '支付系统工程师', '安全研发工程师', '接口测试开发工程师'],
    emerging: ['Agent架构师', '大模型微调工程师', '行业AI落地顾问'],
    base: ['Java', 'Spring Boot', 'MySQL', 'Redis', '消息队列', 'Docker'],
    old: ['Struts', 'EJB'],
    added: ['云原生', 'Service Mesh', 'AI Gateway', '函数计算'],
    responsibilities: [
      '负责后端服务架构设计与核心代码开发',
      '保障系统高可用、高性能与安全合规',
      '设计并实现API接口，支撑前端与移动端业务',
      '参与技术方案评审与代码质量把控'
    ],
    requirements: [
      '计算机科学相关专业本科及以上学历',
      '3年以上后端开发经验，精通Java/Go之一',
      '熟悉分布式系统设计、微服务架构',
      '有高并发、高可用系统实战经验者优先'
    ]
  },
  frontend: {
    type: '前端开发',
    cities: ['上海', '杭州', '深圳'],
    mature: ['前端开发工程师', '高级前端工程师', '移动端开发工程师', '可视化开发工程师', '前端架构师', 'WebGL开发工程师', '低代码平台工程师', '前端测试工程师'],
    emerging: ['AI前端工程师', '智能交互工程师', 'AIGC界面工程师'],
    base: ['JavaScript', 'TypeScript', 'Vue3', 'React', 'Vite', 'Git'],
    old: ['jQuery', 'Vue2'],
    added: ['微前端', '性能优化', 'AI UI', '低代码引擎'],
    responsibilities: [
      '负责Web前端产品的架构设计与开发实现',
      '构建高质量、可复用的UI组件库',
      '持续优化页面性能与用户体验',
      '参与前端工程化建设，提升研发效能'
    ],
    requirements: [
      '计算机科学相关专业本科及以上学历',
      '2年以上前端开发经验，精通Vue3或React',
      '熟悉TypeScript、前端构建工具与工程化实践',
      '有数据可视化、低代码平台或性能优化经验者优先'
    ]
  },
  cloud: {
    type: '云计算',
    cities: ['北京', '深圳', '广州'],
    mature: ['云计算运维工程师', '运维工程师', 'DevOps工程师', 'SRE工程师', '数据库工程师', '容器平台工程师', '网络云工程师', '云安全工程师'],
    emerging: ['FinOps工程师', '云原生AI运维工程师', '算力调度工程师'],
    base: ['Linux', 'Kubernetes', 'Docker', 'Terraform', 'Prometheus', 'CI/CD'],
    old: ['裸机运维', 'Shell脚本'],
    added: ['FinOps', 'AIOps', 'Serverless', 'GPU调度'],
    responsibilities: [
      '负责云平台基础设施的规划、部署与运维',
      '保障云服务的稳定性、安全性与成本优化',
      '建设自动化运维体系，提升运维效率',
      '制定灾备方案并参与应急响应'
    ],
    requirements: [
      '计算机科学、网络工程等相关专业本科及以上学历',
      '3年以上云计算或运维经验',
      '精通Linux系统，熟悉Kubernetes与Docker',
      '有大规模集群运维或FinOps实践经验者优先'
    ]
  },
  testing: {
    type: '测试',
    cities: ['北京', '上海', '深圳'],
    mature: ['测试工程师', '自动化测试工程师', '性能测试工程师', '测试开发工程师', '移动端测试工程师', '安全测试工程师', '测试架构师', '质量管理工程师'],
    emerging: ['AI测试工程师', '智能回归工程师', '混沌工程工程师'],
    base: ['Python', 'Selenium', 'JMeter', 'Git', 'Linux', 'SQL'],
    old: ['手工测试', 'QTP'],
    added: ['AI辅助测试', '混沌工程', '精准测试', '持续质量'],
    responsibilities: [
      '负责产品质量保障，制定测试策略与计划',
      '开发自动化测试框架与测试工具',
      '执行功能、性能、安全等多维度测试',
      '推动缺陷管理流程优化，提升交付质量'
    ],
    requirements: [
      '计算机科学相关专业本科及以上学历',
      '2年以上软件测试经验',
      '精通Python，熟悉Selenium/JMeter等测试工具',
      '有自动化测试框架开发或CI/CD集成经验者优先'
    ]
  },
  product: {
    type: '产品',
    cities: ['上海', '北京', '杭州'],
    mature: ['产品经理', '高级产品经理', '数据产品经理', '商业化产品经理', '用户增长产品经理', '策略产品经理', 'B端产品经理', '产品运营经理'],
    emerging: ['AI产品经理', '智能体产品经理', '数字人产品经理'],
    base: ['需求分析', '用户研究', '原型设计', '数据分析', 'SQL', '项目管理'],
    old: ['瀑布流管理', '纸质原型'],
    added: ['AI产品设计', '增长黑客', '数据驱动决策', '用户旅程编排'],
    responsibilities: [
      '负责产品全生命周期管理，从需求到上线',
      '深入用户调研，洞察需求并制定产品方案',
      '与研发、设计、运营团队紧密协作推动落地',
      '通过数据分析持续优化产品体验与商业指标'
    ],
    requirements: [
      '计算机、设计、心理学等相关专业本科及以上学历',
      '2年以上互联网产品经验',
      '具备优秀的用户洞察与需求分析能力',
      '有AI产品或B端产品经验者优先'
    ]
  }
}

const companies = ['智云科技', '星海数科', '未来引擎', '新知网络', '云图智通', '极光软件', '远洋智能', '蓝海科技', '数澜信息', '启明云服务', '创想互动', '锐智软件', '微光科技', '盘石网络', '安恒信息']
const salaryBands = ['10-18K', '15-25K', '18-30K', '20-35K', '25-40K', '30-45K', '35-55K', '40-60K']
const roleSkillExtras = ['系统设计', '性能调优', '跨团队协作', '项目管理', '业务理解', '安全规范', '工程化实践', '问题排查']

function levelFor(skill, index) {
  if (['JavaScript', 'Python', 'SQL', 'Linux', 'Java', 'C/C++', 'Git', '数据结构', 'TCP/IP', '需求分析'].includes(skill)) return '初级'
  return index % 3 === 0 ? '高级' : '中级'
}

function createJob(track, definition, title, index, emerging = false) {
  const oldSkills = [...definition.base.slice(0, 4), definition.old[index % definition.old.length], roleSkillExtras[index % roleSkillExtras.length]]
  const currentSkills = [...definition.base.slice(0, 4), definition.added[index % definition.added.length], roleSkillExtras[(index + 2) % roleSkillExtras.length]]
  const refined = definition.base[index % definition.base.length] + ' \u2192 ' + definition.base[index % definition.base.length] + ' 工程化'

  return {
    id: 'JD-' + track.toUpperCase() + '-' + String(index + 1).padStart(3, '0'),
    title,
    company: companies[(index + track.charCodeAt(0)) % companies.length],
    city: definition.cities[index % definition.cities.length],
    type: definition.type,
    track,
    kind: emerging ? '新兴未标准化岗位' : '成熟岗位',
    salary: salaryBands[(index + track.charCodeAt(0)) % salaryBands.length],
    status: emerging ? '探索中' : '进行中',
    updated: '2026-07-' + String(10 + (index % 10)).padStart(2, '0'),
    skills: currentSkills,
    skillDetails: currentSkills.map((name, skillIndex) => ({
      name,
      level: levelFor(name, skillIndex),
      requirement: skillIndex < 4 ? '必备技能' : '加分技能'
    })),
    responsibilities: definition.responsibilities,
    requirements: definition.requirements,
    jdVersions: [
      {
        year: 2024,
        version: 'V1.0',
        publishedAt: '2024-06-18',
        content: title + '（2024版）：负责' + definition.type + '相关系统建设，熟悉' + oldSkills.join('、') + '。',
        skills: oldSkills
      },
      {
        year: 2026,
        version: 'V2.0',
        publishedAt: '2026-07-19',
        content: title + '（2026版）：负责智能化业务交付，要求掌握' + currentSkills.join('、') + '。',
        skills: currentSkills
      }
    ],
    evolution: {
      added: [definition.added[index % definition.added.length]],
      removed: [definition.old[index % definition.old.length]],
      changed: [refined]
    }
  }
}

export const jobs = industryTracks.flatMap(track => {
  const definition = trackDefinitions[track.id]
  const mature = definition.mature.map((title, index) => createJob(track.id, definition, title, index, false))
  const emerging = definition.emerging.map((title, index) => createJob(track.id, definition, title, index + 8, true))
  return [...mature, ...emerging]
})

export const jdTimeline = jobs.flatMap(job =>
  job.jdVersions.map(version => ({
    jobId: job.id,
    jobTitle: job.title,
    track: job.track,
    ...version,
    evolution: job.evolution
  }))
)

export const skillCatalog = [
  ...new Map(
    jobs.flatMap(job =>
      job.skillDetails.map(skill => [
        skill.name,
        { ...skill, tracks: [job.track], jobCount: 1 }
      ])
    )
  ).values()
].map((skill, index) => ({
  ...skill,
  id: 'SKILL-' + String(index + 1).padStart(3, '0'),
  heat: 95 - (index % 65),
  trend: index % 5 === 0 ? '新增' : index % 7 === 0 ? '淘汰' : index % 4 === 0 ? '变更' : '稳定'
}))

export const trendData = {
  months: ['2024-07', '2024-10', '2025-01', '2025-04', '2025-10', '2026-07'],
  frontend: [46, 52, 58, 64, 72, 88],
  data: [35, 39, 46, 55, 62, 76],
  ai: [28, 41, 56, 68, 82, 96]
}

export const skills = skillCatalog.slice(0, 12).map((skill, index) => ({
  name: skill.name,
  value: skill.heat,
  color: skill.trend === '新增' ? '#27ae60' : skill.trend === '淘汰' ? '#999999' : skill.trend === '变更' ? '#f39c12' : '#2f7cf6',
  desc: skill.level + ' \u00b7 ' + skill.requirement,
  trend: skill.trend === '淘汰' ? '-12%' : '+' + (12 + index) + '%'
}))

const resumeSkills = [
  ['HTML', 'CSS', 'JavaScript', 'Vue3', 'Git'],
  ['JavaScript', 'TypeScript', 'Vue3', 'Vite', 'ECharts'],
  ['Vue3', 'React', 'TypeScript', 'Node.js', 'Git'],
  ['Python', 'SQL', 'Pandas', 'Tableau', 'Excel'],
  ['Java', 'Spring Boot', 'MySQL', 'Redis', 'Docker'],
  ['Python', 'PyTorch', '机器学习', 'Linux', 'Git'],
  ['JavaScript', 'Vue3', 'WebGL', 'ECharts', '性能优化'],
  ['Linux', 'Docker', 'Kubernetes', 'Prometheus', 'Terraform'],
  ['C/C++', 'Linux', 'MQTT', '嵌入式开发', 'TCP/IP'],
  ['SQL', 'Spark', 'Flink', 'Hive', '数据建模']
]

export const resumeProfiles = resumeSkills.map((skills, index) => {
  const years = [0, 1, 2, 3, 4, 5, 2, 5, 3, 4][index]
  const names = ['陈星', '李沐', '林知远', '王珍', '赵然', '周明', '孙晓', '刘航', '何川', '徐宁']
  return {
    id: 'RESUME-' + String(index + 1).padStart(3, '0'),
    name: names[index],
    role: ['前端开发工程师', '前端开发工程师', '高级前端工程师', '数据分析师', 'Java后端工程师', '算法工程师', '可视化工程师', '云计算运维工程师', '物联网工程师', '大数据开发工程师'][index],
    experience: years === 0 ? '应届生' : years + ' 年工作经验',
    education: years === 0 ? '本科应届 \u00b7 计算机科学' : '本科 \u00b7 软件工程',
    skills,
    projects: [
      {
        name: '岗位能力图谱平台',
        duration: '2025.03-2026.06',
        description: '负责核心模块设计、数据可视化及性能优化。',
        skills: skills.slice(0, 3)
      },
      {
        name: '企业数字化项目',
        duration: '2024.06-2025.02',
        description: '参与需求分析、开发交付与项目复盘。',
        skills: skills.slice(2)
      }
    ],
    summary: '具备 ' + (years === 0 ? '扎实基础' : '完整项目') + '经验，擅长' + skills.slice(0, 3).join('、') + '。'
  }
})

export const resume = {
  ...resumeProfiles[2],
  score: 87,
  hits: ['Vue3', 'TypeScript', 'ECharts', 'Vite', 'Git'],
  missing: ['微前端', '性能优化', 'Node.js'],
  strengths: ['具备完整的 Vue3 项目经验', '熟悉数据可视化与组件化开发', '有良好的工程化与协作意识']
}

export const path = [
  { phase: '基础夯实', time: '第 1-2 周', color: '#2f7cf6', skills: ['JavaScript 进阶', 'TypeScript 类型系统', 'Vue3 核心原理'] },
  { phase: '能力进阶', time: '第 3-5 周', color: '#7c5cff', skills: ['组件设计模式', '性能优化实战', 'Vite 工程化'] },
  { phase: '项目实战', time: '第 6-8 周', color: '#27ae60', skills: ['数据大屏开发', '低代码平台', '项目复盘'] }
]


/* ========== Dashboard 增强数据 ========== */

export const dashboardStats = [
  { label: '收录岗位总数', value: 2846, trend: 12.5, color: '#eaf2ff', icon: 'Files', link: '/jobs',
    sparkline: [2410,2520,2580,2650,2720,2846], detail: [{month:'5月',value:2720,change:'+3.0%'},{month:'6月',value:2780,change:'+2.2%'},{month:'7月',value:2846,change:'+2.4%'}] },
  { label: '技能实体数量', value: 1392, trend: 8.6, color: '#e9f8ef', icon: 'DataAnalysis', link: '/graph',
    sparkline: [1180,1220,1260,1310,1350,1392], detail: [{month:'5月',value:1310,change:'+3.2%'},{month:'6月',value:1350,change:'+3.1%'},{month:'7月',value:1392,change:'+3.1%'}] },
  { label: '活跃企业数量', value: 486, trend: 22.3, color: '#f0edff', icon: 'OfficeBuilding', link: '/jobs',
    sparkline: [340,370,395,420,450,486], detail: [{month:'5月',value:420,change:'+6.3%'},{month:'6月',value:450,change:'+7.1%'},{month:'7月',value:486,change:'+8.0%'}] },
  { label: '简历解析总量', value: 8521, trend: 15.8, color: '#fff5e7', icon: 'DocumentChecked', link: '/resume',
    sparkline: [6200,6800,7100,7600,8100,8521], detail: [{month:'5月',value:7600,change:'+7.0%'},{month:'6月',value:8100,change:'+6.6%'},{month:'7月',value:8521,change:'+5.2%'}] }
]

export const trendDataExtended = {
  months: ['2025-01','2025-04','2025-07','2025-10','2026-01','2026-04','2026-07'],
  forecastMonths: ['2026-08','2026-09'],
  series: {
    '前端开发': { data:[46,52,58,64,72,82,88], forecast:[93,98], color:'#2f7cf6' },
    'AI算法': { data:[28,41,56,68,82,90,96], forecast:[101,106], color:'#27ae60' },
    '后端开发': { data:[42,45,48,52,55,58,62], forecast:[65,68], color:'#f08c2e' },
    '大数据': { data:[35,39,46,55,62,70,76], forecast:[80,84], color:'#7c5cff' },
    '云计算': { data:[30,34,38,42,48,54,60], forecast:[64,68], color:'#3e9cce' },
    '测试': { data:[25,28,32,36,40,44,48], forecast:[51,54], color:'#e74c3c' },
    '产品': { data:[32,35,38,42,46,50,54], forecast:[57,60], color:'#e67e22' }
  }
}

export const skillsByTrack = {
  '全部': [
    { name:'Python', value:92, speed:'+18%', jobs:1846, trend:'新增' },
    { name:'Vue3', value:88, speed:'+22%', jobs:1520, trend:'新增' },
    { name:'TypeScript', value:85, speed:'+25%', jobs:1380, trend:'变更' },
    { name:'React', value:82, speed:'+12%', jobs:1290, trend:'稳定' },
    { name:'Java', value:80, speed:'+8%', jobs:1180, trend:'稳定' },
    { name:'Kubernetes', value:76, speed:'+20%', jobs:980, trend:'新增' },
    { name:'SQL', value:74, speed:'+5%', jobs:920, trend:'稳定' },
    { name:'Docker', value:72, speed:'+15%', jobs:860, trend:'变更' },
    { name:'机器学习', value:70, speed:'+28%', jobs:820, trend:'新增' },
    { name:'大模型应用', value:68, speed:'+45%', jobs:680, trend:'新增' }
  ],
  '前端开发': [
    { name:'Vue3', value:95, speed:'+22%', jobs:1520, trend:'新增' },
    { name:'TypeScript', value:92, speed:'+25%', jobs:1380, trend:'变更' },
    { name:'React', value:88, speed:'+12%', jobs:1290, trend:'稳定' },
    { name:'Vite', value:82, speed:'+30%', jobs:980, trend:'新增' },
    { name:'微前端', value:68, speed:'+35%', jobs:520, trend:'新增' },
    { name:'ECharts', value:65, speed:'+18%', jobs:480, trend:'变更' },
    { name:'Node.js', value:62, speed:'+10%', jobs:450, trend:'稳定' },
    { name:'WebGL', value:45, speed:'+8%', jobs:280, trend:'稳定' }
  ],
  'AI算法': [
    { name:'Python', value:96, speed:'+18%', jobs:1846, trend:'新增' },
    { name:'PyTorch', value:90, speed:'+22%', jobs:1420, trend:'新增' },
    { name:'大模型应用', value:85, speed:'+45%', jobs:680, trend:'新增' },
    { name:'RAG', value:78, speed:'+60%', jobs:520, trend:'新增' },
    { name:'Agent', value:72, speed:'+55%', jobs:420, trend:'新增' },
    { name:'LoRA 微调', value:65, speed:'+50%', jobs:320, trend:'新增' },
    { name:'机器学习', value:82, speed:'+15%', jobs:820, trend:'稳定' },
    { name:'TensorFlow', value:48, speed:'-8%', jobs:380, trend:'淘汰' }
  ],
  '产品': [
    { name:'需求分析', value:90, speed:'+10%', jobs:1200, trend:'稳定' },
    { name:'用户研究', value:85, speed:'+12%', jobs:980, trend:'变更' },
    { name:'数据分析', value:82, speed:'+15%', jobs:860, trend:'变更' },
    { name:'AI产品设计', value:70, speed:'+40%', jobs:420, trend:'新增' },
    { name:'增长黑客', value:65, speed:'+25%', jobs:380, trend:'新增' },
    { name:'原型设计', value:78, speed:'+5%', jobs:720, trend:'稳定' },
    { name:'项目管理', value:72, speed:'+8%', jobs:650, trend:'稳定' },
    { name:'SQL', value:55, speed:'+12%', jobs:320, trend:'变更' }
  ]
}

export const industryDistribution = [
  { name:'人工智能', value:628, percent:22, color:'#7c5cff', speed:'+18%', topSkills:['Python','PyTorch','大模型应用','RAG','Agent'] },
  { name:'前端开发', value:512, percent:18, color:'#2f7cf6', speed:'+12%', topSkills:['Vue3','TypeScript','React','Vite','微前端'] },
  { name:'后端开发', value:455, percent:16, color:'#f08c2e', speed:'+8%', topSkills:['Java','Spring Boot','MySQL','Redis','Docker'] },
  { name:'大数据', value:398, percent:14, color:'#1d9bf0', speed:'+15%', topSkills:['SQL','Spark','Flink','Hive','数据建模'] },
  { name:'云计算', value:341, percent:12, color:'#3e9cce', speed:'+10%', topSkills:['Kubernetes','Docker','Linux','Terraform','CI/CD'] },
  { name:'测试', value:284, percent:10, color:'#e74c3c', speed:'+6%', topSkills:['Python','Selenium','JMeter','Git','自动化测试'] },
  { name:'产品', value:228, percent:8, color:'#e67e22', speed:'+9%', topSkills:['需求分析','用户研究','数据分析','原型设计','AI产品设计'] }
]

export const talentGapFull = [
  { rank:1, skill:'大模型应用开发', gap:3200, growth:'+45%', trend:[8,15,28,42,58,72], path:'/learning', severity:'critical', desc:'LLM微调、Prompt工程、Agent框架搭建' },
  { rank:2, skill:'RAG/Agent 工程', gap:2800, growth:'+60%', trend:[5,12,22,38,52,68], path:'/learning', severity:'critical', desc:'检索增强生成、智能体编排与调试' },
  { rank:3, skill:'云原生架构', gap:2100, growth:'+20%', trend:[20,28,38,48,58,68], path:'/learning', severity:'warning', desc:'K8s运维、Service Mesh、Serverless' },
  { rank:4, skill:'数据治理', gap:1800, growth:'+15%', trend:[25,32,40,48,55,62], path:'/learning', severity:'warning', desc:'数据质量、元数据管理、数据安全合规' },
  { rank:5, skill:'自动化测试', gap:1500, growth:'+18%', trend:[18,25,32,40,48,55], path:'/learning', severity:'normal', desc:'测试框架开发、CI/CD集成、精准测试' },
  { rank:6, skill:'AI产品设计', gap:1200, growth:'+40%', trend:[5,12,22,35,48,60], path:'/learning', severity:'normal', desc:'AI场景定义、用户旅程编排、数据驱动决策' },
  { rank:7, skill:'边缘计算', gap:980, growth:'+25%', trend:[10,18,28,38,48,55], path:'/learning', severity:'normal', desc:'边缘AI部署、设备端推理、低延迟通信' },
  { rank:8, skill:'FinOps', gap:850, growth:'+30%', trend:[5,12,20,32,42,52], path:'/learning', severity:'normal', desc:'云成本优化、资源调度、账单治理' },
  { rank:9, skill:'数字孪生', gap:720, growth:'+28%', trend:[8,15,22,32,42,50], path:'/learning', severity:'normal', desc:'3D建模、实时仿真、工业互联网' },
  { rank:10, skill:'混沌工程', gap:600, growth:'+22%', trend:[6,12,18,28,36,44], path:'/learning', severity:'normal', desc:'故障注入、韧性测试、容灾演练' },
  { rank:11, skill:'微前端架构', gap:550, growth:'+35%', trend:[8,15,24,34,44,52], path:'/learning', severity:'normal', desc:'Module Federation、qiankun、沙箱隔离' },
  { rank:12, skill:'WebGL/3D可视化', gap:480, growth:'+18%', trend:[12,18,24,32,38,44], path:'/learning', severity:'normal', desc:'Three.js、WebGPU、大规模数据渲染' },
  { rank:13, skill:'安全测试', gap:420, growth:'+15%', trend:[15,20,26,32,38,42], path:'/learning', severity:'normal', desc:'渗透测试、漏洞扫描、安全审计' },
  { rank:14, skill:'低代码引擎', gap:380, growth:'+32%', trend:[5,10,18,26,34,42], path:'/learning', severity:'normal', desc:'可视化搭建、DSL设计、组件协议' },
  { rank:15, skill:'向量数据库', gap:350, growth:'+50%', trend:[3,8,15,24,34,42], path:'/learning', severity:'normal', desc:'Milvus、Pinecone、向量检索优化' },
  { rank:16, skill:'DataOps', gap:300, growth:'+20%', trend:[10,16,22,28,34,40], path:'/learning', severity:'normal', desc:'数据流水线、数据版本管理、质量监控' },
  { rank:17, skill:'SRE工程', gap:280, growth:'+12%', trend:[18,22,28,32,36,40], path:'/learning', severity:'normal', desc:'可观测性、SLI/SLO、事故复盘' },
  { rank:18, skill:'AIGC界面', gap:250, growth:'+38%', trend:[2,6,12,20,28,36], path:'/learning', severity:'normal', desc:'AI生成UI、智能交互、多模态界面' },
  { rank:19, skill:'增长运营', gap:220, growth:'+15%', trend:[15,20,24,28,32,36], path:'/learning', severity:'normal', desc:'AB测试、漏斗分析、用户分层运营' },
  { rank:20, skill:'数字人技术', gap:200, growth:'+42%', trend:[2,5,10,16,24,32], path:'/learning', severity:'normal', desc:'语音合成、表情驱动、实时对话' }
]

export const resumeMatchingData = {
  overall: [
    { level:'优秀 (90-100)', count:820, percent:9.6, color:'#27ae60', desc:'技能高度匹配，可直接安排面试', suggestion:'保持技术深度，拓展架构能力' },
    { level:'良好 (80-89)', count:2150, percent:25.2, color:'#2f7cf6', desc:'核心技能覆盖，缺少部分加分项', suggestion:'补充微前端、性能优化等进阶技能' },
    { level:'中等 (70-79)', count:3200, percent:37.6, color:'#f08c2e', desc:'基础技能达标，高级技能不足', suggestion:'系统学习TypeScript、工程化实践' },
    { level:'待提升 (<70)', count:2351, percent:27.6, color:'#e74c3c', desc:'技能匹配度低，需重点提升', suggestion:'夯实JavaScript基础，完成实战项目' }
  ],
  byTrack: {
    '全部': [9.6, 25.2, 37.6, 27.6],
    '前端开发': [12.5, 30.2, 35.8, 21.5],
    'AI算法': [6.8, 18.5, 38.2, 36.5],
    '后端开发': [10.2, 28.6, 36.4, 24.8],
    '产品': [8.4, 22.8, 40.2, 28.6]
  }
}

export const evolutionItems = [
  { name:'大模型应用', level:'高级', desc:'LLM微调、RAG、Agent框架', trend:'+45%', type:'新增', color:'#27ae60', growth:[10,18,28,42,58,72], dimensions:[72,85,68,90,78,65,82,70] },
  { name:'RAG 工程', level:'高级', desc:'检索增强生成系统设计', trend:'+60%', type:'新增', color:'#27ae60', growth:[5,12,22,38,52,68], dimensions:[68,92,55,85,72,60,78,65] },
  { name:'TypeScript', level:'中级', desc:'类型系统、泛型、工程化', trend:'+25%', type:'变更', color:'#f39c12', growth:[35,42,52,62,72,85], dimensions:[85,78,92,70,88,82,75,90] },
  { name:'微前端', level:'中级', desc:'Module Federation、qiankun', trend:'+35%', type:'新增', color:'#27ae60', growth:[8,15,25,38,50,68], dimensions:[65,72,58,80,62,55,70,60] },
  { name:'FinOps', level:'高级', desc:'云成本优化与治理', trend:'+20%', type:'新增', color:'#27ae60', growth:[5,10,18,28,40,55], dimensions:[55,68,72,60,82,45,78,50] },
  { name:'jQuery', level:'初级', desc:'DOM操作、事件绑定', trend:'-18%', type:'淘汰', color:'#999999', growth:[82,72,60,48,38,28], dimensions:[28,22,90,15,35,20,12,18] },
  { name:'Vue2', level:'初级', desc:'Options API、Vuex', trend:'-15%', type:'淘汰', color:'#999999', growth:[90,82,70,58,45,35], dimensions:[35,30,85,20,40,25,18,22] },
  { name:'Struts', level:'初级', desc:'MVC框架、Action配置', trend:'-22%', type:'淘汰', color:'#999999', growth:[45,35,25,18,12,8], dimensions:[8,10,60,5,15,8,5,6] },
  { name:'ECharts', level:'中级', desc:'数据可视化、图表定制', trend:'+18%', type:'变更', color:'#f39c12', growth:[40,48,55,62,70,78], dimensions:[78,72,82,65,88,70,68,75] },
  { name:'Kubernetes', level:'高级', desc:'容器编排、服务网格', trend:'+20%', type:'变更', color:'#f39c12', growth:[30,38,48,58,68,76], dimensions:[76,82,65,78,70,88,60,72] }
]

/* ========== Graph 图谱数据 ========== */

export const graphJobs = [
  { value: 'all', label: '全部岗位' },
  { value: 'frontend', label: '前端开发工程师' },
  { value: 'backend', label: 'Java后端开发' },
  { value: 'ai', label: 'Python算法工程师' },
  { value: 'data', label: '数据分析师' },
  { value: 'product', label: '产品经理' },
  { value: 'test', label: '测试工程师' },
  { value: 'cloud', label: '云计算运维工程师' }
]

export const graphYears = ['2024', '2025', '2026']

export const graphSnapshots = {
  '2024': {
    nodes: [
      { id: 'ind-ai', label: '人工智能', kind: 'industry', size: 42, color: '#B8A0D4' },
      { id: 'ind-fe', label: '前端开发', kind: 'industry', size: 38, color: '#B8A0D4' },
      { id: 'ind-be', label: '后端开发', kind: 'industry', size: 36, color: '#B8A0D4' },
      { id: 'ind-data', label: '大数据', kind: 'industry', size: 34, color: '#B8A0D4' },
      { id: 'ind-cloud', label: '云计算', kind: 'industry', size: 30, color: '#B8A0D4' },
      { id: 'ind-test', label: '测试', kind: 'industry', size: 28, color: '#B8A0D4' },
      { id: 'ind-prod', label: '产品', kind: 'industry', size: 26, color: '#B8A0D4' },
      { id: 'job-fe1', label: '前端开发工程师', kind: 'job', size: 28, color: '#D98B6E', parent: 'ind-fe' },
      { id: 'job-fe2', label: '高级前端工程师', kind: 'job', size: 26, color: '#D98B6E', parent: 'ind-fe' },
      { id: 'job-be1', label: 'Java后端开发', kind: 'job', size: 28, color: '#D98B6E', parent: 'ind-be' },
      { id: 'job-ai1', label: 'Python算法工程师', kind: 'job', size: 30, color: '#D98B6E', parent: 'ind-ai' },
      { id: 'job-ai2', label: '机器学习工程师', kind: 'job', size: 26, color: '#D98B6E', parent: 'ind-ai' },
      { id: 'job-data1', label: '数据分析师', kind: 'job', size: 24, color: '#D98B6E', parent: 'ind-data' },
      { id: 'job-prod1', label: '产品经理', kind: 'job', size: 24, color: '#D98B6E', parent: 'ind-prod' },
      { id: 'job-test1', label: '测试工程师', kind: 'job', size: 22, color: '#D98B6E', parent: 'ind-test' },
      { id: 'job-cloud1', label: '云计算运维工程师', kind: 'job', size: 24, color: '#D98B6E', parent: 'ind-cloud' },
      { id: 'sk-js', label: 'JavaScript', kind: 'skill', status: 'stable', size: 20, color: '#8CA0B8', jobs: 320, level: 'basic', growth: '+5%', desc: '前端基础语言' },
      { id: 'sk-vue2', label: 'Vue2', kind: 'skill', status: 'removed', size: 16, color: '#C0A0A0', jobs: 180, level: 'basic', growth: '-15%', desc: '旧版前端框架' },
      { id: 'sk-jquery', label: 'jQuery', kind: 'skill', status: 'removed', size: 14, color: '#C0A0A0', jobs: 120, level: 'basic', growth: '-18%', desc: 'DOM操作库' },
      { id: 'sk-python', label: 'Python', kind: 'skill', status: 'stable', size: 22, color: '#8CA0B8', jobs: 420, level: 'basic', growth: '+8%', desc: '通用编程语言' },
      { id: 'sk-tf', label: 'TensorFlow', kind: 'skill', status: 'removed', size: 14, color: '#C0A0A0', jobs: 160, level: 'advanced', growth: '-12%', desc: '深度学习框架(旧)' },
      { id: 'sk-java', label: 'Java', kind: 'skill', status: 'stable', size: 20, color: '#f08c2e', jobs: 380, level: 'basic', growth: '+3%', desc: '后端主力语言' },
      { id: 'sk-sql', label: 'SQL', kind: 'skill', status: 'stable', size: 18, color: '#1d9bf0', jobs: 350, level: 'basic', growth: '+2%', desc: '数据库查询语言' },
      { id: 'sk-html', label: 'HTML/CSS', kind: 'skill', status: 'stable', size: 16, color: '#8CA0B8', jobs: 280, level: 'basic', growth: '+1%', desc: 'Web基础' }
    ],
    edges: [
      { source: 'ind-ai', target: 'job-ai1', kind: 'industry-job' },
      { source: 'ind-ai', target: 'job-ai2', kind: 'industry-job' },
      { source: 'ind-fe', target: 'job-fe1', kind: 'industry-job' },
      { source: 'ind-fe', target: 'job-fe2', kind: 'industry-job' },
      { source: 'ind-be', target: 'job-be1', kind: 'industry-job' },
      { source: 'ind-data', target: 'job-data1', kind: 'industry-job' },
      { source: 'ind-prod', target: 'job-prod1', kind: 'industry-job' },
      { source: 'ind-test', target: 'job-test1', kind: 'industry-job' },
      { source: 'ind-cloud', target: 'job-cloud1', kind: 'industry-job' },
      { source: 'job-fe1', target: 'sk-js', kind: 'job-skill' },
      { source: 'job-fe1', target: 'sk-vue2', kind: 'job-skill' },
      { source: 'job-fe1', target: 'sk-jquery', kind: 'job-skill' },
      { source: 'job-fe1', target: 'sk-html', kind: 'job-skill' },
      { source: 'job-fe2', target: 'sk-js', kind: 'job-skill' },
      { source: 'job-fe2', target: 'sk-vue2', kind: 'job-skill' },
      { source: 'job-ai1', target: 'sk-python', kind: 'job-skill' },
      { source: 'job-ai1', target: 'sk-tf', kind: 'job-skill' },
      { source: 'job-ai2', target: 'sk-python', kind: 'job-skill' },
      { source: 'job-be1', target: 'sk-java', kind: 'job-skill' },
      { source: 'job-data1', target: 'sk-sql', kind: 'job-skill' },
      { source: 'job-data1', target: 'sk-python', kind: 'job-skill' }
    ],
    stats: { totalNodes: 22, totalEdges: 21, added: 0, removed: 0, changed: 0 }
  },
  '2026': {
    nodes: [
      { id: 'ind-ai', label: '人工智能', kind: 'industry', size: 50, color: '#B8A0D4' },
      { id: 'ind-fe', label: '前端开发', kind: 'industry', size: 44, color: '#B8A0D4' },
      { id: 'ind-be', label: '后端开发', kind: 'industry', size: 40, color: '#B8A0D4' },
      { id: 'ind-data', label: '大数据', kind: 'industry', size: 38, color: '#B8A0D4' },
      { id: 'ind-cloud', label: '云计算', kind: 'industry', size: 34, color: '#B8A0D4' },
      { id: 'ind-test', label: '测试', kind: 'industry', size: 32, color: '#B8A0D4' },
      { id: 'ind-prod', label: '产品', kind: 'industry', size: 30, color: '#B8A0D4' },
      { id: 'job-fe1', label: '前端开发工程师', kind: 'job', size: 32, color: '#D98B6E', parent: 'ind-fe' },
      { id: 'job-fe2', label: '高级前端工程师', kind: 'job', size: 30, color: '#D98B6E', parent: 'ind-fe' },
      { id: 'job-fe3', label: 'AI前端工程师', kind: 'job', size: 24, color: '#D98B6E', parent: 'ind-fe' },
      { id: 'job-be1', label: 'Java后端开发', kind: 'job', size: 30, color: '#D98B6E', parent: 'ind-be' },
      { id: 'job-ai1', label: 'Python算法工程师', kind: 'job', size: 34, color: '#D98B6E', parent: 'ind-ai' },
      { id: 'job-ai2', label: '机器学习工程师', kind: 'job', size: 30, color: '#D98B6E', parent: 'ind-ai' },
      { id: 'job-ai3', label: 'RAG应用开发工程师', kind: 'job', size: 26, color: '#D98B6E', parent: 'ind-ai' },
      { id: 'job-data1', label: '数据分析师', kind: 'job', size: 28, color: '#D98B6E', parent: 'ind-data' },
      { id: 'job-prod1', label: '产品经理', kind: 'job', size: 28, color: '#D98B6E', parent: 'ind-prod' },
      { id: 'job-prod2', label: 'AI产品经理', kind: 'job', size: 24, color: '#D98B6E', parent: 'ind-prod' },
      { id: 'job-test1', label: '测试工程师', kind: 'job', size: 26, color: '#D98B6E', parent: 'ind-test' },
      { id: 'job-cloud1', label: '云计算运维工程师', kind: 'job', size: 28, color: '#D98B6E', parent: 'ind-cloud' },
      { id: 'sk-ts', label: 'TypeScript', kind: 'skill', status: 'changed', size: 24, color: '#2f7cf6', jobs: 480, level: 'advanced', growth: '+25%', desc: 'JS超集，类型安全' },
      { id: 'sk-vue3', label: 'Vue3', kind: 'skill', status: 'added', size: 26, color: '#27ae60', jobs: 520, level: 'advanced', growth: '+22%', desc: '新一代前端框架' },
      { id: 'sk-react', label: 'React', kind: 'skill', status: 'stable', size: 22, color: '#2f7cf6', jobs: 420, level: 'advanced', growth: '+12%', desc: 'UI组件库' },
      { id: 'sk-vite', label: 'Vite', kind: 'skill', status: 'added', size: 20, color: '#27ae60', jobs: 380, level: 'advanced', growth: '+30%', desc: '前端构建工具' },
      { id: 'sk-mfe', label: '微前端', kind: 'skill', status: 'added', size: 18, color: '#27ae60', jobs: 260, level: 'advanced', growth: '+35%', desc: 'Module Federation' },
      { id: 'sk-aiui', label: 'AI UI', kind: 'skill', status: 'added', size: 16, color: '#27ae60', jobs: 180, level: 'advanced', growth: '+45%', desc: 'AI驱动界面交互' },
      { id: 'sk-python', label: 'Python', kind: 'skill', status: 'stable', size: 26, color: '#7c5cff', jobs: 620, level: 'basic', growth: '+18%', desc: '通用编程语言' },
      { id: 'sk-pytorch', label: 'PyTorch', kind: 'skill', status: 'added', size: 22, color: '#27ae60', jobs: 420, level: 'advanced', growth: '+22%', desc: '深度学习框架' },
      { id: 'sk-llm', label: '大模型应用', kind: 'skill', status: 'added', size: 24, color: '#8BBFA0', jobs: 380, level: 'advanced', growth: '+45%', desc: 'LLM微调与应用' },
      { id: 'sk-rag', label: 'RAG', kind: 'skill', status: 'added', size: 20, color: '#27ae60', jobs: 280, level: 'advanced', growth: '+60%', desc: '检索增强生成' },
      { id: 'sk-agent', label: 'Agent', kind: 'skill', status: 'added', size: 18, color: '#27ae60', jobs: 220, level: 'advanced', growth: '+55%', desc: '智能体框架' },
      { id: 'sk-java', label: 'Java', kind: 'skill', status: 'stable', size: 22, color: '#f08c2e', jobs: 420, level: 'basic', growth: '+8%', desc: '后端主力语言' },
      { id: 'sk-k8s', label: 'Kubernetes', kind: 'skill', status: 'changed', size: 20, color: '#D4C088', jobs: 340, level: 'advanced', growth: '+20%', desc: '容器编排' },
      { id: 'sk-sql', label: 'SQL', kind: 'skill', status: 'stable', size: 20, color: '#1d9bf0', jobs: 380, level: 'basic', growth: '+5%', desc: '数据库查询语言' },
      { id: 'sk-git', label: 'Git', kind: 'skill', status: 'stable', size: 16, color: '#8CA0B8', jobs: 520, level: 'basic', growth: '+3%', desc: '版本控制' }
    ],
    edges: [
      { source: 'ind-ai', target: 'job-ai1', kind: 'industry-job' },
      { source: 'ind-ai', target: 'job-ai2', kind: 'industry-job' },
      { source: 'ind-ai', target: 'job-ai3', kind: 'industry-job' },
      { source: 'ind-fe', target: 'job-fe1', kind: 'industry-job' },
      { source: 'ind-fe', target: 'job-fe2', kind: 'industry-job' },
      { source: 'ind-fe', target: 'job-fe3', kind: 'industry-job' },
      { source: 'ind-be', target: 'job-be1', kind: 'industry-job' },
      { source: 'ind-data', target: 'job-data1', kind: 'industry-job' },
      { source: 'ind-prod', target: 'job-prod1', kind: 'industry-job' },
      { source: 'ind-prod', target: 'job-prod2', kind: 'industry-job' },
      { source: 'ind-test', target: 'job-test1', kind: 'industry-job' },
      { source: 'ind-cloud', target: 'job-cloud1', kind: 'industry-job' },
      { source: 'job-fe1', target: 'sk-ts', kind: 'job-skill' },
      { source: 'job-fe1', target: 'sk-vue3', kind: 'job-skill' },
      { source: 'job-fe1', target: 'sk-react', kind: 'job-skill' },
      { source: 'job-fe1', target: 'sk-vite', kind: 'job-skill' },
      { source: 'job-fe2', target: 'sk-ts', kind: 'job-skill' },
      { source: 'job-fe2', target: 'sk-vue3', kind: 'job-skill' },
      { source: 'job-fe2', target: 'sk-mfe', kind: 'job-skill' },
      { source: 'job-fe3', target: 'sk-aiui', kind: 'job-skill' },
      { source: 'job-fe3', target: 'sk-ts', kind: 'job-skill' },
      { source: 'job-ai1', target: 'sk-python', kind: 'job-skill' },
      { source: 'job-ai1', target: 'sk-pytorch', kind: 'job-skill' },
      { source: 'job-ai1', target: 'sk-llm', kind: 'job-skill' },
      { source: 'job-ai2', target: 'sk-python', kind: 'job-skill' },
      { source: 'job-ai2', target: 'sk-pytorch', kind: 'job-skill' },
      { source: 'job-ai3', target: 'sk-rag', kind: 'job-skill' },
      { source: 'job-ai3', target: 'sk-agent', kind: 'job-skill' },
      { source: 'job-ai3', target: 'sk-llm', kind: 'job-skill' },
      { source: 'job-be1', target: 'sk-java', kind: 'job-skill' },
      { source: 'job-be1', target: 'sk-k8s', kind: 'job-skill' },
      { source: 'job-data1', target: 'sk-sql', kind: 'job-skill' },
      { source: 'job-data1', target: 'sk-python', kind: 'job-skill' },
      { source: 'job-cloud1', target: 'sk-k8s', kind: 'job-skill' },
      { source: 'job-test1', target: 'sk-git', kind: 'job-skill' },
      { source: 'job-prod1', target: 'sk-sql', kind: 'job-skill' },
      { source: 'job-prod2', target: 'sk-llm', kind: 'job-skill' }
    ],
    stats: { totalNodes: 33, totalEdges: 36, added: 10, removed: 3, changed: 2 }
  }
}

export const skillRadar8D = {
  dimensions: ['市场需求','技术热度','岗位覆盖','增长趋势','学习难度','生态成熟','薪资水平','就业广度'],
  data: {
    'Vue3': [88,92,85,90,65,82,88,80],
    'TypeScript': [85,88,82,88,70,78,85,78],
    'Python': [95,90,92,85,55,95,90,92],
    '大模型应用': [92,95,68,95,80,55,95,60],
    'React': [82,85,80,78,65,90,85,78],
    'Java': [80,75,88,65,60,92,82,85],
    'Kubernetes': [78,82,72,85,85,75,88,70],
    'RAG': [88,92,55,95,82,48,92,52],
    'SQL': [75,65,92,50,45,95,72,88],
    'Git': [70,60,95,40,35,98,65,92]
  }
}


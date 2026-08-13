/**
 * 模拟简历数据 - 林苑琪
 * 用于简历匹配诊断页面的测试数据
 */

export const mockResume = {
  // 基础信息
  basic: {
    name: '林苑琪',
    gender: '女',
    phone: '13800138000',
    email: 'linyq_dev@163.com',
    location: '广东广州',
    avatar: '',
    jobIntention: '前端开发工程师（岗位能力图谱匹配目标岗）'
  },

  // 教育经历
  education: {
    school: '广州应用科技学院',
    major: '软件工程',
    degree: '四年制本科',
    duration: '2022.09 - 2026.06',
    courses: [
      'Web前端开发',
      'Vue框架',
      '数据结构',
      '计算机网络',
      '数据库原理',
      '可视化开发'
    ]
  },

  // 专业技能（对应雷达图八大维度）
  skills: {
    dimensions: [
      '基础技能',
      '前端开发框架',
      '组件与工具',
      '跨端开发',
      '全栈开发',
      '技术扩展',
      'AI应用开发能力',
      '综合素养'
    ],
    details: {
      '基础技能': {
        level: 85,
        items: ['HTML/CSS/JavaScript', 'ES6', 'Git', '浏览器兼容优化']
      },
      '前端开发框架': {
        level: 90,
        items: ['Vue3', 'Vite', 'Element Plus', 'Pinia']
      },
      '组件与工具': {
        level: 88,
        items: ['Axios', 'ECharts', 'G6可视化', 'pnpm', 'VSCode插件生态']
      },
      '跨端开发': {
        level: 60,
        items: ['UniApp 简易小程序开发']
      },
      '全栈开发': {
        level: 55,
        items: ['Node.js基础接口编写', 'Express简易服务']
      },
      '技术扩展': {
        level: 70,
        items: ['TypeScript', '性能优化', '单元测试']
      },
      'AI应用开发能力': {
        level: 65,
        items: ['AI代码辅助工具使用', '提示词工程', 'CC Switch模型调度']
      },
      '综合素养': {
        level: 82,
        items: ['需求文档撰写', '团队协作', '项目答辩', '竞赛汇报']
      }
    },
    radarData: {
      jobStandard: [80, 85, 82, 65, 70, 75, 60, 80],
      personalAbility: [85, 90, 88, 60, 55, 70, 65, 82]
    }
  },

  // 项目经历
  projects: [
    {
      name: '岗位能力图谱前端系统（参赛项目）',
      duration: '2025.10 - 2026.05',
      techStack: 'Vite4 + Vue3 + TS + G6 + ECharts + Element Plus',
      responsibilities: [
        '独立开发JD岗位管理、简历匹配、图谱可视化、学习路径四大页面',
        '使用G6实现行业-岗位-技能三层关系图谱，三色区分技能新增/淘汰/变更',
        '开发岗位能力雷达对比图，实现个人能力与岗位标准自动匹配打分',
        '封装全局Axios请求，批量生成模拟岗位与简历测试数据',
        '优化图谱大量节点渲染卡顿问题，实现页面自适应布局'
      ]
    },
    {
      name: '校园图书借阅小程序',
      duration: '2024.03 - 2024.09',
      techStack: 'UniApp + Vue2',
      responsibilities: [
        '图书列表、借阅登记、搜索筛选、个人借阅记录页面开发'
      ]
    }
  ],

  // 竞赛与荣誉
  honors: [
    {
      time: '2025年',
      title: '高校计算机学科竞赛 赛道三等奖'
    },
    {
      time: '2024-2025学年',
      title: '校级二等奖学金'
    }
  ],

  // 自我评价
  selfEvaluation: '熟悉Vue全家桶与数据可视化开发，擅长G6、ECharts图表实现；具备完整前端项目独立开发能力，熟悉岗位技能匹配类业务逻辑；擅长使用AI开发工具提升编码效率，团队协作沟通顺畅，适合前端开发岗位。'
}

// 简历解析后的技能列表
export const mockResumeSkills = [
  'HTML', 'CSS', 'JavaScript', 'ES6', 'Git',
  'Vue3', 'Vite', 'Element Plus', 'Pinia',
  'Axios', 'ECharts', 'G6', 'TypeScript',
  'Node.js', 'Express', 'UniApp',
  '性能优化', '单元测试', 'AI代码辅助'
]

// 岗位匹配结果
export const mockMatchResult = {
  targetJob: '高级前端工程师',
  score: 82,
  matched: ['Vue3', 'TypeScript', 'ECharts', 'Vite', 'Git', 'Element Plus', 'Pinia'],
  missing: [
    { name: '微前端架构', level: 'high', tip: '大型项目常见的应用拆分与集成方案' },
    { name: 'Node.js 深度', level: 'medium', tip: '提升全栈协作与 BFF 开发能力' },
    { name: 'React 框架', level: 'medium', tip: '拓宽技术栈，增加就业竞争力' }
  ],
  strengths: ['具备完整的 Vue3 项目经验', '熟悉数据可视化与组件化开发', '有良好的工程化与协作意识']
}

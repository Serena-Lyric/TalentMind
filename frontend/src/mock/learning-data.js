/**
 * 多岗位学习路线模拟数据
 * 支持从 JD、图谱、简历匹配页面跳转并自动生成对应岗位学习路线
 */

// 岗位学习路线配置
export const jobLearningPaths = {
  frontend: {
    jobTitle: '高级前端工程师',
    currentScore: 82,
    targetScore: 95,
    estimatedWeeks: 12,
    dailyHours: 2,
    prioritySkills: [
      {
        name: '性能优化实战',
        level: 'high',
        reason: '大型项目必备技能，首屏加载、缓存策略与性能监控经验',
        impact: 92,
        trend: [65, 68, 72, 75, 80],
        graphNodeId: 'sk-performance'
      },
      {
        name: '微前端架构',
        level: 'high',
        reason: '企业级应用拆分与集成方案，提升架构能力',
        impact: 88,
        trend: [45, 52, 58, 65, 72],
        graphNodeId: 'sk-micro-frontend'
      },
      {
        name: 'Node.js 服务端',
        level: 'medium',
        reason: '全栈协作与 BFF 开发能力',
        impact: 78,
        trend: [50, 55, 60, 68, 75],
        graphNodeId: 'sk-nodejs'
      },
      {
        name: 'React 框架',
        level: 'medium',
        reason: '拓宽技术栈，增加就业竞争力',
        impact: 72,
        trend: [40, 48, 55, 62, 70],
        graphNodeId: 'sk-react'
      },
      {
        name: 'TypeScript 进阶',
        level: 'medium',
        reason: '类型系统深入，提升代码质量',
        impact: 68,
        trend: [58, 62, 68, 72, 78],
        graphNodeId: 'sk-typescript'
      }
    ],
    learningStages: [
      {
        title: '性能优化与工程化',
        phase: '第一阶段',
        weeks: '第 1-4 周',
        goal: '掌握前端性能优化核心方法，建立工程化思维',
        hours: 32,
        color: '#2f7cf6',
        collapsed: false,
        skills: ['性能优化', 'Webpack', 'Vite', 'Lighthouse'],
        tasks: [
          {
            name: '首屏加载优化实战',
            desc: '学习代码分割、懒加载、预加载等策略',
            output: '性能优化报告',
            done: false,
            status: 'in-progress',
            priority: 'P0',
            dueDate: '2026-07-25'
          },
          {
            name: '缓存策略与 Service Worker',
            desc: '实现离线缓存与资源预缓存',
            output: 'PWA Demo',
            done: false,
            status: 'pending',
            priority: 'P0',
            dueDate: '2026-08-01'
          },
          {
            name: '性能监控埋点方案',
            desc: '实现 FCP/LCP/CLS 等核心指标采集',
            output: '监控 SDK',
            done: false,
            status: 'pending',
            priority: 'P1',
            dueDate: '2026-08-08'
          },
          {
            name: 'Webpack/Vite 构建优化',
            desc: '掌握 Tree Shaking、代码分割、缓存优化',
            output: '优化配置文档',
            done: false,
            status: 'pending',
            priority: 'P1',
            dueDate: '2026-08-15'
          }
        ]
      },
      {
        title: '微前端与架构设计',
        phase: '第二阶段',
        weeks: '第 5-8 周',
        goal: '掌握微前端架构方案，提升大型项目设计能力',
        hours: 40,
        color: '#7c5cff',
        collapsed: false,
        skills: ['微前端', 'qiankun', 'Module Federation', '架构设计'],
        tasks: [
          {
            name: '微前端方案对比与选型',
            desc: '了解 qiankun、Module Federation、Single-SPA 等方案',
            output: '技术选型文档',
            done: false,
            status: 'pending',
            priority: 'P0',
            dueDate: '2026-08-22'
          },
          {
            name: 'qiankun 微前端实战',
            desc: '实现主应用与子应用的集成与通信',
            output: '微前端 Demo',
            done: false,
            status: 'pending',
            priority: 'P0',
            dueDate: '2026-08-29'
          },
          {
            name: 'Module Federation 实践',
            desc: '实现模块联邦与共享依赖',
            output: '联邦应用示例',
            done: false,
            status: 'pending',
            priority: 'P1',
            dueDate: '2026-09-05'
          },
          {
            name: '状态管理与通信机制',
            desc: '掌握跨应用状态共享与事件通信',
            output: '通信方案文档',
            done: false,
            status: 'pending',
            priority: 'P1',
            dueDate: '2026-09-12'
          }
        ]
      },
      {
        title: '全栈能力与 React',
        phase: '第三阶段',
        weeks: '第 9-12 周',
        goal: '掌握 Node.js 服务端开发，拓展 React 技术栈',
        hours: 48,
        color: '#27ae60',
        collapsed: false,
        skills: ['Node.js', 'Express', 'React', 'Next.js'],
        tasks: [
          {
            name: 'Node.js 基础与 Express',
            desc: '搭建 RESTful API 服务',
            output: 'API 服务',
            done: false,
            status: 'pending',
            priority: 'P1',
            dueDate: '2026-09-19'
          },
          {
            name: 'BFF 层设计与实现',
            desc: '学习 Backend for Frontend 架构模式',
            output: 'BFF 服务',
            done: false,
            status: 'pending',
            priority: 'P1',
            dueDate: '2026-09-26'
          },
          {
            name: 'React 核心概念与 Hooks',
            desc: '掌握 JSX、组件化、Hooks 等核心概念',
            output: 'React 组件库',
            done: false,
            status: 'pending',
            priority: 'P1',
            dueDate: '2026-10-03'
          },
          {
            name: 'Next.js 全栈框架实战',
            desc: '实现 SSR/SSG 与 API Routes',
            output: '全栈项目',
            done: false,
            status: 'pending',
            priority: 'P1',
            dueDate: '2026-10-10'
          }
        ]
      }
    ],
    outcome: {
      predictedScore: 95,
      skills: ['性能优化实战', '微前端架构', 'Node.js 服务端', 'React 框架', 'TypeScript 进阶'],
      description: '完成路线后，你将获得可展示的性能优化案例、微前端实战项目与更完整的全栈协作能力，预计岗位匹配度提升至 95 分。'
    }
  },

  data: {
    jobTitle: '数据分析师',
    currentScore: 72,
    targetScore: 90,
    estimatedWeeks: 10,
    dailyHours: 2,
    prioritySkills: [
      {
        name: 'SQL 查询与调优',
        level: 'high',
        reason: '数据岗位的通用基础能力，必须熟练掌握',
        impact: 95,
        trend: [60, 65, 70, 75, 82],
        graphNodeId: 'sk-sql'
      },
      {
        name: 'Python 数据分析',
        level: 'high',
        reason: '掌握 Pandas、NumPy 与常用分析方法',
        impact: 90,
        trend: [55, 60, 68, 75, 82],
        graphNodeId: 'sk-python'
      },
      {
        name: '指标体系设计',
        level: 'medium',
        reason: '提升业务分析的系统性与深度',
        impact: 78,
        trend: [42, 48, 55, 62, 70],
        graphNodeId: 'sk-metrics'
      },
      {
        name: '数据可视化',
        level: 'medium',
        reason: '将分析结果有效呈现给业务方',
        impact: 72,
        trend: [50, 55, 60, 68, 75],
        graphNodeId: 'sk-visualization'
      },
      {
        name: '机器学习基础',
        level: 'medium',
        reason: '预测分析与数据建模能力',
        impact: 65,
        trend: [35, 42, 50, 58, 65],
        graphNodeId: 'sk-ml'
      }
    ],
    learningStages: [
      {
        title: 'SQL 与数据基础',
        phase: '第一阶段',
        weeks: '第 1-3 周',
        goal: '熟练掌握 SQL 查询与数据库操作',
        hours: 24,
        color: '#1d9bf0',
        collapsed: false,
        skills: ['SQL', 'MySQL', 'PostgreSQL', '数据建模'],
        tasks: [
          {
            name: 'SQL 基础语法与查询',
            desc: '掌握 SELECT、JOIN、子查询等核心语法',
            output: 'SQL 练习集',
            done: false,
            status: 'in-progress',
            priority: 'P0',
            dueDate: '2026-07-25'
          },
          {
            name: '复杂查询与窗口函数',
            desc: '学习 ROW_NUMBER、RANK、LAG 等窗口函数',
            output: '高级查询案例',
            done: false,
            status: 'pending',
            priority: 'P0',
            dueDate: '2026-08-01'
          },
          {
            name: 'SQL 性能优化',
            desc: '索引优化、执行计划分析',
            output: '优化指南',
            done: false,
            status: 'pending',
            priority: 'P1',
            dueDate: '2026-08-08'
          }
        ]
      },
      {
        title: 'Python 数据分析',
        phase: '第二阶段',
        weeks: '第 4-6 周',
        goal: '掌握 Python 数据分析核心库',
        hours: 32,
        color: '#7c5cff',
        collapsed: false,
        skills: ['Python', 'Pandas', 'NumPy', 'Matplotlib'],
        tasks: [
          {
            name: 'Pandas 数据处理',
            desc: 'DataFrame 操作、数据清洗、聚合分析',
            output: '数据分析报告',
            done: false,
            status: 'pending',
            priority: 'P0',
            dueDate: '2026-08-15'
          },
          {
            name: 'NumPy 数值计算',
            desc: '数组操作、矩阵运算、统计计算',
            output: '计算示例',
            done: false,
            status: 'pending',
            priority: 'P1',
            dueDate: '2026-08-22'
          },
          {
            name: '数据可视化实战',
            desc: 'Matplotlib、Seaborn、Plotly 图表制作',
            output: '可视化作品集',
            done: false,
            status: 'pending',
            priority: 'P1',
            dueDate: '2026-08-29'
          }
        ]
      },
      {
        title: '业务分析与建模',
        phase: '第三阶段',
        weeks: '第 7-10 周',
        goal: '掌握业务分析方法与机器学习基础',
        hours: 40,
        color: '#27ae60',
        collapsed: false,
        skills: ['业务分析', '指标体系', '机器学习', 'A/B测试'],
        tasks: [
          {
            name: '指标体系设计',
            desc: '学习 AARRR、HEART 等指标框架',
            output: '指标体系文档',
            done: false,
            status: 'pending',
            priority: 'P0',
            dueDate: '2026-09-05'
          },
          {
            name: 'A/B 测试与因果推断',
            desc: '实验设计、显著性检验、结果解读',
            output: 'A/B 测试报告',
            done: false,
            status: 'pending',
            priority: 'P1',
            dueDate: '2026-09-12'
          },
          {
            name: '机器学习基础实战',
            desc: 'Scikit-learn 分类、回归、聚类',
            output: '预测模型',
            done: false,
            status: 'pending',
            priority: 'P1',
            dueDate: '2026-09-19'
          },
          {
            name: '综合分析项目',
            desc: '端到端数据分析项目实战',
            output: '完整分析报告',
            done: false,
            status: 'pending',
            priority: 'P0',
            dueDate: '2026-09-26'
          }
        ]
      }
    ],
    outcome: {
      predictedScore: 90,
      skills: ['SQL 查询与调优', 'Python 数据分析', '指标体系设计', '数据可视化', '机器学习基础'],
      description: '完成路线后，你将具备完整的数据分析能力，能够独立完成从数据提取到分析报告的全流程，预计岗位匹配度提升至 90 分。'
    }
  },

  ai: {
    jobTitle: 'AI 算法工程师',
    currentScore: 68,
    targetScore: 92,
    estimatedWeeks: 14,
    dailyHours: 3,
    prioritySkills: [
      {
        name: '深度学习框架',
        level: 'high',
        reason: 'PyTorch/TensorFlow 是算法工程师必备技能',
        impact: 95,
        trend: [55, 60, 68, 75, 85],
        graphNodeId: 'sk-pytorch'
      },
      {
        name: '大模型应用开发',
        level: 'high',
        reason: 'LLM 微调、RAG 系统设计与 Agent 框架搭建',
        impact: 92,
        trend: [40, 50, 62, 75, 88],
        graphNodeId: 'sk-llm'
      },
      {
        name: '机器学习算法',
        level: 'high',
        reason: '经典算法原理与实现',
        impact: 88,
        trend: [50, 55, 62, 70, 78],
        graphNodeId: 'sk-ml-algo'
      },
      {
        name: 'RAG 系统设计',
        level: 'medium',
        reason: '检索增强生成系统架构与实现',
        impact: 82,
        trend: [30, 42, 55, 68, 80],
        graphNodeId: 'sk-rag'
      },
      {
        name: 'Agent 框架',
        level: 'medium',
        reason: '智能体框架搭建与工具调用',
        impact: 75,
        trend: [25, 35, 48, 62, 75],
        graphNodeId: 'sk-agent'
      }
    ],
    learningStages: [
      {
        title: '机器学习基础',
        phase: '第一阶段',
        weeks: '第 1-4 周',
        goal: '掌握经典机器学习算法原理与实现',
        hours: 36,
        color: '#7c5cff',
        collapsed: false,
        skills: ['Python', 'Scikit-learn', '特征工程', '模型评估'],
        tasks: [
          {
            name: '监督学习算法',
            desc: '线性回归、决策树、随机森林、SVM',
            output: '算法实现笔记',
            done: false,
            status: 'in-progress',
            priority: 'P0',
            dueDate: '2026-07-25'
          },
          {
            name: '无监督学习算法',
            desc: 'K-Means、PCA、聚类分析',
            output: '聚类案例',
            done: false,
            status: 'pending',
            priority: 'P0',
            dueDate: '2026-08-01'
          },
          {
            name: '特征工程实战',
            desc: '特征提取、选择、转换与降维',
            output: '特征工程指南',
            done: false,
            status: 'pending',
            priority: 'P1',
            dueDate: '2026-08-08'
          },
          {
            name: '模型评估与调优',
            desc: '交叉验证、超参搜索、模型融合',
            output: '调优报告',
            done: false,
            status: 'pending',
            priority: 'P1',
            dueDate: '2026-08-15'
          }
        ]
      },
      {
        title: '深度学习与 PyTorch',
        phase: '第二阶段',
        weeks: '第 5-9 周',
        goal: '掌握深度学习核心概念与 PyTorch 框架',
        hours: 48,
        color: '#f08c2e',
        collapsed: false,
        skills: ['PyTorch', 'CNN', 'RNN', 'Transformer'],
        tasks: [
          {
            name: 'PyTorch 基础与张量操作',
            desc: '自动求导、数据加载、模型定义',
            output: 'PyTorch 笔记',
            done: false,
            status: 'pending',
            priority: 'P0',
            dueDate: '2026-08-22'
          },
          {
            name: 'CNN 卷积神经网络',
            desc: '图像分类、目标检测基础',
            output: '图像分类模型',
            done: false,
            status: 'pending',
            priority: 'P0',
            dueDate: '2026-08-29'
          },
          {
            name: 'RNN 与序列模型',
            desc: 'LSTM、GRU 与序列建模',
            output: '文本分类模型',
            done: false,
            status: 'pending',
            priority: 'P1',
            dueDate: '2026-09-05'
          },
          {
            name: 'Transformer 架构',
            desc: '注意力机制、BERT、GPT 原理',
            output: 'Transformer 笔记',
            done: false,
            status: 'pending',
            priority: 'P0',
            dueDate: '2026-09-12'
          }
        ]
      },
      {
        title: '大模型应用开发',
        phase: '第三阶段',
        weeks: '第 10-14 周',
        goal: '掌握 LLM 微调、RAG 与 Agent 开发',
        hours: 56,
        color: '#27ae60',
        collapsed: false,
        skills: ['LLM', 'RAG', 'Agent', 'LoRA', 'LangChain'],
        tasks: [
          {
            name: 'LLM 微调实战',
            desc: 'LoRA、QLoRA 微调方法与实践',
            output: '微调模型',
            done: false,
            status: 'pending',
            priority: 'P0',
            dueDate: '2026-09-19'
          },
          {
            name: 'RAG 系统设计与实现',
            desc: '向量数据库、检索策略、生成优化',
            output: 'RAG 系统',
            done: false,
            status: 'pending',
            priority: 'P0',
            dueDate: '2026-09-26'
          },
          {
            name: 'Agent 框架开发',
            desc: 'ReAct、Function Calling、工具链',
            output: 'Agent 应用',
            done: false,
            status: 'pending',
            priority: 'P0',
            dueDate: '2026-10-03'
          },
          {
            name: '综合 AI 项目',
            desc: '端到端 AI 应用开发实战',
            output: 'AI 项目作品',
            done: false,
            status: 'pending',
            priority: 'P0',
            dueDate: '2026-10-10'
          }
        ]
      }
    ],
    outcome: {
      predictedScore: 92,
      skills: ['深度学习框架', '大模型应用开发', '机器学习算法', 'RAG 系统设计', 'Agent 框架'],
      description: '完成路线后，你将具备完整的 AI 算法开发能力，能够独立完成从模型训练到应用部署的全流程，预计岗位匹配度提升至 92 分。'
    }
  },

  backend: {
    jobTitle: 'Java 后端开发工程师',
    currentScore: 70,
    targetScore: 92,
    estimatedWeeks: 12,
    dailyHours: 2,
    prioritySkills: [
      {
        name: 'Spring Boot 深度',
        level: 'high',
        reason: '企业级 Java 开发核心框架',
        impact: 95,
        trend: [60, 65, 72, 78, 85],
        graphNodeId: 'sk-spring'
      },
      {
        name: '分布式系统设计',
        level: 'high',
        reason: '微服务架构与分布式事务处理',
        impact: 88,
        trend: [45, 52, 60, 68, 78],
        graphNodeId: 'sk-distributed'
      },
      {
        name: '数据库优化',
        level: 'high',
        reason: 'MySQL 调优、索引设计、分库分表',
        impact: 85,
        trend: [55, 60, 68, 75, 82],
        graphNodeId: 'sk-db-opt'
      },
      {
        name: 'Redis 缓存',
        level: 'medium',
        reason: '高性能缓存方案与分布式锁',
        impact: 78,
        trend: [50, 55, 62, 70, 78],
        graphNodeId: 'sk-redis'
      },
      {
        name: '消息队列',
        level: 'medium',
        reason: '异步处理与系统解耦',
        impact: 72,
        trend: [42, 48, 55, 62, 70],
        graphNodeId: 'sk-mq'
      }
    ],
    learningStages: [
      {
        title: 'Spring Boot 进阶',
        phase: '第一阶段',
        weeks: '第 1-4 周',
        goal: '深入 Spring Boot 核心机制与最佳实践',
        hours: 32,
        color: '#f08c2e',
        collapsed: false,
        skills: ['Spring Boot', 'Spring Cloud', 'MyBatis', 'JPA'],
        tasks: [
          {
            name: 'Spring Boot 自动配置原理',
            desc: '深入理解 Starter、条件装配、配置绑定',
            output: '原理分析文档',
            done: false,
            status: 'in-progress',
            priority: 'P0',
            dueDate: '2026-07-25'
          },
          {
            name: 'Spring Cloud 微服务',
            desc: '服务注册、配置中心、网关、熔断',
            output: '微服务架构图',
            done: false,
            status: 'pending',
            priority: 'P0',
            dueDate: '2026-08-01'
          },
          {
            name: 'ORM 框架深度',
            desc: 'MyBatis Plus、JPA 高级特性',
            output: 'ORM 最佳实践',
            done: false,
            status: 'pending',
            priority: 'P1',
            dueDate: '2026-08-08'
          },
          {
            name: '安全与认证',
            desc: 'OAuth2、JWT、Spring Security',
            output: '安全方案',
            done: false,
            status: 'pending',
            priority: 'P1',
            dueDate: '2026-08-15'
          }
        ]
      },
      {
        title: '分布式系统设计',
        phase: '第二阶段',
        weeks: '第 5-8 周',
        goal: '掌握分布式系统核心概念与实现',
        hours: 40,
        color: '#7c5cff',
        collapsed: false,
        skills: ['分布式', '微服务', 'RPC', '分布式事务'],
        tasks: [
          {
            name: '分布式理论基础',
            desc: 'CAP、BASE、一致性算法',
            output: '理论笔记',
            done: false,
            status: 'pending',
            priority: 'P0',
            dueDate: '2026-08-22'
          },
          {
            name: '分布式事务解决方案',
            desc: 'Seata、TCC、Saga 模式',
            output: '事务方案对比',
            done: false,
            status: 'pending',
            priority: 'P0',
            dueDate: '2026-08-29'
          },
          {
            name: 'RPC 框架实战',
            desc: 'Dubbo、gRPC 使用与原理',
            output: 'RPC 服务示例',
            done: false,
            status: 'pending',
            priority: 'P1',
            dueDate: '2026-09-05'
          },
          {
            name: '分布式缓存与锁',
            desc: 'Redis 集群、分布式锁实现',
            output: '缓存方案',
            done: false,
            status: 'pending',
            priority: 'P1',
            dueDate: '2026-09-12'
          }
        ]
      },
      {
        title: '高性能与高可用',
        phase: '第三阶段',
        weeks: '第 9-12 周',
        goal: '掌握高性能系统设计与高可用架构',
        hours: 44,
        color: '#27ae60',
        collapsed: false,
        skills: ['性能优化', '高可用', '监控', 'DevOps'],
        tasks: [
          {
            name: '数据库性能优化',
            desc: '索引优化、慢查询分析、分库分表',
            output: '优化报告',
            done: false,
            status: 'pending',
            priority: 'P0',
            dueDate: '2026-09-19'
          },
          {
            name: '消息队列实战',
            desc: 'Kafka/RabbitMQ 使用与优化',
            output: 'MQ 应用案例',
            done: false,
            status: 'pending',
            priority: 'P1',
            dueDate: '2026-09-26'
          },
          {
            name: '系统监控与告警',
            desc: 'Prometheus、Grafana、ELK',
            output: '监控大盘',
            done: false,
            status: 'pending',
            priority: 'P1',
            dueDate: '2026-10-03'
          },
          {
            name: '综合项目实战',
            desc: '高并发电商系统设计与实现',
            output: '完整项目',
            done: false,
            status: 'pending',
            priority: 'P0',
            dueDate: '2026-10-10'
          }
        ]
      }
    ],
    outcome: {
      predictedScore: 92,
      skills: ['Spring Boot 深度', '分布式系统设计', '数据库优化', 'Redis 缓存', '消息队列'],
      description: '完成路线后，你将具备企业级 Java 后端开发能力，能够设计和实现高性能、高可用的分布式系统，预计岗位匹配度提升至 92 分。'
    }
  },

  product: {
    jobTitle: '产品经理',
    currentScore: 75,
    targetScore: 90,
    estimatedWeeks: 10,
    dailyHours: 2,
    prioritySkills: [
      {
        name: '需求分析与用户研究',
        level: 'high',
        reason: '产品经理核心能力，用户洞察与需求挖掘',
        impact: 92,
        trend: [62, 68, 75, 80, 88],
        graphNodeId: 'sk-requirement'
      },
      {
        name: '数据分析能力',
        level: 'high',
        reason: '数据驱动决策，产品优化依据',
        impact: 85,
        trend: [50, 58, 65, 72, 80],
        graphNodeId: 'sk-data-analysis'
      },
      {
        name: '产品设计与原型',
        level: 'medium',
        reason: '产品方案设计与交互原型制作',
        impact: 78,
        trend: [55, 60, 68, 75, 82],
        graphNodeId: 'sk-design'
      },
      {
        name: '项目管理',
        level: 'medium',
        reason: '跨团队协作与项目推进能力',
        impact: 72,
        trend: [48, 55, 62, 70, 78],
        graphNodeId: 'sk-pm'
      },
      {
        name: '商业思维',
        level: 'medium',
        reason: '商业模式设计与商业化落地',
        impact: 68,
        trend: [40, 48, 55, 62, 70],
        graphNodeId: 'sk-business'
      }
    ],
    learningStages: [
      {
        title: '用户研究与需求分析',
        phase: '第一阶段',
        weeks: '第 1-3 周',
        goal: '掌握用户研究方法与需求分析框架',
        hours: 24,
        color: '#e67e22',
        collapsed: false,
        skills: ['用户研究', '需求分析', '用户画像', '用户旅程'],
        tasks: [
          {
            name: '用户访谈与问卷设计',
            desc: '定性与定量用户研究方法',
            output: '用户研究报告',
            done: false,
            status: 'in-progress',
            priority: 'P0',
            dueDate: '2026-07-25'
          },
          {
            name: '用户画像与场景分析',
            desc: '构建用户画像，分析使用场景',
            output: '用户画像文档',
            done: false,
            status: 'pending',
            priority: 'P0',
            dueDate: '2026-08-01'
          },
          {
            name: '需求优先级排序',
            desc: 'Kano 模型、RICE 评分、MoSCoW 方法',
            output: '需求优先级矩阵',
            done: false,
            status: 'pending',
            priority: 'P1',
            dueDate: '2026-08-08'
          }
        ]
      },
      {
        title: '产品设计与原型',
        phase: '第二阶段',
        weeks: '第 4-6 周',
        goal: '掌握产品设计方法与原型制作工具',
        hours: 28,
        color: '#2f7cf6',
        collapsed: false,
        skills: ['产品设计', 'Figma', 'Axure', '交互设计'],
        tasks: [
          {
            name: '信息架构设计',
            desc: '产品结构设计、导航设计',
            output: '信息架构图',
            done: false,
            status: 'pending',
            priority: 'P0',
            dueDate: '2026-08-15'
          },
          {
            name: '交互设计与原型制作',
            desc: 'Figma/Axure 原型设计实战',
            output: '交互原型',
            done: false,
            status: 'pending',
            priority: 'P0',
            dueDate: '2026-08-22'
          },
          {
            name: 'PRD 文档撰写',
            desc: '产品需求文档写作规范与实践',
            output: 'PRD 文档',
            done: false,
            status: 'pending',
            priority: 'P1',
            dueDate: '2026-08-29'
          }
        ]
      },
      {
        title: '数据驱动与商业化',
        phase: '第三阶段',
        weeks: '第 7-10 周',
        goal: '掌握数据分析方法与商业化思维',
        hours: 36,
        color: '#27ae60',
        collapsed: false,
        skills: ['数据分析', 'A/B测试', '商业化', '增长策略'],
        tasks: [
          {
            name: '产品数据分析',
            desc: '核心指标定义、数据埋点、分析框架',
            output: '数据分析报告',
            done: false,
            status: 'pending',
            priority: 'P0',
            dueDate: '2026-09-05'
          },
          {
            name: 'A/B 测试与实验',
            desc: '实验设计、结果分析、决策应用',
            output: '实验报告',
            done: false,
            status: 'pending',
            priority: 'P1',
            dueDate: '2026-09-12'
          },
          {
            name: '商业模式设计',
            desc: '价值主张、收入模式、成本结构',
            output: '商业画布',
            done: false,
            status: 'pending',
            priority: 'P1',
            dueDate: '2026-09-19'
          },
          {
            name: '增长策略与运营',
            desc: 'AARRR 模型、增长黑客方法',
            output: '增长方案',
            done: false,
            status: 'pending',
            priority: 'P0',
            dueDate: '2026-09-26'
          }
        ]
      }
    ],
    outcome: {
      predictedScore: 90,
      skills: ['需求分析与用户研究', '数据分析能力', '产品设计与原型', '项目管理', '商业思维'],
      description: '完成路线后，你将具备完整的产品经理能力，能够独立负责产品从 0 到 1 的全流程，预计岗位匹配度提升至 90 分。'
    }
  }
}

// 学习资源推荐
export const learningResources = {
  '性能优化实战': {
    tutorials: ['Web 性能优化实战指南', 'Chrome DevTools 性能分析'],
    quizBank: '前端性能优化题库 (120 题)',
    projects: ['电商首屏优化', 'SPA 应用性能监控']
  },
  '微前端架构': {
    tutorials: ['qiankun 微前端从入门到实战', 'Module Federation 深度解析'],
    quizBank: '微前端架构题库 (80 题)',
    projects: ['企业后台微前端改造', '多团队协作微前端方案']
  },
  'SQL 查询与调优': {
    tutorials: ['SQL 必知必会', 'MySQL 性能优化实战'],
    quizBank: 'SQL 查询题库 (200 题)',
    projects: ['电商数据分析查询', '用户行为分析 SQL']
  },
  'Python 数据分析': {
    tutorials: ['Python 数据分析实战', 'Pandas 数据处理进阶'],
    quizBank: 'Python 数据分析题库 (150 题)',
    projects: ['销售数据分析报告', '用户画像分析']
  },
  '深度学习框架': {
    tutorials: ['PyTorch 深度学习实战', 'TensorFlow 2.0 入门到进阶'],
    quizBank: '深度学习题库 (180 题)',
    projects: ['图像分类模型', '文本情感分析']
  },
  '大模型应用开发': {
    tutorials: ['LLM 微调实战教程', 'LangChain 应用开发'],
    quizBank: '大模型应用题库 (100 题)',
    projects: ['智能客服系统', '文档问答应用']
  },
  'Spring Boot 深度': {
    tutorials: ['Spring Boot 高级特性', 'Spring Cloud 微服务实战'],
    quizBank: 'Spring Boot 题库 (160 题)',
    projects: ['电商后台系统', '微服务架构改造']
  },
  '分布式系统设计': {
    tutorials: ['分布式系统原理与范型', '微服务架构设计'],
    quizBank: '分布式系统题库 (120 题)',
    projects: ['分布式事务方案', '高可用架构设计']
  },
  '需求分析与用户研究': {
    tutorials: ['用户研究方法论', '需求分析实战'],
    quizBank: '用户研究题库 (80 题)',
    projects: ['用户访谈报告', '需求优先级矩阵']
  },
  '数据分析能力': {
    tutorials: ['产品经理数据分析', '数据驱动产品决策'],
    quizBank: '产品数据分析题库 (100 题)',
    projects: ['产品数据分析报告', 'A/B 测试方案']
  }
}

// 学习方案本地存储
export const learningPlanStorage = {
  KEY: 'learning_plans',
  get() {
    try {
      return JSON.parse(localStorage.getItem(this.KEY) || '[]')
    } catch {
      return []
    }
  },
  save(plan) {
    const plans = this.get()
    plans.push({
      ...plan,
      id: Date.now(),
      savedAt: new Date().toISOString()
    })
    localStorage.setItem(this.KEY, JSON.stringify(plans))
  },
  remove(id) {
    const plans = this.get().filter(p => p.id !== id)
    localStorage.setItem(this.KEY, JSON.stringify(plans))
  }
}

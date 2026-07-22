# TalentMind 系统架构设计文档 v2

- **日期**: 2026-07-20
- **项目**: 多源异构数据驱动岗位和能力图谱构建与动态演化分析
- **团队**: 五人分工协作
- **版本说明**: v2 在 v1 基础上强化"动态演化技术闭环"、"大模型增强层(反幻觉)"、"多源异构数据价值分层"、"层级分类体系"、"路径推荐匹配";舍弃"能力等级细粒度匹配";移除一切无数据支撑的精确数字。v1 文档 `2026-07-20-talentmind-系统架构-design.md` 保留存档。

## 1. 项目概述

多源异构数据驱动的岗位能力图谱系统。核心闭环:

> 多源数据采集 → 岗位发现 → 能力图谱构建 → **动态演化分析** → 简历解析 → 人岗匹配 → 可视化展示

**"动态演化"是赛题题眼**,本版本将其从"定期更新"升级为有生命周期模型、有数据依据的技术闭环。

### 赛题核心要求
- 新岗位发现与定义
- 既有岗位能力动态更新与**演化分析**
- 新一代信息技术岗位全景图谱
- 简历解析、人岗匹配和差距分析
- JD/简历解析准确率 ≥ 90%

### 评分维度
| 维度 | 权重 |
|------|------|
| 作品完整性 | 30 |
| 实用价值 | 30 |
| 技术创新性 | 25 |
| 用户体验 | 15 |

### 交付优先级总原则
完整性+实用价值=60 分是基本盘。**先保闭环跑通(P0),再叠加创新增强(P1)**。所有创新点不得拖垮主线闭环。

## 2. 关键技术决策

| 决策项 | 选择 | 理由 |
|--------|------|------|
| 大模型 | 云端 LLM API(必须支持多模态图像输入) | 快速迭代;多模态为硬约束(简历/图片JD兜底) |
| 大模型增强 | **skill_dict 约束抽取 + evidence + confidence** | 反幻觉、可溯源,提准确率与可辩护性 |
| 图谱规模 | 架构按中等(B)设计,实现分阶段(A→B) | 留索引/缓存位置,先跑闭环再扩数据 |
| 匹配算法 | LLM抽取+规则/向量匹配 + **岗位路径推荐** | 可解释、支撑差距分析与职业路径 |
| 数据采集 | 两阶段:数据集兜底 → 代理池稳定爬取 | 下游不空转,创新在清洗/交叉验证 |
| 后端架构 | FastAPI 单体 + 统一数据池 | 五人协作集成风险最低 |
| 分类体系 | **3-4 层级(领域→岗位族→岗位→技能)** | 比 flat 丰富,又不因层级过深致数据稀疏 |

### 决策记录(避免后续反复/偏移)
> 本节记录关键取舍及其理由,防止团队后续重复讨论或方向漂移。

- **DR-1 舍弃能力等级细粒度匹配**:从简历可靠抽取"高级/中级/初级"极主观,难验证,直接威胁 ≥90% 准确率;投入产出比不划算。**决定舍弃**,匹配不做细粒度职级维度。
- **DR-2 移除一切无数据支撑的精确数字**:`growth_rate`、`confidence`、"预计X个月"等,**仅在有真实数据支撑时保留,否则一律去掉或改为定性表达**。编造的精确数字是答辩负资产。
- **DR-3 RAG 不另造向量库**:领域知识约束复用 `skill_dict`,做 skill_dict-grounded 抽取,不搭独立 RAG 系统(五人赛期净负担)。
- **DR-4 需求指数为 P1 增强**:三源融合(招聘/技术热度/社区)是加分项,不得阻塞 P0 闭环;权重为经验值,答辩需诚实说明"可调经验权重"。
- **DR-5 分类 3-4 层而非 5 层**:项目限定"新一代信息技术"单一产业,Domain/Industry 再分冗余;层级过深会使节点数据稀疏、图空。

## 3. 动态演化技术闭环(核心创新)

### 岗位生命周期模型
将岗位/技能建模为生命周期,而非静态节点:
```
技能出现 → 技能增长 → 岗位形成 → 岗位成熟 → 技能衰退 → 岗位迁移
```
`emerging_job.evolution` 记录阶段判定。**阶段分类基于当前技能组合特征即可判定**;涉及 `growth_rate`/`confidence` 等数字**仅在有历史时序数据时计算并保留,否则省略**(见 DR-2)。

### 数据前提:历史时序数据(决定演化是"数据驱动"还是"概念演示")
真实演化需跨时间点数据。单次爬取只是当下快照,观测不出增长率。若能获取**学校资源 / 大厂公开历史数据集**,演化即从概念升级为数据驱动。计划内需先核实:
1. **粒度**:需 JD 级明细或技能级频次;仅"年度Top20榜"只能撑趋势图,撑不了细粒度岗位形成分析
2. **时间点**:至少年度、最好季度,需 2-3 个时间点才成曲线
3. **词表一致**:跨年份技能名必须归一到同一 `skill_dict`(如 2024"K8s" = 2026"Kubernetes"),否则趋势断裂

**计划新增步骤**:历史数据源核实与词表对齐(C+A)。有历史数据 → 走数据驱动;无 → 降级为基于 `first_seen` 时间戳的窗口内统计 + 策展案例展示,且不输出编造增长率。

### 演化可视化(B)
技能/岗位随时间迁移的时间轴视图(如 机器学习工程师 → LLM应用工程师 → Agent工程师),让"动态演化"评委看得见。数据来源标注清晰,不含无依据数字。

## 4. 系统架构

### 分层架构
```
┌─────────────────────────────────────────────────┐
│  前端层 (B)   Vue3/React + G6/ECharts + Axios      │
│  首页 · 能力大脑 · 岗位地图 · 能力图谱 · 匹配页 · 演化时间轴 │
└───────────────────────┬─────────────────────────┘
                        │ REST/JSON
┌───────────────────────▼─────────────────────────┐
│  API 层  FastAPI 单体 (D 搭骨架)                    │
│  routers: job(C) · graph(D) · resume(E) · match(E) │
│  统一: 响应格式 · 异常处理 · 依赖注入 · Pydantic 校验 │
└──────┬──────────┬───────────┬──────────┬─────────┘
       │          │           │          │
┌──────▼───┐ ┌────▼────┐ ┌────▼────┐ ┌───▼─────────┐
│ LLM服务  │ │ 图谱服务 │ │ 匹配服务 │ │ 简历解析服务  │
│ (C)      │ │ (D)     │ │ (E)     │ │ (E)          │
│约束抽取   │ │ Cypher  │ │加权+向量 │ │PDF/DOCX+多模态│
│+evidence │ │ 查询    │ │+路径推荐 │ │              │
└──────────┘ └─────────┘ └─────────┘ └──────────────┘
       │          │           │          │
┌──────▼──────────▼───────────▼──────────▼─────────┐
│  数据层  MySQL · Neo4j(图谱) · Redis(缓存/队列)      │
└───────────────────────▲─────────────────────────┘
                        │ 写入
              ┌─────────┴──────────────┐
              │ 离线采集进程 (A)          │
              │ 招聘源+技术生态+社区(分层) │
              └────────────────────────┘
```

### 解耦核心原则
跨人协作只通过两种契约:**数据库表结构** 和 **API/Pydantic 模型**。不直接调他人函数。

### 两条数据流
**离线批处理流**(保准确率,定时/手动触发):
```
多源采集 → 清洗去重交叉验证 → jd_pool
  → skill_dict约束抽取(+evidence/confidence) → job_skill
  → 聚类新岗位发现 + 生命周期判定 → emerging_job
  → 图谱构建 → Neo4j
```
**实时交互流**(用户即时):
```
上传简历 → 解析抽取 → 匹配算法 → 差距分析+路径推荐 → 返回
```

### 部署
- 开发期:`docker-compose` 拉起 MySQL+Neo4j+Redis+FastAPI;前端 `npm run dev`
- 演示期:单机部署,`uvicorn` + Nginx 托管前端静态文件
- 不引入 K8s/Kafka/微服务网关;Redis 做轻量队列

### 工程约定
- 统一响应 `{code, message, data}`,`code=0` 成功
- 统一异常处理,永不裸抛 500
- 配置走 `.env`+Pydantic Settings,**API Key 不进代码库**

## 5. 多源异构数据价值分层(A)

**修复 v1 隐患**:v1 的多个招聘源本质同质。本版按价值分三层,让"多源异构"名副其实,并为演化提供数据依据。

| 层 | 数据源 | 产出信号 |
|----|--------|---------|
| 第一层 岗位需求 | Boss/猎聘/智联/拉勾 | 企业需求(JD) |
| 第二层 技术生态 | GitHub(star增长/issue/release频率) | 技术热度 |
| 第三层 社区趋势 | CSDN/掘金/技术博客/牛客 | 社区讨论热度 |

**岗位需求指数(P1 增强,见 DR-4)**:
```
需求指数 = 招聘需求 40% + 技术热度 30% + 社区热度 30%
```
权重为**可调经验值**,答辩须如实说明,不宣称"学习所得"。GitHub 反爬弱、优先爬取。**此为 P1,不得阻塞 P0 闭环**——闭环先在 JD 数据跑通。

## 6. 五人分工

### A — 数据采集工程师
- **技术栈**: Python + `requests`/`httpx` + `Playwright` + 代理IP池 + `BeautifulSoup`/正则 + `APScheduler`
- **职责**:
  1. **三层多源采集**(招聘/技术生态/社区),代理池+随机延迟+断点续爬
  2. 数据清洗:去HTML、正文提取、字段规整
  3. **交叉验证去重(创新点)**:同岗位多源比对,识别抄袭/滞后,打质量分
  4. 标签化:岗位大类、来源、时间戳
  5. 写入 `raw_jd` + `jd_pool`;技术热度/社区信号入 `signal` 表(P1)
  6. **配合历史数据源核实与词表对齐**(演化数据前提)
- **产出**: `jd_pool` 表(+`signal` 表,P1)

### C — 大模型算法工程师
- **技术栈**: 云端 LLM API(**必须多模态**) + Prompt工程 + `pydantic` + `scikit-learn`(聚类) + embedding
- **职责**:
  1. **skill_dict 约束抽取**:检索 `skill_dict` 候选作上下文,LLM 映射到标准词(不自由生成);输出 `evidence`(JD出处)+`confidence` → `job_skill`
  2. **新岗位发现(核心)**:技能组合聚类 → LLM 生成定义 → `emerging_job`
  3. **动态演化分析**:生命周期阶段判定;有历史数据则算真实趋势,无则窗口内统计(不编数字)
  4. **维护 `skill_dict`**(系统地基,尽早产出)
  5. **多模态硬约束**:选支持图像的模型;对全队提供"文本抽取+多模态抽取"双接口
- **产出**: `job_skill`、`emerging_job`、`skill_dict` + 双抽取接口

### D — 知识图谱 + 后端工程师
- **技术栈**: Neo4j 社区版 + `Cypher` + `neo4j` driver + FastAPI(骨架) + SQLAlchemy
- **职责**:
  1. **搭 FastAPI 骨架**(全队地基):结构、依赖注入、连接池、统一响应/异常中间件、基础模型
  2. **图谱构建**:节点 `Domain`/`JobFamily`/`Job`/`Skill`(3-4层);关系 `REQUIRES`(权重)/`RELATED_TO`/`BELONGS_TO`
  3. **图谱查询 API**: `/graph/overview`、`/graph/job/{id}`、`/graph/skill-path`
  4. 数据库统一管理:表结构、Redis缓存、索引优化
- **产出**: FastAPI 骨架 + 图谱 API + Neo4j 数据

### E — 算法应用 + 产品架构工程师
- **技术栈**: `PyMuPDF`/`pdfplumber` + `python-docx` + LLM API(复用C接口) + embedding + `numpy`
- **职责**:
  1. **简历解析**:PDF(文本层/复杂排版分流,后者多模态)+DOCX **必做**;图片格式走"统计分布→阈值决策"闸门;不支持格式前端明确提示
  2. **人岗匹配(B主线)**:技能集 vs 岗位权重,加权+embedding 相似度 → 匹配分/已有/缺失。**不做细粒度能力等级匹配(DR-1)**
  3. **岗位路径推荐(加分,阶段3)**:当前岗位→目标岗位的技能差距路径(如 后端→AI应用:补 LLM/RAG/Agent)。**不输出"预计X个月"等无依据数字(DR-2)**
  4. **匹配 API**: `/resume/analyze`、`/match`
  5. **系统整合责任**:端到端串联,保证 demo 闭环
- **产出**: `/resume/analyze`、`/match` API

### B — 前端/UI 工程师
- **技术栈**: Vue3/React + ECharts/G6 + Axios + Element/Ant Design
- **职责**:首页、AI人才能力大脑、岗位地图、能力图谱、匹配上传页、**演化时间轴**。重点图谱交互流畅 + 差距/路径展示清晰(用户体验15分)

### 关键交接点
| 交接 | 上游产出 | 下游消费 | 契约 |
|------|---------|---------|------|
| A → C | 清洗后JD文本 | 约束抽取 | `jd_pool` |
| A → C | 技术/社区信号(P1) | 需求指数 | `signal` |
| C → D | 结构化岗位技能 | 图谱构建 | `job_skill`+`skill_dict` |
| C → E | 技能词典 | 简历归一 | `skill_dict` |
| C → E | 双抽取接口 | 简历抽取 | 接口约定 |
| D → 全队 | FastAPI骨架 | 挂router | 框架约定 |
| D → B | 图谱API | 可视化 | `/graph/*` |
| E → B | 匹配+路径 | 匹配页 | `/match`、`/resume/*` |
| C → E | 岗位技能权重 | 匹配算法 | `job_skill` |

**技能对齐(地基)**:C抽JD、E抽简历、D建图谱,技能名强制归一到 `skill_dict.canonical`,否则匹配算错、图谱重复节点。skill_dict-grounded 抽取同时解决此问题。

## 7. 核心数据契约与 API

### MySQL 数据表

**`jd_pool`**(A产出,C消费)
```
id BIGINT PK · source VARCHAR · job_title VARCHAR · raw_text TEXT
duties TEXT · experience VARCHAR · quality FLOAT(交叉验证质量分0-1)
dup_group VARCHAR(去重分组) · crawled_at DATETIME · status VARCHAR(raw/cleaned/extracted)
```

**`signal`**(A产出,P1,需求指数用)
```
id BIGINT PK · skill_or_job VARCHAR · signal_type VARCHAR(github/community)
metric VARCHAR(star/issue/release/post) · value FLOAT · captured_at DATETIME
```

**`skill_dict`**(C产出,全队归一)
```
id INT PK · canonical VARCHAR UNIQUE · aliases JSON · category VARCHAR
```

**`job_skill`**(C产出,D/E消费)
```
id BIGINT PK · jd_id BIGINT FK · job_name VARCHAR · level VARCHAR
skills JSON([{skill_id,name,weight,confidence,evidence}] 已归一) · duties TEXT · extracted_at DATETIME
```
> `confidence`+`evidence` 支撑反幻觉与人工复核;低 confidence 进复核队列。

**`emerging_job`**(C产出)
```
id INT PK · job_name VARCHAR · definition TEXT(LLM生成) · core_skills JSON
first_seen DATETIME · evolution JSON({stage, [growth_rate仅有历史数据时]})
```
> `evolution.stage` 恒有;`growth_rate`/`confidence` 仅在真实历史数据支撑时出现(DR-2)。

**`resume`**(E产出)
```
id BIGINT PK · raw_format VARCHAR(pdf/docx/image) · skills JSON(已归一)
experience JSON · parsed_at DATETIME
```

### Neo4j 图谱(D,3-4层)
```
节点: (:Domain {name})        -- AI/后端/前端/数据智能
      (:JobFamily {name})     -- 如 AI工程
      (:Job {name, level})
      (:Skill {name, category}) -- 对齐 skill_dict.canonical
关系: (Job)-[:REQUIRES {weight}]->(Skill)
      (Job)-[:BELONGS_TO]->(JobFamily)-[:PART_OF]->(Domain)
      (Skill)-[:RELATED_TO {strength}]->(Skill)
```

### 核心 API
| Method | Path | 负责人 | 请求 | 响应 data |
|--------|------|--------|------|-----------|
| GET | `/graph/overview` | D | `domain?` | 全景图谱 nodes+edges |
| GET | `/graph/job/{id}` | D | - | 岗位技能树 |
| GET | `/graph/skill-path` | D | `from,to` | 技能关联路径 |
| GET | `/jobs/emerging` | C | `limit` | 新岗位+定义+evolution |
| GET | `/jobs/evolution` | C | `range` | 演化时间轴数据 |
| POST | `/resume/analyze` | E | multipart文件 | 解析技能+经验 |
| POST | `/match` | E | `resume_id, job_id?` | 匹配度+已有+缺失+路径推荐 |

`/match` 的 `job_id` 可选:传则针对指定岗位;不传则自动推荐匹配度最高岗位为 `target_job`。所有接口套 `{code, message, data}`。

### 契约冻结
第一天全队过表和 API 后冻结。**加字段允许(向后兼容),改/删字段必须全队通知**。无数据阶段用 Mock 填充,谁都不阻塞谁。

## 8. 错误处理与测试策略

### 分层错误处理
- **LLM层**(C/E):超时/限流→指数退避重试(≤3次),失败落 `status=failed` 不丢数据;输出不合法→强制 JSON mode+Pydantic 校验+重试;批量单条失败隔离;**低 confidence→人工复核队列**
- **文件解析层**(E):格式不支持→明确提示;解析空/乱→多模态兜底;仍失败→"无法识别"不静默
- **图谱层**(D):节点不存在→空结果+提示;慢查询→Redis缓存热点
- **统一异常中间件**(D):未捕获→`{code:非0,message,data:null}`,记日志,永不裸抛500

### 测试策略
- **准确率验证(硬指标,E+C)**:50-100份 JD/简历标注测试集作 ground truth,算 Precision/Recall/**F1≥90%**;不达标则迭代 prompt/补 few-shot/强化 skill_dict 约束。作答辩证据
- **分层测试**:单元(匹配/归一/Cypher/清洗去重)· 契约(对冻结API验响应结构)· 集成(E主责,端到端上传→匹配→出结果)
- **数据质量测试**(A):去重率、质量分分布抽样人工核对,作交叉验证机制证据

### 测试优先级
1. **P0 必做**:准确率测试集 + 端到端集成测试
2. **P1 该做**:核心单元 + API契约测试
3. **P2 有空**:边界/异常路径全覆盖

## 9. 交付分期(P0 / P1 边界)

- **P0 闭环(必须完成)**:多源采集(JD为主)→约束抽取→图谱构建→简历解析→人岗匹配→可视化。生命周期**阶段分类**属 P0(基于当前特征可判定)。
- **P1 增强(闭环稳后叠加)**:三源需求指数(`signal` 表)· 基于历史数据的真实演化趋势 · 岗位路径推荐 · 演化时间轴富化。
- **贯穿要求**:无数据支撑的精确数字一律不出现(DR-2);能力等级细粒度匹配不做(DR-1)。





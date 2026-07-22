# TalentMind 系统架构设计文档

- **日期**: 2026-07-20
- **项目**: 新一代信息技术岗位能力图谱与人岗匹配系统
- **团队**: 五人分工协作

## 1. 项目概述

本项目是一个 AI + 数据工程 + 知识图谱 + 应用系统的综合项目。核心目标是完成完整闭环:

> 多源数据采集 → 岗位发现 → 能力图谱构建 → 动态演化 → 简历解析 → 人岗匹配 → 可视化展示

### 赛题核心要求
- 新岗位发现与定义
- 既有岗位能力动态更新
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

## 2. 关键技术决策

| 决策项 | 选择 | 理由 |
|--------|------|------|
| 大模型 | 云端 LLM API | 快速迭代,专注业务逻辑,免部署调优 |
| 图谱规模 | 架构按中等规模(B)设计,实现分阶段(A→B) | 留好索引/缓存位置,先跑通闭环再扩数据 |
| 匹配算法 | LLM 抽取 + 规则/向量匹配(B主线),图谱推理(C加分项) | 可解释、支撑差距分析,与图谱解耦不互相拖累 |
| 数据采集 | 两阶段:数据集兜底 → 代理池稳定爬取 | 保证下游不空转,创新点在清洗/交叉验证 |
| 后端架构 | FastAPI 单体 + 统一数据池 | 五人协作集成风险最低,交付确定性优先 |

### 图谱规模 A/B 说明
A(几百岗位+几千技能)与 B(数千岗位+上万技能)**技术栈完全相同**(均 Neo4j 社区版单机),代码架构相同。差异仅在数据量与查询优化(索引/缓存)。B 可随时平滑退回 A,退化是"减法",风险极低。策略:**架构按 B 设计,实现按 A 节奏先跑通闭环,再逐步加数据与优化**。

### 数据采集手段修正
"24小时多线程"不能突破反爬,反而更快被封。真正决定采集量的是:代理 IP 池、随机延迟、JS 逆向能力、断点续爬。目标(真实数据最大化)保留,手段升级为 **分布式 + 代理IP池 + 随机延迟 + 断点续爬**。优先级:GitHub/牛客/博客/开源社区(反爬弱)先爬满,Boss/猎聘/智联(反爬强)量力而行。

## 3. 系统架构

### 分层架构

```
┌─────────────────────────────────────────────────┐
│  前端层 (B)   Vue3/React + G6/ECharts + Axios      │
│  首页 · 能力大脑 · 岗位地图 · 能力图谱 · 匹配页 · 趋势榜 │
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
│ 文本抽取  │ │ Cypher  │ │ 加权+向量│ │ PDF/DOCX+多模态│
│ 多模态    │ │ 查询    │ │ 差距分析 │ │              │
└──────────┘ └─────────┘ └─────────┘ └──────────────┘
       │          │           │          │
┌──────▼──────────▼───────────▼──────────▼─────────┐
│  数据层                                            │
│  MySQL(JD池/简历/词典) · Neo4j(图谱) · Redis(缓存/队列)│
└───────────────────────▲─────────────────────────┘
                        │ 写入
              ┌─────────┴─────────┐
              │  离线爬虫进程 (A)   │
              │  Playwright+代理池  │
              └───────────────────┘
```

### 解耦核心原则
所有跨人协作只通过两种契约:**数据库表结构** 和 **API/Pydantic 数据模型**。任何人不直接调用他人函数,只读写约定好的表或调用 API。

### 两条数据流

**离线批处理流**(慢工出细活,保准确率,定时/手动触发):
```
爬虫采集 → 清洗去重交叉验证 → jd_pool
  → LLM 技能抽取 → job_skill
  → 聚类新岗位发现 → emerging_job
  → 图谱构建 → Neo4j
```
图谱全景、岗位地图、趋势榜查询的都是预计算结果,前端秒开。

**实时交互流**(用户即时体验,实时 API):
```
用户上传简历 → 解析抽取 → 匹配算法 → 差距分析 → 返回
```
匹配用到的岗位技能权重从 `job_skill` 预读,实时部分仅计算"候选人 vs 已有岗位",很轻。

### 部署方案
- **开发期**:`docker-compose` 一键拉起 MySQL + Neo4j + Redis + FastAPI;前端 `npm run dev`。统一五人环境
- **演示期**:单机部署(社区版 Neo4j 单机足够 B 规模)。FastAPI 用 `uvicorn`,前端打包静态文件由 Nginx/FastAPI 托管
- **不引入** K8s、Kafka、微服务网关(五人比赛项目负收益);用 `docker-compose` + Redis 轻量队列

### 工程约定
- 统一响应格式:`{code, message, data}`,`code=0` 成功,D 在骨架定义
- 统一异常处理:LLM 失败/超时、解析失败、图谱异常均有兜底,永不裸抛 500
- 配置集中:LLM API Key、数据库连接、代理池走 `.env` + Pydantic Settings,**API Key 不进代码库**

## 4. 五人分工

### A — 数据采集工程师
- **技术栈**: Python + `requests`/`httpx` + `Playwright`(JS渲染) + 代理IP池 + `BeautifulSoup`/正则 + `APScheduler`
- **职责**:
  1. 多源爬虫(GitHub/牛客/博客优先,Boss/猎聘量力而行),代理池+随机延迟+断点续爬
  2. 数据清洗:去 HTML、正文提取、字段规整
  3. **交叉验证去重(创新点)**:同岗位多源比对,识别抄袭/滞后 JD,打质量分
  4. 标签化:岗位大类、来源标签、时间戳
  5. 写入 MySQL `raw_jd` + `jd_pool`
- **产出契约**: `jd_pool` 表。前期用公开数据集填充解锁下游

### C — 大模型算法工程师
- **技术栈**: 云端 LLM API + Prompt 工程 + `pydantic`(约束输出) + `scikit-learn`(聚类)
- **职责**:
  1. **技能抽取**:读 `jd_pool`,LLM 抽结构化 `{岗位,核心技能[],等级,职责}` → `job_skill`
  2. **新岗位发现(赛题核心)**:技能组合聚类(embedding+KMeans/DBSCAN)→ LLM 生成岗位定义 → `emerging_job`
  3. **岗位能力动态更新**:定期重跑,对比技能频次,标记新增/衰退技能
  4. **维护技能标准词典 `skill_dict`**(系统地基,全系统技能对齐基础)
  5. **多模态为选型硬约束**:LLM 必须支持图像输入;对全队提供"文本抽取 + 多模态抽取"双接口(供 E 简历兜底、图片JD复用)
- **产出契约**: `job_skill`、`emerging_job`、`skill_dict` 三表 + 双抽取接口

### D — 知识图谱 + 后端工程师
- **技术栈**: Neo4j 社区版 + `Cypher` + `neo4j` driver + FastAPI(骨架搭建) + SQLAlchemy
- **职责**:
  1. **搭建 FastAPI 后端骨架**(全队地基):项目结构、依赖注入、连接池、统一响应格式、异常中间件、Pydantic 基础模型
  2. **图谱构建**:读 `job_skill`/`skill_dict` → Neo4j。节点 `Job`/`Skill`/`Category`,关系 `REQUIRES`(带权重)/`RELATED_TO`/`BELONGS_TO`
  3. **图谱查询 API**: `/graph/overview`、`/graph/job/{id}`、`/graph/skill-path`
  4. **数据库统一管理**:MySQL 表结构、Redis 缓存策略、索引优化
- **产出契约**: FastAPI 骨架 + 图谱查询 API + Neo4j 数据

### E — 算法应用 + 产品架构工程师
- **技术栈**: `PyMuPDF`/`pdfplumber` + `python-docx` + LLM API(复用C接口) + embedding + `numpy`
- **职责**:
  1. **简历解析**:PDF(文本层可提取 / 扫描件复杂排版分流,后者走多模态)+ DOCX **必做**;图片格式走"统计实际分布 → 阈值(如10%)决策"闸门,不预先投入;不支持格式前端明确提示
  2. **人岗匹配(B主线)**:候选人技能集 vs 岗位技能权重,加权匹配度 + embedding 相似度 → 匹配分/已有/缺失
  3. **差距分析 + 学习建议**:缺失技能 → 学习路线
  4. **匹配 API**: `/resume/analyze`、`/match`
  5. **系统整合责任**:端到端串联,保证 demo 闭环
- **产出契约**: `/resume/analyze`、`/match` API,直接对接前端

### B — 前端/UI 工程师
- **技术栈**: Vue3/React + ECharts/G6(图谱可视化) + Axios + Element/Ant Design
- **职责**:首页、AI人才能力大脑、岗位地图、能力图谱、人岗匹配上传页、**趋势榜(动态演化可视化,让创新点看得见)**。重点图谱交互流畅度 + 差距分析清晰展示(用户体验15分)

### 关键交接点
| 交接 | 上游产出 | 下游消费 | 契约 |
|------|---------|---------|------|
| A → C | 清洗后 JD 文本 | LLM 技能抽取 | `jd_pool` 表 |
| C → D | 结构化岗位技能 | 图谱构建 | `job_skill`+`skill_dict` |
| C → E | 技能标准词典 | 简历技能归一 | `skill_dict` 表 |
| C → E | 双抽取接口 | 简历文本/多模态抽取 | 接口约定 |
| D → 全队 | FastAPI 骨架 | 各自挂 router | 代码框架约定 |
| D → B | 图谱查询 API | 可视化渲染 | `/graph/*` 契约 |
| E → B | 匹配结果 | 匹配页展示 | `/match`、`/resume/*` 契约 |
| C → E | 岗位技能权重 | 匹配算法 | `job_skill` 表 |

**技能对齐(隐藏地基风险)**:C 抽 JD、E 抽简历、D 建图谱,技能名必须强制归一到 `skill_dict.canonical`,否则匹配算错、图谱重复节点,90% 准确率无从谈起。`skill_dict` 需 C 尽早产出。

## 5. 核心数据契约与 API

### MySQL 数据表

**`jd_pool`** — 数据池(A 产出,C 消费)
```
id BIGINT PK · source VARCHAR · job_title VARCHAR · raw_text TEXT
duties TEXT · experience VARCHAR · quality FLOAT(交叉验证质量分0-1)
dup_group VARCHAR(去重分组,同组=疑似重复/抄袭) · crawled_at DATETIME
status VARCHAR(raw/cleaned/extracted)
```

**`skill_dict`** — 技能标准词典(C 产出,全队归一)
```
id INT PK · canonical VARCHAR UNIQUE(标准名"Kubernetes")
aliases JSON(["K8s","k8s"]) · category VARCHAR(语言/框架/工具/理论)
```

**`job_skill`** — 结构化岗位技能(C 产出,D/E 消费)
```
id BIGINT PK · jd_id BIGINT FK · job_name VARCHAR · level VARCHAR(初/中/高级)
skills JSON([{skill_id,name,weight}] 已归一) · duties TEXT · extracted_at DATETIME
```

**`emerging_job`** — 新岗位发现(C 产出,展示用)
```
id INT PK · job_name VARCHAR("RAG工程师") · definition TEXT(LLM生成)
core_skills JSON · first_seen DATETIME(支撑动态演化) · freq_trend JSON(趋势榜数据源)
```

**`resume`** — 简历解析结果(E 产出)
```
id BIGINT PK · raw_format VARCHAR(pdf/docx/image) · skills JSON(已归一)
experience JSON · parsed_at DATETIME
```

### Neo4j 图谱结构(D 负责)
```
节点:  (:Job {name, level})
       (:Skill {name, category})    -- name 对齐 skill_dict.canonical
       (:Category {name})           -- AI领域/后端/前端...
关系:  (Job)-[:REQUIRES {weight}]->(Skill)
       (Job)-[:BELONGS_TO]->(Category)
       (Skill)-[:RELATED_TO {strength}]->(Skill)
```

### 核心 API 契约
| Method | Path | 负责人 | 请求 | 响应 data |
|--------|------|--------|------|-----------|
| GET | `/graph/overview` | D | `category?` | 全景图谱 nodes+edges |
| GET | `/graph/job/{id}` | D | - | 岗位技能树 |
| GET | `/graph/skill-path` | D | `from,to` | 技能关联路径 |
| GET | `/jobs/emerging` | C | `limit` | 新岗位列表+定义 |
| GET | `/jobs/trends` | C | `range` | 技能升降榜(动态演化) |
| POST | `/resume/analyze` | E | multipart 文件 | 解析技能+经验 |
| POST | `/match` | E | `resume_id, job_id?` | 匹配度+已有+缺失+学习建议 |

`/match` 的 `job_id` 可选:传则针对指定岗位算匹配;不传则系统在已有岗位中自动推荐匹配度最高的岗位作为 `target_job`。

所有接口套 `{code, message, data}`,`code=0` 成功。`/match` 响应示例:
```json
{
  "code": 0, "message": "ok",
  "data": {
    "target_job": "AI应用工程师", "score": 82,
    "matched": ["Python", "Docker"],
    "missing": ["LangChain", "RAG", "Vector Database"],
    "suggestions": [{"skill": "RAG", "path": "..."}]
  }
}
```

### 契约冻结策略
开工**第一天全队过一遍这几张表和 7 个 API**,确认后冻结。
- 表**加字段**允许(向后兼容),**改/删字段**必须全队通知
- API **响应加字段**允许,**改结构**必须通知前端
- 无数据阶段:C/D/E 用 Mock 填充表/接口,B 用 Mock 响应做页面,**谁都不阻塞谁**

## 6. 错误处理与测试策略

### 分层错误处理
- **LLM 调用层**(C/E):超时/限流 → 指数退避重试(≤3次),失败落 `status=failed` 不丢数据;输出不合法 → 强制 JSON mode/function calling + Pydantic 校验,失败重试再记录;批量抽取单条失败隔离不中断整批
- **文件解析层**(E):格式不支持 → 明确错误码提示上传 PDF/DOCX;解析空/乱 → 多模态兜底,仍失败返回"无法识别"不静默
- **图谱查询层**(D):节点不存在 → 空结果+提示不抛异常;慢查询 → Redis 缓存热点
- **统一异常中间件**(D):未捕获异常 → `{code:非0, message, data:null}`,记日志,永不裸抛 500

### 测试策略
- **准确率验证(硬指标,E+C 主责)**:建 50-100 份 JD/简历标注测试集作 ground truth,算 Precision/Recall/**F1 ≥ 90%**;不达标则迭代 prompt / 补 few-shot / 强化 `skill_dict`。此测试集同时作答辩证据
- **分层测试**:单元测试(匹配算法/技能归一/Cypher/清洗去重)· 契约测试(对冻结 API 验响应结构)· 集成测试(E 主责,端到端"上传→匹配→出结果")
- **数据质量测试**(A):去重率、质量分分布抽样人工核对,作交叉验证机制的创新点证据

### 测试优先级
1. **P0 必做**:准确率测试集 + 端到端集成测试
2. **P1 该做**:核心单元测试 + API 契约测试
3. **P2 有空再做**:边界/异常路径全覆盖




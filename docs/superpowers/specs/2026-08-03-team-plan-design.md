# TalentMind 团队协作与数据契约设计

- **日期**: 2026-08-03
- **定位**: 全队协作主文档，替代 `2026-07-20-talentmind-系统架构-design-v2.md`（v2 保留存档，其 API 清单作废，见决策 D6）
- **决策依据**: `docs/superpowers/决策跟踪.md`（D1–D18）

## 1. 竞赛目标（XH-202621）

功能四件套：
1. 新岗位发现与定义（岗位名称、核心职责、必备技能、加分技能、典型行业应用场景，支持人工优化）
2. 既有岗位能力动态更新（新增/删除/修改能力项 + 更新说明 + 数据源）
3. 新一代信息技术岗位全景图谱（技能点粒度，按技术栈/级别切换视图）
4. 简历解析（PDF/Word）+ 多维度人岗匹配 + 差距分析 + 学习路径规划

硬性指标：JD 解析 / 简历提取 / 匹配准确率 ≥90%；≥100 条岗位 JD 测试用例；单测覆盖率 ≥60%；系统可部署运行。评分：完整性 30 / 实用价值 30 / 技术创新 25 / 用户体验 15。

## 2. 协作模式（D2–D5）

- 5 人 5 台电脑；主数据库与统一 API 在 A 电脑；最终在 A 电脑合并全部模块；其他电脑默认只放自己模块的文件。
- 模块间通过「文件交接 + A 唯一集成」协作：M2/M3 产出标准数据文件，M4 交付可运行模块，A 导入主库并维护 API，M5 对接 API（开发期 Mock）。
- 技术栈自选、效果优先；契约只约定数据格式与接口。

## 3. 模块划分

| 模块 | 职责 | 产出 | 不负责 |
|---|---|---|---|
| M1 数据采集（A） | 爬取岗位 JD + 简历/人才原始数据；清洗、去重、交叉验证 | jd_pool / talent_raw / signal；样例文件 | 抽取、图谱、匹配 |
| M2 岗位分析 | JD → 结构化岗位定义；技能归一；新岗位发现；动态演化 | skill_dict / job_definition / job_skill / job_change_log（文件） | API、图谱、前端 |
| M3 图谱 | 岗位结构化数据 → 图谱节点/关系（点和线） | graph.json（nodes/edges） | 抽取、匹配 |
| M4 简历+匹配 | 解析简历；匹配库内岗位；差距分析/路径建议 | 可运行模块 + 输入输出约定 + 测试集 | 图谱、前端 |
| M5 前端 | 所有岗位 / 图谱 / 岗位匹配三个页面 | 三页代码（Mock → 真 API） | 后端逻辑 |

## 4. 需求 → 模块映射

| 竞赛需求 | 主责模块 | 协作模块 |
|---|---|---|
| 新岗位发现与定义 | M2 | M1 供数据、M3 建图谱、M5 展示 |
| 既有岗位能力动态更新 | M2 | M1 供数据、M5 展示 |
| 全景图谱 | M3 | M2 供结构化数据、M5 可视化 |
| 简历解析 + 匹配 + 差距分析 + 路径 | M4 | M2 供 skill_dict/岗位数据、M5 交互 |
| 原始采集与交叉验证 | M1 | — |
| 集成 / API / 部署 | A | 全员交接 |

## 5. 产出-消费矩阵

| 数据产物 | 产出 | 消费 | 交接形式 | 时点 |
|---|---|---|---|---|
| 原始 JD（≥100 条） | M1 | M2 | jd.json / jd_pool 导出 | 第 1 周 |
| 原始人才数据 | M1 | M4（测试样本） | talent_raw 文件 | 第 1 周 |
| 技能词典 skill_dict | M2 | M3、M4 | skill_dict.json | 第 1-2 周 |
| 岗位定义（五要素+来源+收集时间） | M2 | M3、A | job_definition.json | 第 2 周 |
| 岗位技能明细（证据链） | M2 | M3、A | job_skill.json | 第 2 周 |
| 图谱数据 nodes/edges | M3 | A（导入 Neo4j） | graph.json | 第 2-3 周 |
| 简历解析 + 匹配模块 | M4 | A（集成进 API） | 可运行代码 + 约定 | 第 3 周 |
| 统一 API | A | M5 | API 文档 + Mock | 第 2 周起 |
| 前端三页 | M5 | 用户 | 代码 | 第 1-3 周 |
| ≥100 条 JD 标注测试集 | M2+M4 | A（验收） | 文件 | 第 2-3 周 |

## 6. 数据契约（MySQL，冻结于 backend/app/contracts/ddl.sql）

### 6.1 分层

- **原始层（M1）**: jd_pool（岗位原始 JD）、talent_raw（人才原始线索）、signal（技术/社区热度，P1）
- **分析层**: skill_dict（技能归一）、job_definition（岗位定义主表）、job_skill（岗位技能证据链明细）、job_change_log（能力变更审计）、resume（简历解析结果）

### 6.2 job_definition（新增，取代 emerging_job）

字段：`job_name`、`core_duties`、`required_skills`(JSON)、`bonus_skills`(JSON)、`scenarios`(JSON)、`source`(JSON 平台数组)、`quality`(FLOAT)、`is_emerging`、`evolution`(JSON)、`first_seen`、`collected_at`、`updated_at`。

说明：无 status/reviewed 审核状态（D14）；source 仅记录平台（D17）；is_emerging 由 M2 判定（D12）；evolution 分 P0 静态分类 / P1 趋势（D13）。

### 6.3 job_skill（改造）

`skills` JSON 条目结构：`{skill_id, name, weight, confidence, evidence, is_required}`。is_required 区分必备/加分；evidence + confidence 为反幻觉证据链。

### 6.4 job_change_log（新增）

字段：`job_id`、`change_type`(added/removed/modified)、`skill_name`、`detail`(JSON)、`source`、`reason`、`created_at`。

### 6.5 其余表

jd_pool / talent_raw / signal / skill_dict / resume 保持原定义不变。

## 7. 图谱契约（Neo4j）

- 节点：Job（对齐 job_definition.job_name）、Skill（对齐 skill_dict.canonical）
- 关系：REQUIRES（weight，required/bonus 标记）、RELATED_TO（技能关联）
- M3 产出 graph.json（nodes/edges），A 导入 Neo4j（docker 命名卷 neo4j_data 持久化，重启不丢；graph.json 留仓库双保险）

## 8. 交接文件标准（D16）

- 统一 UTF-8、JSON 数组、snake_case、目录 `exchange/<模块>/`；字段冻结于本文件 + ddl.sql
- 文件清单：M1 `jd.json`；M2 `skill_dict.json` / `job_definition.json` / `job_skill.json`；M3 `graph.json`；M4 可运行模块 + `match_result.json` 示例；M5 mock 数据

job_definition.json 示例：

```json
[{
  "job_name": "RAG工程师",
  "core_duties": "负责检索增强生成系统的搭建与优化",
  "required_skills": ["langchain", "rag", "embedding"],
  "bonus_skills": ["faiss", "fine-tuning"],
  "scenarios": ["智能客服", "企业知识库问答"],
  "source": ["Boss直聘", "猎聘"],
  "quality": 0.9,
  "collected_at": "2026-08-03T10:00:00",
  "is_emerging": true
}]
```

## 9. API 契约（A 维护，M5 消费）

| 页面 | API | 说明 |
|---|---|---|
| 所有岗位 | GET /jobs | 列表/搜索/筛选/分页 |
| 图谱 | GET /graph/overview、GET /graph/job/{id} | 全景 / 岗位技能子图 |
| 岗位匹配 | POST /resume/analyze、POST /match | 上传解析；匹配 + 差距 + 路径 |

统一响应 `{code, message, data}`；开发期 M5 用 Mock，接口文档由 A 维护。此集合由页面需求推导，非 v2 清单。

## 10. 反幻觉与证据链

- LLM 抽取受 skill_dict 约束（只能映射到标准词，禁止自由生成）
- 每条技能必须输出 evidence（JD 原文）+ confidence；无证据 / 低置信 → 人工复核队列，不进图谱与匹配
- job_skill 是证据链载体，答辩可溯源

## 11. 动态演化

- is_emerging 判定（M2）：岗位名+技能组合聚类 → 与既有 job_definition 比对 → 信号判断（JD 少但增长 / 技能组合新颖 / 来源分散）→ LLM 生成候选定义 → 人工确认
- evolution：P0 静态阶段分类（萌芽/增长/成熟/衰退，基于技能组合特征，不编造数字）；P1 基于多轮采集时间序列算真实趋势

## 12. 验收与测试

- 测试集：≥100 条 JD 标注（M2+M4 构建、A 验收）；三项准确率 ≥90% 分模块验证（M2: JD 解析；M4: 简历提取与匹配）
- 单测覆盖率 ≥60%（每模块自带测试）
- 交付物：方案文档、PPT、10 分钟演示视频、源码、部署说明、1 新岗位 + 1 既有岗位图谱示例（含输入输出）

## 13. 里程碑（4 周）

- 第 0 天：冻结本契约
- 第 1 周：M1 ≥100 条 JD；M2 skill_dict 初版 + 抽取管道；M3 格式约定 + 样例；M4 简历解析；M5 Mock 三页
- 第 2 周：M2 交 job_definition / job_skill / job_change_log；M3 交 graph.json；M4 交匹配模块；M5 联调
- 第 3 周：A 集成、测试集与三项准确率验证
- 第 4 周：部署、文档、演示视频

## 14. 契约冻结规则

- 加表 / 加字段自由；改 / 删字段须全队通知（渠道：本文件 + 决策跟踪.md）
- 本文件与 v2 冲突时以本文件为准（D6）；未决事项见决策跟踪.md

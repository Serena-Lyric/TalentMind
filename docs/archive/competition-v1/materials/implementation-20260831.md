# 多源异构数据驱动岗位和能力图谱构建与动态演化分析研究——作品设计实现方案

> 题目编号：XH-202621　发榜单位：科大讯飞股份有限公司
> 版本：v0.1（初版，2026-08-31）
> 状态说明：本初版用于内部评审与开会讨论；文中所有量化数字均来自系统实测（2026-08-31 复核），标注"待验证/待完成"的项为真实缺口，不隐瞒。

---

## 1. 项目概述

### 1.1 背景与痛点

国家正从"人口红利"转向"人才红利"，"人工智能+"行动深入推进，新一代信息技术成为数字经济与产业升级的核心引擎。但技术迭代速度远超人才培养周期，劳动力市场出现结构性矛盾：企业在新兴岗位"招不到合适的人"，新兴领域青年"职业路径模糊、技能需求动态性强"。传统人才盘点依赖关键词匹配，缺乏对技术趋势的实时感知，难以回答"技术 A 的爆发会导致新兴岗位 B 产生哪些新技能需求"这一动态关联问题。

### 1.2 项目目标

构建一个能够自我进化的"人才能力大脑"，实现从"静态画像"到"动态感知"的跨越，围绕三大核心难题攻关：

1. 从海量多源数据中精准发现并定义新兴岗位，更新既有岗位的能力要求，构建可动态更新的岗位能力图谱；
2. 解决招聘数据中的"时滞、噪声、抄袭"问题，并通过技术手段有效防控 AI 生成内容"幻觉"，提升图谱构建科学性；
3. 实现高精度的简历解析与细粒度的人岗差距分析，提供针对性改进建议与岗位学习路径规划。

### 1.3 系统定位

面向新一代信息技术领域（人工智能、大数据、智能系统、物联网等），形成"新岗位发现与定义 → 既有岗位能力动态更新 → 全景图谱可视化 → 人岗匹配诊断 → 学习路径规划"的完整系统。

---

## 2. 系统总体架构

### 2.1 技术架构

五层架构：

```text
应用服务层   Vue3 前端 6 页（Dashboard / Jobs / Graph / Resume / ResumeDemo / Learning）+ FastAPI 20 接口
   │
图谱与应用层 Neo4j 知识图谱（Job–Skill REQUIRES / Job–Job RELATED_TO）；M4 匹配与差距分析
   │
岗位分析层   M2 岗位定义五要素抽取、技能 canonical 归一、演化阶段判定、变更审计（job_change_log）
   │
数据清洗层   HTML 剥离、字段归一、经验截断修复、去重、交叉验证（cross_source）、质量分（quality）
   │
数据采集层   多源异构 JD 采集（LinkedIn / HN / BOSS / 智联 / 猎聘）+ 技术信号采集（GitHub / 博客 RSS）
```

### 2.2 模块划分与数据流

| 模块 | 职责 | 正式位置 |
|---|---|---|
| M1 数据采集 | 多源异构 JD 与信号采集、清洗、去重、交叉验证 | `backend/app/collect/` |
| M2 岗位分析 | 新岗位发现与定义、既有岗位能力动态更新、技能归一 | `backend/app/job_analysis/` |
| M3 图谱构建 | 岗位-技能知识图谱构建与 Neo4j 导入 | `backend/app/graph/` |
| M4 简历解析与匹配 | 简历解析（PDF/Word）、人岗匹配、差距分析、学习路径 | `backend/app/matching/` |
| M5 前端 | 岗位/图谱/匹配/学习路径等 6 页面 | `frontend/` |
| A 集成层 | 统一 API、交接校验、数据导入、编排 | `backend/app/integration/`、`backend/app/routers/` |

数据流：`采集源 → M1 → MySQL（jd_pool/signal/talent_raw）→ M2 → job_definition/job_skill/job_change_log → M3 → graph.json → Neo4j → 20 统一 API → M5 前端`；M4 消费 M2 岗位数据完成简历解析与匹配。

### 2.3 部署架构

- docker-compose 单点部署：MySQL 8、Neo4j 5、Redis 7（Docker 命名卷持久化）。
- 后端 FastAPI（统一响应 `{code:0, message, data}`），默认端口 18000；前端 Vite，默认端口 18080（本机 8000/5173 受 Windows 端口权限限制）。
- 环境配置经 `backend/.env`（gitignore 保护），LLM 密钥不入库。

---

## 3. 核心技术创新（对应评分"技术创新性"25 分）

### 3.1 多源异构数据采集与交叉验证

**数据源矩阵（2026-08-31 实测）**：

| 数据源 | 数量 | 类型 |
|---|---|---|
| LinkedIn 岗位帖 | 123,849 条 | 全行业 JD |
| Hacker News "Who is hiring" | 1,793 条 | 技术岗月帖 |
| BOSS 直聘 | 1,131 条 | 中文岗位（受控人工登录 CDP 采集） |
| 智联招聘 | 1,088 条 | 中文岗位 |
| 猎聘 | 764 条 | 中文岗位 |
| GitHub / 技术博客 RSS 信号 | 1,493 条 | 技能/岗位热度信号（github 354 + blog 1,139） |
| **jd_pool 合计** | **128,625 条**（全部 cleaned） | 原始 JD 库 |

**合规采集策略**：LinkedIn/HN 走公开数据与公开 API；BOSS/智联/猎聘采用**受控人工登录 + 页面可见 DOM 低速采集**（不读取 Cookie/密码、不拦截请求、不调用私有接口、不处理验证码），检测到登录页/验证页立即停止。计划任务仅作尽力触发，持续采集循环自带幂等与断点恢复。

**"时滞、噪声、抄袭"处理**：
- 时滞：采集时间戳 + 帖子发布时间双记录，区分"发布时点"与"入库时点"；
- 噪声：HTML 剥离、字段归一化、经验字段截断修复（上限 255 字符，曾因单行描述捕获整段致 1406 报错，已修复）；
- 抄袭：`cross_validate` 双向包含 + 长度比 ≥0.6 判定重复，当前 `cross_source=1` 共 885 对（LinkedIn+HN 同岗位交叉命中），命中后 `quality` 质量分上浮。

**质量分体系**：`quality` 独立字段（0–1）+ `cross_source` 交叉验证标记（D17/D42），与"来源平台"字段分离，不混淆数据来源与质量。

### 3.2 能力"幻觉"防控

- **skill_dict 约束抽取（D31）**：285 个 canonical 技能词表为全局唯一技能词典；M2 大模型抽取候选技能必须映射到词典内，未命中进入 `unknown_skills` 队列，禁止自由生成技能名；
- **证据链**：`job_skill.skills[]` 每条技能带 `evidence`（JD 原文引用）+ `confidence` + `is_required`，答辩可逐条溯源；
- **双模型交叉验证**：M2 L5 阶段用 qwen3.7-plus ∥ mimo-v2.5-pro 独立核查每条技能证据：双证通过标 `verified`，单证存疑降置信度 0.15 标 `suspicious`，双证失败直接删除（幻觉过滤）；
- **known limitation（如实说明）**：当前 470 条岗位数据的技能 canonical 命中率约 4%（required 107/2739、bonus 65/756），大量技能名未归一，M2 正在补发按词典约束重跑的数据；图谱构建器因此跳过 4,426 个未归一技能，当前技能节点 118 个。

### 3.3 新岗位发现与定义

技术路线：`JD 聚类（技能组合特征）→ 与既有 job_definition 比对 → 大模型候选生成 → 人工确认`。

- `is_emerging` 字段标记新岗位（当前 470 岗位中 119 个 is_emerging=1，2026-08-31 实测）；
- 岗位定义五要素：岗位名称、核心职责、必备技能、加分技能、典型行业应用场景 + 收集时间/来源/质量分；
- 示例：**Data Architect**（is_emerging=true，stage=growth，skill_novelty=high，由 4 条 JD 聚合），详见 `02-测试数据/岗位图谱示例/`。

### 3.4 既有岗位能力动态更新

- 多轮采集时间序列对比（differ 指纹对比：内容未变跳过、新岗位进管道、下架岗位记变更日志）；
- 变更类型枚举：`added / removed / modified / duties_changed / scenarios_added / scenarios_removed / evolution_changed`，全部记录数据源（evidence 原文）与说明；
- 审计追踪：`job_change_log` 表记录每次变更；
- 演化阶段：`evolution.stage` 分萌芽/增长/成熟/衰退（P0 静态分类基于技能组合特征，不编造数字）；
- 示例：**Senior PHP Developer**（stage=mature，由 3 条 JD 聚合），详见 `02-测试数据/岗位图谱示例/`。
- **known limitation（如实说明）**：`job_change_log` 当前 0 条（M2 新包未交付变更日志），动态更新机制已实现、待 M2 增量数据验证。

### 3.5 新一代信息技术岗位全景图谱（技能点级粒度）

- 本体：岗位（Job）—技能（Skill），关系 REQUIRES（weight + is_required）+ RELATED_TO（岗位相似度）；
- 存储：Neo4j 5（Docker 命名卷持久化），当前 **588 节点（470 Job + 118 Skill）/ 3,998 条关系（REQUIRES 1,012 + RELATED_TO 2,986）**（2026-08-31 实测）；
- `graph.json` 为可追溯交接产物（588 节点/4,003 边，Neo4j MERGE 去重 5 条重复关系）；
- 可视化：前端 GraphPanorama 支持力导向、树状、环形、桑基、星云五种视图，可按技术栈/级别筛选；
- **known limitation（如实说明）**：当前无 industry 节点、无 Skill–Skill 关系；节点中文名 `name_zh` 为空（待 M2 翻译数据）；RELATED_TO 全为 Job–Job。

### 3.6 简历解析与人岗匹配

- 简历解析：PDF / DOC / DOCX / TXT，`pdfplumber / python-docx / mammoth`，个人信息/教育/经历/技能提取；
- 技能提取：500+ 技能关键词库 + 同义词映射 + skill_dict canonical 归一（D31）；
- 匹配：`quick_match` 加权规则（编程语言 1.5x、后端框架 1.3x、数据库 1.2x），输出 score/matched/missing/strengths/target_job；
- 目标岗位协议：`POST /api/resume/upload` 支持 `target_job_id`，按用户选择岗位匹配（2026-08-31 已闭环）；
- 差距分析：missing 技能缺口（level/tip）；
- 学习路径：**待 M4 pathfinder 回包**（missing→level/tip+路径），前端 Learning 页已就绪等待真实接口。

---

## 4. 系统实现

### 4.1 后端（FastAPI，20 个统一接口）

| 模块 | 接口 |
|---|---|
| 看板 | overview / trend / skill-distribution / skill-radar / industry-tracks |
| 岗位 | 列表 / 详情 / 新增 / 编辑 / 删除 / 批量删除 / 导入 / 导出 |
| 简历 | upload（含 target_job_id）/ skill-dimensions / target-jobs |
| 图谱 | data / jobs / years / skill-radar |

统一响应 `{code:0, message, data}`；字段 snake_case；写操作（岗位 CRUD/导入/批量删除）已由前端真实调用（2026-08-31 完成）。

### 4.2 前端（Vue3，6 页面）

Dashboard（真实统计/趋势/技能分布）、Jobs（列表 + 写操作闭环）、Graph（Neo4j 真实数据五种视图）、Resume（上传解析 + 目标岗位匹配 + 雷达）、ResumeDemo（最近解析结果预览/导出 PDF）、Learning（学习路径，待 M4）。

技术栈：Vue 3.5 + TypeScript + Vite 4.5 + Element Plus + ECharts + AntV G6 + Pinia + Axios。

### 4.3 数据契约

- `backend/app/contracts/ddl.sql` 冻结 8 表：jd_pool / signal / talent_raw / skill_dict / job_definition / job_skill / job_change_log / resume；
- 加字段自由，改/删字段须全队通知；技能 canonical 全局唯一（285 词表）。

---

## 5. 测试与验证（对应评分"实用价值"30 分）

### 5.1 单元测试

- 后端：**224 通过 / 5 失败**（2026-08-31 全量实测；5 个失败为 M2 新旧数据语义差异，待 M2 新回包修复，不属集成缺陷）；
- M2 管道覆盖率：**71.4%**（2382/3336 行，coverage 报告见 `exchange/m2/test-coverage-71.4.json`）；
- 前端：`pnpm run build`（含 vue-tsc 类型检查）通过。

### 5.2 测试数据（≥100 条 JD 测试集）

- `100条JD测试集.json`：100 条 JD（jd_id/job_title/管道判定/预期技能字段），已抽样、**待人工标注**（见 `02-测试数据/`）；
- **诚实说明**：JD 解析准确率、简历提取准确率、匹配准确率三项均需人工标注测试集后出具报告，当前未编造数字。

### 5.3 数据安全（D37）

集成测试写库数据按测试夹具特征精确清理（finally/teardown），禁止按 source 宽泛删除；每次测试后查库验证夹具计数为 0、生产数据未误删（曾误删 5000 条 jd_pool，已修复并形成陷阱记录）。

---

## 6. 完整性与当前缺口（对应评分"完整性"30 分）

| 环节 | 状态 |
|---|---|
| 多源数据采集 → 清洗 → 交叉验证 | ✅ 128,625 条全 cleaned、885 对交叉验证 |
| 新岗位发现与定义 | ✅ 470 定义、119 新岗位标记、Data Architect 案例 |
| 既有岗位能力动态更新 | 🟡 机制就绪（differ/change_log/evolution），变更日志数据待 M2 增量 |
| 能力图谱动态（Neo4j） | ✅ 588 节点/3,998 边，五种视图 |
| 简历解析 → 匹配 → 差距分析 | 🟡 解析与匹配可用，pathfinder/学习路径待 M4 回包 |
| 系统可部署运行 | ✅ docker-compose 一键启动，后端 18000/前端 18080 |
| 技能 canonical 归一 | 🟡 命中率约 4%，待 M2 按词典重跑 |
| 中文展示（job_name_zh） | 🟡 待 M2 翻译数据 |

---

## 7. 后续计划

1. **M2 回包**：翻译后岗位数据（job_name_zh）+ canonical 归一 + 变更日志 → 中文展示恢复、图谱重建、动态更新验证；
2. **M4 回包**：pathfinder 实现 → 学习路径页接真实数据；resume 落库；≥30 份简历标注测试集与准确率报告；
3. **测试集标注**：100 条 JD 人工标注，出具三项准确率报告（目标 ≥90%）；
4. **材料补齐**：PPT 作品介绍、≤10 分钟演示视频（含新岗位 + 既有岗位图谱演示）、部署说明完善、覆盖率截图；
5. **提交打包**：按"单位—姓名—作品名称—电话"命名压缩包，上传云盘并提交邮箱（截止 2026-09-05）。

---

## 附：关键指标速查（2026-08-31 实测）

- jd_pool 128,625 条（linkedin 123,849 / hn 1,793 / boss 1,131 / zhaopin 1,088 / liepin 764）
- signal 1,493 条（github 354 / blog 1,139，时间 08-17 ~ 08-28）
- cross_source 885 对；skill_dict 285 词表
- job_definition 470（is_emerging 119）/ job_skill 470（证据链）
- Neo4j 588 节点 / 3,998 边；API 20 个；前端 6 页
- 后端测试 224 通过 / 5 失败；M2 覆盖率 71.4%
- 部署：docker-compose（MySQL/Neo4j/Redis），后端 18000 / 前端 18080

# TalentMind 模块联合情况核对 + 前端整合方案

- 日期：2026-08-31
- 角色：A（唯一集成者）复核 + 整合方案
- 依据：AGENT_START_HERE.md / A_AGENT_HANDOVER.md / 资产与状态.md / 决策跟踪.md / ddl.sql / 2026-08-30 各审计清单；`input/` 四份队员回包与正式 `backend/app/`、`frontend/` 逐一核对
- 范围：核对 M1–M5 与 A 后端的联合情况；重点解决「实际产品（frontend/）与前端开发者原包（input/岗位能力图谱前端系统/）不一致」；给出完整整合方案（含是否全部重新整合的裁决建议）

---

## 一、各模块联合情况核对（实测证据）

> 数据核验于 2026-08-31 执行：exchange/m2、exchange/m3、MySQL/Neo4j、后端路由、前端源码与构建。

### M1 数据采集（A 自持）—— 正常，非本次重点
- 位置 `backend/app/collect/`；多平台低速循环持续运行（LinkedIn/HN/BOSS/智联/猎聘）。
- 2026-08-30 记录 `jd_pool=128625`，全部 cleaned；`signal` 多源累计；本次未改任何 M1 逻辑。

### M2 岗位分析（回包 `input/M2交付包/`）—— 已迁入，但数据质量 4 项未达标
| 项 | 实测 | 结论 |
|---|---|---|
| 文件/库内数量 | job_definition=470、job_skill=470（交接说明声称 488） | 数量差异待 M2 澄清 |
| 关联 | job_skill.job_name == job_definition.job_name = 470/470 | **P5 关联已解决**（旧 3/22 断裂已修复） |
| job_name_zh | 0/470 条含该字段 | 违反中英文统一（L2），且导致 API 中文名失效（见 A-P0） |
| 技能 canonical | required 107/2739、bonus 65/756、job_skill 111/3269 ∈ 285 词典 | **严重违反 D31 反幻觉**：约 96% 技能未归一，直接污染图谱与匹配 |
| job_change_log | 0 条 | 演化/动态更新无数据 |

### M3 图谱（回包 `input/图谱模块/`）—— 未直接导入旧快照，A 已用新 M2 重建
- `input/图谱模块/graph.py` 的 812 节点旧快照（旧 code、独立路径、vis.js 静态页）未入库（符合 2026-08-30 交接红线）。
- 正式重建：`backend/app/graph/builder.py` → `exchange/m3/graph.json` 588 节点/4003 边 → Neo4j 588/3998（MERGE 去重 5 条重复关系）。
- 问题：graph.json 节点字段为 `type`（非契约 `kind`）、`name_zh` 全部为空（0/588）、无 Skill–Skill RELATED_TO、行业/赛道映射缺失。

### M4 人岗匹配（回包 `input/人岗匹配/`）—— 核心能力已迁入，pathfinder 未实现
- 已迁入 `backend/app/matching/`（file_parser/resume_parser/job_parser/matcher/skill_extractor/generate_test_data + canonical 归一，D31）。
- 未完成：pathfinder（missing→level/tip+路径）；中文紧邻英文抽取（`熟悉Python`）；resume 落库（resume=0）；≥30 份标注测试集 + ≥90% 准确率报告；target_job 参与匹配协议未闭环。
- `input/人岗匹配/岗位测试用例/` 含真实简历，按 D36 保留、禁止迁移/删除。

### M5 前端（回包 `input/岗位能力图谱前端系统/` vs 正式 `frontend/`）—— 差异是本次核心，详见第二节
### A 后端（`backend/app/routers/mvp.py`，20 接口）—— 半数可用、半数占位/断裂
| 接口组 | 状态（2026-08-30/31 实测） |
|---|---|
| /api/jobs 列表/详情/写操作 | 列表/详情真实（470）；写操作后端已实现但前端未调用 |
| /api/graph/* | data 真实（588/3998），但 focus/year 参数未实现；skill-radar 空 |
| /api/resume/* | upload 真实（422 已修）；target-jobs 真实；skill-dimensions 空 |
| /api/dashboard/* | overview 真实（470）；trend 空；skill-distribution 真实；skill-radar 占位全 50；industry-tracks 静态 |
| 中文名 | **`_load_zh_map` 因旧 zh 22 条 vs 新 en 470 条长度不等而失效 → API/图谱岗位名全部回退英文** |
| 测试 | 223 passed / 6 failed（5 个 M2 新旧语义差异 + 1 个采集集成测试查询未限定 source/夹具） |

---

## 二、前端差异分析（实际产品 vs 前端开发者原包）

### 2.1 开发者原包（`input/岗位能力图谱前端系统/`）实际包含
- 路由 11 条：/jobs、/graph-collection、/learning、/resume、/resume-demo、/collection、/evolution、/analytics、/challenge-cup-test、/nebula-test、/nebula-test-page
- 页面：Jobs、GraphCollection（采集图谱）、Learning、Resume、ResumeDemo、**Collection（BOSS 采集控制台）**、**JobEvolution（能力动态更新）**、**Analytics（数据分析）** + 3 个测试页
- API 层：dashboard/jobs/resume/graph + **collection（10 端）、evolution（约 12 端）、learning（3 端）、jd-filter（9 端）、challenge-cup（静态加载）**
- Mock 体系：USE_MOCK 开关、mock-server.cjs、src/data/mock.ts（46KB）、src/mock/*
- 组件：AbilityRadar/GraphPanorama/LearningRoadmap/PageDecorations/ResumeDiagnosis/**ResumeMatching**
- 工具：resumeParser.ts、algorithms/data-loader.ts、nebula-layout.ts

### 2.2 正式整合版（`frontend/`）实际包含
- 路由 6 条：/dashboard、/jobs、/graph、/resume、/resume-demo、/learning
- 页面：**Dashboard（A 新建，原包没有）**、Jobs、Graph（A 改写的包裹页）、Resume、ResumeDemo、Learning（空态）
- API 层：仅 20 接口对应的 dashboard/jobs/resume/graph
- 无 mock（按 D20/D29 移除）；无 Collection/Evolution/Analytics/GraphCollection；无 ResumeMatching/PageDecorations
- 待修运行时问题：ResumeDiagnosis 中 `MagicStick` 未 import；AbilityRadar 空 dimensions 初始化 ECharts 崩溃（2026-08-30 交接，未修）

### 2.3 差异根因
1. A 按 20 接口契约裁剪了页面，删掉了契约里没有的 Evolution/Collection/Analytics/GraphCollection；这些页面依赖的 `/api/evolution/*`、`/api/collection/*`、`/api/learning/*`、`/api/jd-filter/*` 后端从未实现。
2. A 新建 Dashboard 并把图谱页改名 /graph，造成「实际产品」与开发者记忆中的页面结构不同。
3. 移除 mock 后，Learning/ResumeDemo/雷达/趋势失去数据源，变成空态（诚实降级，但视觉上与开发者的完整页面差距很大）。
4. 竞赛需求 2「既有岗位能力动态更新」对应的 Evolution 页面被裁掉，需求覆盖出现缺口。

---

## 三、整合方案（裁决建议：采用「补齐整合」，不推倒重来；另附全量重做预案）

### 3.0 先裁决 4 个决策点（用户/全队拍板）
| # | 决策点 | 建议 |
|---|---|---|
| D-A | 目标页面集：6 页 vs 9 页 | **9 页**（恢复 Evolution；Collection/Analytics 视人力，至少 Evolution 必须，对应竞赛需求 2） |
| D-B | M2 中文名与 canonical 谁补 | **M2 补 job_name_zh + 按 skill_dict 约束重跑 canonical**；A 侧仅做展示映射兜底 |
| D-C | Learning/Evolution 数据源 | 依赖 M4 pathfinder / M2 job_change_log；未就绪前保持诚实空态，不 mock |
| D-D | Collection 页 | 建议做「只读控制台」：A 侧采集状态资产现成（boss_collect_loop/check_collect_status），包一层只读 API 成本低、答辩加分 |

### 3.1 为什么不全量重做
- 现有 `frontend/` 已：接入 20 个真实 API、通过 `pnpm run build`（今日实测）、修复上传 422、清理演示数据；删掉 mock 符合契约。
- M5 原包大量页面（Collection/Evolution/Analytics/jd-filter）依赖**不存在**的后端接口，推倒重来只会原样带回「页面有、后端无」问题，并丢失 A 已完成的接线与修复。
- 因此「全部重新整合」只保留为 3.6 预案：仅当用户希望以 M5 原包视觉为唯一基线、并接受后端同步新增 4 组接口时才选择。

### 3.2 阶段 1：后端补齐（A 侧，先行，约 2–3 天）
1. **中文名闭环**：M2 补 `job_name_zh`（或 A 建立 470 条映射表）→ `import_exchange` 落库 → mvp.py 删除按序 zip 过渡逻辑，优先读库内 zh；M3 重建时写 `name_zh` 到 graph.json 与 Neo4j。
2. **图谱契约对齐**：graph.json 节点统一 `kind`（type→kind 转换已在 API 层做，改为 builder 直接输出契约字段）；重建图谱写入 name_zh；定义 focus_job/year 参数语义并实现（或明确 400/空结果）。
3. **Dashboard 真实化**：trend 用 `job_definition.collected_at`（或 signal.captured_at）聚合真实时序；skill-radar 无数据返回 `data:null`+message（删全 50 占位）；industry-tracks 文档标注为展示映射。
4. **Resume 协议闭环**：upload 接收 `target_job_id`（或新增按岗位匹配接口）；skill-dimensions 从 job_skill 聚合真实维度；解析结果落库 resume 表。
5. **Learning 接口**：定义并实现 `POST /api/learning/generate-path`、`GET /api/learning/jobs`、`GET /api/learning/job-skills/{id}`（依赖 M4 pathfinder；先返回空态契约）。
6. **（D-D=是时）Collection 只读接口**：`GET /api/collection/status|stats|database-stats|cdp-status|history`（只读，包装现有采集状态资产，不暴露写）。
7. **DTO 冻结**：全部 snake_case；前端 request 层统一转换；API 文档与实测 JSON 一致。
8. **修复 6 个失败测试**：5 个 M2 语义差异→按新契约更新旧测试；1 个采集集成测试→查询限定 source/夹具标识。

### 3.3 阶段 2：前端补齐（以现有 frontend/ 为基线，约 2–3 天）
1. **先修阻塞**：MagicStick import；AbilityRadar 空 dimensions 只显示空态、不初始化 ECharts（沿用 2026-08-30 交接顺序）。
2. Resume：目标岗位传 `target_job_id`；雷达接真实维度；上传校验统一（大小/扩展名/MIME）；ResumeDemo 接 Pinia 最近解析结果。
3. Jobs：写操作真实调用 create/update/delete/batch-delete/import/export，带 loading/失败提示；详情走 /jobs/{id}。
4. Dashboard：数字/趋势/技能分布/珊瑚块全部来自 API；空数据显示「暂无」。
5. Learning：接真实 generate-path；未就绪保持空态。
6. Graph：focus/year 下拉加载接口数据；导出真实 JSON/PNG；默认视图节点密度控制（Top N/仅关联）。
7. **恢复 Evolution 页**（能力动态更新，竞赛需求 2）：数据源 = job_change_log + job_definition.evolution；0 条时诚实空态；审核流暂缓。
8. **（D-D=是时）恢复 Collection 页**：只读展示任务状态/CDP/库统计/历史，调用阶段 1 的只读接口；启动/停止按钮禁用并标注「需 M1 控制端」。
9. 清理过时文档（readme.txt 的 Mock 开关说明）；补充 404 路由。

### 3.4 阶段 3：M2/M3/M4 数据与模块侧（并行）
- M2：补 job_name_zh；技能 canonical 化（按 285 词典归一，至少把 3269 个技能名映射回词典/unknown 队列）；澄清 470/488；输出 job_change_log。
- M3：基于修复后 M2 重建（name_zh、kind、去重、可选 Skill–Skill）；Neo4j 换图前先清空（工程经验 #7）。
- M4：实现 pathfinder（missing→level/tip+path）；修复中文紧邻英文抽取；≥30 份标注测试集+准确率报告；target_job 协议闭环；resume 落库。

### 3.5 阶段 4：端到端验收（4 关门禁，每轮必过）
1. schema 校验（validate_exchange，change_type 枚举硬校验）
2. 模块单测 + 集成测试（223+ 基线，新增用例按 D37 精确清理夹具，跑完查库计数=0）
3. 前端 `pnpm run build`（vue-tsc）+ 六/九页逐页浏览器验收
4. 真实数据冒烟：/api/jobs=470、/api/graph/data=588/3998、上传→雷达→学习路径全链路
完成后同步 `docs/superpowers/资产与状态.md`、`决策跟踪.md`、README。

### 3.6 预案：如果决定「全部重新整合」
- 步骤：① 冻结 20+新增接口契约与 DTO；② 以 M5 原包 src/ 为基线整目录迁回 frontend/（保留 request.ts 统一响应 code=0 与 /api 代理）；③ 逐页接线：Jobs/Graph/Resume/Dashboard 用现有 20 接口，Evolution/Collection/Analytics/Learning 用阶段 1 新增接口；④ 删除 mock 引用与测试页；⑤ 保留 A 已修复的 422 适配、vue-tsc 构建、演示数据清理成果（手工合并，不能用原包覆盖）。
- 成本：约多 1–2 天，且必须并行完成 3.2 的新接口，否则恢复的页面仍是空壳。
- 风险：原包 LearningRoadmap/Resume 等与后端 DTO 字段不同，需逐字段对齐；可能重新引入 mock 依赖。

---

## 四、需要用户/全队确认的清单
1. 3.0 四个决策点（页面集 / M2 中文名与 canonical / Learning 数据源 / Collection 页）。
2. M2 470 vs 488、canonical 4% 命中是否由 M2 下轮修复（A 不静默改写模块逻辑，红线）。
3. Learning 在 M4 pathfinder 未完成前保持空态（不恢复 mock）是否可接受。
4. 本方案是否纳入 `docs/superpowers/plans/` 并同步决策跟踪（加 D-A~D-D 记录）。

---

## 附：今日核验命令与结果
- 前端：`cd frontend; pnpm run build` → 通过（仅 chunk>500kB 警告）
- 数据：job_definition=470 / job_skill=470 / job_name_zh=0 / canonical 命中 required 107·bonus 65·job_skill 111；graph.json 588 节点/4003 边，`type` 非 `kind`、name_zh=0；后端路由 20 条，无 /api/collection、/api/evolution、/api/learning、/api/jd-filter
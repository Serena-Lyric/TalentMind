# A 角色开发路线与交接文档（给下一个接手 A 工作的 Agent）

> **2026-10-26 当前维护入口：** 正式开发仅master；V1使用标签 `competition-v1-2026-09-05` 和[Release](https://github.com/Serena-Lyric/TalentMind/releases/tag/competition-v1-2026-09-05)。M1旧阶段事实与恢复见[正式历史](docs/superpowers/archive/2026-10-22-M1-collection-validation-and-recovery.md)，本文件下方冻结交接按当时时点理解。

> **2026-10-15 入口更新（D61/D62）**：当前产品方案见 [PRODUCT_DECISIONS.md](docs/PRODUCT_DECISIONS.md)，通用规则与 GitHub 流程见 [AGENTS.md](AGENTS.md)，阅读范围按 [AGENT_START_HERE.md](AGENT_START_HERE.md) 选择。本文件是 A 角色相关任务的补充交接，历史操作步骤不自动授权采集、迁移或清理；核心阅读不再要求逐文件复述。M1 第二阶段已合并，证据见 [PR #1](https://github.com/Serena-Lyric/TalentMind/pull/1)。


> **第二轮保全交接（2026-10-14，最新）**：审查资料及工具已入 master（`65a6b01`）；V1 归档不变。私有备份最终为 `D:\backup\TalentMind-2026-10-14` 内 9 文件约 0.967 GB，两版 SQL + Neo4j dump + 800 路径/729 对象的去重私有包及清单；旧整盘/冷卷/镜像/依赖和重复目录已移除，原工作区私有资料和 Docker 数据未改动。先读 `docs/GitHub资产补全与备份精简报告-2026-10-14.md` 与精简版 `docs/V1恢复手册.md`。下方第一轮备份清单是历史记录。

> **2026-10-14 冻结交接**：V1 已归档到 `archive/competition-v1`（`4a473c2f8ee6b814acd6ed97a670563ece0f3ae0`），本轮未修改业务或原数据库。`D:\backup\TalentMind-2026-10-14` 已保全并实际恢复核验；离机私有副本仍未完成。当前冷卷 JD=2988（BOSS 多 4 条），竞赛 SQL=2984，两版均保留。接手先读 `docs/仓库冻结与资产保全报告-2026-10-14.md` 和 `docs/V1恢复手册.md`；下方 09 月统计为带日期的历史/竞赛基线，不作为本机原始层实时值。

> **2026-09-05 演示提交基线（历史快照）**：演示口径数据已全量对齐。MySQL `job_definition/job_skill/job_change_log=717/717/275`（新一代 342 / 现有 375；已删除 AI 测试开发工程师与博士后共 2 条，含 32 条演示日志；job_id NULL=3）；原始层 `jd_pool=2984`（BOSS 1133/智联 1088/猎聘 763）、`signal=1540`、`resume=0`；Neo4j=**7845 节点/11412 关系**（Job 717/Skill 4671/Industry 2457；REQUIRES 8866/APPLIES_TO 2539/RELATED_TO 7），与 `exchange/m3/graph.json` 一致；后端全量测试 **246 passed**（Python 3.14.5）。完整交接见 `docs/superpowers/archive/2026-09-05/2026-09-05-提交基线对齐与部署交接.md`，部署/导入见 `docs/部署与导入说明.md`。

> **陷阱提醒（2026-09-05）**：`import_all()`/`import_change_logs()` 默认读取 `input/岗位数据-新一代与现有/`（719/243 原回包），直接运行会覆盖 717/275 演示库；从提交物复现请按 `docs/部署与导入说明.md`（SQL 快照或对 `exchange/m2` 显式路径导入）。历史默认导入测试会重建分析层为 719/243；集成测试须指向隔离库，禁止以演示库运行后再恢复的方式测试。

> **2026-09-04 复核校正（历史快照）**：MySQL 分析层 `job_definition/job_skill/job_change_log=717/717/275`（719 导入后 09-04 删除 AI 测试开发工程师与博士后(61322) 共 2 条定义+技能、新增 32 条演示变更日志）；Neo4j 7852 节点/11423 关系不变；原始层 `jd_pool=2984 cleaned`（BOSS 1133/智联 1088/猎聘 763，HN/LinkedIn 原始 JD 已按 D55 外部归档、主库为 0），signal=1540。**每日计划任务 `TalentMindCollect` 已加暂停开关**（存在 `data/local/PAUSE_COLLECT` 即退出；恢复=删标记+还原 `scripts/collect_daily.ps1`，硬停需管理员执行 `schtasks /Change /TN TalentMindCollect /Disable`）。库/图实时数字以 `docs/superpowers/资产与状态.md` 为准；下文 2026-09-02 增补及其余带日期阶段块均为历史快照。
> **2026-09-04 会话收尾交接（本轮 Agent）**：详见 `output/文档整合-2026-09-03/01-总览/01-工作交接-2026-09-04.md`（会话级交接）与 `docs/superpowers/archive/2026-09-04/2026-09-04-文档核验与勘误报告.md`。要点：MySQL 分析层 717/717/275（删除 AI 测试开发工程师与博士后 61322）、原始层 jd_pool=2984/HN=0；每日采集任务已加 PAUSE_COLLECT 暂停开关；学习路径已实现针对性建议与分层路径；简历解析新增 项目/荣誉/自我评价（docx 支持表格）；未建任何 commit。

> **2026-09-02 M2 完整回包接入增补**：用户明确选择完整导入 `input/岗位数据-新一代与现有/`，D56 覆盖 D55 的英文结构化目录不入主库限制。当前 MySQL `job_definition/job_skill/job_change_log=719/719/243`，其中 3 条无法关联的岗位级变更日志保留原始 `m2_job_id`；Neo4j 已重建为 7852 节点/11423 关系。`exchange/m2/` 已同步完整数组交接文件。采集历史任务已兼容旧 UTF-8/GBK 日志，控制台支持 BOSS/智联/猎聘；简历页移除手动目标岗，推荐至少 3 张且展示分至少 90，学习路径由点击的推荐岗位 ID 驱动。
> **2026-09-02 文档交接审计（补录）**：此前「前端重整 5/5」与「M2 完整导入」两个 Agent 均只各自同步了部分文档、未做正式交接；本次已对照真实库/图（MySQL 719/719/243、Neo4j 7852/11423）核对并合并文档状态。**当时状态以 2026-09-04 复核校正块为准；当前实现和未决查资产与状态并核对源码/测试**；下文各带日期的阶段块均为历史记录，不再代表当前库/图。

> **前置**：按 `AGENT_START_HERE.md` 完成核心阅读；A 角色任务只读本文件与任务相关章节，无需逐文件复述。
> **角色**：A = M1 数据采集负责人 + 唯一集成者（决策 D2/D3/D4）。你接手的是"系统集成 + 回发闭环验收 + 继续 A 的未完成事项"。

> **2026-09-02 整体修复阶段增补（历史记录）**：本轮完成前端构建门禁和 M2 语义回归修复：`pnpm run build` 通过；后端全量 `232 passed`；`validate_exchange` 通过（仅保留既有 M2 canonical 警告）。英文 JD 已保存到仓库外 `D:\Application\ClaudeCode\repository\TalentMind-external-archives\english-jd-2026-09-01`，当时主库仅保留中文三平台（MySQL `jd_pool=2983`、`job_definition=1973`、`job_skill=1973`，Neo4j=2173 节点/7673 关系）；**该阶段状态已被随后 D56 M2 完整导入覆盖，勿再引用**。采集页进入时自动准备独立 Edge，并以单轮模式尝试启动；当前实测 BOSS 页面需要人工登录，因此未启动采集进程。
> **2026-08-31 交接增补（优先阅读）**：完成必读文档真实性核对与五模块整合核对（报告见 `output/2026-08-31-必读文档真实性核对与五模块整合核对报告.md`）。按用户指示：**采集暂停（数据量已够，暂不采集）**——循环是否在运行由接手 agent 用 `Get-Process` / `Get-NetTCPConnection -LocalPort 9333` 自行检查，**不要臆测 PID 仍在运行**；**M2 将补发翻译后岗位数据、M4 将补发含 pathfinder 的回包**，收到后再完成中文名落库与 Learning 接入；页面集已按方案 A 重整为当前 `frontend/` 9 个正式业务页面。联调端口定案：后端 `18000`、前端 `18080`（`vite.config.ts` 已默认代理 `/api`→18000，可用 `VITE_PROXY_TARGET` 覆盖）。当前已知状态：上述是历史记录；本轮已按 D56 完整导入 719 个 M2 岗位，英文来源随回包进入主库。
>
> **2026-08-31 前端重整增补**：用户确认采用方案 A，已按 `input/图谱.png` 与 `input/采集模块管理.png` 重新整合 `frontend/`，不再做补丁式页面拼接。正式导航现含 9 个业务页面；Career Nebula 使用真实 `/api/graph/data`；Collection 通过 `backend/app/collect/control.py` 包装既有 M1 循环，进入页自动准备 Edge，已登录才尝试单轮采集；新增 `/api/collection/*`、`/api/evolution/*` 路由。前端构建通过，浏览器逐页冒烟通过；后端全量结果为 226 通过/5 失败，失败均为既有 M2 语义差异。

> **2026-08-30 交接增补（历史记录）**：最近已推送基线为 GitHub `8def99d`；当前工作树仍有未提交变更，接手后先 `git status --short --branch`，不得回滚。M2 旧回包当时为 470 条；本轮已按 D56 更新为完整 719 条并重建图谱。当前服务联调端口为后端 `18000`、前端 `18080`。
>
> **已解决/仍待办**：2026-08-31 已修复 `MagicStick` 导入、`AbilityRadar` 空 dimensions 崩溃、Resume 上传 422 和目标岗位传参；当前 `frontend/` 已完成统一壳层与业务页重新整合。Learning 已接入中文岗位技能目录，基于简历内存态生成确定性技能缺口和阶段建议，不恢复 Mock。详见 `docs/superpowers/specs/2026-08-31-frontend-reintegration-design.md`。

## 一、A 按任务选读（通用路线之外）

| 文件 | 作用 |
|---|---|
| `backend/app/integration/validate_exchange.py` | 交接文件 schema 校验器（回包第一关；change_type 枚举硬校验、版本头软提示） |
| `backend/app/integration/import_exchange.py` | M2 交接 → MySQL 导入（**全量重建语义**：M2 产出是权威岗位集合） |
| `backend/app/integration/import_graph.py` | graph.json → Neo4j（MERGE 幂等；换数据先清空） |
| `backend/app/routers/mvp.py` | 原 20 个统一 API（jobs/graph/resume/dashboard）；新增 `routers/collection.py` 与 `routers/evolution.py` 提供采集控制台和能力动态只读 API |
| `backend/app/collect/README.md` | **M1 采集模块文档（数据源矩阵/命令/幂等/合规/监控）** |
| `scripts/collect_daily.ps1` / `check_collect_status.ps1` | 每日采集（SYSTEM 任务）/ 一键监控（任务/日志/数据量） |
| `backend/app/collect/fetch_all.py` | **统一采集入口**（signals + hn + 交叉验证，一键） |
| `backend/app/collect/collect_loop.py` | **持续采集循环**（每 N 小时一轮，--forever；2026-08-31 起暂停采集，接手 agent 自行检查是否在运行） |
| `backend/app/collect/cross_validate.py` | 多源交叉验证（D42：cross_source 标记 + quality 上浮） |
| `docs/superpowers/plans/2026-08-17-multisource-collection-plan.md` | 多源采集计划（P0 信号 ✅ / P1 岗位 ✅ / P2 交叉验证 ✅） |
| `data/local/m2-data-pack/` | **M2 数据包（已发送 M2 开发者）**：jd_pool.sql 全量 + jd.json + skill_dict + signal 快照 + 交叉验证报告 |
| `backend/.env` | 本地配置（MySQL/Neo4j/Redis/LLM 密钥，gitignore 保护，**禁止外传/入库**） |
| `frontend/前后端接口对接文档.md` | 20 接口基线文档 |
| `output/` | 回发包 v3（已发送四位队员；结构见 08-14 roundtrip 方案） |

## 二、历史状态（已归档，详见 `docs/superpowers/历史时间线.md`）

> 历史数据快照与早期运行记录（截至 2026-08-23 / 2026-08-20）已归档至 `docs/superpowers/历史时间线.md` 第三节；当前状态以本文件顶部增补与 `docs/superpowers/资产与状态.md` 为准。

## 三、历史交接清单（2026-08/09；不自动执行）

以下采集重启、导入和清理步骤保留当时上下文；当前接手按顶部 D61/D62 入口与 AGENTS，仅做本次授权范围工作。

> **接手 48h 行动清单**：① 即进入**回包验收期（8/19 M2 → 8/20 M3/M4 → 8/21 M5）**，按下方「队员回包验收」4 关执行；② 确认 `collect_loop` 进程存活（重启命令见第四节）并记录 `check_collect_status.ps1` 基线；③ 若 M2 已用数据包重跑，用新产出重导 `exchange/m2` 并过 `validate_exchange`；④ 全队会议补告知契约变更（change_type/experience/source 语义）；⑤ 每轮采集后确认 signal 时间序列在增长。

### 1. 立即（等队员回包前）
- [ ] 全队会议：正式通知 change_type / experience 扩容 + 中英文统一规则 + 版本 v3 基线 + 错峰时间表（材料见 `笔记.md` 第十一节 + `output/` 各包问题/要求清单）。
- [x] 补填 `exchange/m1/quality_check.md` 抽样 10 条核对结论（2026-08-16 AI 标注 10/10 通过，可人工复核）。
- [ ] 熟悉验收工具链：`validate_exchange.py`、`import_exchange.py`、`import_graph.py`、测试命令（`cd backend && .\.venv\Scripts\python.exe -m pytest -q`）。
- [x] **持续采集监控**：`powershell -File scripts\check_collect_status.ps1`（已验证；8/19 循环第 5 轮、signal 3 天）；确认 `collect_loop` 进程存活（重启：见第四节）。

### 2. 队员回包验收（4 关门禁，见 08-14 roundtrip 方案 Step 5）
1. **schema 校验**：`validate_exchange`（字段/类型/枚举/关联/版本头）；
2. **diff 检查**：A 修改文件未被回滚（M2 `stage3_extract.py` canonical 约束、M2 翻译稳定 key、M4 `matcher.py` canonical 化、前端 request/vite 配置、`job_analysis/db.py` 解析器修复等）；
3. **单测/集成**：队员测试结果 + A 机复验（最新全量 236 passed）；
4. **导入 + 前端冒烟**：import_exchange/import_graph → MySQL/Neo4j → `/api` → 前端页面。

### 3. 队员回包后的跟进
- [ ] **M2 回包后重生成数据快照**（`output/` 各包 `依赖数据快照/快照说明.md`：snapshot_version+1）同步 M3/M4/M5；
- [x] 当前中文三平台桥接目录已重跑 M3 builder（`exchange/m2` 语义不回灌英文），清空重导 Neo4j；
- [x] M2 完整回包已增加 `job_name_zh/name_en/category`，API/图谱已切换到完整中文/英文展示字段；
- [x] 当前主库 `job_skill↔job_definition=719/719` 已按 M2 `job_id` 对齐；`job_change_log=243`，其中 3 条 orphan 记录保留原始 `m2_job_id`。

### 4. 未完成事项（P1 / 收尾）
- [x] signal 时间序列 3 天达成：**M2 数据包 2026-08-19-1 版已生成**（signal 253 条/3 天）；后续更新参考 `data/local/gen_pack3.py` 逻辑。
- [x] 阶段 7 当前系统修复收口：外部归档、中文目录重建、前端/后端门禁与浏览器冒烟已完成；
- [ ] 阶段 7 清理：`input/` 下原始对照包（`图谱模块/`、`岗位能力图谱前端系统/`、`人岗匹配/`；旧 `jd-filter-package/` 已于 2026-08-30 删除）（**`input/人岗匹配/岗位测试用例/*.pdf/docx` 真实简历删除前先列清单与用户确认**，D36）；
- [ ] 部署说明与演示材料（P3）；P1 项（见 `笔记.md` 第七节）：M2 is_emerging 复核与 100 JD 测试集；M3 Skill–Skill；resume 落库；P6 中文平台合规方案（用户确认后续再议）。

## 四、操作手册（A 常用命令）

采集、全量导入和图谱重导均为会写入数据的显式操作，需符合当前授权；下列命令是入口参考，不是要求接手时运行。当前图谱应复用已核验的 graph.json，旧 builder 不能复现 Industry 节点。

```powershell
# 启动基础设施
docker compose up -d

# 启动后端 / 前端（两个终端）
# 统一端口：后端 18000、前端 18080（8000/5173 受本机 Windows WSAEACCES 限制）。
cd backend; .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 18000
cd frontend; pnpm exec vite --host 127.0.0.1 --port 18080
# vite.config.ts 已内置 /api 代理默认指向 http://127.0.0.1:18000（可用 VITE_PROXY_TARGET 覆盖），无需再维护审计临时配置。

# 默认离线回归；集成测试另配隔离服务，禁止指向演示库
cd backend; .\.venv\Scripts\python.exe -m pytest -m "not integration" -q

# ★ 采集（D39–D44）
cd backend
.\.venv\Scripts\python.exe -m app.collect.fetch_all                 # 一键：信号+hn+交叉验证
.\.venv\Scripts\python.exe -m app.collect.collect_loop --hours 6 --forever   # 持续采集循环（后台用 Start-Process -WindowStyle Hidden）
.\.venv\Scripts\python.exe -m app.collect.fetch_hn_jobs --months 5  # 扩充 HN 历史月份
.\.venv\Scripts\python.exe -m app.collect.cross_validate            # 多源交叉验证（--dry-run 只分析）
powershell -File ..\scripts\check_collect_status.ps1                # 监控：任务/日志/数据量

# 交接校验（回包第一关）
cd backend; .\.venv\Scripts\python.exe -m app.integration.validate_exchange

# M2 交接 → MySQL（全量重建）
cd backend; .\.venv\Scripts\python.exe -c "from app.integration.import_exchange import import_all; print(import_all())"

# graph.json → Neo4j（换数据先清空再导）
cd backend; .\.venv\Scripts\python.exe -c "from app.integration.import_graph import import_graph; print(import_graph())"

# 重建图谱（基于 exchange/m2 产出）
cd backend; .\.venv\Scripts\python.exe -c "from app.graph import builder as b; b.DATA_SOURCE_PRIORITY=['m2']; print(b.build_graph())"

# M2 管道重跑（需 backend/.env 配 LLM_API_KEY；输入用 M2 数据包的 jd_pool.sql 或 jd.json）
cd backend; .\.venv\Scripts\python.exe -m app.job_analysis.main <输入SQL/JSON路径>

# 前端构建（含 vue-tsc 类型检查）
cd frontend; pnpm run build
```

## 五、红线（不可违反）

1. **禁止 `git add -A`**：`input/` 含真实简历、`output/` 含打包物、`backend/.env` 含密钥、`data/local/` 含大型 SQL/数据包；只 add 明确文件。
2. **D57 中转站边界**：`input/`、`output/`（含 Markdown 审计/交接清单）与 `docs/submit`、`docs/前端卡通图片`、`docs/originalfile`、`笔记.md`、`data/local`、`.superpowers` 均不入库、不同步 GitHub（本地保留，配 README 清单溯源）；只 add 明确文件，禁止 `git add -A`。
3. **契约变更先通知**：改/删字段须全队通知（D32/D33/P4 已执行，通知随会议）；加字段自由但须同步 `validate_exchange` 与文档（D38 source_detail、D42 cross_source、D39 signal.source 均已记录）。
4. **不臆测**：不确定先查资产清单/决策跟踪/笔记；仍不确定问用户。
5. **测试门禁**：按 AGENTS 和改动范围运行相关测试/构建；集成测试只能使用隔离环境，历史通过数不代表本轮验证。纯文档维护检查内容、链接、格式和范围。
6. **测试数据清理（D37）**：集成测试写库数据必须按测试夹具特征精确清理（finally/teardown），禁止按 source 宽泛删除；跑完测试后查询 DB 验证无残留、生产数据未被误删。
7. **幂等与增量（D44）**：`fetch_signals` 追加式（不覆盖历史时间点）；`fetch_hn_jobs` 按帖清理（勿改回"当日先清后写"，会误删历史月份，见 traps/2026-08-17-hn-idempotency-wiped-history.md）；计划任务 Task To Run 必须用 powershell 全路径（SYSTEM 任务相对路径不启动）。



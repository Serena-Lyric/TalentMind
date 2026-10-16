# TalentMind

> **2026-10-14 第二轮保全**：V1 归档仍为 `archive/competition-v1`（`4a473c2f8ee6b814acd6ed97a670563ece0f3ae0`）；master 已补充 [审查资料](docs/archive/competition-v1/README.md)。私有备份 `D:\backup\TalentMind-2026-10-14` 精简为 9 文件约 0.967 GB（两版 SQL、Neo4j dump、去重私有资料与清单），实际释放约 27.207 GB；不再保存整机盘、冷卷、镜像及依赖副本。JD=2984 与 2988 两版均保留，业务逻辑和当前 Docker 数据未改动。见 [第二轮报告](docs/GitHub资产补全与备份精简报告-2026-10-14.md) 和 [恢复手册](docs/V1恢复手册.md)。

TalentMind 是一个契约式单体的人才数据与岗位智能系统。当前仓库承担两个角色：

1. A 负责的 M1 数据获取与清洗开发仓；
2. M1–M5 全部模块集成后的完整系统唯一主仓。

这两个角色共享同一份代码、同一份数据契约和同一套测试入口。不要再建立第二份“采集仓”，也不要在根目录长期维护重复的旧实现。

## 当前状态

2026-10-16 M2 B3-0（Issue #8）：新增显式离线岗位四维断言、原文证据验证与 SQLite 版本/历史重放基础，见 [M2 README](backend/app/job_analysis/README.md) 和 [临时执行报告](docs/review/M2-stage-B3-0.md)。taxonomy 为空或合成示例，全部待审核、正式统计资格关闭；未建立正式职业目录或自动分类器，不启动 B4/真实数据/生产迁移。

2026-10-16 M2 B2 第二轮：新增只读词典审计、严格同义/版本视图、类别与候选治理，以及分离预测/参考/证据检查的离线评测基础；使用与限制见 [M2 README](backend/app/job_analysis/README.md)。正式词典自动准入关闭，Codex 合成参考待人类审核，不作为语义准确率；本轮仅独立 PR 交审，不启动 B3/B4 或生产迁移。

2026-10-16 M2 B2 第一轮：新增离线技能五态、简单组合、陈述级程度与冲突的保守语义扩展，支持持久化、增量复用和恢复；入口与限制见 [M2 README](backend/app/job_analysis/README.md)。仅支持确定性语法子集，未做真实准确率评测，不启用词典准入、后续阶段或正式统计；[PR #6](https://github.com/Serena-Lyric/TalentMind/pull/6) 已完成 ChatGPT 独立静态审查并获用户合并授权，实际状态以 PR 为准。

2026-10-15 M2 阶段 B1：新增显式范围配置的离线 JD 分层筛选与审计，保留无效、范围外、待复核及执行错误，支持版本复用、历史追溯和恢复；使用方式见 [M2 README](backend/app/job_analysis/README.md)。不写技能事实、正式数据库或既有交接，不代表 B2/B3/B4 或正式统计已完成；[PR #5](https://github.com/Serena-Lyric/TalentMind/pull/5) 已审查并合并。

2026-10-15 M2 阶段 A：新增独立 SQLite 事实基础层和显式离线入口，支持完整输入/版本失效、逐 JD 引文核对、增量复用与中断恢复、固定成员重放。见 [M2 运行与测试说明](backend/app/job_analysis/README.md)。当前 CLI 为 Python 字面规则演示；未替换旧管道/交接/API，不代表五态识别、独立职位需求率或模型效果已完成。

2026-10-15 产品归档：当前确认方案以 [PRODUCT_DECISIONS.md](docs/PRODUCT_DECISIONS.md) 为主要依据；本轮 M2 单条事实、技能语义与岗位分层等规则是产品目标，尚未完成新方案实现验收。Agent 从 [AGENT_START_HERE.md](AGENT_START_HERE.md) 按任务选读，GitHub 分阶段提交、ChatGPT 审查及授权合并统一见 [AGENTS.md](AGENTS.md)。

2026-10-15：M1 第二阶段完成离线开发并经过集中审查；记录见 [PR #1](https://github.com/Serena-Lyric/TalentMind/pull/1)。三平台有效 JD v2 已通过离线回归；BOSS 增加逐页列表与逐条详情提交，智联/猎聘中断保护待后续完成。未启动真实采集，未操作正式数据库。

M1 第二阶段只读核对的 Git 交接文件：`exchange/m2` 为 **717 定义 / 717 技能 / 275 日志**，`exchange/m3/graph.json` 为 **7845 节点 / 11412 关系**。这不是本轮实时数据库查询；保全时原始 JD 2988 与竞赛快照 2984 的区别见恢复手册。以下 09 月记录保留历史语境，历史通过数不代表本轮测试。

> **2026-09-05 演示提交基线（历史快照）**：演示口径数据已全量对齐。MySQL `job_definition/job_skill/job_change_log=717/717/275`（新一代 342 / 现有 375；已删除 AI 测试开发工程师与博士后共 2 条，含 32 条演示日志；job_id NULL=3）；原始层 `jd_pool=2984`（BOSS 1133/智联 1088/猎聘 763）、`signal=1540`、`resume=0`；Neo4j=**7845 节点/11412 关系**（Job 717/Skill 4671/Industry 2457；REQUIRES 8866/APPLIES_TO 2539/RELATED_TO 7），与 `exchange/m3/graph.json` 一致；后端全量测试 **246 passed**（Python 3.14.5）。完整交接见 `docs/superpowers/archive/2026-09-05/2026-09-05-提交基线对齐与部署交接.md`，部署/导入见 `docs/部署与导入说明.md`。

> **陷阱提醒（2026-09-05）**：`import_all()`/`import_change_logs()` 默认读取 `input/岗位数据-新一代与现有/`（719/243 原回包），直接运行会覆盖 717/275 演示库；从提交物复现请按 `docs/部署与导入说明.md`（SQL 快照或对 `exchange/m2` 显式路径导入）。历史默认导入测试会重建分析层为 719/243；集成测试须指向隔离库，禁止以演示库运行后再恢复的方式测试。

> **2026-09-02 整合记录（含 09-04 修订，历史快照）**：用户已明确选择完整导入 M2 719 个岗位（新一代 344、现有 375），包含 LinkedIn/HN，覆盖 D55 的旧边界（D56）。MySQL `job_definition/job_skill/job_change_log=717/717/275`（2026-09-04 复核：719 导入后删除 AI 测试开发工程师与博士后(61322) 共 2 条定义+技能、新增 32 条演示变更日志）；Neo4j 为 7852 节点/11423 关系（岗位/技能/行业均已解析）。前端已接入完整岗位目录、历史日志识别、BOSS/智联/猎聘控制、简历自动推荐与绑定学习路径；前端构建和当前回归测试已通过。


- M1 数据采集管道位于 `backend/app/collect/`，继续复用，不重写。
- 当前冻结的数据契约位于 `backend/app/contracts/ddl.sql`。
- FastAPI 后端入口是 `backend/app/main.py`，现有健康检查为 `GET /health`。
- MySQL、Neo4j、Redis 由根目录 `docker-compose.yml` 提供。
- 当前原始对照包保留在 `input/`：`图谱模块/`、`岗位能力图谱前端系统/`、`人岗匹配/`；旧 `input/jd-filter-package/` 已被 2026-08-30 M2 新回包替代并删除。
- 完整资产清单、整合状态与已知限制见 `docs/superpowers/资产与状态.md`（工作前必读）。
- 文档导航：`docs/README.md`（docs 地图）；历史记录：`docs/superpowers/历史时间线.md`；未决问题：`docs/superpowers/未决问题清单.md`。D57 起 `input/`、`output/` 与便利/参赛文件（`docs/submit`、`docs/originalfile`、`docs/前端卡通图片`、`笔记.md`）仅本地保留，不同步 GitHub。
- 尚未迁入的模块不得复制一份临时正式代码到其他根目录；交付物先放 `exchange/` 并记录自述。

## 模块实现与交接状态（2026-10-15 代码/文件核查）

| 模块 | 正式位置 | 状态 |
|---|---|---|
| M1 数据采集 | `backend/app/collect/` | 复用三平台适配器与公共管道；BOSS 已加中断保护，智联/猎聘仍整轮缓冲。采集页须手动启动；每日脚本检测 `PAUSE_COLLECT`，直接 CLI 不受该标记约束。 |
| M2 岗位分析 | `backend/app/job_analysis/` | 规则/LLM/合并/导出源码已迁入；当前交接为 717/717/275。`main --help` 可运行，完整 CLI 的绝对导入仍待修复；默认 `import_all()` 读取本地旧回包，重建时须显式指定 `exchange/m2` 且仅对隔离实例操作。 |
| M3 图谱 | `backend/app/graph/` | 现有交接含岗位/技能/行业 7845 节点与 11412 边；旧 builder 只构建岗位/技能，不能直接复现当前交接图，禁止覆盖已核验文件。 |
| M4 简历匹配 | `backend/app/matching/` | 文件/文本解析与加权规则匹配；上传不落库。学习路径已由集成层 `routers/learning.py` 实现确定性技能缺口/阶段建议，M4 pathfinder 独立模块仍未回包。 |
| M5 前端 | `frontend/` | 9 个业务页面；控制台可启动 BOSS/智联/猎聘，LinkedIn/HN 仅展示。简历自动推荐与学习路径已接 API；部分展示分和平台回退数值仍为演示口径，不能据此声称匹配准确率或实时统计。 |



> **2026-08-31 前端整合状态**：用户确认不再采用补丁式整合。正式前端现以 `input/图谱.png`、`input/采集模块管理.png` 为视觉基准重新组装，导航包含 Dashboard、JD 岗位、采集图谱、数据分析、采集模块管理、能力动态更新、简历分析、学习路径和简历预览。`input/` 仍是只读对照包，不是运行时源码；没有可信后端数据的页面展示诚实空态。采集控制台通过 `backend/app/collect/control.py` 包装既有 M1 循环，不自动启动采集。

历史整合记录（2026-09-02）：整合未决项已于 2026-08-13 裁决（决策 D26–D37），并在 2026-09-02 完成整体修复阶段第一轮收口；当时按用户 D56 完整导入 M2 719 岗位，后端全量 **236 passed**，前端构建通过。当时协作采用 `docs/superpowers/plans/2026-08-14-module-roundtrip.md` 回发闭环；当前 GitHub 流程见 AGENTS。旧实施计划（08-08 六份 + 08-13 整合计划）已归档 `docs/superpowers/plans/archive/`。资产清单与已知限制详见 `docs/superpowers/资产与状态.md`。

## 目录说明

```text
TalentMind/
├─ backend/
│  ├─ app/
│  │  ├─ collect/          # M1：采集、清洗、去重、入库
│  │  ├─ job_analysis/     # M2：岗位分析
│  │  ├─ graph/            # M3：图谱节点和关系
│  │  ├─ matching/         # M4：正式匹配实现
│  │  ├─ integration/      # A：交接导入、编排、组装
│  │  ├─ routers/          # A：统一 API 路由
│  │  ├─ contracts/        # DDL 和跨模块数据契约
│  │  ├─ db/               # 数据库连接与初始化
│  │  ├─ llm/              # LLM 适配
│  │  └─ skills/           # 技能标准化
│  └─ tests/               # 后端测试
├─ frontend/               # M5 正式前端
├─ exchange/               # 模块交接文件、接口自述、小型 Mock
├─ data/local/             # 大型本地数据、网页快照和缓存（不入 Git）
├─ docs/                   # 需求、设计、计划、决策和演示材料
├─ docker-compose.yml      # MySQL、Neo4j、Redis
└─ README.md               # 本文件
```

目录边界是硬约束：

- 正式后端源码只放 `backend/app/`；正式前端源码只放 `frontend/`。
- `exchange/` 只放可审阅、可追溯的交接内容，不作为运行时源码目录。
- 大型数据只放 `data/local/` 或数据库 Docker volume；真实简历等敏感文件必须脱敏。
- Git 历史负责保存旧版本，工作树不长期保留 `legacy/` 或重复源码副本。

## 技术与数据流

```text
采集源
  ↓
M1 backend/app/collect
  ↓  原始层：jd_pool / talent_raw / signal
MySQL（DDL：backend/app/contracts/ddl.sql）
  ↓
M2 岗位分析 → M3 图谱 graph.json → Neo4j
  ↓
M4 简历解析与岗位匹配
  ↓
A 统一集成层与 FastAPI routers
  ↓
M5 前端
```

Neo4j 的 `graph.json` 既是 M3 的交接产物，也是 A 导入 Neo4j 的可追溯备份。正式运行数据由 MySQL、Neo4j、Redis 的 Docker 命名卷持久化，不提交数据库文件。

## 本地启动

### 1. 准备 Python 环境

在仓库根目录执行：

```powershell
cd backend
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

按本机配置编辑 `backend/.env`。`OPENAI_API_KEY` 仅在启用 LLM 功能时需要，禁止把真实密钥提交到 Git。

### 2. 启动基础设施

在仓库根目录执行：

```powershell
docker compose up -d
docker compose ps
```

默认端口：MySQL `3306`、Neo4j 浏览器 `7474`、Neo4j Bolt `7687`、Redis `6379`。

### 3. 启动后端

```powershell
cd backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 18000 --reload
```

访问 `http://127.0.0.1:18000/health`，应得到统一响应结构 `{code, message, data}`。本机 8000/5173 受 Windows 端口权限限制（WSAEACCES），统一使用 **后端 18000 / 前端 18080**（前端 vite 已默认代理 `/api` 到 18000，可用 `VITE_PROXY_TARGET` 覆盖）。

### 4. 启动前端（另开终端，在仓库根目录执行）

```powershell
cd frontend
pnpm install --frozen-lockfile
pnpm run dev
```

访问 `http://127.0.0.1:18080/`；`pnpm run build` 包含类型检查。启动服务不会自动恢复每日采集。

### 5. 一键启动 / 一键停止（Windows 快捷程序，可选）

日常联调可双击根目录快捷程序，替代上面第 2–3 步手动操作：

- **启动**：`start_system.bat` —— 拉起 Docker 容器 + 后端 (18000) + 前端 (18080)，就绪后打开浏览器（不启动数据采集）；
- **关闭**：`stop_system.bat`（2026-09-04 新增）—— 停止后端、前端与 Docker 容器（MySQL/Neo4j/Redis，命名卷数据保留，不退出 Docker Desktop）；只想关前后端、保留数据库运行时，改用 `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\stop_system.ps1 -KeepDocker`。

逻辑位于 `scripts\start_system.ps1` / `scripts\stop_system.ps1`，按端口用 `Get-NetTCPConnection` + `Stop-Process` 定位并清理进程。

## 测试

纯单元测试不依赖 Docker：

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -m "not integration"
```

需要数据库的集成测试只在隔离实例运行；先配置测试进程连接专用 MySQL/Neo4j/Redis，确认不指向演示库。不要直接对日常 Compose 数据执行以下命令：

```powershell
# 配置并核对隔离测试服务连接后
cd backend
.\.venv\Scripts\python.exe -m pytest -m integration
```

新增模块必须至少提供一个模块级测试和一个与 A 集成的验证。测试数据优先放 `backend/tests/fixtures/`，不要从 `data/local/` 读取不可复现的个人目录。

集成测试数据自动清理（D37）：测试写入 DB 的数据必须按测试夹具特征精确删除（finally/teardown），禁止按 source 等宽泛条件 DELETE；运行集成测试后需查询 DB 验证无测试残留、生产数据未被误删。

## 模块交接规范

交接目录使用 `exchange/m1` 至 `exchange/m5`。每次交接至少包含：

- `README.md`：模块负责人、版本、运行方式、输入、输出、依赖和已知限制；
- 小型 JSON 或 Mock：UTF-8、数组根节点、snake_case；
- 验证命令和样例结果；
- 与 `backend/app/contracts/` 对应的契约说明。

M2、M3 默认交结构化文件；M4 交可运行模块；M5 对接 A 的统一 API 并提供 Mock。统一响应约定为 `{code, message, data}`，具体接口由 A 集成时最终确定。

字段变更规则：可以按授权新增表或字段；修改或删除冻结字段前，必须先更新决策记录并通知所有模块负责人。执行数据库迁移另需用户许可。文件交接约定继续适用于模块产物；当前开发、审查与合并职责见 [AGENTS.md](AGENTS.md)。

## 旧代码与清理规则

现有 `backend` 不是待清空的旧项目，其中的 M1、DDL、数据库连接、LLM、技能标准化和测试都是当前方案的可复用资产。处理顺序固定为：

1. 先在正式目录完成迁移或组装；
2. 切换 import、配置和测试路径；
3. 运行模块测试和集成验证；
4. 检查没有调用方、生成物或敏感数据依赖；
5. 最后才删除重复源码和缓存。

`input/人岗匹配/` 的迁移当前明确暂缓（原根目录交付目录已统一归档 `input/`）。它仍是待审查的原型区，不作为正式后端入口；后续开始迁移前，必须重新盘点源码、测试、样例数据、UI 原型和简历文件。

## 文档入口

- 当前产品方案：[PRODUCT_DECISIONS.md](docs/PRODUCT_DECISIONS.md)（已确认目标与待决策，独立于实现状态）
- Agent 阅读路线：[AGENT_START_HERE.md](AGENT_START_HERE.md)（核心 + 按模块选读）
- 目录设计：`docs/superpowers/specs/2026-08-11-repository-organization-design.md`
- 团队基础设计：`docs/superpowers/specs/2026-08-03-team-plan-design.md`（历史背景，服从明确替代后的当前规则）
- 历史决策与变更索引：[决策跟踪](docs/superpowers/决策跟踪.md)（保留 D1–D60，新增索引）
- 实施计划：`docs/superpowers/plans/`
- 数据契约：`backend/app/contracts/ddl.sql`
- 前端说明页：`docs/team-plan.html`
- 文档地图：`docs/README.md`（docs 全目录索引 + 归档说明）
- Agent 行为约束：`AGENTS.md`、`CLAUDE.md`

产品决策确认后分批更新主文档与决策索引；目录、契约或交接变更同步资产与状态和相关入口，通用协作规则仅在 AGENTS 维护。发现由 AI 修复的 bug 时，在 `docs/superpowers/traps/` 留下“症状 → 根因 → 修复 → 教训”记录。

## 当前不做的事

- 不整体删除 `backend`；
- 不把 M1 采集管道重写成另一套实现；
- 不迁移 `input/人岗匹配/`（已按用户要求暂缓）；
- 不提交 `.env`、真实密钥、数据库 volume、未经脱敏的简历和大型本地数据；
- 未获用户授权的任务不创建 Git commit；已授权的阶段开发可按 [AGENTS.md](AGENTS.md) 在独立分支分项提交并创建 PR，但不得未经审查合并 `master`。


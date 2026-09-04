# TalentMind

TalentMind 是一个契约式单体的人才数据与岗位智能系统。当前仓库承担两个角色：

1. A 负责的 M1 数据获取与清洗开发仓；
2. M1–M5 全部模块集成后的完整系统唯一主仓。

这两个角色共享同一份代码、同一份数据契约和同一套测试入口。不要再建立第二份“采集仓”，也不要在根目录长期维护重复的旧实现。

## 当前状态
> **2026-09-02 本轮最新状态**：用户已明确选择完整导入 M2 719 个岗位（新一代 344、现有 375），包含 LinkedIn/HN，覆盖 D55 的旧边界（D56）。MySQL `job_definition/job_skill/job_change_log=717/717/275`（2026-09-04 复核：719 导入后删除 AI 测试开发工程师与博士后(61322) 共 2 条定义+技能、新增 32 条演示变更日志）；Neo4j 为 7852 节点/11423 关系（岗位/技能/行业均已解析）。前端已接入完整岗位目录、历史日志识别、BOSS/智联/猎聘控制、简历自动推荐与绑定学习路径；前端构建和当前回归测试已通过。


- M1 数据采集管道位于 `backend/app/collect/`，继续复用，不重写。
- 当前冻结的数据契约位于 `backend/app/contracts/ddl.sql`。
- FastAPI 后端入口是 `backend/app/main.py`，现有健康检查为 `GET /health`。
- MySQL、Neo4j、Redis 由根目录 `docker-compose.yml` 提供。
- 当前原始对照包保留在 `input/`：`图谱模块/`、`岗位能力图谱前端系统/`、`人岗匹配/`；旧 `input/jd-filter-package/` 已被 2026-08-30 M2 新回包替代并删除。
- 完整资产清单、整合状态与已知限制见 `docs/superpowers/资产与状态.md`（工作前必读）。
- 文档导航：`docs/README.md`（docs 地图）；历史记录：`docs/superpowers/历史时间线.md`；未决问题：`docs/superpowers/未决问题清单.md`。D57 起 `input/`、`output/` 与便利/参赛文件（`docs/submit`、`docs/originalfile`、`docs/前端卡通图片`、`笔记.md`）仅本地保留，不同步 GitHub。
- 尚未迁入的模块不得复制一份临时正式代码到其他根目录；交付物先放 `exchange/` 并记录自述。

## 模块交付与整合状态（2026-09-02 更新）

| 模块 | 正式位置 | 状态 |
|---|---|---|
| M1 数据采集 | `backend/app/collect/` | 采集循环仍按用户指示暂停；采集模块管理页进入时自动准备独立 Edge，已登录时仅尝试单轮，未登录只提示人工登录。当前主库中文原始 JD：BOSS 1131、智联 1088、猎聘 764。|
| M2 岗位分析 | `backend/app/job_analysis/` | 已接入 M2 2026-09-01 完整回包：719 个岗位、719 条合并技能记录、243 条能力更新日志；完整导入入口为 `app.integration.import_exchange.import_all()`。|
| M3 图谱 | `backend/app/graph/` | 已按 M2 完整 719 岗位重建（D56，含 LinkedIn/HN）；当前 Neo4j 7852 节点/11423 关系（岗位 719 / 技能 4671 / 行业 2462），`exchange/m3/graph.json` 已同步。|
| M4 简历匹配 | `backend/app/matching/` | 文件解析+匹配可用；待回包实现 pathfinder |
| M5 前端 | `frontend/` | 已完成统一重新整合：全局学校品牌、JD 三平台统计/搜索、Career Nebula 图谱、简历内存态匹配、采集控制台和技能学习路径；`pnpm run build` 通过。|



> **2026-08-31 前端整合状态**：用户确认不再采用补丁式整合。正式前端现以 `input/图谱.png`、`input/采集模块管理.png` 为视觉基准重新组装，导航包含 Dashboard、JD 岗位、采集图谱、数据分析、采集模块管理、能力动态更新、简历分析、学习路径和简历预览。`input/` 仍是只读对照包，不是运行时源码；没有可信后端数据的页面展示诚实空态。采集控制台通过 `backend/app/collect/control.py` 包装既有 M1 循环，不自动启动采集。

整合未决项已于 2026-08-13 裁决（决策 D26–D37），并在 2026-09-02 完成整体修复阶段第一轮收口；本轮按用户 D56 完整导入 M2 719 岗位，后端全量 **236 passed**，前端构建通过。协作按 `docs/superpowers/plans/2026-08-14-module-roundtrip.md` 回发闭环执行；旧实施计划（08-08 六份 + 08-13 整合计划）已归档 `docs/superpowers/plans/archive/`。资产清单与已知限制详见 `docs/superpowers/资产与状态.md`。

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
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

访问 `http://127.0.0.1:18000/health`，应得到统一响应结构 `{code, message, data}`。本机 8000/5173 受 Windows 端口权限限制（WSAEACCES），统一使用 **后端 18000 / 前端 18080**（前端 vite 已默认代理 `/api` 到 18000，可用 `VITE_PROXY_TARGET` 覆盖）。

## 测试

纯单元测试不依赖 Docker：

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -m "not integration"
```

需要数据库的集成测试：

```powershell
docker compose up -d
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

字段变更规则：可以新增表或字段；修改或删除冻结字段前，必须先更新决策记录并通知所有模块负责人。

## 旧代码与清理规则

现有 `backend` 不是待清空的旧项目，其中的 M1、DDL、数据库连接、LLM、技能标准化和测试都是当前方案的可复用资产。处理顺序固定为：

1. 先在正式目录完成迁移或组装；
2. 切换 import、配置和测试路径；
3. 运行模块测试和集成验证；
4. 检查没有调用方、生成物或敏感数据依赖；
5. 最后才删除重复源码和缓存。

`input/人岗匹配/` 的迁移当前明确暂缓（原根目录交付目录已统一归档 `input/`）。它仍是待审查的原型区，不作为正式后端入口；后续开始迁移前，必须重新盘点源码、测试、样例数据、UI 原型和简历文件。

## 文档入口

- 当前架构设计：`docs/superpowers/specs/2026-08-11-repository-organization-design.md`
- 团队总设计：`docs/superpowers/specs/2026-08-03-team-plan-design.md`
- 决策记录：`docs/superpowers/决策跟踪.md`
- 实施计划：`docs/superpowers/plans/`
- 数据契约：`backend/app/contracts/ddl.sql`
- 前端说明页：`docs/team-plan.html`
- 文档地图：`docs/README.md`（docs 全目录索引 + 归档说明）
- Agent 行为约束：`AGENTS.md`、`CLAUDE.md`

修改目录、契约或协作流程时，先更新决策记录，再同步 README 和约束文件。发现由 AI 修复的 bug 时，在 `docs/superpowers/traps/` 留下“症状 → 根因 → 修复 → 教训”记录。

## 当前不做的事

- 不整体删除 `backend`；
- 不把 M1 采集管道重写成另一套实现；
- 不迁移 `input/人岗匹配/`（已按用户要求暂缓）；
- 不提交 `.env`、真实密钥、数据库 volume、未经脱敏的简历和大型本地数据；
- 不创建 Git commit，除非用户明确要求。


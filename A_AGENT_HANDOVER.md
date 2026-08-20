# A 角色开发路线与交接文档（给下一个接手 A 工作的 Agent）

> **前置**：先完成 `AGENT_START_HERE.md` 通用路线（逐文件阅读并给出要点证明），再读本文件。
> **角色**：A = M1 数据采集负责人 + 唯一集成者（决策 D2/D3/D4）。你接手的是"系统集成 + 回发闭环验收 + 继续 A 的未完成事项"。

## 一、A 专属必读（通用路线之外）

| 文件 | 作用 |
|---|---|
| `backend/app/integration/validate_exchange.py` | 交接文件 schema 校验器（回包第一关；change_type 枚举硬校验、版本头软提示） |
| `backend/app/integration/import_exchange.py` | M2 交接 → MySQL 导入（**全量重建语义**：M2 产出是权威岗位集合） |
| `backend/app/integration/import_graph.py` | graph.json → Neo4j（MERGE 幂等；换数据先清空） |
| `backend/app/routers/mvp.py` | 20 个统一 API（jobs/graph/resume/dashboard；中英文 title/name_en 已生效） |
| `backend/app/collect/README.md` | **M1 采集模块文档（数据源矩阵/命令/幂等/合规/监控）** |
| `scripts/collect_daily.ps1` / `check_collect_status.ps1` | 每日采集（SYSTEM 任务）/ 一键监控（任务/日志/数据量） |
| `backend/app/collect/fetch_all.py` | **统一采集入口**（signals + hn + 交叉验证，一键） |
| `backend/app/collect/collect_loop.py` | **持续采集循环**（每 N 小时一轮，--forever；当前运行中） |
| `backend/app/collect/cross_validate.py` | 多源交叉验证（D42：cross_source 标记 + quality 上浮） |
| `docs/superpowers/plans/2026-08-17-multisource-collection-plan.md` | 多源采集计划（P0 信号 ✅ / P1 岗位 ✅ / P2 交叉验证 ✅） |
| `data/local/m2-data-pack/` | **M2 数据包（已发送 M2 开发者）**：jd_pool.sql 全量 + jd.json + skill_dict + signal 快照 + 交叉验证报告 |
| `backend/.env` | 本地配置（MySQL/Neo4j/Redis/LLM 密钥，gitignore 保护，**禁止外传/入库**） |
| `frontend/前后端接口对接文档.md` | 20 接口基线文档 |
| `output/` | 回发包 v3（已发送四位队员；结构见 08-14 roundtrip 方案） |

## 二、当前状态（截至 2026-08-20，工作树未提交）

- **数据闭环**：jd_pool **126133 cleaned**（linkedin 123849 + hn 1796 + boss 488）；signal **433 条 / 4 天时间序列**；cross_source **888 行（数据库实时值；最新报告重算为 887 行，含 1 条历史残留标记）**；skill_dict 285；job_definition 22；job_skill 22；job_change_log 0；Neo4j Job 22 / Skill 75 / REQUIRES 191 / RELATED_TO 31。BOSS 扩大采集详见 `exchange/m1/boss-collection-handover-20260820.md`。
- **通用持续采集运行中（D44）**：`collect_loop.py` 后台循环（每 6h 一轮 --forever，当前已完成第 11 轮，PID 见 `data/local/logs/collect_loop.out.log`）；BOSS 独立循环已完成第 1–15 轮并新增 14 条，第 16 轮因 CDP 无可用页面安全停止；9333 仍监听但无可用 BOSS 页面；SYSTEM 计划任务 02:00 保留为尽力触发（自动触发不可靠，勿依赖）。
- **M2 数据包已发**：`data/local/m2-data-pack/` **2026-08-19-1 版**（signal 3 天时间序列 253 条 + jd_pool.sql 6796 + jd.json 200 + skill_dict + 交叉验证报告）；岗位数据足量支撑 M2；下次更新视 signal 天数或 M2 反馈。
- **测试**：后端 221 全量通过，包含 BOSS CDP 连接与详情归一化测试；前端 `pnpm run build` 通过。
- **服务**：后端 uvicorn :8000、前端 vite :5173；MySQL/Neo4j/Redis 在 Docker。
- **回发闭环**：`output/` 四包 v3 已发队员，二次开发窗口 8/16–19，A 验收 8/19–21（错峰：M2 8/19 → M3/M4 8/20 → M5 8/21）。
- **契约/决策**：D37 测试数据安全清理、D38 source=linkedin+source_detail、D39 多源信号、D40 HN 岗位、D41 采集模块完整开发、D42 交叉验证、D43 M2 数据包、D44 持续采集改设计、D45–D48 BOSS 受控 CDP 采集与 9333 端口、D49 BOSS 扩大采集结果；未决 P1/P2/P3/P5/P6（P6=其他中文平台合规方案，BOSS 已进入可运行受控方案）。
- **A 集成修改文件清单（回包防覆盖）**：`job_analysis/db.py`（解析器反斜杠转义保留，M2 数据包依赖）；`collect/` 系列（fetch_all/collect_loop/cross_validate/fetch_signals/fetch_hn_jobs/hn_hiring/trending/blog_rss、cleaner/repository/schema/dataset）；`ddl.sql`（experience/change_type 扩容、source_detail、cross_source、signal.source）。

## 三、交接：你接手后必须做的事

> **接手 48h 行动清单**：① 即进入**回包验收期（8/19 M2 → 8/20 M3/M4 → 8/21 M5）**，按下方「队员回包验收」4 关执行；② 确认 `collect_loop` 进程存活（重启命令见第四节）并记录 `check_collect_status.ps1` 基线；③ 若 M2 已用数据包重跑，用新产出重导 `exchange/m2` 并过 `validate_exchange`；④ 全队会议补告知契约变更（change_type/experience/source 语义）；⑤ 每轮采集后确认 signal 时间序列在增长。

### 1. 立即（等队员回包前）
- [ ] 全队会议：正式通知 change_type / experience 扩容 + 中英文统一规则 + 版本 v3 基线 + 错峰时间表（材料见 `笔记.md` 第十一节 + `output/` 各包问题/要求清单）。
- [x] 补填 `exchange/m1/quality_check.md` 抽样 10 条核对结论（2026-08-16 AI 标注 10/10 通过，可人工复核）。
- [ ] 熟悉验收工具链：`validate_exchange.py`、`import_exchange.py`、`import_graph.py`、测试命令（`cd backend && .\.venv\Scripts\python.exe -m pytest -q`）。
- [x] **持续采集监控**：`powershell -File scripts\check_collect_status.ps1`（已验证；8/19 循环第 5 轮、signal 3 天）；确认 `collect_loop` 进程存活（重启：见第四节）。

### 2. 队员回包验收（4 关门禁，见 08-14 roundtrip 方案 Step 5）
1. **schema 校验**：`validate_exchange`（字段/类型/枚举/关联/版本头）；
2. **diff 检查**：A 修改文件未被回滚（M2 `stage3_extract.py` 约束、M4 `matcher.py` canonical 化、前端 request/vite 配置、`job_analysis/db.py` 解析器修复等）；
3. **单测/集成**：队员测试结果 + A 机复验（208 基线 + 模块新增）；
4. **导入 + 前端冒烟**：import_exchange/import_graph → MySQL/Neo4j → `/api` → 前端页面。

### 3. 队员回包后的跟进
- [ ] **M2 回包后重生成数据快照**（`output/` 各包 `依赖数据快照/快照说明.md`：snapshot_version+1）同步 M3/M4/M5；
- [ ] 用新产出重跑 M3 builder（`exchange/m2` → graph.json）→ 清空重导 Neo4j；
- [ ] 若 M2 增加 `job_name_zh`：API/图谱切换到正式中文字段（当前为过渡映射）；
- [ ] 重跑 `validate_exchange` 确认关联警告（当前 job_skill↔job_definition 3/22）清零。

### 4. 未完成事项（P1 / 收尾）
- [x] signal 时间序列 3 天达成：**M2 数据包 2026-08-19-1 版已生成**（signal 253 条/3 天）；后续更新参考 `data/local/gen_pack3.py` 逻辑。
- [ ] 阶段 7 清理：`input/` 下原交付目录（`jd-filter-package/`、`图谱模块/`、`岗位能力图谱-前端源码/`、`人岗匹配/`，2026-08-16 确认已归档于此）（**`input/人岗匹配/岗位测试用例/*.pdf/docx` 真实简历删除前先列清单与用户确认**，D36）；
- [ ] 部署说明与演示材料（P3）；P1 项（见 `笔记.md` 第七节）：M2 is_emerging 复核与 100 JD 测试集；M4 pathfinder（队员 P0）；M5 空列/趋势/Learning；M3 Skill–Skill；resume 落库；P6 中文平台合规方案（用户确认后续再议）。

## 四、操作手册（A 常用命令）

```powershell
# 启动基础设施
docker compose up -d

# 启动后端 / 前端（两个终端）
cd backend; .\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
cd frontend; pnpm dev

# 全量测试
cd backend; .\.venv\Scripts\python.exe -m pytest -q

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
2. **`笔记.md` 不提交**（用户要求）；`output/`、`input/`、`data/local/` 不入库。
3. **契约变更先通知**：改/删字段须全队通知（D32/D33/P4 已执行，通知随会议）；加字段自由但须同步 `validate_exchange` 与文档（D38 source_detail、D42 cross_source、D39 signal.source 均已记录）。
4. **不臆测**：不确定先查资产清单/决策跟踪/笔记；仍不确定问用户。
5. **测试门禁**：任何集成改动后必须 `pytest` 全量通过（208 基线）+ 前端 `pnpm run build`。
6. **测试数据清理（D37）**：集成测试写库数据必须按测试夹具特征精确清理（finally/teardown），禁止按 source 宽泛删除；跑完测试后查询 DB 验证无残留、生产数据未被误删。
7. **幂等与增量（D44）**：`fetch_signals` 追加式（不覆盖历史时间点）；`fetch_hn_jobs` 按帖清理（勿改回"当日先清后写"，会误删历史月份，见 traps/2026-08-17-hn-idempotency-wiped-history.md）；计划任务 Task To Run 必须用 powershell 全路径（SYSTEM 任务相对路径不启动）。

## 2026-08-20 低速持续采集

- 已新增 `backend/app/collect/boss_collect_loop.py`，BOSS 独立于通用 `collect_loop.py` 运行。
- 默认单关键词/城市、1 页、最多 12 条岗位/8 条详情；页面间隔 15–30 秒，关键词/城市切换间隔 6–12 分钟，默认不间断运行。
- 检测到登录页或验证页立即停止；不实现验证码/登录/反爬绕过。日志为 `data/local/logs/boss_collect_loop.out.log`。
- 当前运行记录（2026-08-20 17:20:11 +08:00）：BOSS 低速循环已按新默认节奏重启，启动器 PID 20544、工作进程 PID 35472；首轮北京/Python 于 17:23:46 完成，`listed=12/details=8/new=0/skipped=12`，随后等待 575.8 秒切换。

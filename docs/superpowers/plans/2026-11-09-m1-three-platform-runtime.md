# M1 三平台隔离持续采集实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 用一个 Edge CDP 引擎、一个调度器和三套独立 Profile/状态，实现 BOSS、智联、猎聘的低频持续采集、单站阻断隔离、逐条提交和可恢复游标。

**Architecture:** 复用现有 `collect/browser.py` 与 `fetch_*_jobs.py` 的 Edge CDP、DOM 解析、频率和身份门禁；新增 `collect/runtime/` 负责平台契约、每站状态、子进程 worker 与调度。旧接口保留兼容，新链路通过隔离模拟和全仓回归后才标记旧可写入口退役候选。

**Tech Stack:** Python 3、FastAPI、SQLAlchemy、SQLite、websockets、Vue 3、Element Plus。

**Spec:** [Issue #79](https://github.com/Serena-Lyric/TalentMind/issues/79)、[开源与 Gate 0 证据](../specs/2026-11-09-m1-three-platform-runtime-reuse-review.md)

## Global Constraints

- Gate 0 固定选型：复用现有 Edge CDP；不新增 Playwright、网络监听、第二套浏览器引擎或混合桥接。
- 独立 Profile：`data/local/collection/browser_profiles/{boss,zhaopin,liepin}`；运行态：`data/local/collection/runtime/{platform}`。
- 页面动作 15–30 秒；关键词/城市切换 360–720 秒；页面稳定至少 5 秒；更慢配置可保留。
- 频率门禁不可删除；每平台独立 SQLite 账本；正式旧账本未获许可不删除、不迁移。
- 单站 `blocked/needs_login/failed` 只停该站；不自动轮询验证页，不重试未知提交。
- 有效详情在下一页面动作前逐条提交；数据库失败停该站，已提交项保留。
- 不可靠身份保持 `pending/unknown`；禁止按下标、相似标题或公司猜测身份；`source_detail` 不静默截断。
- 真实网站持续采集、正式库迁移、正式数据删除、PR 合并均不在本计划执行范围；补充单次实测已记录为严格契约失败，未获重试授权。

## Review Focus

- 单站阻断是否只停该站，另外两站继续轮换和写入。
- 两平台同时执行长动作时是否因 SQLite 文件锁互相阻塞。
- 旧 unfinished flight 迁移后是否仍阻止继续，恢复后是否保留冷却。
- 同一详情重复采集是否幂等，数据库失败是否保留已提交前序项。
- 页面换代/迟到响应/同标题不同公司是否被拒绝而不是合并。

---

### Task 1: 补齐 BOSS 稳定身份与内容准入

**Files:**
- Modify: `backend/app/collect/fetchers/boss.py`
- Test: `backend/tests/test_boss_fetcher.py`

**Interfaces:**
- Consumes: `RawJD(source, job_title, raw_html, source_detail, identity_status, content_eligible, identity_evidence)`
- Produces: `normalize_boss_job(raw: dict, detail: dict | None = None) -> RawJD | None`，稳定 BOSS 详情 URL 且正文非空时返回 `identity_status='verified'`、`content_eligible=True`、含 `strategy/source/detail_url/observed_at` 的 JSON evidence。

- [x] **Step 1: 写失败测试**：新增 `test_boss_normalization_records_verified_detail_identity`，断言合成详情返回 verified、content_eligible True、evidence 可 JSON 解析且 URL 去查询参数；另加 `test_boss_normalization_rejects_overlong_source_detail`，断言超过 128 字符时不静默截断。
- [x] **Step 2: 运行 RED**：`cd backend; .\.venv\Scripts\python.exe -m pytest tests/test_boss_fetcher.py::test_boss_normalization_records_verified_detail_identity -q`，预期 FAIL（unknown/null）。
- [x] **Step 3: 最小实现**：只在 canonical BOSS detail URL 存在且 `detail_text` 非空时写入 verified/content_eligible；缺失时保持 unknown/None。
- [x] **Step 4: 运行 GREEN**：同命令 PASS。
- [x] **Step 5: 提交**：仅暂存两个文件，提交 `fix(collect): record BOSS detail identity evidence`。

### Task 2: 每平台独立频率账本与旧账本迁移门禁

**Files:**
- Modify: `backend/app/collect/frequency.py`
- Modify: `backend/app/collect/frequency_recovery.py`
- Test: `backend/tests/test_collection_frequency.py`
- Test: `backend/tests/test_collection_frequency_recovery.py`

**Interfaces:**
- Produces: `frequency.ledger_path(platform: str) -> Path`、`frequency.legacy_migration_required(platform: str) -> bool`
- Produces: `frequency_recovery.migrate_legacy_platform(platform: str, source_path: Path | None = None) -> dict`
- Preserves: `reserve_action`、`run_action`、`get_status`、`recover` 的现有签名与返回值字段。

- [x] **Step 1: 写失败测试**：`test_platform_actions_use_independent_ledgers` 用两个线程同时阻塞两个平台，断言总耗时 < 1 秒且两文件存在。
- [x] **Step 2: 写失败测试**：`test_legacy_flight_migration_preserves_unfinished_and_cooldown` 合成旧共享账本，迁移后仍 unfinished；恢复后下一次动作不早于原冷却。
- [x] **Step 3: 运行 RED**：两个新增测试均 FAIL。
- [x] **Step 4: 最小实现**：默认路径改为 `runtime/{platform}/frequency.sqlite3`；所有连接按平台路径；旧 `_STATE_PATH` 覆盖继续供测试兼容；迁移只复制并写审计表，不删除旧文件。
- [x] **Step 5: 运行 GREEN**：频率与恢复专项 PASS。
- [x] **Step 6: 提交**：`fix(collect): isolate frequency ledgers per platform`。

### Task 3: 每平台原子运行状态

**Files:**
- Create: `backend/app/collect/runtime/__init__.py`
- Create: `backend/app/collect/runtime/state.py`
- Test: `backend/tests/test_collection_runtime_state.py`

**Interfaces:**
- Produces: `RuntimeState(platform, status, keyword_index, city_index, page, next_run_at, last_saved_identity, last_success_at, stop_reason, stats, updated_at)`
- Produces: `load_state(platform, root=None) -> RuntimeState`、`save_state(state, root=None) -> None`
- Produces: `request_stop(platform, root=None) -> None`、`stop_requested(platform, root=None) -> bool`、`clear_stop(platform, root=None) -> None`

- [x] **Step 1: 写失败测试**：状态保存后新连接可读回；非法 status 被拒绝；stop 标记可创建/清除。
- [x] **Step 2: 运行 RED**。
- [x] **Step 3: 最小实现**：SQLite `state.sqlite3`、`runtime_state` 单行、`PRAGMA synchronous=FULL`；路径固定到 `runtime/{platform}`。
- [x] **Step 4: 运行 GREEN**。
- [x] **Step 5: 提交**：`feat(collect): persist per-platform runtime state`。

### Task 4: 平台契约与统一 CDP 执行引擎

**Files:**
- Create: `backend/app/collect/runtime/platforms.py`
- Create: `backend/app/collect/runtime/browser.py`
- Modify: `backend/app/collect/fetch_boss_jobs.py`
- Modify: `backend/app/collect/fetch_cn_jobs.py`
- Test: `backend/tests/test_collection_runtime_browser.py`

**Interfaces:**
- Produces: `PlatformDefinition(source, label, host_hint, cities, profile_dir, runtime_dir, search_url)`
- Produces: `CdpEngine.fetch_once(platform, keyword, city, page, db_provider, on_event=None) -> dict`
- `fetch_boss_jobs.run_fetch(..., db_provider=None)` 与 `fetch_cn_jobs.run_fetch(..., db_provider=None)` 在提供 provider 时使用注入会话，默认行为不变。

- [x] **Step 1: 写失败测试**：fake `run_fetch` 捕获 profile、页数、detail/max 上限和 db provider；断言三平台各自使用固定 Profile，且不调用第二个引擎。
- [x] **Step 2: 运行 RED**。
- [x] **Step 3: 最小实现**：平台定义复用现有 URL/SiteSpec；`CdpEngine` 仅分派到现有 BOSS/CN 入口，映射 blocked/needs_login/failed/success。
- [x] **Step 4: 运行 GREEN**。
- [x] **Step 5: 提交**：`feat(collect): add unified CDP runtime engine`。

### Task 5: 逐条 sink 与 worker 轮换/阻断隔离

**Files:**
- Create: `backend/app/collect/runtime/sink.py`
- Create: `backend/app/collect/runtime/worker.py`
- Test: `backend/tests/test_collection_runtime_worker.py`

**Interfaces:**
- Produces: `DatabaseSink(provider)` 提供 `db_provider()` 和 `record_stats(stats)`。
- Produces: `run_worker(platform, config, *, engine, sink, state_root=None, max_rounds=0, clock=time.time, sleeper=time.sleep) -> RuntimeState`
- Worker 状态：`running -> waiting | needs_login | blocked | failed | stopped`。

- [x] **Step 1: 写失败测试**：三站 fake engine 并发，BOSS 抛 blocked 后 BOSS stopped，智联/猎聘继续并写入；轮换顺序为关键词→城市→页码。
- [x] **Step 2: 写失败测试**：等待期 stop 立即结束；未知提交异常停该站且不重试。
- [x] **Step 3: 运行 RED**。
- [x] **Step 4: 最小实现**：worker 只负责游标、状态、等待与单次 engine 调用；不复制解析/入库逻辑。
- [x] **Step 5: 运行 GREEN**。
- [x] **Step 6: 提交**：`feat(collect): run isolated rotating workers`。

### Task 6: 调度器与单站恢复

**Files:**
- Create: `backend/app/collect/runtime/scheduler.py`
- Test: `backend/tests/test_collection_runtime_scheduler.py`

**Interfaces:**
- Produces: `RuntimeConfig`、`start(config) -> dict`、`stop() -> dict`、`status() -> dict`、`resume(platform, confirmed=False) -> dict`
- 启动前若 `legacy_migration_required` 为真则 fail closed；每个 worker 独立 Popen，输出写 `runtime/{platform}/worker.log`。

- [x] **Step 1: 写失败测试**：注入 fake spawner，启动 3 个 PID；一个退出为 blocked 时状态聚合仍保留另两站 running/waiting。
- [x] **Step 2: 写失败测试**：stop 对三个 worker 都发停止标记；resume 未确认的 blocked 被拒绝，确认后冷却至少 30 秒。
- [x] **Step 3: 运行 RED**。
- [x] **Step 4: 最小实现**：调度器只管理进程/状态，不执行页面动作。
- [x] **Step 5: 运行 GREEN**。
- [x] **Step 6: 提交**：`feat(collect): schedule isolated platform workers`。

### Task 7: /collection 统一控制 API 与页面

**Files:**
- Modify: `backend/app/routers/collection.py`
- Modify: `frontend/src/api/collection.ts`
- Create: `frontend/src/components/CollectionRuntime.vue`
- Modify: `frontend/src/views/Collection.vue`
- Test: `backend/tests/test_collection_runtime_api.py`
- Test: `frontend/tests/collectionRuntime.test.ts`

**Interfaces:**
- API: `GET /collection/runtime/status`、`POST /collection/runtime/start`、`POST /collection/runtime/stop`、`POST /collection/runtime/resume/{platform}`。
- UI 只显示三站状态、当前组合/页码、真实计数、错误和停止/恢复按钮；不新增看板。

- [x] **Step 1: 写失败 API 测试**：start 转发配置；status 三站；resume 拒绝未确认 blocked；旧 `/collection/start` 仍可用。
- [x] **Step 2: 写失败前端测试**：三站状态渲染、单站恢复、stop 后无迟到覆盖。
- [x] **Step 3: 运行 RED**。
- [x] **Step 4: 最小实现**：路由薄封装；组件只消费 API，不推断入库成功。
- [x] **Step 5: 运行 GREEN**：后端 API 专项、前端专项。
- [x] **Step 6: 提交**：`feat(collection): expose isolated runtime controls`。

### Task 8: 三站隔离模拟闭环与历史 RED→GREEN

**Files:**
- Create: `backend/tests/test_collection_runtime_three_sites.py`
- Create: `docs/superpowers/traps/2026-11-09-boss-collection-identity-metadata-gap.md`
- Modify: `docs/superpowers/specs/2026-11-09-m1-three-platform-runtime-reuse-review.md`

**Interfaces:**
- 测试使用本地模拟站点/fake engine 和三个隔离 SQLite；不访问真实网站，不连接正式库。

- [x] **Step 1: 写失败测试**：启动→列表→详情→校验→隔离 SQLite 单条提交→第二轮幂等→停止→重启恢复；BOSS 模拟 blocked，智联/猎聘继续轮换。
- [x] **Step 2: 覆盖历史回归**：同标题不同公司、迟到详情、推荐字段、空卡、跨站长动作、未完成 flight、控制台 0 入库。
- [x] **Step 3: 运行 RED/GREEN**：先失败，再最小修复。
- [x] **Step 4: 记录陷阱**：症状→根因→修复→教训，写明真实单次实测机械成功但身份字段失败，不写成通过。
- [x] **Step 5: 提交**：`test(collect): prove isolated three-site runtime`。

### Task 9: 全仓验证、文档与 PR

**Files:**
- Modify: `docs/superpowers/资产与状态.md`
- Modify: `backend/app/collect/README.md`
- Modify: `docs/PRODUCT_DECISIONS.md`（仅在确认新长期规则时）
- Modify: `docs/README.md`（仅导航需要）
- Review: `docs/review/` 临时阶段报告（合并前移除）

- [x] **Step 1: 运行后端离线回归**：`cd backend; .\.venv\Scripts\python.exe -m pytest -m "not integration"`。
- [x] **Step 2: 运行前端**：`cd frontend; pnpm test; pnpm run typecheck; pnpm run build`。
- [x] **Step 3: 核对生产库 0 写/0 删**：只读确认隔离路径与正式连接未变化；不得用测试清理生产库。
- [x] **Step 4: 写回资产/README/陷阱**，检查相对链接与 diff。
- [ ] **Step 5: 精准暂存、提交、推送临时分支并创建面向 master 的 PR；不自动合并、不触发三站真实持续采集。**
- [ ] **Step 6: 在 Issue #79 写回 head、测试数字、单次实测失败证据、离线三站证据和待实机门槛。**


# Issue #81 P3：M1 旧入口清理计划（2026-11-20）

## 目标与边界

按实际调用图收敛 M1 为 `runtime/` 单一采集入口，删除旧单轮、批次、普通浏览器桥接、低速循环、HN/信号入口及其前端消费者。

同时保留线上七页正在使用的读取能力：

- `GET /collection/status`、`/collection/progress`、`/collection/platforms`、`/collection/config`、`/collection/database-stats`、`/collection/stats`、`/collection/recent`；
- `GET /collection/history`、`/collection/results`、`/collection/raw/{id}`（历史任务、事件与原文读取）；
- `GET /collection/frequency/{platform}`、`POST /collection/frequency/{platform}/recover`；
- `POST /collection/prepare`、`GET /collection/cdp-status`（浏览器准备与访问检查）；
- `GET/POST /collection/runtime/*`（三平台 runtime 状态、启动、停止、恢复）；
- `GET /collection/readiness`。

M1 真实浏览器采集暂缓不构成删除理由。M2 版本比较、M3 历史图谱和业务数据不在本阶段范围；`data/local`、MySQL/SQLite、持久卷不删除。

## 实际消费者映射

以下按仓库内 import、路由注册、前端调用和测试夹具核对，不按文件名推断。

### 后端

| 符号/文件 | 实际消费者 | 处理 |
|---|---|---|
| `app.routers.collection` 的 `/collection/start`、`/collection/stop` | 前端 `Collection.vue` `startTask/stopTask`；`scripts/stop-local.ps1`；`test_collection_product.py`、`test_collection_worker_process.py`、`test_collection_runtime_api.py` | 删除路由与前端调用；`stop-local.ps1` 改用 runtime 停止 |
| `app.routers.collection` 的 `/collection/batches*` 7 个路由 | 前端 `CollectionBatch.vue` + `api/collection.ts`；`scripts/stop-local.ps1`；批次测试 | 删除 |
| `control.start_task`、`stop_task`、`_launch_task`、`_spawn_worker`、`_worker_environment`、`_watch_process`、`_parse_log_line`、`_update_task`、`_archive_task`、`_task_snapshot`、`_wait_task_done`、`_release_lease`、`_ensure_no_external_task`、`upsert_external_task` | 旧单轮路由、`batch.py`、`bridge.py` 及对应测试 | 删除；历史 `control-state.json` 与 `*.events.jsonl` 仍由读取函数消费 |
| `control.get_platforms/get_config/update_config/get_status/get_history/get_results/get_raw/get_recent_raw/get_database_stats/get_cdp_status/prepare_browser/get_frequency_status/recover_frequency` | `app.routers.collection` 的保留路由；线上采集页状态、频率、历史、原文与准备面板 | 保留 |
| `control._validated_config`、`_reserve_tasks`、`_release_tasks`、`_load_state/_save_state/_default_state/_empty_task` | 保留的 prepare/config/frequency 路由及读取逻辑 | 保留；占用检查收敛为仅防并发 prepare/recover |
| `boss_collect_loop.DEFAULT_CITIES` | `control._PLATFORMS` | 删除模块，城市默认值内联到 `control._PLATFORMS` |
| `boss_collect_loop.py`、`cn_collect_loop.py`、`collect_loop.py`、`fetch_all.py` | 旧 CLI；`control`、测试、`scripts/collect_daily.ps1` | 删除；删除 `scripts/collect_daily.ps1` |
| `batch.py` | `/collection/batches*`、`control`、批次测试 | 删除 |
| `bridge.py`、`bridge_schema.py`、`bridge_access.py`、`routers/collection_bridge.py` | `/api/collection/bridge/*`、`main.py` CORS/路由、旧扩展、桥接测试 | 删除；`main.py` 移除桥接路由与扩展 Origin |
| `fetch_hn_jobs.py`、`fetch_signals.py`、`cross_validate.py`、`fetchers/hn_hiring.py`、`fetchers/trending.py`、`fetchers/blog_rss.py`、`fetchers/github.py`、`fetchers/base.py` | 仅旧 CLI、`fetch_all/collect_loop` 与各自测试 | 删除；`test_hn_hiring.py`、`test_signal_fetchers.py`、`test_github_fetcher.py`、`test_cross_validate.py` 同步删除 |
| `beautifulsoup4` | 仅上述 HN/信号 fetcher | 从 `backend/requirements.txt` 删除；`httpx` 仍被 browser/CDP/M2 使用，保留 |
| `runtime/`、`fetch_boss_jobs.py`、`fetch_cn_jobs.py`、`pipeline.py`、`repository.py`、`identity.py`、`frequency.py`、`frequency_recovery.py`、`browser.py`、`worker_process.py`、`readiness.py`、`timing_validation.py`、`cleaner.py`、`events.py`、`fetchers/boss.py`、`fetchers/cdp.py`、`fetchers/job_sites.py` | runtime 调度、采集器、API 与测试 | 保留 |
| `import_csv.py`、`fetchers/dataset.py` | LinkedIn 历史数据集导入 CLI 与测试 | 保留（不属于 HN/信号入口） |

### 前端/脚本/部署

| 符号/文件 | 实际消费者 | 处理 |
|---|---|---|
| `CollectionBatch.vue`、`api/collection.ts` 批次类型与函数 | `Collection.vue` 批量 tab、批次测试 | 删除组件、API 函数、测试 |
| `CollectionBridge.vue`、`api/collection.ts` 桥接类型与函数、`frontend/bridge-extension/*` | `Collection.vue` 桥接 tab、扩展测试 | 删除组件、API 函数、扩展目录、测试 |
| `startCollection/stopCollection`、`startTask/stopTask/canStart/canStop/startHint` | `Collection.vue` 单轮启动面板 | 删除；保留 prepare、状态、历史、结果、原文、统计 |
| `prepareCollection/getCollectionStatus/getCollectionResults/getCollectionHistory/getCollectionRaw/getDatabaseStats/getCollectionFrequency/recoverCollectionFrequency/getCDPStatus/getCollectionReadiness` | `Collection.vue` 保留面板 | 保留 |
| `CollectionRuntime.vue` 与 runtime API | 线上持续采集状态卡与启停 | 保留 |
| `scripts/stop-local.ps1` | `/collection/batches`、`/collection/stop` | 改为 `/collection/runtime/stop` 并轮询 `/collection/runtime/status`，确认无 running/waiting 后退出 |
| `deploy/backend/Dockerfile` 的 `frontend/bridge-extension/manifest.json` COPY | 旧扩展配对 | 删除该 COPY |
| `frontend/tests/helpers/collectionComponent.ts` 的批次/桥接默认值 | 旧组件测试 | 删除对应默认值与 `batch` 选项 |
| `collectionConsole.test.ts`、`collectionRecovery.test.ts` 中启动/批次断言 | 旧单轮与批次 UI | 改为只验证 prepare、状态、频率、历史、原文、统计 |

## 保留的读取契约

- 历史任务：`control.get_history` 继续合并 `control-state.json` 与旧 `*collect_loop*.out.log`，字段缺失保持 `None`（前端显示 `—`）。
- 历史事件：`control.get_results` 继续只读 `data/local/collection/<run_id>.events.jsonl`；删除写入口不删除历史文件。
- 历史原文：`get_raw`/`get_recent_raw` 继续按 `jd_pool` 读取，`TALENTMIND_LOCAL_RAW` 门禁不变。
- 状态：`get_status` 继续读取 `control-state.json`；遗留的活动状态按“控制器已重启”归档为 error，不伪装为运行中。
- 频率：`get_frequency_status`/`recover_frequency` 保留跨进程账本与恢复票据。
- 准备：`prepare_browser` 只准备、不采集；`auto_start` 继续接受但忽略。
- runtime：状态/启动/停止/恢复接口与 lease、频率门禁不变。

## 实施步骤

1. 后端控制层：删除旧单轮/批次/桥接路径与不再使用的 imports；保留上面的读取、准备、频率、配置与统计函数。
2. 路由与启动：移除 `collection_bridge` 注册、旧 start/stop/batches 路由；`main.py` 移除扩展 Origin。
3. 旧采集入口：删除循环、`fetch_all`、HN/信号 fetcher 与相关测试；更新 `scripts/collect_daily.ps1` 的替代状态（删除脚本）。
4. 前端：删除批次/桥接组件、扩展、API 函数与测试；`Collection.vue` 收敛为 runtime + prepare + 状态/结果 + 历史/原文 + 统计。
5. 运维：更新 `scripts/stop-local.ps1` 与 Dockerfile；删除 `beautifulsoup4` 依赖。
6. 文档：更新 `backend/app/collect/README.md` 的退役清单与新入口说明，不重写历史记录。

## 验证

- `cd backend && .venv/Scripts/python.exe -m pytest -m "not integration" -q`，输出到临时文件只读尾部。
- `cd frontend && pnpm test && pnpm run typecheck && pnpm run build`。
- `git grep` 确认 `batch`、`bridge`、`boss_collect_loop`、`cn_collect_loop`、`collect_loop`、`fetch_all`、`fetch_hn_jobs`、`fetch_signals` 无残留代码引用（历史文档与 git 历史除外）。
- `git diff --stat` 只包含本计划文件与计划内清理文件。
- 不启动 Docker、不访问招聘站、不触发采集、不删除 `data/local` 或任何业务数据。

## 风险与说明

- 删除 `/collection/stop` 后，若存在清理前已启动的旧单轮子进程，API 不再负责停止；部署前应确认无旧任务运行。`stop-local.ps1` 只覆盖 runtime。
- 旧 `control-state.json` 中未结束的 bridge 记录不再阻止 prepare/frequency；记录本身保留为历史，不删除。
- 前端仅做离线单测/typecheck/build，不声称线上页面已人工复验。
- M1 真实采集仍暂缓；保留 runtime 与 prepare 不代表真实三站采集已通过。

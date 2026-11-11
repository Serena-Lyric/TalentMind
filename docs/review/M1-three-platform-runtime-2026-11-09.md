# M1 三平台隔离持续运行时阶段报告

日期：2026-11-09（Asia/Singapore）

依据：[Issue #79](https://github.com/Serena-Lyric/TalentMind/issues/79)。基线：`master@7e4ea38f4f251e2285f7848f690747ee012bd2a1`。分支：`codex/m1-three-platform-runtime`。

## 范围与提交

- Gate 0 A–E 浏览器对照、开源许可证/源码复用核查。
- 每平台独立频率账本、运行状态、Profile/进程/端口、worker、调度器、统一 CDP 引擎和 sink。
- BOSS 稳定身份/内容准入字段，`source_detail` 超长拒绝而非截断。
- `/collection` 三站状态、统一启动/停止和单站人工恢复。
- 三站隔离模拟、历史 RED→GREEN 映射、兼容/退役候选清单。

主要提交：`8ce062e`、`08b6f12`、`d6a726a`、`a7e1f25`、`ad98497`、`d4cc0f7`、`ee57b34`、`662f197`、`b235bdc`、`726992f`。PR：<https://github.com/Serena-Lyric/TalentMind/pull/80>。

## 验证

- 后端：`cd backend; .\.venv\Scripts\python.exe -m pytest -m "not integration" -q`
  - **2728 passed / 2 skipped / 18 deselected**。
- 前端：`cd frontend; pnpm test`
  - **293 passed / 0 failed**。
- 前端：`pnpm run build`
  - 类型检查和生产构建通过；Vite 仅保留既有大 chunk 警告。
- PR #80 当前 head 的 CI 以 GitHub checks 为准；旧 head 结果不外推。
- 隔离证据：
  - 三站模拟覆盖单条 SQLite 提交、第二轮幂等、停止/重启、BOSS blocked 后智联/猎聘继续。
  - 每平台独立频率账本并行执行测试通过；旧 flight 迁移保留 unfinished 和冷却。
  - BOSS 身份/内容字段纯函数回归通过；长来源键三类拒绝测试通过。
- 正式 MySQL/Neo4j：未连接、未写入、未删除。真实平台只执行过一次已授权的 BOSS 单次低频采集，使用隔离 SQLite；机械写入 1 行，但旧入口身份字段为 `unknown/NULL`，严格契约失败，未重试。

## Gate 0 与待实机门槛

- A 普通 Profile、B 调试启动、C 只读 CDP、D BOSS 普通＋智联 CDP、E 双 CDP 独立进程/Profile/端口均未出现站点阻断。
- B 的旧标签和 C 的城市变化保留为可比性限制，不宣称严格因果证明。
- 真实三站持续采集、正式旧账本迁移、历史身份升级、真实单次重试、独立复审与 PR 合并均未完成。
- 当前旧单轮、批次、桥接入口保留兼容；新链路通过复审并获负责人授权后才可讨论移除旧可写入口。

## 审查重点

单站阻断隔离、跨平台长动作不互锁、旧 flight 不绕过冷却、逐条提交与幂等、迟到/换页/公司冲突、`source_detail` 不静默截断，以及“执行结束”和“业务入库/拒绝”不可混淆。


## 首轮独立复审修复（2026-11-10）

固定复审 head：`5e3cb969067336657a57524e8c88f9b2c7f53611`；逐项修复如下：

| 项 | 修复 | 提交/回归 |
|---|---|---|
| P1-1 默认启动 | `config_from_payload({})` 保留默认关键词与三站城市；部分城市覆写只替换指定平台；显式空/畸形值仍拒绝；慢于默认上限的合法间隔保留 | `fa31620`；`test_collection_runtime_config.py`、ASGI 空 `{}` 启动、前端默认 `{}` 请求 |
| P1-2 BOSS 真采身份 | `fetch_boss_jobs.run_fetch` 将已验证详情 URL 作为独立参数传给 `normalize_boss_job` | `e922318`；合成 CDP + 隔离 SQLite 保存后读回 `verified/True` |
| P1-3 分页游标 | BOSS/智联入口新增 `start_page`；`CdpEngine` 把 worker 页码作为单页起点传递 | `6b42b7e`；引擎参数、BOSS/智联实际 URL 指定页测试 |
| P1-4 检查点/回执 | `scheduler.start` 保留既有游标、`next_run_at`、最后保存身份与统计；blocked/needs_login/failed 不自动清除；`last_saved_identity` 只接受 persisted inserted/updated/skipped 回执 | `d38218c`；调度器重启、无保存事件、三类回执测试 |
| P1-5 旧账本门禁 | `frequency.assert_legacy_migrated` 下沉到真实预约底层；旧单轮、批次、bridge 创建入口提前 fail closed | `e1f3af8`；unfinished/cooldown 底层测试及三入口测试 |
| P1-6 跨入口互斥 | 新增 `runtime/lease.py`，每平台 writer lock；runtime 三 worker、旧 control/batch、bridge 统一占用；PID+创建时间识别 stale lock | `1f34174`；lease 单测、runtime↔旧单轮、runtime↔bridge 双向抢占 |
| 次要契约 | 页面/组合间隔只校验有限值与硬下限，不再把默认 30/720 秒当绝对上限 | `fa31620`；慢配置正例 |

新增测试只使用临时文件、合成 CDP/worker 和隔离 SQLite；没有新增真实站点采集、正式库写入/删除或迁移。真实 BOSS 单次重试仍未执行。


## 第二轮独立复审修复（2026-11-10）

复审 head：`745b6f17edacfe53cfe349db6f0f0725b12d260e`。新增问题与修复：

| 项 | 修复 | 回归 |
|---|---|---|
| P1-A writer.lock 空文件竞争 | 改为原子目录获取 + `owner.json` 原子替换；owner 缺失/损坏 fail closed，不当作 stale；stale 目录先原子改名再清理 | `test_two_processes_cannot_both_publish_writer_lock`、`test_incomplete_lock_record_fails_closed_and_is_not_deleted` |
| P1-B lease 绑定 API PID | scheduler/control 在子进程启动后 `lease.rebind` 到实际 worker 根 PID；scheduler 使用 `worker_process.spawn/stop`，终止失败不释放、不标 stopped；新后端可从 scheduler.json 恢复并确认退出后回收 worker-owned lease | `test_scheduler_binds_runtime_lease_to_spawned_worker_pid`、`test_new_backend_can_stop_restored_worker_and_release_worker_owned_lease`、`test_stop_fails_closed_when_worker_termination_is_unconfirmed` |
| P1-C Stop→Start 绕过受限门禁 | stop 保留 blocked/needs_login/failed 状态，不再覆盖为 stopped；start 继续拒绝，必须显式恢复 | `test_stop_preserves_manual_gate_and_start_rejects` |
| P2 计划/游标错位 | scheduler.json stop 时保留 config；空 payload 启动复用原计划；显式配置变化且已有游标时要求 `reset_checkpoint` | `test_custom_config_stop_start_empty_reuses_stored_plan` |

所有验证仍使用临时文件、合成进程/CDP 与隔离 SQLite；真实站点重试、正式库操作、迁移和合并仍未执行。


## 第三轮独立复审定向修复（2026-11-11）

复审起点：`b7065624e10e78fb20968c7281a604b4a939d5f3`。代码与回归提交：`c72cbce`。

| 项 | 修复 | RED→GREEN 回归 |
|---|---|---|
| P1-1 stale lock 回收竞态 | 每个平台 lease 的 acquire/rebind/release/release_if_dead 在 OS sidecar 锁和进程内互斥下执行；回收前复核 owner token。旧 Lease 不能移除新 owner。 | `test_two_processes_cannot_reclaim_the_same_stale_writer_lock`、`test_stale_release_cannot_remove_a_new_owner` |
| P1-2 Windows worker 树接管 | worker 使用具名 Job Object，名称写入 scheduler.json 和 lease owner；恢复端重开 Job、终止并等待所有成员。无可验证句柄时 fail closed；停止未确认时不释放 lease。 | `test_restored_scheduler_stops_real_child_before_releasing_writer`、`test_restored_scheduler_fails_closed_without_process_tree_handle`、`test_stop_keeps_runtime_lease_when_scheduler_cannot_restore_worker` |
| P1-3 单站门禁隔离 | start 保留受限站的状态与 STOP，只跳过该站并启动其他可运行站；受限站仍需显式恢复。即使受限 worker 尚在进程表中，也不会创建第二个该站 worker。无法取得已有 lease 时，resume 不会清除 STOP/人工门禁。 | `test_start_skips_platform_that_needs_manual_recovery`、`test_stop_preserves_manual_gate_and_start_skips_restricted_platform`、`test_resume_keeps_manual_gate_when_worker_lease_has_no_restorable_process` |
| P2 计划/checkpoint 不匹配 | checkpoint 存在但 scheduler.json 缺失、缺 config 或损坏时，start/resume 不再猜默认计划；先通过 start 显式 reset_checkpoint 才能复位游标。 | `test_start_requires_checkpoint_reset_when_saved_plan_is_missing`、`test_start_requires_checkpoint_reset_when_scheduler_json_is_corrupt`、`test_explicit_checkpoint_reset_allows_default_plan_when_config_is_unavailable`、原 `test_custom_config_stop_start_empty_reuses_stored_plan` |

### 验证

- Windows 本机四个定向测试文件：`python -m pytest tests/test_collection_runtime_lease.py tests/test_collection_runtime_scheduler.py tests/test_collection_worker_process.py tests/test_collection_worker_restore_windows.py -q` → **38 passed**。
- M1 控制、bridge、batch、frequency、runtime 扩展回归 → **323 passed / 6 deselected**。排除的 6 项在缺少本地服务配置时导入 `app.db.mysql`/`app.main`，需读取缺失的 Settings 字段。
- 全后端 `python -m pytest -m "not integration" -q` 在 collection 阶段遇到 15 个配置错误：当前检出没有所需的本地 `mysql_url`、Neo4j、Redis 和 LLM 配置；未设置占位值、未连接任何数据库。
- `git diff --check` 通过。所有新增进程测试只启动本地合成 wrapper/child；未访问招聘站、未连接或写入正式数据库、未迁移数据。

扩展 M1 集合明确排除的测试为 `test_get_recent_raw_returns_latest_rows`、`test_control_api_pairing_list_detail_and_verification_stop`、`test_database_failure_is_unknown`、`test_database_quality_and_latest_cover_all_platforms`、`test_raw_adds_requirements_and_preserves_stored_duties`、`test_raw_reads_identity_metadata_from_migrated_schema`。全后端 collection 错误同样来自上述缺失 Settings，不是测试执行失败。

### 遗留边界

升级前已经存在且没有 `job_name` 的 Windows worker lease 无法证明子进程树是否已退出，代码会保留该 lease 并阻止同平台新写入，需要人工处理旧运行态。PR #80 仍需独立复审；未合并、未运行真实采集或正式库操作。


## 第四轮 P2 定向修复（2026-11-11）

第四轮 Review 固定 head 为 `61128e19ab243dc3f9c8a03898b232cb5ee5ec54`，确认此前四项缺陷已通过，并指出“全站受限 + 计划缺失/损坏 + 非零 checkpoint”使显式复位不可达。本轮只修此 P2，并按行内意见修正部分启动提示。

| 项 | 修复 | 回归 |
|---|---|---|
| 全受限时复位不可达 | `start(reset_checkpoint=true)` 在“无可运行站”拒绝之前执行本地复位；先确认无运行 worker/state，再取得全部三站 writer lease；计划可信时沿用，否则写入默认计划；保留 `status`、`stop_reason`、STOP，不 spawn worker、不做数据库就绪/频率预检 | ASGI API + 临时 SQLite 覆盖旧格式/损坏计划、复位后逐站 resume 可达、缺少显式 reset 时 start/resume 继续拒绝、存活 lease 阻止复位 |
| 部分启动提示过宽 | 前端按返回状态报告实际启动 worker 数及仍待人工处理的平台；全站受限时提供确认后的本地复位入口 | `collectionRuntime.test.ts` 覆盖全站复位按钮与部分启动提示 |

### 本轮验证

- `python -m pytest tests/test_collection_runtime_api.py tests/test_collection_runtime_browser.py tests/test_collection_runtime_config.py tests/test_collection_runtime_lease.py tests/test_collection_runtime_scheduler.py tests/test_collection_runtime_state.py tests/test_collection_runtime_three_sites.py tests/test_collection_runtime_worker.py tests/test_collection_worker_process.py tests/test_collection_worker_restore_windows.py -q`：**68 passed**。用例使用临时 SQLite、合成进程和本地 ASGI API；未访问招聘站或正式数据库。
- `pnpm test`：**295 passed**。
- `pnpm run build`：类型检查和生产构建成功；Vite 报告 chunk 超过 500 kB（`GraphPanorama` 与主 bundle）。
- `git diff --check`：通过。

全后端测试、本地 Windows Job Object 实机用例和真实三站试采未在本轮运行；未访问正式 MySQL/Neo4j、未迁移数据库、未合并 PR。PR #80 与 Issue #79 保持打开，等待新 head 独立复审。


## 第五轮 P2 严格复位标志类型（2026-11-11）

第五轮独立 Review 确认第四轮全站受限复位缺口已通过，并指出 `bool(payload.get("reset_checkpoint"))` 会把非空字符串及其他 truthy JSON 值当作明确授权，可能静默清除本地进度。本轮只收紧此参数，不调整先前复位路径或 UI 可用性范围。

- `scheduler.start` 现在只接受原生 `bool`；缺省与 `false` 保持普通启动语义，字符串、数字、数组、对象和 `null` 在读取/修改状态之前拒绝。
- ASGI + 临时 SQLite 用例覆盖有效/损坏计划、非零 checkpoint、无效类型状态零修改；原生 `false` 的正常启动与损坏计划 fail-closed 路径、原生 `true` 的复位均有回归。

### 本轮验证

- `python -m pytest tests/test_collection_runtime_api.py tests/test_collection_runtime_browser.py tests/test_collection_runtime_config.py tests/test_collection_runtime_lease.py tests/test_collection_runtime_scheduler.py tests/test_collection_runtime_state.py tests/test_collection_runtime_three_sites.py tests/test_collection_runtime_worker.py tests/test_collection_worker_process.py tests/test_collection_worker_restore_windows.py -q`：**86 passed**。
- `git diff --check`：通过。
- 本轮未改前端；未访问招聘站、未连接正式数据库、未运行数据库迁移。全后端本地套件未运行，本机缺少服务配置且未使用占位配置。

PR #80 与 Issue #79 保持打开，等待新 head 独立复审；未合并。

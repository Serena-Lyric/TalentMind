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
  - **2718 passed / 2 skipped / 18 deselected**。
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

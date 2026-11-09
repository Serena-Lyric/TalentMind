# M1 三平台隔离持续运行时阶段报告

日期：2026-11-09（Asia/Singapore）

依据：[Issue #79](https://github.com/Serena-Lyric/TalentMind/issues/79)。基线：`master@7e4ea38f4f251e2285f7848f690747ee012bd2a1`。分支：`codex/m1-three-platform-runtime`。

## 范围与提交

- Gate 0 A–E 浏览器对照、开源许可证/源码复用核查。
- 每平台独立频率账本、运行状态、Profile/进程/端口、worker、调度器、统一 CDP 引擎和 sink。
- BOSS 稳定身份/内容准入字段，`source_detail` 超长拒绝而非截断。
- `/collection` 三站状态、统一启动/停止和单站人工恢复。
- 三站隔离模拟、历史 RED→GREEN 映射、兼容/退役候选清单。

主要提交：`8ce062e`、`08b6f12`、`d6a726a`、`a7e1f25`、`ad98497`、`d4cc0f7`、`ee57b34`、`662f197`（文档提交见本报告所在提交）。

## 验证

- 后端：`cd backend; .\.venv\Scripts\python.exe -m pytest -m "not integration" -q`
  - **2687 passed / 2 skipped / 18 deselected**。
- 前端：`cd frontend; pnpm test`
  - **293 passed / 0 failed**。
- 前端：`pnpm run build`
  - 类型检查和生产构建通过；Vite 仅保留既有大 chunk 警告。
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

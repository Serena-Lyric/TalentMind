# M1 交接

M1 数据采集模块交接区。

**已产出（2026-08-17 重新导出）**：
- `jd.json`：200 条清洗后 JD（quality 降序；**source=linkedin + source_detail=linkedin_job_postings，D38 来源标签**）
- `quality_check.md`：质量分/去重抽样核对记录（10 条抽样已由 AI 基于数据标注：10/10 通过，2026-08-16；另含 archive 全部 11 个数据集抽检记录）
- `接口自述.md`：只产文件、无对外接口（D19）

正式实现位于 `backend/app/collect/`；signal 已通过 GitHub Trending/博客 RSS 采集并入库（2026-08-22 核验为 610 条：github 150、blog 460，6 天时间序列；详见 `backend/app/collect/README.md`）。

## BOSS 专项交接（2026-08-20）

- `boss-collection-handover-20260820.md`：BOSS 求职端“我要投职”人工登录 + Edge CDP 9333 扩大采集的命令、数据库核验、测试结果、合规约束和注销待办。
- 当前（2026-08-22）`jd_pool=126266`，其中 `source=boss=621`（linkedin 123849、hn 1796）；archive `postings.csv` 的 123849 条有效岗位已全部导入。BOSS 低速循环当前仍在运行，已完成第 116 轮并累计新增 133 条；不要把历史首轮 `boss=151` 或扩大批次结束时的 `boss=470` 误认为当前总量。详细快照见 `collection-status-20260822.md`。

## BOSS 前端控制资料包（2026-08-21）

- `boss-frontend-control-pack-20260821/`：面向前端的 BOSS 采集启动、停止、状态机、进度字段、控制语义、数据口径和联调待确认问题资料包；不含源码、环境密钥、真实简历或本地运行数据。
- 当前运行核验（2026-08-22）：BOSS 父/工作进程 PID `33828/26124` 均存活，低速循环已完成第 116 轮；9333 端口可用，日志错误为空。单轮 `--once` 记录仍保留在资料包中，属于 2026-08-21 历史核验。

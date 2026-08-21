# M1 交接

M1 数据采集模块交接区。

**已产出（2026-08-17 重新导出）**：
- `jd.json`：200 条清洗后 JD（quality 降序；**source=linkedin + source_detail=linkedin_job_postings，D38 来源标签**）
- `quality_check.md`：质量分/去重抽样核对记录（10 条抽样已由 AI 基于数据标注：10/10 通过，2026-08-16；另含 archive 全部 11 个数据集抽检记录）
- `接口自述.md`：只产文件、无对外接口（D19）

正式实现位于 `backend/app/collect/`；signal 已通过 GitHub Trending/博客 RSS 采集并入库（2026-08-21 核验为 485 条：github 114、blog 371；详见 `backend/app/collect/README.md`）。

## BOSS 专项交接（2026-08-20）

- `boss-collection-handover-20260820.md`：BOSS 求职端“我要投职”人工登录 + Edge CDP 9333 扩大采集的命令、数据库核验、测试结果、合规约束和注销待办。
- 当前 `jd_pool=126133`，其中 `source=boss=488`（linkedin 123849、hn 1796）；其中 archive `postings.csv` 的 123849 条有效岗位已全部导入，BOSS 的持续循环当前未运行。下一个 Agent 先读该文件，不要把历史首轮 `boss=151` 或扩大批次结束时的 `boss=470` 误认为当前总量。

## BOSS 前端控制资料包（2026-08-21）

- `boss-frontend-control-pack-20260821/`：面向前端的 BOSS 采集启动、停止、状态机、进度字段、控制语义、数据口径和联调待确认问题资料包；不含源码、环境密钥、真实简历或本地运行数据。
- 当前启动核验：单轮 `--once` 正常完成，`listed=12/details=8/new=0/skipped=12`；当前无持续采集进程，9333 端口可访问且有 BOSS 页面目标。

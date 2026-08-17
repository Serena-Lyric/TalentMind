# M1 交接

M1 数据采集模块交接区。

**已产出（2026-08-17 重新导出）**：
- `jd.json`：200 条清洗后 JD（quality 降序；**source=linkedin + source_detail=linkedin_job_postings，D38 来源标签**）
- `quality_check.md`：质量分/去重抽样核对记录（10 条抽样已由 AI 基于数据标注：10/10 通过，2026-08-16；另含 archive 全部 11 个数据集抽检记录）
- `接口自述.md`：只产文件、无对外接口（D19）

正式实现位于 `backend/app/collect/`；`signal`（P1）未做。

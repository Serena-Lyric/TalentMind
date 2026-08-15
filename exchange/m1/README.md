# M1 交接

M1 数据采集模块交接区。

**已产出（2026-08-15）**：
- `jd.json`：200 条清洗后 JD（quality 降序，来自 postings.csv 5000 行导入；jd_pool 现 5003 条 cleaned）
- `quality_check.md`：质量分/去重抽样核对记录（10 条待 A 补填结论）
- `接口自述.md`：只产文件、无对外接口（D19）

正式实现位于 `backend/app/collect/`；`signal`（P1）未做。

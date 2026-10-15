# M2 标准交接（原回包 2026-09-01，演示基线 2026-09-05）

交接最初来自仓库根 `input/岗位数据-新一代与现有/`，标准化后已按演示提交调整。2026-10-15 文件计数：

- `job_definition.json`：717 条岗位定义（新一代 342、现有 375）；
- `job_skill.json`：717 条按 M2 `job_id` 合并后的技能明细；
- `job_change_log.json`：275 条日志，保留 `object_type/source_jd_time`，含 32 条演示日志；
- `job_definition_zh.json`：717 条兼容展示快照；
- `m2-full-return-20260902.md`：历史导入摘要，原回包为 719/719/243（技能原始拆分文件 723 条），不当作当前文件计数。



说明：完整回包中的 3 条 `object_type=job` 变更日志无法关联到 719 条定义，导入时保留在 `job_change_log` 并将 `job_id` 置空、原值写入 `m2_job_id`；这不是静默丢弃。

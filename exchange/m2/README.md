# M2 完整回包（2026-09-01 生成，2026-09-02 导入）

当前交接产出来自 `input/岗位数据-新一代与现有/`，已标准化复制到本目录：

- `job_definition.json`：719 条岗位定义（新一代 344、现有 375）；
- `job_skill.json`：719 条按 M2 `job_id` 合并后的技能明细（原始拆分文件共 723 条）；
- `job_change_log.json`：243 条能力更新日志，保留 `object_type/source_jd_time`；
- `job_definition_zh.json`：719 条兼容展示快照；
- `m2-full-return-20260902.md`：导入摘要。



说明：完整回包中的 3 条 `object_type=job` 变更日志无法关联到 719 条定义，导入时保留在 `job_change_log` 并将 `job_id` 置空、原值写入 `m2_job_id`；这不是静默丢弃。

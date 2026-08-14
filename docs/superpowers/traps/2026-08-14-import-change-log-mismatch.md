# 陷阱：job_change_log 导入的 DDL 字段与 M2 产出语义不一致（潜伏于空数据）

- 日期：2026-08-14
- 症状：`import_all()` 在 job_change_log 为空时全部通过；M2 产出非空 change_log 时导入必然失败（`object_type` 列不存在 / `job_id` 类型不符 / `change_type` 超长 1406）。
- 根因：
  1. `import_exchange.py::import_change_logs` 的 INSERT 含 `object_type` 列，但 DDL `job_change_log` 无此列（M2 differ 模型有 object_type，导入层照搬未核对）。
  2. M2 产出的 `job_id` 是 job_name（字符串），DDL 语义是 job_definition.id（BIGINT），按 job_id 的 delete/insert 均不匹配。
  3. `change_type VARCHAR(16)` 装不下 D32 扩展枚举 `scenarios_removed`/`evolution_changed`（17 字符），MySQL `STRICT_TRANS_TABLES` 报 `ERROR 1406`。
- 修复：
  1. `import_change_logs` 去掉 object_type；导入前把 job_name 解析为 job_definition.id（解析不到跳过）；改为全量重建。
  2. 新增集成测试 `test_import_change_logs_job_name_resolution`（含 object_type 字段样例 + 不可解析名）。
  3. change_type 列宽问题记录为决策跟踪 P4，通知全队后扩容（本陷阱修复未改 DDL）。
- 教训：
  1. 空数据路径不执行 INSERT，SQL 字段不匹配不会暴露——改导入层必须对照 DDL 逐列核对，并用非空样例测试。
  2. 交接字段语义（job_name vs id）要在契约层对齐；A 集成层负责映射并留测试。

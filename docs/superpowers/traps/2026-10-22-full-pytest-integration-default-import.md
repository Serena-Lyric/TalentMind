# 裸跑 pytest 触发默认全量导入

## 症状

后端使用裸 `pytest -q` 跑完整套件后，正式 MySQL 的分析层由 `job_definition/job_skill/job_change_log=717/717/275` 变为 `719/719/243`。`jd_pool`、signal、skill_dict、Neo4j 未变化，但分析层与 Neo4j 的 717 Job 基线出现不一致。

## 根因

`pytest -q` 默认也执行 `@pytest.mark.integration`。`test_integration_mvp.py::test_import_exchange_idempotent` 调用了 `import_all()`；该函数默认读取 `input/岗位数据-新一代与现有/`，整表删除并重建分析层。测试名称中的“幂等”只验证重复结果相等，不能保护当前正式数据。

## 修复

新增 `backend/tests/conftest.py`：默认给所有 integration item 添加 skip。只有显式设置 `TALENTMIND_ALLOW_INTEGRATION=1`，且人工核对目标是隔离实例后，才允许执行。核验命令在未授权时得到 `24 skipped / 1529 deselected`。

## 后续恢复边界

- 已保存事故后三表私有 dump：`data/local/phase1-acceptance-20261022/analysis-after-accidental-integration-20261021T175645Z.sql`。
- `data/local/talentmind-db-full-20260904.sql` 在临时 MySQL 验证为 `jd_pool=2984 / 717 / 717 / 275`；当前原始层为 2988 且 checksum 与采前一致，因此不能整库回灌。
- 若用户批准恢复，应从该已恢复验证的快照只选择性恢复三张分析表，并在临时实例预演；不得删除或重灌 `jd_pool`。

## 教训

“完整测试”不等于“所有标记都执行”。包含真实服务写入的测试必须默认安全关闭；不能依赖测试名、文档提醒或运行者记忆来保护正式库。

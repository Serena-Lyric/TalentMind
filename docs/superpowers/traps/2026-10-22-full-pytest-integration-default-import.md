# 裸跑 pytest 触发默认全量导入

## 症状

后端使用裸 `pytest -q` 跑完整套件后，正式 MySQL 的分析层由 `job_definition/job_skill/job_change_log=717/717/275` 变为 `719/719/243`。`jd_pool`、signal、skill_dict、Neo4j 未变化，但分析层与 Neo4j 的 717 Job 基线出现不一致。

## 根因

`pytest -q` 默认也执行 `@pytest.mark.integration`。`test_integration_mvp.py::test_import_exchange_idempotent` 调用了 `import_all()`；该函数默认读取 `input/岗位数据-新一代与现有/`，整表删除并重建分析层。测试名称中的“幂等”只验证重复结果相等，不能保护当前正式数据。

## 修复

新增 `backend/tests/conftest.py`：默认给所有 integration item 添加 skip。只有显式设置 `TALENTMIND_ALLOW_INTEGRATION=1`，且人工核对目标是隔离实例后，才允许执行。核验命令在未授权时得到 `24 skipped / 1529 deselected`。

后续复核确认，测试标记与环境变量只能防止默认收集，不能证明实际连接目标安全。新增 `backend/app/integration/destructive_guard.py`：

- MySQL 破坏性入口按实际 `@@hostname`、`@@server_uuid`、`DATABASE()`、端口和版本生成目标指纹；
- Neo4j 清图入口按实际 `db.info()`、服务组件和脱敏 URI 生成目标指纹；
- 每次操作还必须匹配独立授权文件中的 `operation`、完整目标、指纹和有效期；`TALENTMIND_ALLOW_INTEGRATION=1` 单独存在也不会放行。

2026-10-22 事故审计进一步确认：`skill_dict` 虽仍为 285 行，但 285 个主键全部后移 570；`job_definition`/`job_skill` 新增原回包中的两个已删除岗位；`job_change_log` 删除 32 条演示记录。`jd_pool`/`talent_raw` 行内容未变，但测试夹具插入后清理使 `AUTO_INCREMENT` 分别前移 3 和 2，行数相等不能证明没有副作用。

## 后续恢复边界

- 已保存事故后三表私有 dump：`data/local/phase1-acceptance-20261022/analysis-after-accidental-integration-20261021T175645Z.sql`。
- `data/local/talentmind-db-full-20260904.sql` 在临时 MySQL 验证为 `jd_pool=2984 / 717 / 717 / 275`；当前原始层为 2988 且 checksum 与采前一致，因此不能整库回灌。
- 若用户批准恢复，应从该已恢复验证的快照只选择性恢复三张分析表，并在临时实例预演；不得删除或重灌 `jd_pool`。

## 2026-10-22 正式恢复结果

用户另行批准后，已改用以 2026-10-21 八表摘要确认一致、来自 2026-10-17 冷卷的四表转储，在冻结写入并完成新全库/四表/卷级冷备及隔离恢复验证后，仅恢复 `skill_dict/job_definition/job_skill/job_change_log`。正式库当前为 `285/717/717/275`，其余四表内容未变；未调用 `import_all()`，未重建 Neo4j，未执行身份字段 DDL。完整证据见[正式恢复最终报告](../../review/P0-formal-restore-final-2026-10-22.md)。

## 教训

“完整测试”不等于“所有标记都执行”。“幂等”也不等于无损。包含真实服务写入的测试必须默认安全关闭；不能依赖测试标记、环境变量、测试名、行数、文档提醒或运行者记忆来保护正式库。破坏性入口必须验证实际目标并要求独立、绑定目标指纹的显式授权。

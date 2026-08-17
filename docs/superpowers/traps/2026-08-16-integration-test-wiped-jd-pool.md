# 陷阱：集成测试误删 jd_pool 生产数据（2026-08-16）

## 症状
- 文档记录 MySQL `jd_pool` 为 **5003 条 cleaned**（postings.csv 导入 5000 行，2026-08-15），实际查询只有 **3 条**，且全部是测试夹具行（`AI应用工程师` / `后端工程师` / `Mixed Batch JD`）。
- `talent_raw` 记录 2 条，实际是测试夹具行（`octocat` / `mixed_batch_user`）。
- `SHOW TABLE STATUS` 显示 jd_pool `Auto_increment=110832`、表 `Create_time=2026-08-15 02:32:41`：表曾经历约 11 万次插入后被大量删除（DELETE 不重置自增）。

## 根因
- `backend/app/collect/fetchers/dataset.py` 把 postings.csv 导入的 `source` 硬编码为 `"dataset"`，与旧 dataset 数据同源标签。
- `backend/tests/test_collect_integration.py` 测试开头执行 `DELETE FROM jd_pool WHERE source='dataset'`（无精确夹具过滤），且无 finally 清理 → **跑一次 `pytest -m integration` 就把全部 source='dataset' 的生产行（5003 条）删光**，只留下测试自插的 2 条；另一测试再插入 1 条 `Mixed Batch JD`。
- `test_talent_pipeline_integration.py` 同样用 `DELETE FROM talent_raw WHERE source='github'` 的宽泛条件，存在同样风险。

## 修复
1. 测试清理改为**按测试夹具特征精确删除**（`job_title IN (...)` / `identity_hint=:h` / 唯一 reason 标记），并把清理放进 `finally`（断言失败也不残留）：
   - `backend/tests/test_collect_integration.py`
   - `backend/tests/test_talent_pipeline_integration.py`
   - `backend/tests/test_integration_mvp.py`（CRUD/import/change_log 清理全部进 finally）
2. 清库（删除 5 条测试残留）后，从 `docs/originalfile/archive/postings.csv` 重新导入 5000 行（`jd_pool=5000 cleaned`，quality 0.14–1.0 / 均值 0.757 / 4548 个 dup 分组）。
3. 新增决策 D37：测试数据自动清理与验证规范（AGENTS.md「测试数据清理」、CLAUDE.md 铁律 5、资产与状态维护规则 5、笔记全队通知 12）。
4. 跑完 23 个集成测试后**核查数据库**：测试夹具行全部为 0、`jd_pool` 5000 条完好、分析层 285/22/22/0 不变。

## 教训
- **禁止在测试里按宽泛条件（source 等）DELETE**；测试清理必须能精确圈定自己创建的数据，并放入 finally/teardown。
- **跑完集成测试后必须查询 DB 验证测试数据已真实清理**（D37），不能只看测试通过。
- 同一来源标签（dataset）会同时覆盖生产与测试数据时，删除条件必须带夹具特征；否则一次测试运行就是一次数据事故。
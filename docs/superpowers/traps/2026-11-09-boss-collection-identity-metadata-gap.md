# BOSS 单次采集机械成功但身份字段为空

## 症状

2026-11-09 使用现有 `fetch_boss_jobs.run_fetch` 对 BOSS 做单页、单关键词/城市、最多 1 条详情、15 秒动作间隔的隔离实测：列表 16 条，最终 `listed=1`、`detail_attempted=1`、`detail_obtained=1`、`inserted=1`，隔离 SQLite 可读回 1 行；但该行 `identity_status=unknown`、`content_eligible=null`。机械采集成功，端到端契约不能算通过。

## 根因

`normalize_boss_job()` 只生成正文和来源 URL，没有把 canonical BOSS 详情 URL 与正文准入写入 `RawJD.identity_status/content_eligible/identity_evidence`。下游因此只能看到一条“已插入但身份未知”的观察。另有一个风险：旧代码将 `source_detail` 静默截到 128 字符，长 URL 可能错误合并。

## 修复

- BOSS 列表 URL 与详情 URL canonical 后相等、详情正文非空时写入 `verified`、`content_eligible=True` 和可审计 evidence。
- `source_detail` 超过 128 字符时拒绝该观察，不再截断。
- 新运行时通过注入的隔离 SQLite provider 走同一 pipeline/repository；缺身份列时继续 fail closed。
- 回归：`backend/tests/test_boss_fetcher.py::test_boss_normalization_records_verified_detail_identity`、`test_boss_normalization_rejects_overlong_source_detail`。

## 教训

“有正文并插入成功”不等于“身份和内容准入已记录”。统计、正文、稳定身份和提交回执必须分别可验证；单次实测失败不能通过事后修改行或降低身份门禁来补成成功。真实重试需另行授权。

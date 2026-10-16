# B3-5 候选目录与人工准入 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 实现 Issue #18 已确认的八类候选初稿、离线审核与准入结构契约，正式目录保持零条。

**Architecture:** 独立 `canonical_catalog/`，只追加 c35 表，复用 AnalysisStore(recover=False)、严格 JSON、摘要和原子发布。候选快照、审核、release manifest 和导出各自不可变；生产授权由逐项用户确认与受控 PR 合并完成，CLI 不认证身份。非合成 manifest 只生成待授权发布提案；合成模式可模拟 admitted，但不写正式 release。

**Tech Stack:** Python、Pydantic、SQLite、pytest；无新依赖。

**Spec:** [Issue #18](https://github.com/Serena-Lyric/TalentMind/issues/18)（产品描述已由用户明确确认并要求实施）。不重复请求已有授权。

## Global Constraints

- 最新 master `26c51346e71462d3e53cd58f69ed8d8f5aecdff6`，独立分支和工作树；不自动合并或删除。
- 追加 M2-52～60 / D91～99；旧 family v1/v2/v3、旧审核、报告、输入、DDL 字节不改。
- 所有候选定义/别名未获逐项确认，均 unconfirmed；正式 release 空。
- 不要求真实 JD 作为首次准入前置，不分类 JD、不计算人数/统计/熟练度，不启动 B4。
- 全部测试纯合成、临时文件自动清理，父/子进程阻网，不读取旧 .env。

## Review Focus

- 同名跨类不合并，同类重名/别名冲突保守拒绝；职责不同但共用工具不合并。
- 审核必须绑定完整候选定义、目录快照、具名审核和原始来源；字符串不认证人。
- 修改定义、family、别名、边界或规则版本后必须重新审议，旧批准不可搬用。
- 发布输出故障与硬退出必须可恢复；提交前整轮回滚，提交后旧字节重放。
- 旧六种报告、七/八类历史与 A running 状态共库不受新层影响。

### Task 1: 契约与八类候选

**Files:** `backend/app/job_analysis/canonical_catalog/models.py`、`candidates.v1.json`、`release.empty.v1.json`；`backend/tests/test_job_analysis/test_canonical_catalog.py`；产品决策与索引。

**Interfaces:** `validate_catalog(value, source_root) -> (catalog, frozen_sources)`；Source 使用相对路径、完整原字节 SHA-256 和精确引文，不推断语义。

- [x] 写八类覆盖、不等量、稳定 ID、职责/成果/排除项/相邻边界/来源及 unconfirmed 测试；缺字段、错来源、重复与跨类同名测试。
- [x] 运行专项，确认缺模块/资产导致 RED。
- [x] 最小严格 schema 与来源校验，追加九条规则及候选草案；运行 GREEN。

### Task 2: 不可变生命周期与 CLI

**Files:** 同包 `store.py`、`runner.py`、`__main__.py`；`backend/tests/test_job_analysis/test_canonical_catalog_storage.py`。

**Interfaces:** `execute(store, catalog_path, source_root, revision, output)` 保存快照；`review(store, snapshot_id, event_path, source_root)` 追加审核；`export(store, snapshot_id, manifest_path=None, source_root=None, output=None)` 冻结审核截面/验证发布提案；`replay(store, artifact_id)` 校验并重放。

- [x] 写具名审核、版本/来源、拒绝/延期/再审、独立 manifest、合成完整状态机及非合成不准入的 RED。
- [x] 实现 c35 追加表和触发器，绑定依赖摘要/原始文件字节，逐轮事务及原子输出，运行 GREEN。
- [x] 写 CLI run/review/export/replay、硬退出、输出故障、旧混合历史恢复和防覆盖 RED，再最小实现并 GREEN。

### Task 3: 回归与交审

**Files:** M2 README、docs 导航、资产状态、`docs/review/M2-stage-B3-5.md`、必要 traps。

- [x] 父/子进程阻网执行完整非集成测试，报告 passed/skipped/deselected/连接尝试及临时清理。
- [x] 独立只读 reviewer 审查并对阻塞项 RED→GREEN 修复，核查 diff/字节保全。
- [ ] 提交明确文件、推送独立分支、创建关联 Issue #18 的 PR，附报告并验证未合并/未自动合并。

## 执行记录

- 已核对原工作树资产文档为用户未提交修改，实施仅在新工作树。Issue 提供完整已确认产品描述，本计划细化工程，不新增产品裁决。

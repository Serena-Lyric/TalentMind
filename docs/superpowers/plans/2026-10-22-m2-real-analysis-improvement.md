# M2 真实岗位能力分析改进实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复真实中文 JD 中可复现的 B1/B2/B3 分析缺口，并为现有 M2 页面补上可持久化、可导出的人工复核闭环。

**Architecture:** 继续使用现有 B1→B2→B2.2→B3 产品编排和独立 SQLite。规则只增加有明确原文证据的有限关系；产品工作流只追加审核事件和版本对照能力，不重建系统，不触碰正式分析表。

**Tech Stack:** Python 3.14、FastAPI、Pydantic、SQLite、pytest、Vue 3、TypeScript、Element Plus、Node test runner。

**Spec:** `docs/superpowers/specs/2026-10-22-m2-real-analysis-improvement-design.md`

## Global Constraints

- 简体中文交付；保留用户工作树和其他工作树。
- 分支从最新 `origin/master` 创建，分支名 `codex/m2-real-analysis-20261022`。
- 不运行 `import_all()`、`import_graph()`、正式 DDL、正式批量分析或真实采集。
- `jd_pool` 仅通过既有只读事务读取；新产物只写 `data/local/` 或仓库外隔离目录。
- integration 测试默认跳过；任何写库集成测试必须有独立目标授权文件，且本轮不执行。
- 人工审核只能由用户在页面填写，不能由实现或测试自动生成真实签署。
- 没有人工真值时不得计算真实 precision/recall，不得把规则覆盖称为准确率。
- 每次新增或移动资产、改变契约、完成阶段后，同步 README、资产状态和阶段报告。

## Review Focus

- 内联章节标题：同一行 `岗位职责` 后接 `任职要求` 时，不得把要求句误归为职责。
- 条件污染：一个“若/针对/公司/以上”片段不得使整份 JD 的所有技能陈述失效。
- 组合语义：`至少一种`、`任选其一`、`和/及` 不得被拆成相互独立且全部必备的技能。
- 证据身份：跨字段去重后，保留的字段、字符区间和原文必须仍能精确回切冻结输入。
- 人工与机器分账：机器重放、人工接受/拒绝和未审核必须分别计数，不能改写原报告。

---

### Task 0: P0 隔离对象收尾

**Files:**
- No tracked file changes in this task; evidence is recorded in the final stage report.

**Interfaces:**
- Consumes: P0 final restore reports under `docs/review/`.
- Produces: removal evidence for the three named exited containers and their three named volumes only.

- [ ] **Step 1: Inspect each named container's full ID, exit code, port binding, image digest and volume**
- [ ] **Step 2: Verify no undefined container references the three target volumes**
- [ ] **Step 3: Recompute the external P0 backup hashes and verify every file listed in `SHA256SUMS.txt`**
- [ ] **Step 4: Remove only the three verified containers by full ID**
- [ ] **Step 5: After containers disappear, remove only the three verified volumes by exact name**
- [ ] **Step 6: Verify the formal MySQL, Neo4j, Redis, backend and frontend remain available; record the exact check and actual access path**

### Task 1: 移植独立安全基线

**Files:**
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_integration_guard.py`
- Create: `backend/app/integration/destructive_guard.py`
- Create: `backend/tests/test_destructive_guard.py`
- Modify: `backend/app/integration/import_exchange.py`
- Modify: `backend/app/integration/import_graph.py`
- Modify: `backend/app/integration/README.md`
- Create: `docs/superpowers/traps/2026-10-22-full-pytest-integration-default-import.md`

**Interfaces:**
- Produces: `require_mysql_destructive_authorization(operation: str, session: Session, *, authorization_file=None) -> dict`
- Produces: `require_neo4j_destructive_authorization(operation: str, driver: Driver, *, uri: str, authorization_file=None) -> dict`
- Produces: pytest collection hook skips every `integration` item unless `TALENTMIND_ALLOW_INTEGRATION=1`.

- [ ] **Step 1: Add the guard regression tests and integration-default tests from the verified P0 safety commits**
- [ ] **Step 2: Run guard tests before production paths are imported**

Run: `python -m pytest tests/test_integration_guard.py tests/test_destructive_guard.py -q`
Expected: FAIL because `destructive_guard` and guarded imports are not present.

- [ ] **Step 3: Add the live-target authorization guard and wrap all six destructive import entry points before any write**
- [ ] **Step 4: Run targeted safety tests**

Run: `python -m pytest tests/test_integration_guard.py tests/test_destructive_guard.py -q`
Expected: PASS; denial tests contain no executed destructive statements.

- [ ] **Step 5: Verify default collection does not enter integration**

Run: `python -m pytest --collect-only -q`
Expected: integration items are skipped/deselected without connecting to MySQL or Neo4j.

- [ ] **Step 6: Commit**

Commit message: `fix(integration): isolate destructive imports from default tests`

### Task 2: 改进 B1 真实职责识别

**Files:**
- Modify: `backend/app/job_analysis/screening/rules.py`
- Modify: `backend/tests/test_job_analysis/test_screening.py`

**Interfaces:**
- Produces: `RULESET = "conservative-activity-v4"`.
- Produces: evidence remains `{field,start,end,quote,signal}` with original frozen offsets.

- [ ] **Step 1: Add failing tests for object-first technical duties and non-duty counterexamples**

Test cases:
- `岗位职责：负责仿真系统架构设计与软件开发` -> `valid/in_scope`.
- `岗位职责：负责后端接口开发、单元测试和部署` -> `valid/in_scope`.
- `岗位职责：负责数据清洗与数据仓库建设` -> `valid/in_scope`.
- `公司介绍：我们研发软件产品` -> not `in_scope`.
- `任职要求：熟悉 Python` -> not confirmed from qualification alone.

- [ ] **Step 2: Run the focused test and confirm the new current-duty cases fail**

Run: `python -m pytest tests/test_job_analysis/test_screening.py -q`
Expected: FAIL only on the new current-job positive cases.

- [ ] **Step 3: Add conservative object/action relations and deduplicate identical evidence spans**
- [ ] **Step 4: Run B1 tests**

Run: `python -m pytest tests/test_job_analysis/test_screening.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

Commit message: `fix(m2): recognize explicit Chinese duty activities`

### Task 3: 修正 B2 上下文、章节和明确能力表达

**Files:**
- Modify: `backend/app/job_analysis/semantics/rules.py`
- Modify: `backend/tests/test_job_analysis/test_semantics.py`

**Interfaces:**
- Produces: `RULESET = "bounded-skill-clauses-v4"`.
- Preserves: statement schema `id, skills, state, relation, degree, requirement_object, target, condition, section, reason, evidence, context, scope_evidence`.

- [ ] **Step 1: Add failing tests for the five review-focus behaviors**

Test cases:
- A risk word in an unrelated sentence does not turn a separate explicit requirement into `uncertain`.
- `岗位职责：...任职要求：...` on one line assigns the correct section for both fragments.
- `任职要求：熟练掌握 Python，并能独立完成接口开发` -> Python `required`.
- `加分项：熟悉 Docker，具备容器化经验` -> Docker `preferred`.
- A skill occurring only in `job_title` -> `mentioned`, not `required` or `uncertain`.
- Identical `duties` text repeated inside `raw_text` produces one machine statement for that occurrence.
- Existing conditional, negation, alternative and multiple-degree cases remain uncertain/unpromoted.

- [ ] **Step 2: Run the focused tests and confirm each new case fails for the intended reason**

Run: `python -m pytest tests/test_job_analysis/test_semantics.py -q`
Expected: FAIL on unrelated risk contamination, inline headings, extended capability, title-only and duplicate cases.

- [ ] **Step 3: Scope risk evidence locally, split inline headings, deduplicate cross-field clauses, and add conservative capability patterns**
- [ ] **Step 4: Run B2 tests**

Run: `python -m pytest tests/test_job_analysis/test_semantics.py -q`
Expected: PASS, including all original complex-logic tests.

- [ ] **Step 5: Commit**

Commit message: `fix(m2): scope skill semantics to local evidence`

### Task 4: 增加 B3 明确职责大类候选

**Files:**
- Modify: `backend/app/job_analysis/role_classification/proposals/rules.py`
- Modify: `backend/tests/test_job_analysis/test_role_proposals.py`
- Modify: `backend/tests/test_job_analysis/test_role_family_versions.py`

**Interfaces:**
- Preserves: `RULESET = "closed-delivery-clauses-v2"` for the unchanged fixed delivery productions.
- Produces: `DUTY_RULESET = "closed-action-object-duties-v1"` for the new action/object grammar.
- Preserves: candidates are `{family_id, clues[]}`, each clue has `kind`, `rule`, and exact evidence.
- Preserves: `review_status="pending_review"`, `classification_complete=False`, `formal_statistics_eligible=False`, `canonical_job.state="unknown"`.

- [ ] **Step 1: Add failing positive tests for explicit duty patterns**

Test cases:
- “负责软件模块的架构设计、编码实现与单元测试” -> `software_engineering`.
- “负责数据仓库 ETL 流程设计与开发” -> `data_ai`.
- “负责设计测试用例并执行自动化测试” -> `test_quality_engineering`.
- “负责部署应用、维护服务器并监控系统” -> `infrastructure_operations`.

- [ ] **Step 2: Add negative tests for title-only, company/history, negation, examples, training, sales and requirements-only text**
- [ ] **Step 3: Run the focused tests and confirm only new explicit-duty positives fail**

Run: `python -m pytest tests/test_job_analysis/test_role_proposals.py tests/test_job_analysis/test_role_family_versions.py -q`
Expected: FAIL on the new explicit-duty candidates.

- [ ] **Step 4: Add finite action/object duty rules without creating canonical jobs or vacancy counts**
- [ ] **Step 5: Run B3 tests**

Run: `python -m pytest tests/test_job_analysis/test_role_proposals.py tests/test_job_analysis/test_role_family_versions.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

Commit message: `feat(m2): propose families from explicit duty evidence`

### Task 5: 实现最小人工复核闭环

**Files:**
- Modify: `backend/app/job_analysis/product/workflow.py`
- Modify: `backend/app/routers/m2.py`
- Modify: `backend/tests/test_m2_product.py`
- Modify: `backend/tests/test_m2_product_api.py`
- Modify: `frontend/src/api/m2.ts`
- Modify: `frontend/src/views/M2.vue`
- Modify: `frontend/tests/m2Product.test.ts`
- Modify: `frontend/tests/helpers/m2Component.ts`

**Interfaces:**
- Produces: `Workflow.review(run_id: str, ordinal: int, event: dict) -> dict`
- Produces: `Workflow.reviews(run_id: str) -> list[dict]`
- Produces: `Workflow.review_export(run_id: str) -> dict`
- Produces: `POST /api/m2/runs/{run_id}/items/{ordinal}/review`
- Produces: `GET /api/m2/runs/{run_id}/reviews/export`
- Review request: `{decision: accepted|rejected|needs_followup, reviewer, note, machine_sha256}`
- Review event: immutable, run/item/version bound, with machine result separated from human decision.

- [ ] **Step 1: Add failing backend tests for append-only review, stale machine hash rejection, human/machine count separation and export**
- [ ] **Step 2: Run the focused backend tests and confirm the review API does not exist**

Run: `python -m pytest tests/test_m2_product.py tests/test_m2_product_api.py -q`
Expected: FAIL with missing review interface.

- [ ] **Step 3: Add the `product_reviews` append-only table, validation and export methods**
- [ ] **Step 4: Add local-only review routes**
- [ ] **Step 5: Run the focused backend tests and confirm they pass**

Run: `python -m pytest tests/test_m2_product.py tests/test_m2_product_api.py -q`
Expected: PASS.

- [ ] **Step 6: Add failing frontend tests for review submission, stale detail protection and export**
- [ ] **Step 7: Implement review form, history display and JSON download in the existing drawer**
- [ ] **Step 8: Run frontend tests**

Run: `npm test`
Expected: PASS.

- [ ] **Step 9: Commit**

Commit message: `feat(m2): add evidence-bound human review workflow`

### Task 6: 真实冻结输入版本对照与验收

**Files:**
- Create: `docs/review/M2-real-analysis-2026-10-22.md`
- Create: `docs/superpowers/traps/2026-10-22-m2-real-evidence-scope.md`
- Modify: `backend/app/job_analysis/README.md`
- Modify: `docs/superpowers/资产与状态.md`

**Interfaces:**
- Consumes: existing `main120` and `holdout60` frozen inputs.
- Produces: new immutable product `run_id`s with revision `v3`.
- Produces: private comparison JSON under `data/local/m2-real-analysis-20261022/`; raw JD stays uncommitted.

- [ ] **Step 1: Run all affected M2 backend tests**

Run: `python -m pytest tests/test_job_analysis/test_screening.py tests/test_job_analysis/test_semantics.py tests/test_job_analysis/test_role_proposals.py tests/test_job_analysis/test_role_family_versions.py tests/test_m2_product.py tests/test_m2_product_api.py -q`
Expected: PASS.

- [ ] **Step 2: Run the guarded non-integration backend regression**

Run: `python -m pytest -m "not integration" -q`
Expected: no database/service connection attempts; report any pre-existing failures exactly.

- [ ] **Step 3: Run frontend tests and build**

Run: `npm test`
Expected: PASS.

Run: `npm run build`
Expected: exit 0.

- [ ] **Step 4: Replay the two existing frozen cohorts with revision `v3`**

Run the existing `Workflow.replay` path for old `main120` run `29af896353304a7e92346378e2057ddd` and holdout run `39a61ec6f94e44e0814b9dd302dcc939`.
Expected: two new immutable run IDs; old IDs and frozen inputs unchanged.

- [ ] **Step 5: Run one small frozen-input sample first and inspect its evidence**

Expected: one new immutable sample run completes without unexpected failure before the two cohort runs.

- [ ] **Step 6: Compare old/new per-item outcomes and validate every evidence span**

Expected: produce actual counts, added/reduced/inverted samples, B1/B2/B2.2/B3 deltas, false-positive review list, false-negative review list, zero invalid evidence spans, and separate signed/unsigned counts.

- [ ] **Step 7: Verify the page/API can create, run, inspect, review and export**

Expected: the local M2 page displays the new runs and evidence; review submission persists; export is re-readable.

- [ ] **Step 8: Reconfirm formal data unchanged**

Expected: exact MySQL eight-table counts/content hashes and Neo4j 7,845/11,412 remain equal to the P0 baseline.

- [ ] **Step 9: Write the stage report and update the asset/usage docs**
- [ ] **Step 10: Commit**

Commit message: `docs(m2): record real analysis improvement and review evidence`

### Task 7: 独立交付 PR

**Files:**
- Modify only if required by final verification: the files listed in Tasks 1–6.

- [ ] **Step 1: Inspect the full diff and confirm no M1 collection adaptation, formal DDL, import or graph code is included**
- [ ] **Step 2: Push the independent branch**
- [ ] **Step 3: Open a ready PR against `master` only after verification**
- [ ] **Step 4: Attach the PR and report its URL, validation evidence and remaining manual-review items**


# 智联身份待审实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不执行 DDL 的前提下实现 `verified/pending/unknown` 身份模型、智联 DOM 面板绑定校验、离线回放，以及 M1→M2→M3 的透明传播。

**Architecture:** M1 先生成独立的内容判定和身份判定，pending 只有在动态面板绑定证据成立时才允许写入；数据库使用可检测的新增列保存身份、内容资格和证据。M2 冻结并分析 pending 记录，M3 仅将其投影为候选观察。

**Tech Stack:** Python 3.14、FastAPI、SQLAlchemy、MySQL 8、Pytest、Vue 3、TypeScript、Vitest。

**Spec:** `docs/superpowers/specs/2026-10-21-zhaopin-identity-pending-design.md`

## Global Constraints

- 身份枚举只能是 `verified / pending / unknown`；拒绝与失败不是身份状态。
- 历史数据默认 `unknown`；不得批量推断为 `verified`。
- pending 不计入正式独立岗位数或已确认技能需求。
- 不修改 `job_definition`、`job_skill`、`job_change_log` 或 Neo4j。
- 不自动提升 B3。
- 本轮不执行 DDL、不连接生产库做迁移、不运行真实采集。
- `complete` 保持历史严格口径；pending 只增加新计数。
- 所有身份证据、回放输入和报告继续留在私有路径。

## Review Focus

- 相同标题来自不同卡片时，旧面板内容不得被误认成当前岗位。
- 面板在异步更新期间出现两次不同内容时，不得过早判为稳定。
- 迁移前旧 schema 缺少新列时，pending 不得静默降级后写库。
- pending 进入 M2/M3 后，任何前端或汇总都不得把它显示为已确认独立岗位。
- 不同观察时间不能被标题、公司或正文相似度自动合并。

---

### Task 1: 身份与内容纯规则

**Files:**
- Create: `backend/app/collect/identity.py`
- Create: `backend/tests/test_collection_identity.py`

**Interfaces:**
- Produces: `IDENTITY_STATUSES = ('verified', 'pending', 'unknown')`
- Produces: `content_rejection(spec: SiteSpec, job: dict, detail: dict) -> str | None`
- Produces: `identity_decision(spec: SiteSpec, job: dict, detail: dict, binding: dict, observed_at: str) -> tuple[str, dict, str | None]`
- Produces: `dom_fingerprint(evidence: dict) -> str`

- [ ] **Step 1: Write failing tests**

```python
def test_valid_dom_binding_is_pending_not_verified(): ...
def test_panel_not_updated_is_rejected(): ...
def test_same_title_with_unchanged_panel_is_rejected(): ...
def test_url_identity_must_match_detail_url(): ...
def test_empty_and_truncated_content_are_not_eligible(): ...
def test_fingerprint_changes_when_observation_time_changes(): ...
```

- [ ] **Step 2: Run tests to verify failure**

Run: `backend/.venv/Scripts/python.exe -m pytest tests/test_collection_identity.py -q` from `backend/`

Expected: import/function-not-defined failures.

- [ ] **Step 3: Implement pure decisions**

Move content validation out of `fetch_cn_jobs.detail_rejection`; require exact normalized title match for DOM pending, active target, visible stable panel, and changed panel state unless the target was already active before click. Fingerprint canonical JSON with `platform`, `list_page_url`, `card_index`, title, company, location, salary, description SHA-256, `observed_at`, and `binding_policy='zhaopin-dom-panel-v1'`.

- [ ] **Step 4: Run tests**

Run: `backend/.venv/Scripts/python.exe -m pytest tests/test_collection_identity.py -q` from `backend/`

Expected: all new tests pass.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/collect/identity.py backend/tests/test_collection_identity.py
git commit -m "feat(m1): add identity and content decisions"
```

### Task 2: 智联动态面板绑定

**Files:**
- Modify: `backend/app/collect/fetchers/job_sites.py`
- Modify: `backend/app/collect/fetch_cn_jobs.py`
- Modify: `backend/tests/test_cn_job_fetchers.py`
- Modify: `backend/tests/test_cn_detail_gate.py`

**Interfaces:**
- Produces: `build_panel_probe_js(spec: SiteSpec, card_index: int) -> str`
- Produces: `await_stable_panel(client, spec, card_index, before, timeout) -> dict`
- Produces job field: `_observation_key` for event correlation only
- Produces job fields: `_list_url`, `_list_title`, `_list_company` and final `_identity_evidence`
- Consumes: Task 1 `identity_decision` and `content_rejection`

- [ ] **Step 1: Write failing browser-binding tests**

Use Node `vm` synthetic DOM to cover target active, panel transition, two stable samples, stale panel, duplicate-title cards, timeout, and missing panel.

- [ ] **Step 2: Run RED**

Run: `backend/.venv/Scripts/python.exe -m pytest tests/test_cn_job_fetchers.py tests/test_cn_detail_gate.py -q` from `backend/`

Expected: new binding tests fail because probe/polling does not exist.

- [ ] **Step 3: Implement probe and dynamic polling**

Capture the panel before click. Poll until two identical consecutive `(panel_title, description, company, visible, target_active)` observations after a transition; reject when no transition is observed for a previously inactive card. Do not use one fixed sleep as proof. Compute `_observation_key` from platform, list URL, card index and list-card digest; compute the final source fingerprint only after content and binding pass.

- [ ] **Step 4: Run tests**

Run: `backend/.venv/Scripts/python.exe -m pytest tests/test_cn_job_fetchers.py tests/test_cn_detail_gate.py -q` from `backend/`

Expected: all pass, including original liepin and URL identity regressions.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/collect/fetchers/job_sites.py backend/app/collect/fetch_cn_jobs.py backend/tests/test_cn_job_fetchers.py backend/tests/test_cn_detail_gate.py
git commit -m "feat(m1): verify zhaopin dom panel binding"
```

### Task 3: M1 统计、事件与结果

**Files:**
- Modify: `backend/app/collect/fetch_cn_jobs.py`
- Modify: `backend/app/collect/control.py`
- Modify: `backend/tests/test_cn_detail_gate.py`
- Modify: `backend/tests/test_collection_product.py`
- Modify: `frontend/src/api/collection.ts`
- Modify: `frontend/src/views/Collection.vue`

**Interfaces:**
- Produces event/task fields: `content_eligible`, `identity_pending`, `identity_verified`
- Produces result fields: `identity_status`, `content_eligible`, `identity_evidence`
- Preserves in events: `_observation_key`; final `source_detail` remains the strong DOM fingerprint
- Preserves: `complete` only for content-eligible verified records

- [ ] **Step 1: Write failing event/API/UI tests**

Assert `detail_obtained=5` can coexist with `content_eligible=5`, `identity_pending=5`, `complete=0`, `inserted=5`; pending results expose evidence and are not labeled rejected.

- [ ] **Step 2: Run RED**

Run: `backend/.venv/Scripts/python.exe -m pytest tests/test_cn_detail_gate.py tests/test_collection_product.py -q` from `backend/`; run `pnpm --dir frontend test -- collectionConsole.test.ts` from repository root.

Expected: missing counters/fields or old rejected behavior.

- [ ] **Step 3: Implement M1 propagation**

Add counters without changing `complete`; emit binding/content evidence; merge `listed → detail → persisted` events by `_observation_key`, while `persisted.source_detail` stores the final fingerprint. Treat `--no-details` as `content_eligible=null`, `identity_status=unknown`, never pending. Display identity status separately from outcome.

- [ ] **Step 4: Run tests**

Re-run the Task 3 commands.

Expected: all pass.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/collect/fetch_cn_jobs.py backend/app/collect/control.py backend/tests/test_cn_detail_gate.py backend/tests/test_collection_product.py frontend/src/api/collection.ts frontend/src/views/Collection.vue
git commit -m "feat(m1): expose pending identity statistics"
```

### Task 4: 数据库契约与兼容持久化

**Files:**
- Modify: `backend/app/contracts/ddl.sql`
- Create: `backend/app/contracts/migrations/2026-10-21-jd-pool-identity-status.sql`
- Modify: `backend/app/collect/repository.py`
- Modify: `backend/app/collect/schema.py`
- Modify: `backend/tests/test_collect_repo.py`
- Modify: `backend/tests/test_talent_schema.py`
- Modify: `backend/tests/test_ddl_integration.py`

**Interfaces:**
- Produces: `schema_capabilities(db) -> dict[str, bool]`
- Produces persisted columns: `identity_status`, `content_eligible`, `identity_evidence`
- Raises before write: `identity_schema_migration_required`

- [ ] **Step 1: Write failing schema-compatibility tests**

Cover old schema read/write, new schema pending write, absent-column pending rejection, historical `unknown`, and no silent evidence loss.

- [ ] **Step 2: Run RED**

Run: `backend/.venv/Scripts/python.exe -m pytest tests/test_collect_repo.py tests/test_talent_schema.py tests/test_ddl_integration.py -q` from `backend/`.

Expected: new column/capability assertions fail. Integration fixture must use a disposable database only.

- [ ] **Step 3: Implement additive contract and adaptive insert**

Add columns with historical defaults from the spec. Dynamically include new fields only when present; reject a pending row with the explicit migration-required error if columns are absent.

- [ ] **Step 4: Run tests**

Run Task 4 test command. Do not execute the migration SQL against any database.

Expected: tests pass; no DDL executed by the application.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/contracts/ddl.sql backend/app/contracts/migrations/2026-10-21-jd-pool-identity-status.sql backend/app/collect/repository.py backend/app/collect/schema.py backend/tests/test_collect_repo.py backend/tests/test_talent_schema.py backend/tests/test_ddl_integration.py
git commit -m "feat(db): define compatible identity metadata"
```

### Task 5: M2 身份透传

**Files:**
- Modify: `backend/app/job_analysis/product/source.py`
- Modify: `backend/app/job_analysis/product/workflow.py`
- Modify: `frontend/src/api/m2.ts`
- Modify: `frontend/src/views/M2.vue`
- Modify: `backend/tests/test_m2_product.py`
- Modify: `backend/tests/test_m2_product_api.py`
- Modify: `frontend/tests/m2Product.test.ts`

**Interfaces:**
- Produces item fields: `identity_status`, `content_eligible`, `identity_evidence`
- Produces summary: `identity={verified,pending,unknown}` and `content_eligible`
- Produces input-invalid result: `content_ineligible` when a new-era row has `content_eligible=false`
- Preserves: global `formal_statistics_eligible=false`

- [ ] **Step 1: Write failing M2 tests**

Test pending input is frozen, analyzed, visible in item/report, excluded from confirmed-demand eligibility, and remains distinguishable from B1 validity and B2 states.

- [ ] **Step 2: Run RED**

Run: `backend/.venv/Scripts/python.exe -m pytest tests/test_m2_product.py tests/test_m2_product_api.py -q` from `backend/`; run `pnpm --dir frontend test -- m2Product.test.ts`.

Expected: pending fields are absent or treated as generic warnings.

- [ ] **Step 3: Implement M2 propagation**

Normalize absent columns to `unknown`/NULL, parse identity evidence, store item state, and show a separate “身份待审” tag. A new-era `content_eligible=false` row becomes `input_invalid/content_ineligible` before stages; historical NULL rows retain existing behavior. Do not alter valid B1/B2/B3 semantics.

- [ ] **Step 4: Run tests**

Re-run Task 5 commands.

Expected: all pass.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/job_analysis/product/source.py backend/app/job_analysis/product/workflow.py frontend/src/api/m2.ts frontend/src/views/M2.vue backend/tests/test_m2_product.py backend/tests/test_m2_product_api.py frontend/tests/m2Product.test.ts
git commit -m "feat(m2): propagate pending identity"
```

### Task 6: M3 候选观察图谱

**Files:**
- Modify: `backend/app/graph/product_bundle.py`
- Modify: `frontend/src/graph/realSnapshot.ts`
- Modify: `frontend/src/components/GraphPanorama.vue`
- Modify: `backend/tests/test_m2_graph.py`
- Modify: `frontend/tests/realSnapshot.test.ts`

**Interfaces:**
- Consumes M2 `identity_status`, `content_eligible`, `identity_evidence`
- Produces manifest identity counts and per-source identity metadata
- Preserves: graph candidates are observations, not confirmed jobs

- [ ] **Step 1: Write failing graph tests**

Require pending source records and manifest counts to survive binding validation; reject graph artifacts if pending loses identity metadata. Check UI exposes “身份待审” on selected job nodes.

- [ ] **Step 2: Run RED**

Run: `backend/.venv/Scripts/python.exe -m pytest tests/test_m2_graph.py -q` from `backend/`; run `pnpm --dir frontend test -- realSnapshot.test.ts`.

Expected: missing identity field/manifest count.

- [ ] **Step 3: Implement M3 projection**

Add identity metadata to source records, manifest counts, and selected-node details. Do not write Neo4j or change formal statistics flags.

- [ ] **Step 4: Run tests**

Re-run Task 6 commands.

Expected: all pass.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/graph/product_bundle.py frontend/src/graph/realSnapshot.ts frontend/src/components/GraphPanorama.vue backend/tests/test_m2_graph.py frontend/tests/realSnapshot.test.ts
git commit -m "feat(m3): label identity-pending observations"
```

### Task 7: 私有事件离线回放

**Files:**
- Create: `backend/app/collect/identity_replay.py`
- Create: `backend/tests/test_identity_replay.py`
- Create after execution: `data/local/identity-pending-replay-20261021/` (ignored private output)

**Interfaces:**
- Consumes: one or more `*.events.jsonl` paths and an explicit private output directory
- Produces: case results, counts, input SHA-256 and binding note

- [ ] **Step 1: Write failing replay tests**

Cover valid pending, async wrong-job, same-title/no-update, empty, truncated, same-observation dedupe, and different-observation separation.

- [ ] **Step 2: Run RED**

Run: `backend/.venv/Scripts/python.exe -m pytest tests/test_identity_replay.py -q` from `backend/`.

Expected: replay entry point missing.

- [ ] **Step 3: Implement replay**

Read real event content from the provided path, generate synthetic legal/illegal binding transitions, record that old events lack panel-transition evidence, and write private JSON only.

- [ ] **Step 4: Run offline replay on the current five records**

Run the replay against `zhaopin-5f7079ff40394431b084ca07f55e2d5e.events.jsonl`, with output under the ignored path. Report that the result validates decision logic and content eligibility, not historical click correctness.

- [ ] **Step 5: Commit tests and tool only**

```powershell
git add backend/app/collect/identity_replay.py backend/tests/test_identity_replay.py
git commit -m "test(m1): replay pending identity cases offline"
```

### Task 8: 文档、授权门禁与最终验证

**Files:**
- Modify: `backend/app/collect/README.md`
- Modify: `docs/PRODUCT_DECISIONS.md`
- Modify: `docs/superpowers/资产与状态.md`
- Create if a bug is fixed: `docs/superpowers/traps/2026-10-21-zhaopin-identity-pending.md`
- Create: `docs/review/Zhaopin-identity-pending-2026-10-21.md`

**Interfaces:**
- Documents schema compatibility, migration authorization gate, rollback, offline evidence and real-run boundary

- [ ] **Step 1: Update documentation**

Record the confirmed business rule, implementation status, migration not executed, offline result, unresolved real binding verification, and the exact next bounded acceptance request.

- [ ] **Step 2: Run targeted backend regression**

Run selected M1/M2/M3 tests and full relevant frontend tests; do not use production data or external model calls.

- [ ] **Step 3: Run frontend typecheck/build**

Run: `pnpm --dir frontend run build`

Expected: exit 0; existing chunk warnings may remain.

- [ ] **Step 4: Verify worktree and private artifacts**

Run `git status --short`, inspect diff, confirm no DDL was executed and no private evidence was staged.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/collect/README.md docs/PRODUCT_DECISIONS.md docs/superpowers/资产与状态.md docs/review/Zhaopin-identity-pending-2026-10-21.md
git commit -m "docs: record identity-pending implementation and gates"
```

## DDL 授权门禁

Tasks 1–8 不执行迁移 SQL。完成离线回放和代码审查后，另行提交迁移执行申请，至少包含：

- 目标实例 host/port/database 的非敏感标识。
- 当前 schema、八表行数与有序摘要。
- 冷备路径、SHA-256、文件大小和隔离恢复结果。
- 预计执行的追加列 SQL。
- 迁移后核验命令与失败回退负责人。

未获得新的明确授权，不执行 DDL、不启动真实采集。

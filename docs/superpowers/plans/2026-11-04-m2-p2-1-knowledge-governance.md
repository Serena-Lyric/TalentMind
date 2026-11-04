# M2 P2-1 外部知识初始化、事实对齐与自动治理 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从可追溯外部知识建立小规模版本化知识快照，在不改写 P1 事实的前提下完成严格对齐、候选治理、岗位比较、画像读取和知识变更影响定位。

**Architecture:** 新增独立 `job_analysis.knowledge` 包。公开目录保存来源元数据、少量逐字摘录和 test/candidate 知识；私有运行产物保存对齐、岗位比较、候选版本和画像。所有读取显式绑定知识 SHA 与 P1 分析 SHA，正式知识准入保持关闭。

**Tech Stack:** Python 3.14、Pydantic 2.12、标准库 pathlib/hashlib/unicodedata、pytest；无模型、数据库或网络运行时依赖。

**Spec:** [Issue #61](https://github.com/Serena-Lyric/TalentMind/issues/61)、[产品决策 §3](../../PRODUCT_DECISIONS.md#3-m2-已确认产品规则)、[P2 分段目标](2026-10-28-m2-core-delivery/P2-knowledge-role.md)、[审核标准](../specs/2026-10-28-m2-delivery-review-standard.md)。

## Global Constraints

- P1 `claims/requirements/relations`、五态、程度、条件、组合、对象、证据和 `machine_unreviewed` 只能引用或原样复制，不能回写或强化。
- 同义仅接受快照中显式且带来源的精确别名；名称相似、向量相似、共同出现和同一模型重复输出不能建立同义。
- 知识状态严格区分 `test / candidate / formal`；外部标准导入和候选积累均不自动取得 TalentMind 正式准入。
- 同源转载按规范化正文分组，不增加独立证据；公司名或无上下文名词不自动成为技能候选。
- 知识、输入、分析和候选版本分离；旧结果不可覆盖，知识变化不得伪装成 JD 变化。
- 正式 DB、Neo4j、DDL、真实采集、HOLD、外部模型、收费 API和私有全文公开均不执行。
- 新代码必须有非 integration 专项测试、既有相关回归和实际 GitHub Actions CI。

## Review Focus

- 同标题或同技能但交付责任不同：岗位比较必须保留未覆盖责任，不能仅凭词面确认同岗。
- `JavaScript/JS` 等精确别名可对齐，而 `JavaScript/TypeScript`、`Kubernetes/容器编排` 必须分别表达不同关系。
- `any_of`、degree polarity、condition 和 `machine_unreviewed`：对齐前后必须逐字段相同。
- 内容相同的跨平台重复：候选可去重保留来源，但独立证据数不得按转载次数增长。
- 别名增删、概念修订和角色边界变化：只定位受影响对象并生成新解释，旧知识、旧解释和 P1 输入保持可读。

---

### Task 1: Knowledge Contract and Validated Public Snapshot

**Files:**
- Create: `backend/app/job_analysis/knowledge/__init__.py`
- Create: `backend/app/job_analysis/knowledge/models.py`
- Create: `backend/app/job_analysis/knowledge/catalog.py`
- Create: `backend/app/job_analysis/knowledge/storage.py`
- Create: `backend/app/job_analysis/knowledge/catalog/backend-foundations.v1/knowledge.json`
- Create: `backend/app/job_analysis/knowledge/catalog/backend-foundations.v1/manifest.json`
- Create: `backend/tests/test_job_analysis/test_knowledge_catalog.py`

**Interfaces:**
- Produces: `load_snapshot(path: Path | str) -> LoadedSnapshot`
- Produces: `KnowledgeSnapshot`, `KnowledgeSource`, `Concept`, `ConceptRelation`, `RoleDefinition`
- Produces immutable result storage: `save_result(path, value) -> str`, `read_result(path) -> dict`

- [ ] **Step 1: Write failing catalog tests**

```python
def test_shipped_catalog_binds_sources_licenses_and_exact_excerpts():
    loaded = load_snapshot(SHIPPED_CATALOG)
    assert loaded.snapshot.revision == "backend-foundations-1"
    assert {s.id for s in loaded.snapshot.sources} >= {"src-python-docs", "src-mdn", "src-kubernetes"}
    assert all(source.license_id and source.license_url for source in loaded.snapshot.sources)

def test_ambiguous_alias_is_rejected_instead_of_silently_merged():
    value = catalog_value()
    value["concepts"][1]["aliases"][0]["term"] = value["concepts"][0]["name"]
    with pytest.raises(ValueError, match="ambiguous"):
        validate_snapshot(value)
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `backend/.venv/Scripts/python.exe -m pytest tests/test_job_analysis/test_knowledge_catalog.py -q`

Expected: collection/import failure because `app.job_analysis.knowledge` does not exist.

- [ ] **Step 3: Implement strict models and manifest verification**

Use Pydantic `extra="forbid", strict=True`; stable IDs; `https://` source URIs;
SHA-256 fields; explicit license/use constraints; exact excerpt evidence; relation
types `exact_synonym / broader_than / narrower_than / related_to / version_of`.
Reject duplicate IDs, blank text, duplicate aliases, conflicting aliases,
unbound evidence and formal entries without approval evidence.

- [ ] **Step 4: Add the small sourced catalog**

Initialize only:

- Python concept and exact `JS` alias/TypeScript distinct related concepts from
  Python 3.14.10 Chinese docs and MDN Chinese pages;
- Kubernetes and container-orchestration related concepts from official
  Kubernetes Chinese docs;
- two P0 role candidates imported from `baseline/role-references.v1.json`;
- one clearly labelled `test` role boundary case for mechanism verification.

Every source records URI, document version or retrieval snapshot, retrieval date,
license ID/URI, use constraint and downloaded-byte SHA-256. Store only short
citation excerpts, not downloaded pages.

- [ ] **Step 5: Run catalog tests and manifest CLI**

Run: `backend/.venv/Scripts/python.exe -m pytest tests/test_job_analysis/test_knowledge_catalog.py -q`

Run: `backend/.venv/Scripts/python.exe -m app.job_analysis.knowledge validate catalog/backend-foundations.v1`

Expected: PASS; CLI exits 0 and prints only snapshot ID/revision/SHA/counts.

- [ ] **Step 6: Commit**

```bash
git add backend/app/job_analysis/knowledge backend/tests/test_job_analysis/test_knowledge_catalog.py
git commit -m "feat(m2): add versioned external knowledge snapshot"
```

### Task 2: Strict P1 Alignment Without Fact Rewriting

**Files:**
- Create: `backend/app/job_analysis/knowledge/alignment.py`
- Create: `backend/tests/test_job_analysis/test_knowledge_alignment.py`
- Modify: `backend/app/job_analysis/knowledge/models.py`

**Interfaces:**
- Consumes: `LoadedSnapshot`, validated `Analysis`
- Produces: `align_analysis(analysis: dict, knowledge: LoadedSnapshot) -> AlignmentResult`
- Produces per member: exact concept, ambiguity candidates, relation or true unknown

- [ ] **Step 1: Write failing behavior tests**

```python
def test_alignment_preserves_any_of_degree_condition_and_machine_review():
    result = align_analysis(mixed_analysis(), shipped())
    original = mixed_analysis()["claims"][0]["requirement"]
    aligned = result.requirements[0]
    assert aligned.source_requirement == original
    assert aligned.source_requirement["combination"] == "any_of"
    assert result.semantic_review == "machine_unreviewed"

def test_exact_alias_merges_but_typescript_is_not_javascript():
    members = {a.member: a for a in align_analysis(js_ts_analysis(), shipped()).alignments}
    assert members["JS"].concept_id == members["JavaScript"].concept_id
    assert members["TypeScript"].concept_id != members["JavaScript"].concept_id

def test_name_similarity_and_cooccurrence_cannot_create_alias():
    result = align_analysis(unknown_analysis("Java Script 开发"), shipped())
    assert result.alignments[0].state == "unknown"
```

- [ ] **Step 2: Run tests and verify RED**

Run: `backend/.venv/Scripts/python.exe -m pytest tests/test_job_analysis/test_knowledge_alignment.py -q`

Expected: FAIL because `align_analysis` is missing.

- [ ] **Step 3: Implement exact normalization and ambiguity handling**

Normalize only NFKC, outer whitespace and casefold for lookup. Preserve the
original member and all requirement fields verbatim. If one alias maps to more
than one concept, return `ambiguous` with all concept IDs and no selected mapping.
Unknown members retain `concept_id=null`, `knowledge_id=null`.

- [ ] **Step 4: Bind output to immutable P1 identity**

Record namespace/JD/input SHA/input version, full analysis digest, knowledge
snapshot SHA/revision, each original claim/member evidence and alignment reason.
Do not write to the source analysis object.

- [ ] **Step 5: Run focused and baseline contract tests**

Run: `backend/.venv/Scripts/python.exe -m pytest tests/test_job_analysis/test_knowledge_alignment.py tests/test_job_analysis/test_baseline_contract.py -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/job_analysis/knowledge/alignment.py backend/app/job_analysis/knowledge/models.py backend/tests/test_job_analysis/test_knowledge_alignment.py
git commit -m "feat(m2): align P1 facts to versioned knowledge"
```

### Task 3: Role Comparison and Candidate Profile Read Boundary

**Files:**
- Create: `backend/app/job_analysis/knowledge/roles.py`
- Create: `backend/app/job_analysis/knowledge/profile.py`
- Create: `backend/tests/test_job_analysis/test_knowledge_roles.py`

**Interfaces:**
- Produces: `compare_roles(analysis, knowledge) -> RoleComparisonSet`
- Produces: `build_profile(role_id, comparisons, alignments) -> RoleProfile`
- Produces comparisons with checked role scope, covered/uncovered duties, explicit conflicts and `supported/unresolved/not_supported`

- [ ] **Step 1: Write failing tests for comparison distinctions**

```python
def test_same_tool_different_work_is_not_supported_as_same_role():
    result = compare_roles(teaching_analysis(), shipped())
    programming = by_role(result, "p0-ref-programming")
    assert programming.judgment != "supported"
    assert programming.uncovered_duty_ids

def test_explicit_boundary_can_reject_but_directory_gap_cannot():
    rejected = by_role(compare_roles(teaching_boundary_analysis(), shipped()), "test-ref-excludes-teaching")
    missing = by_role(compare_roles(unknown_role_work_analysis(), shipped()), "p0-ref-programming")
    assert rejected.judgment == "not_supported"
    assert rejected.conflicts
    assert missing.judgment == "unresolved"

def test_profile_keeps_member_states_and_never_claims_universal_requirement():
    profile = build_profile("p0-ref-programming", comparisons, alignments)
    assert profile.mode == "candidate_profile"
    assert any(r.state == "preferred" for r in profile.members[0].requirements)
    assert profile.claim_scope == "linked_members_only"
```

- [ ] **Step 2: Run tests and verify RED**

Run: `backend/.venv/Scripts/python.exe -m pytest tests/test_job_analysis/test_knowledge_roles.py -q`

Expected: FAIL because `compare_roles` and `build_profile` are missing.

- [ ] **Step 3: Implement evidence-anchored comparison**

Use role responsibility phrases and explicit boundary patterns only. A match must
be an exact normalized phrase or all configured anchors in one evidenced local
duty. `not_supported` requires a boundary conflict. Coverage gaps, empty
catalogues and unrestrieved candidates remain `unresolved`. Report checked role
IDs and that no conclusion covers roles outside the snapshot.

- [ ] **Step 4: Build minimal profiles**

Profiles reference linked analysis versions and member requirement states; mark
`candidate_profile`, `not_market_statistics`, `not_formal_role`, and preserve
per-member conflicts/unknowns. Rebuilding from the same bound inputs is stable.

- [ ] **Step 5: Run focused and existing role tests**

Run: `backend/.venv/Scripts/python.exe -m pytest tests/test_job_analysis/test_knowledge_roles.py tests/test_job_analysis/test_role_classification.py tests/test_job_analysis/test_baseline_contract.py -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/job_analysis/knowledge/roles.py backend/app/job_analysis/knowledge/profile.py backend/tests/test_job_analysis/test_knowledge_roles.py
git commit -m "feat(m2): add explainable role comparison and candidate profiles"
```

### Task 4: Append-only Candidate Governance

**Files:**
- Create: `backend/app/job_analysis/knowledge/candidates.py`
- Create: `backend/tests/test_job_analysis/test_knowledge_governance.py`

**Interfaces:**
- Produces: `CandidateRegistry(path)`
- Produces: `registry.observe(analysis, alignment) -> CandidateVersion | None`
- Produces: `registry.revise(candidate_id, description, reason, evidence) -> CandidateVersion`
- Produces: `registry.read(candidate_id, version=None) -> CandidateVersion`
- Produces: `admission_decision(candidate) -> AdmissionDecision` that remains `allowed=false`

- [ ] **Step 1: Write failing governance tests**

```python
def test_unknown_with_capability_context_creates_candidate_without_formal_admission(tmp_path):
    registry = CandidateRegistry(tmp_path / "registry")
    record = registry.observe(analysis_with_unknown("Flink SQL"), alignment)
    assert record.status == "observing"
    assert admission_decision(record).allowed is False

def test_noncability_and_contextless_name_do_not_create_skill_candidate(tmp_path):
    registry = CandidateRegistry(tmp_path / "registry")
    assert registry.observe(education_analysis(), education_alignment) is None
    assert registry.observe(company_only_analysis(), company_alignment) is None

def test_republished_identical_content_does_not_add_independent_evidence(tmp_path):
    registry = CandidateRegistry(tmp_path / "registry")
    first = registry.observe(analysis_for("BOSS", "同一正文", "candidate"), alignment_one)
    second = registry.observe(analysis_for("Zhaopin", "同一正文", "candidate"), alignment_two)
    assert first.independent_evidence == 1
    assert second.independent_evidence == 1
    assert len(second.referenced_observations) == 2

def test_revision_is_append_only_and_conflicts_preserve_competing_hypotheses(tmp_path):
    second = registry.revise(first.candidate_id, "修正后的描述", "新增同上下文证据", [evidence])
    assert second.version == 2
    assert registry.read(first.candidate_id, 1) == first
```

- [ ] **Step 2: Run tests and verify RED**

Run: `backend/.venv/Scripts/python.exe -m pytest tests/test_job_analysis/test_knowledge_governance.py -q`

Expected: FAIL because the registry is missing.

- [ ] **Step 3: Implement deduplicated evidence and low-risk revision**

Candidate creation requires `target=capability`, non-null category, non-empty
requirement evidence and a non-title-only context. Deduplicate observations by
P1 analysis/member key; compute independence from normalized source content, not
platform or company count. Version files are write-once and bound to their digest.

- [ ] **Step 4: Implement formal/key structural stops**

Formal admission, merge/split and identity confirmation always remain
`requires_human_decision`. Contradictory surfaced hypotheses remain co-listed;
automatic revisions append a version and never erase prior evidence. Failed
updates leave the prior valid head readable.

- [ ] **Step 5: Run focused and existing governance tests**

Run: `backend/.venv/Scripts/python.exe -m pytest tests/test_job_analysis/test_knowledge_governance.py tests/test_job_analysis/test_governance.py -q`

Expected: PASS with no formal admission.

- [ ] **Step 6: Commit**

```bash
git add backend/app/job_analysis/knowledge/candidates.py backend/tests/test_job_analysis/test_knowledge_governance.py
git commit -m "feat(m2): govern candidate knowledge with append-only evidence"
```

### Task 4b: Version Impact and Conservative Re-alignment

**Files:**
- Create: `backend/app/job_analysis/knowledge/impact.py`
- Create: `backend/tests/test_job_analysis/test_knowledge_versions.py`

**Interfaces:**
- Produces: `locate_impact(old, new, records) -> ImpactReport`
- Produces: `redeliver(analysis, new_knowledge) -> AlignmentResult`

- [ ] **Step 1: Write failing version tests**

```python
def test_new_alias_changes_alignment_but_not_p1_input_or_old_result():
    old_alignment = align_analysis(unknown_analysis(), old)
    new_alignment = align_analysis(same_analysis, new)
    assert old_alignment.alignments[0].state == "unknown"
    assert new_alignment.alignments[0].concept_id == "concept-python"
    assert new_alignment.source_analysis_sha256 == old_alignment.source_analysis_sha256
    assert same_analysis["claims"] == before_claims

def test_impact_is_scoped_and_falls_back_to_all_when_change_scope_unknown():
    assert locate_impact(old, new, [hit, miss]).affected == [hit.analysis_key]
    assert locate_impact(old, unrelated, [hit, miss]).conservative is True
```

- [ ] **Step 2: Run tests and verify RED**

Run: `backend/.venv/Scripts/python.exe -m pytest tests/test_job_analysis/test_knowledge_versions.py -q`

Expected: FAIL because impact/re-alignment APIs are missing.

- [ ] **Step 3: Implement deterministic snapshot diff**

Compare concept revisions, aliases, relations and role definitions. Map changed
aliases/concepts/roles to recorded alignments/comparisons. If the snapshot hash
changes without a provable affected set, return conservative `all`.

- [ ] **Step 4: Implement new-explanation generation**

Always create a new alignment bound to the new knowledge SHA; never mutate the old
result. Assert input SHA and copied requirement fields remain identical.

- [ ] **Step 5: Run focused version tests**

Run: `backend/.venv/Scripts/python.exe -m pytest tests/test_job_analysis/test_knowledge_versions.py -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/job_analysis/knowledge/impact.py backend/tests/test_job_analysis/test_knowledge_versions.py
git commit -m "feat(m2): locate knowledge impact and re-align by version"
```

### Task 5: CLI, Documentation and CI

**Files:**
- Create: `backend/app/job_analysis/knowledge/__main__.py`
- Create: `backend/app/job_analysis/knowledge/README.md`
- Modify: `backend/app/job_analysis/README.md`
- Create: `.github/workflows/m2-p2-knowledge.yml`
- Create: `backend/tests/test_job_analysis/test_knowledge_cli.py`
- Create: `docs/superpowers/traps/2026-11-04-m2-knowledge-alignment.md`

**Interfaces:**
- Produces safe CLI commands: `validate`, `align`, `compare`, `govern`, `profile`, `impact`
- Output paths in the repository must remain under `data/local/`; public catalog is read-only

- [ ] **Step 1: Write failing CLI tests**

```python
def test_cli_align_writes_new_immutable_result_and_safe_summary(tmp_path):
    completed = run_cli("align", "--analysis", analysis_path, "--snapshot", SHIPPED_CATALOG, "--output", output)
    summary = json.loads(completed.stdout)
    assert completed.returncode == 0
    assert summary["knowledge_revision"] == "backend-foundations-1"
    assert "Java" not in completed.stdout

def test_cli_refuses_to_overwrite_existing_alignment(tmp_path):
    second = run_cli("align", ...)
    assert second.returncode == 1
```

- [ ] **Step 2: Run tests and verify RED**

Run: `backend/.venv/Scripts/python.exe -m pytest tests/test_job_analysis/test_knowledge_cli.py -q`

Expected: FAIL because the CLI module does not exist.

- [ ] **Step 3: Implement CLI and immutable output**

Read raw P1 `Analysis` JSON or a saved P1 `run.json`, validate it before use,
write result directories with `value.json` and digest manifest, and print only
counts/SHA/status. Reject overwrite and secret-bearing/private output in public
repository paths.

- [ ] **Step 4: Add documentation and trap record**

Document actual commands, status semantics, version binding, source/license
limits, formal-admission stop, and residual gaps. Trap record states symptom,
root cause, fix and lesson; do not copy private data.

- [ ] **Step 5: Add GitHub Actions**

Workflow triggers on pull requests and `master` pushes affecting the
knowledge/baseline code or tests. On Ubuntu/Python 3.12:

```bash
python -m compileall app/job_analysis/knowledge app/job_analysis/baseline
python -m pytest tests/test_job_analysis/test_knowledge_*.py tests/test_job_analysis/test_baseline_contract.py -q
```

It must not read private data or secrets, start services, call models or omit failures.

- [ ] **Step 6: Run all P2-1 tests and non-integration affected regression**

Run:

```bash
cd backend
./.venv/Scripts/python.exe -m pytest tests/test_job_analysis/test_knowledge_*.py tests/test_job_analysis/test_baseline_contract.py tests/test_job_analysis/test_understanding.py tests/test_job_analysis/test_governance.py -q
```

Expected: 0 failures; integration tests not selected or explicitly skipped.

- [ ] **Step 7: Commit**

```bash
git add backend/app/job_analysis/knowledge backend/app/job_analysis/README.md backend/tests/test_job_analysis/test_knowledge_cli.py .github/workflows/m2-p2-knowledge.yml docs/superpowers/traps/2026-11-04-m2-knowledge-alignment.md
git commit -m "docs(m2): expose P2-1 knowledge workflow and CI"
```

### Task 6: Controlled Real-Data Verification, Review and Delivery

**Files:**
- Modify: `docs/superpowers/资产与状态.md`
- Modify: `docs/superpowers/plans/2026-10-28-m2-core-delivery-plan.md`
- No private JD, HOLD, model response or raw source document is committed.

**Interfaces:**
- Consumes existing local P1 run(s) and DEV-only controlled facts from Issue #61 authorization
- Produces private alignment/comparison output summary and reproducible commands

- [ ] **Step 1: Locate an existing P1 run without opening HOLD**

List only available run paths and manifests; select an already stored DEV run with
a readable `m2-semantic-0.2` analysis. Record path category, input/knowledge SHA,
status and date, not private text in Git.

- [ ] **Step 2: Align controlled real P1 facts**

Run the CLI against the fixed knowledge snapshot and write output under
`data/local/`. Verify original input SHA, all requirement fields, evidence and
`machine_unreviewed` are unchanged; report completed/unknown/ambiguous counts.

- [ ] **Step 3: Run negative and governance scenarios**

Use public synthetic cases for exact alias, JavaScript/TypeScript distinction,
any_of, degree/condition, duplicate repost, unknown candidate revision, role
responsibility mismatch, explicit boundary rejection, alias update and old-version
read. Keep results separate from real DEV mechanism checks.

- [ ] **Step 4: Verify branch and CI**

Re-read Issue acceptance checklist and map each item to code/test/output. Stage
only explicit files, run the fresh full focused suite, push the branch, and create
the PR. Wait for GitHub Actions to finish against the actual pushed head.

- [ ] **Step 5: Report in Issue #61 and request independent review**

Provide base/head SHA, actual diff, commands/exit codes, CI run URL and target SHA,
knowledge/source hashes, real DEV vs synthetic vs not-run counts, errors/unknowns,
rollback/replay evidence and residual limits. Do not mark Issue complete, merge,
or start P2-2.

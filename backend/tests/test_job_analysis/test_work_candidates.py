"""Synthetic P3 lifecycle contracts; these fixtures are not human semantic truth."""
from copy import deepcopy

import pytest

from app.job_analysis.foundation.inputs import InputRecord, digest
from test_knowledge_alignment import analysis_with, evidence, shipped


@pytest.fixture(autouse=True)
def cleanup_p3_files(tmp_path, tmp_path_factory):
    """Remove only this test's synthetic files, including after assertion failures."""
    import shutil
    target = tmp_path.resolve()
    root = tmp_path_factory.getbasetemp().resolve()
    assert target != root and target.is_relative_to(root)
    try:
        yield
    finally:
        shutil.rmtree(target)
        assert not target.exists()


def work(jd_id="one", text="开发订单接口，保障订单服务运行。", *, source="Synthetic", title="研发工程师"):
    value = analysis_with(["Python"], jd_id=jd_id)
    row = dict(id=jd_id, source=source, job_title=title, raw_text=text)
    record = InputRecord.from_row("synthetic", row)
    value.update(input_row=row, input_sha256=record.fingerprint)
    value["claims"] = [dict(id="d1", kind="duty", text=text, evidence=[evidence(record, text)],
                            core=True, requirement=None, reason="合成工作陈述")]
    return value


def ref(value, claim="d1"):
    return dict(analysis_sha256=digest(value), claim_id=claim)


def create(value, candidate_id="work-orders"):
    return dict(op="create", candidate_id=candidate_id, description="订单接口工作假设",
                research_question="跨语言实现是否承担相同订单服务责任？", core_work=[ref(value)])


def batch(store, batch_id, values=(), operations=(), **extra):
    return dict(schema_version="m2-work-batch-1", batch_id=batch_id,
                baseline=store.read()["binding"], operation_version="synthetic-operations-1",
                analysis_sha256s=sorted({digest(value) for value in values}), operations=list(operations), **extra)


def apply(store, request, values=(), knowledge=None):
    from app.job_analysis.work_candidates.service import apply_batch
    return apply_batch(store, request, {digest(value): value for value in values}, knowledge or shipped())


def test_two_batches_persist_identity_history_and_exact_retry(tmp_path):
    from app.job_analysis.work_candidates.storage import CandidateStore
    first, second = work(), work("two", "使用 Go 开发订单接口，保障订单服务运行。", title="平台程序员")
    path = tmp_path / "p3.sqlite3"
    with CandidateStore(path, create=True) as store:
        request = batch(store, "batch-one", [first], [create(first)])
        original = deepcopy(first)
        one = apply(store, request, [first])
        assert first == original
        assert one["binding"]["revision"] == 1
        assert len(one["candidates"]) == 1
    with CandidateStore(path) as store:
        two = apply(store, batch(store, "batch-two", [second]), [second])
        assert set(two["candidates"]) == {"work-orders"}
        assert two["candidates"]["work-orders"]["version"] == 2
        assert len(two["relations"]) == 2
        assert {r["state"] for r in two["relations"].values()} == {"pending_review"}
        assert store.read(1) == one
        assert apply(store, request, [first]) == one
        assert store.read() == two
        assert store.source("analysis", digest(first)) == first
        assert two["counts"]["independent_evidence"] is None
        assert two["counts"]["vacancies"] is None
        assert two["formal_roles"] == []


def test_stale_baseline_changed_retry_and_invalid_batch_roll_back(tmp_path):
    from app.job_analysis.work_candidates.storage import CandidateStore
    a = work()
    with CandidateStore(tmp_path / "state.db", create=True) as store:
        request = batch(store, "b1", [a], [create(a)])
        stale = batch(store, "stale", [a])
        one = apply(store, request, [a])
        with pytest.raises(ValueError, match="baseline"):
            apply(store, stale, [a])
        changed = deepcopy(request)
        changed["operation_version"] = "different"
        with pytest.raises(ValueError, match="batch ID"):
            apply(store, changed, [a])
        broken = batch(store, "broken", [a], [create(a, "new-candidate"), create(a)])
        with pytest.raises(ValueError, match="exists"):
            apply(store, broken, [a])
        assert store.read() == one
        assert store.history("work-orders")[0]["candidate"]["version"] == 1


@pytest.mark.parametrize("op", ["merge", "split", "publish", "formal", "assign_role"])
def test_formal_and_structural_operations_are_unavailable(tmp_path, op):
    from app.job_analysis.work_candidates.storage import CandidateStore
    with CandidateStore(tmp_path / "state.db", create=True) as store:
        with pytest.raises(ValueError):
            apply(store, batch(store, "bad", operations=[dict(op=op)]))
        assert store.read()["binding"]["revision"] == 0


def test_new_candidate_requires_actual_duty_and_research_question(tmp_path):
    from app.job_analysis.work_candidates.storage import CandidateStore
    a = analysis_with(["Python"])
    with CandidateStore(tmp_path / "state.db", create=True) as store:
        op = create(a)
        op["core_work"] = [ref(a, "r1")]
        with pytest.raises(ValueError, match="duty"):
            apply(store, batch(store, "skills-only", [a], [op]), [a])
        assert store.read()["candidates"] == {}


def link(value, candidate_id="work-orders", reason="明确提出局部工作研究关系"):
    return dict(op="link", candidate_id=candidate_id, analysis_sha256=digest(value), work_ids=["d1"], reason=reason)


def correction(relation, decision="withdraw", **extra):
    return dict(op="correct", relation_id=relation["id"], expected_sha256=digest(relation),
                decision=decision, reason="下一批根据完整责任重新检查", verification=None, **extra)


def test_explicit_multicandidate_links_and_similarity_chain_never_confirm_identity(tmp_path):
    from app.job_analysis.work_candidates.storage import CandidateStore
    a = work("a", "开发订单接口并交付交易服务。")
    b = work("b", "开发订单接口，同时分析广告投放效果。")
    c = work("c", "分析广告投放效果并提供经营建议。")
    with CandidateStore(tmp_path / "state.db", create=True) as store:
        one = apply(store, batch(store, "one", [a, c], [create(a), create(c, "work-ads")]), [a, c])
        two = apply(store, batch(store, "two", [b], [link(b), link(b, "work-ads")]), [b])
        b_relations = [r for r in two["relations"].values() if r["jd_id"] == "b"]
        assert len(b_relations) == 2
        assert {r["state"] for r in b_relations} == {"pending_review"}
        assert not any(r["jd_id"] == "c" and r["candidate_id"] == "work-orders" for r in two["relations"].values())
        assert two["report"]["baseline"] == one["binding"]
        assert all(r["baseline"] == one["binding"] for r in b_relations)
        assert all(r["semantic_validation"] == "not_run" for r in b_relations)


def test_withdraw_and_counterevidence_preserve_old_relation_and_reject_stale_correction(tmp_path):
    from app.job_analysis.work_candidates.storage import CandidateStore
    a = work()
    with CandidateStore(tmp_path / "state.db", create=True) as store:
        one = apply(store, batch(store, "one", [a], [create(a)]), [a])
        rel = next(iter(one["relations"].values()))
        two = apply(store, batch(store, "two", operations=[correction(rel, "weakens")]))
        assert two["relations"][rel["id"]]["state"] == "disputed"
        assert store.read(1)["relations"][rel["id"]] == rel
        with pytest.raises(ValueError, match="relation version"):
            apply(store, batch(store, "stale-correction", operations=[correction(rel)]))
        current = two["relations"][rel["id"]]
        three = apply(store, batch(store, "three", operations=[correction(current)]))
        assert three["relations"][rel["id"]]["state"] == "withdrawn"
        assert three["candidates"]["work-orders"]["members"] == []
        # Running the original observation again must not resurrect a withdrawn hypothesis.
        four = apply(store, batch(store, "four", [a]), [a])
        assert four["relations"][rel["id"]] == three["relations"][rel["id"]]
        assert len(store.history("work-orders")) == 3


def test_same_analysis_new_batch_and_rerun_do_not_inflate_members_or_strength(tmp_path):
    from app.job_analysis.work_candidates.storage import CandidateStore
    a = work()
    rerun = deepcopy(a)
    rerun["analyzer"]["revision"] = "recompiled-2"
    copy = work("copy", source="Syndicated")
    with CandidateStore(tmp_path / "state.db", create=True) as store:
        one = apply(store, batch(store, "one", [a], [create(a)]), [a])
        two = apply(store, batch(store, "two", [a, rerun, copy]), [a, rerun, copy])
        assert two["counts"] == dict(linked_jd_identities=2, unique_content_groups=1,
                                     independent_evidence=None, vacancies=None)
        assert len(two["candidates"]["work-orders"]["members"]) == 2
        original = next(r for r in two["relations"].values() if r["jd_id"] == "one")
        assert original["analysis_sha256"] == digest(a)
        assert original["pending_analysis_sha256s"] == [digest(rerun)]
        assert original["needs_reassessment"] is True
        three = apply(store, batch(store, "three", [a, rerun, copy]), [a, rerun, copy])
        assert three["candidates"] == two["candidates"]
        assert three["relations"] == two["relations"]
        assert store.read(1) == one


def test_partial_multijob_and_empty_catalog_keep_gaps_without_manufacturing_candidates(tmp_path):
    from app.job_analysis.work_candidates.storage import CandidateStore
    a = work(text="岗位一开发交易接口，岗位二维护监控平台。")
    a["coverage"]["classification"] = dict(status="not_run", reason="合成多职位未拆分")
    a["outcome"] = "partial"
    no_duties = analysis_with(["Python"], jd_id="skills-only")
    with CandidateStore(tmp_path / "state.db", create=True) as store:
        result = apply(store, batch(store, "one", [a, no_duties]), [a, no_duties])
        assert result["candidates"] == {}
        assert result["counts"]["vacancies"] is None
        assert result["report"]["inputs"][digest(a)]["outcome"] == "partial"
        assert result["report"]["inputs"][digest(a)]["coverage"] == a["coverage"]
        assert result["report"]["searches"][0]["checked_candidates"] == 0
        assert any(s["status"] == "no_usable_duties" for s in result["report"]["searches"])


def test_description_revision_does_not_change_comparison_scope_or_old_facts(tmp_path):
    from app.job_analysis.work_candidates.storage import CandidateStore
    a = work()
    with CandidateStore(tmp_path / "state.db", create=True) as store:
        one = apply(store, batch(store, "one", [a], [create(a)]), [a])
        op = dict(op="describe", candidate_id="work-orders", expected_version=1,
                  description="修订的订单服务研究说明", research_question="原成员责任是否仍可解释？",
                  unresolved=["不同技术栈的完整语义还需验证"], reason="解释文字修订，不扩大职责范围")
        two = apply(store, batch(store, "two", operations=[op]))
        assert two["candidates"]["work-orders"]["core_work"] == one["candidates"]["work-orders"]["core_work"]
        assert two["candidates"]["work-orders"]["version"] == 2
        assert store.source("analysis", digest(a)) == a
        assert two["report"]["change_nature"] == "candidate_research_not_market_change"
        assert store.read(1) == one
        with pytest.raises(ValueError, match="candidate version"):
            apply(store, batch(store, "stale-description", operations=[op]))


def test_review_evidence_is_subject_bound_and_does_not_authenticate_human_or_publish(tmp_path):
    import hashlib
    from app.job_analysis.work_candidates.service import review_subject
    from app.job_analysis.work_candidates.storage import CandidateStore
    a = work()
    with CandidateStore(tmp_path / "state.db", create=True) as store:
        one = apply(store, batch(store, "one", [a], [create(a)]), [a])
        rel = next(iter(one["relations"].values()))
        subject = review_subject(rel, one["candidates"]["work-orders"], "corroborates")
        text = "合成独立对照材料 " + subject
        verification = dict(kind="synthetic_control", subject_sha256=subject,
                            document=text, document_sha256=hashlib.sha256(text.encode()).hexdigest(), quote=text,
                            reviewer="synthetic-reference", provider_version="fixture-1")
        op = correction(rel, "corroborates")
        op["verification"] = verification
        two = apply(store, batch(store, "two", operations=[op]))
        current = two["relations"][rel["id"]]
        assert current["state"] == "controlled_support"
        assert current["semantic_validation"] == "synthetic_control_only"
        assert current["human_confirmation"] == "not_confirmed"
        assert current["formal_identity"] is None
        # An ordinary rerun must not promote controlled support or drop its evidence.
        three = apply(store, batch(store, "three", [a]), [a])
        assert three["relations"] == two["relations"]
        assert three["formal_roles"] == []
        bad = correction(current, "corroborates")
        bad["verification"] = verification
        with pytest.raises(ValueError, match="subject"):
            apply(store, batch(store, "bad-review", operations=[bad]))


def test_same_skill_different_duty_may_be_a_hint_but_never_same_work(tmp_path):
    from app.job_analysis.work_candidates.storage import CandidateStore
    a = work("developer", "使用 Python 开发订单服务接口。")
    b = work("analyst", "使用 Python 分析广告投放效果。")
    with CandidateStore(tmp_path / "state.db", create=True) as store:
        apply(store, batch(store, "one", [a], [create(a)]), [a])
        two = apply(store, batch(store, "two", [b]), [b])
        assert all(r["state"] == "pending_review" for r in two["relations"].values())
        assert all(r["formal_identity"] is None for r in two["relations"].values())
        assert two["report"]["searches"][0]["semantic_status"] == "not_evaluated"


def test_two_new_candidates_and_explicit_links_do_not_read_half_updated_baseline(tmp_path):
    from app.job_analysis.work_candidates.storage import CandidateStore
    a, b = work(), work("two")
    with CandidateStore(tmp_path / "state.db", create=True) as store:
        with pytest.raises(ValueError, match="baseline"):
            apply(store, batch(store, "one", [a, b], [create(a), link(b)]), [a, b])
        assert store.read()["binding"]["revision"] == 0


def test_knowledge_change_is_versioned_without_rewriting_relation_or_facts(tmp_path):
    from app.job_analysis.knowledge.catalog import LoadedSnapshot
    from app.job_analysis.work_candidates.storage import CandidateStore
    a = work()
    knowledge = shipped()
    changed = knowledge.snapshot.model_copy(deep=True)
    changed.revision = "new-empty-roles"
    changed.roles = []
    new_knowledge = LoadedSnapshot(knowledge.path, changed, digest(changed.model_dump()))
    with CandidateStore(tmp_path / "state.db", create=True) as store:
        one = apply(store, batch(store, "one", [a], [create(a)]), [a])
        two = apply(store, batch(store, "two", [a]), [a], new_knowledge)
        assert two["relations"] == one["relations"]
        assert two["report"]["knowledge"]["revision"] == "new-empty-roles"
        assert two["report"]["reassessment_reasons"] == ["knowledge_changed"]
        assert store.source("analysis", digest(a)) == a
        assert store.read(1) == one


def test_reinterpretation_rebinds_only_same_jd_with_new_scope_and_retains_counterevidence(tmp_path):
    from app.job_analysis.work_candidates.storage import CandidateStore
    a = work()
    revised = work(text="分析订单接口性能并交付诊断报告。")
    with CandidateStore(tmp_path / "state.db", create=True) as store:
        one = apply(store, batch(store, "one", [a], [create(a)]), [a])
        old = next(iter(one["relations"].values()))
        op = correction(old, "weakens", replacement=dict(analysis_sha256=digest(revised), work_ids=["d1"]),
                        counterevidence=[ref(revised)])
        two = apply(store, batch(store, "two", [revised], [op]), [revised])
        relation = two["relations"][old["id"]]
        assert relation["analysis_sha256"] == digest(revised)
        assert relation["last_correction"]["counterevidence"] == [ref(revised)]
        assert relation["superseded_analysis_sha256s"] == [digest(a)]
        assert relation["needs_reassessment"] is False
        assert store.read(1)["relations"][old["id"]] == old
        repeat = apply(store, batch(store, "old-observation-replay", [a]), [a])
        assert repeat["relations"] == two["relations"]
        assert repeat["candidates"] == two["candidates"]
        foreign = work("other")
        bad = correction(relation, replacement=dict(analysis_sha256=digest(foreign), work_ids=["d1"]))
        with pytest.raises(ValueError, match="same JD"):
            apply(store, batch(store, "bad", [foreign], [bad]), [foreign])


def test_external_review_record_stays_unverified_and_wrong_document_is_rejected(tmp_path):
    import hashlib
    from app.job_analysis.work_candidates.service import review_subject
    from app.job_analysis.work_candidates.storage import CandidateStore
    a = work()
    a["namespace"] = "dev-unreviewed"
    for c in a["claims"]:
        for e in c["evidence"]:
            e["namespace"] = a["namespace"]
    with CandidateStore(tmp_path / "state.db", create=True) as store:
        one = apply(store, batch(store, "one", [a], [create(a)]), [a])
        rel = next(iter(one["relations"].values()))
        subject = review_subject(rel, one["candidates"]["work-orders"], "corroborates")
        verification = dict(kind="synthetic_control", subject_sha256=subject, document=subject,
                            document_sha256=hashlib.sha256(subject.encode()).hexdigest(), quote=subject,
                            reviewer="claimed reviewer", provider_version="external-1")
        op = correction(rel, "corroborates")
        op["verification"] = verification
        with pytest.raises(ValueError, match="synthetic"):
            apply(store, batch(store, "bad-control", operations=[op]))
        verification["kind"] = "external_review_record"
        result = apply(store, batch(store, "external", operations=[op]))
        current = result["relations"][rel["id"]]
        assert current["state"] == "pending_review"
        assert current["semantic_validation"] == "external_record_unverified"
        assert current["human_confirmation"] == "not_confirmed"
        assert result["formal_roles"] == []


def test_parallel_writers_and_registry_identity_prevent_stale_commit(tmp_path):
    from app.job_analysis.work_candidates.storage import CandidateStore
    a = work()
    with CandidateStore(tmp_path / "one.db", create=True) as first:
        request = batch(first, "one", [a], [create(a)])
        with CandidateStore(tmp_path / "one.db") as second:
            stale = batch(second, "two", [a], [create(a)])
            apply(first, request, [a])
            with pytest.raises(ValueError, match="baseline"):
                apply(second, stale, [a])
        with CandidateStore(tmp_path / "other.db", create=True) as foreign:
            with pytest.raises(ValueError, match="baseline"):
                apply(foreign, request, [a])


def test_immutable_history_and_foreign_sqlite_are_protected(tmp_path):
    import sqlite3
    from contextlib import closing
    from app.job_analysis.work_candidates.storage import CandidateStore
    path = tmp_path / "foreign.db"
    with closing(sqlite3.connect(path)) as conn:
        with conn:
            conn.execute("CREATE TABLE unrelated(value TEXT)")
    original = path.read_bytes()
    with pytest.raises(ValueError, match="no automatic migration"):
        CandidateStore(path)
    assert path.read_bytes() == original
    a = work()
    with CandidateStore(tmp_path / "p3.db", create=True) as store:
        apply(store, batch(store, "one", [a], [create(a)]), [a])
        for query in ("DELETE FROM batches", "UPDATE sources SET body='{}'",
                      "INSERT OR REPLACE INTO sources SELECT * FROM sources"):
            with pytest.raises(sqlite3.IntegrityError, match="immutable"):
                store.conn.execute(query)


def test_explicit_many_jds_to_one_candidate_is_allowed_without_overwriting_old_versions(tmp_path):
    from app.job_analysis.work_candidates.storage import CandidateStore
    a, b, c = work(), work("two"), work("three")
    with CandidateStore(tmp_path / "state.db", create=True) as store:
        apply(store, batch(store, "one", [a], [create(a)]), [a])
        result = apply(store, batch(store, "two", [b, c], [link(b), link(c)]), [b, c])
        assert len(result["candidates"]["work-orders"]["members"]) == 3


def test_duplicate_content_and_observation_provenance_are_inspectable(tmp_path):
    from app.job_analysis.work_candidates.storage import CandidateStore
    a, copy = work(), work("copy", source="Syndicated")
    with CandidateStore(tmp_path / "state.db", create=True) as store:
        apply(store, batch(store, "one", [a], [create(a)]), [a])
        two = apply(store, batch(store, "two", [a, copy]), [a, copy])
        assert two["report"]["observation_nature"][digest(a)] == "duplicate_analysis"
        assert two["report"]["observation_nature"][digest(copy)] == "new_jd_identity"
        assert len(two["content_groups"]) == 1
        assert len(two["content_groups"][0]["jd_identities"]) == 2
        assert two["content_groups"][0]["source_independence"] == "unknown"
        assert all(r["source_independence"] == "unknown" for r in two["relations"].values())


def test_algorithm_binding_covers_p1_p2_dependency_sources(tmp_path):
    from app.job_analysis.work_candidates.service import algorithm_version
    version = algorithm_version()
    assert version["dependencies"]["knowledge/alignment.py"]
    assert version["dependencies"]["baseline/contract.py"]
    assert version["dependencies"]["work_candidates/service.py"]
    assert version["sha256"] == digest(version["dependencies"])

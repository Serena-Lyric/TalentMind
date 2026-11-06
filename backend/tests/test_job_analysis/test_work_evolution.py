"""Controlled source-projection behavior, never independent Chinese semantic truth."""
from copy import deepcopy

import pytest

from app.job_analysis.foundation.inputs import InputRecord, digest
from app.job_analysis.work_candidates.storage import CandidateStore
from test_work_candidates import apply, batch, cleanup_p3_files, correction, create, ref, work
from test_knowledge_alignment import evidence, shipped
from test_knowledge_roles import analysis_with_duties


def duties(jd_id, texts, *, coverage="complete", stack="Python"):
    return analysis_with_duties(texts, jd_id=jd_id, requirement=stack, duty_coverage=coverage)


def research(state, cid="work-orders"):
    return state["candidates"][cid]["research"]


def relation(state, jd_id):
    return next(r for r in state["relations"].values() if r["jd_id"] == jd_id)


def test_three_batches_use_effective_duties_then_withdraw_and_replay(tmp_path):
    first, other = duties("a", ["开发订单交易接口。"]), duties("a2", ["开发订单交易接口。"])
    second = duties("b", ["开发订单交易接口。", "交付库存盘点报告。"])
    third = duties("c", ["交付库存盘点报告。"])
    path = tmp_path / "state.db"
    with CandidateStore(path, create=True) as store:
        seed = create(first)
        seed["core_work"] += [ref(other)]
        one = apply(store, batch(store, "one", [first, other], [seed]), [first, other])
        two = apply(store, batch(store, "two", [second], [dict(op="link", candidate_id="work-orders",
                    analysis_sha256=digest(second), work_ids=["d1", "d2"], reason="局部多职责研究")]), [second])
        assert research(two)["description"] != research(one)["description"]
        assert ref(second, "d2") in research(two)["comparison_work"]
        # All batch-two comparisons still used batch-one; the added inventory duty cannot self-prove.
        assert two["report"]["searches"][0]["candidate_baselines"]["work-orders"]["research_sha256"] == digest(research(one))
        assert all(p["core_reference"] != ref(second, "d2") for m in two["report"]["searches"][0]["matches"] for p in m["pairs"])
        assert [x["text"] for x in research(two)["shared_statements"]] == ["开发订单交易接口。"]
    with CandidateStore(path) as store:
        three = apply(store, batch(store, "three", [third]), [third])
        search = three["report"]["searches"][0]
        assert search["candidate_baselines"]["work-orders"]["research_sha256"] == digest(research(two))
        assert any(p["core_reference"] == ref(second, "d2") for m in search["matches"] for p in m["pairs"])
        assert relation(three, "c")["state"] == "pending_review"
        assert research(three)["shared_statements"] == []  # chain never proves a common group
        assert research(three)["semantic_validation"] == "not_run"
        four = apply(store, batch(store, "four", operations=[correction(relation(three, "b")), correction(relation(three, "c"))]))
        assert ref(second, "d2") not in research(four)["comparison_work"]
        assert "库存" not in research(four)["description"]
        assert len(research(four)["historical_relations"]) >= 4
        assert store.read(2) == two
        assert store.source("analysis", digest(second)) == second
        assert three["report"]["evolution"]["work-orders"]["applied"] is True
        assert four["report"]["evolution"]["work-orders"]["removed_comparison_work"]


def test_automatic_local_scope_does_not_invent_shared_core_and_counterevidence_narrows(tmp_path):
    a = duties("a", ["使用 Java 开发订单接口。"])
    b = duties("b", ["使用 Java 讲授编程课程。"])
    with CandidateStore(tmp_path / "s.db", create=True) as store:
        one = apply(store, batch(store, "one", [a], [create(a)]), [a])
        two = apply(store, batch(store, "two", [b]), [b])
        assert research(two)["shared_statements"] == []
        assert relation(two, "b")["state"] == "pending_review"
        assert {e["jd_id"] for e in research(two)["member_explanations"]} == {"a", "b"}
        three = apply(store, batch(store, "three", operations=[correction(relation(two, "b"), "weakens", counterevidence=[ref(b)])]))
        assert research(three)["status"] == "disputed"
        assert ref(b) not in research(three)["comparison_work"]
        excluded = next(e for e in research(three)["member_explanations"] if e["jd_id"] == "b")
        assert excluded["counterevidence"] == [ref(b)]
        assert excluded["eligibility"] == "disputed"
        assert "软件开发" not in research(three)["description"]
        assert store.read(1) == one


def test_repeated_observation_and_republication_do_not_raise_support_or_churn_research(tmp_path):
    a = duties("a", ["开发订单交易接口。"])
    with CandidateStore(tmp_path / "s.db", create=True) as store:
        one = apply(store, batch(store, "one", [a], [create(a)]), [a])
        two = apply(store, batch(store, "two", [a]), [a])
        assert two["candidates"] == one["candidates"]
        assert two["report"]["evolution"]["work-orders"]["applied"] is False
        assert two["report"]["evolution"]["work-orders"]["reason"] == "no_effective_evidence_change"
        repost = duties("copy", ["开发订单交易接口。"])
        three = apply(store, batch(store, "three", [repost]), [repost])
        assert research(three)["independent_support"] is None
        assert len(research(three)["content_groups"]) == 1
        assert research(three)["shared_statements"] == []
        assert research(three)["version"] == research(one)["version"]
        assert research(three)["description"] == research(one)["description"]
        assert three["report"]["evolution"]["work-orders"]["applied"] is False
        assert three["report"]["evolution"]["work-orders"]["evidence_updated"] is True
        assert len(research(three)["member_explanations"]) == 2  # provenance still records the new identity
        assert not any(s["kind"] == "review_split" for s in three["structural_suggestions"])
        assert research(three)["unresolved"] == research(one)["unresolved"]
        assert three["counts"]["vacancies"] is None


def test_full_source_context_partial_and_unselected_duties_are_not_silently_promoted(tmp_path):
    a = duties("mixed", ["开发订单交易接口。", "讲授编程课程。"], coverage="partial")
    row = a["input_row"]
    a["claims"].append(dict(id="g1", kind="goal", text="开发订单交易接口。", core=None, requirement=None,
                             evidence=[evidence(InputRecord.from_row("synthetic", row), "开发订单交易接口。")], reason="合成目标"))
    with CandidateStore(tmp_path / "s.db", create=True) as store:
        one = apply(store, batch(store, "one", [a], [create(a)]), [a])
        r = research(one)
        assert r["comparison_work"] == [ref(a)]
        explanation = r["member_explanations"][0]
        assert len(explanation["work_context"]) == 3
        assert explanation["unselected_duty_ids"] == ["d2"]
        assert explanation["coverage"] == a["coverage"]
        assert r["shared_statements"] == []
        assert r["unresolved"]
        assert one["formal_roles"] == []


def test_same_responsibility_different_stack_is_literal_support_not_human_confirmation(tmp_path):
    a, b = duties("py", ["开发订单交易接口。"], stack="Python"), duties("go", ["开发订单交易接口。"], stack="Go")
    with CandidateStore(tmp_path / "s.db", create=True) as store:
        apply(store, batch(store, "one", [a], [create(a)]), [a])
        two = apply(store, batch(store, "two", [b]), [b])
        assert research(two)["shared_statements"][0]["text"] == "开发订单交易接口。"
        assert research(two)["nature"] == "machine_hypothesis"
        assert all(r["human_confirmation"] == "not_confirmed" for r in two["relations"].values())


def test_batch_order_has_same_meaning_and_all_comparisons_use_old_research(tmp_path):
    a = duties("a", ["开发订单交易接口。"])
    b, c = duties("b", ["开发订单交易接口。", "输出仓库报告。"]), duties("c", ["输出仓库报告。"])
    outputs = []
    for index, values in enumerate(([b, c], [c, b])):
        with CandidateStore(tmp_path / f"{index}.db", create=True) as store:
            one = apply(store, batch(store, "one", [a], [create(a)]), [a])
            two = apply(store, batch(store, "two", values), values)
            assert not any(r["jd_id"] == "c" for r in two["relations"].values())
            assert all(s["candidate_baselines"]["work-orders"]["research_sha256"] == digest(research(one)) for s in two["report"]["searches"])
            outputs.append([(e["jd_id"], e["selected_work_ids"]) for e in research(two)["member_explanations"]])
    assert outputs[0] == outputs[1]


def test_seed_withdrawal_removes_search_basis_instead_of_falling_back_to_old_seed(tmp_path):
    a, b = duties("a", ["开发订单交易接口。"]), duties("b", ["开发订单交易接口。"])
    with CandidateStore(tmp_path / "s.db", create=True) as store:
        one = apply(store, batch(store, "one", [a], [create(a)]), [a])
        two = apply(store, batch(store, "two", operations=[correction(relation(one, "a"))]))
        assert research(two)["status"] == "no_active_basis"
        assert research(two)["comparison_work"] == []
        three = apply(store, batch(store, "three", [b]), [b])
        assert three["report"]["searches"][0]["matches"] == []
        assert len(three["relations"]) == 1


def test_new_knowledge_reinterprets_old_members_without_new_analysis_or_market_facts(tmp_path):
    from app.job_analysis.knowledge.catalog import LoadedSnapshot
    knowledge = shipped()
    empty = knowledge.snapshot.model_copy(deep=True)
    empty.roles = []
    empty.revision = "synthetic-empty"
    old_knowledge = LoadedSnapshot(knowledge.path, empty, digest(empty.model_dump()))
    a = duties("a", ["编写并调试订单服务代码"])
    original = deepcopy(a)
    with CandidateStore(tmp_path / "s.db", create=True) as store:
        one = apply(store, batch(store, "one", [a], [create(a)]), [a], old_knowledge)
        two = apply(store, batch(store, "two"), knowledge=knowledge)
        m = research(two)["member_explanations"][0]
        assert research(one)["member_explanations"][0]["role_explanations"] == []
        assert next(r for r in m["role_explanations"] if r["role_id"] == "p0-ref-programming")["judgment"] == "supported"
        assert store.source("comparison", m["role_comparison_sha256"])["knowledge_sha256"] == knowledge.sha256
        assert store.source("alignment", m["alignment_sha256"])["knowledge_sha256"] == knowledge.sha256
        assert two["relations"] == one["relations"]
        assert two["analysis_sha256s"] == one["analysis_sha256s"]
        assert a == original == store.source("analysis", digest(a))
        assert "knowledge_reinterpretation" in two["report"]["evolution"]["work-orders"]["causes"]
        assert two["report"]["evolution"]["work-orders"]["change_nature"] == "candidate_research_not_market_change"
        assert two["formal_roles"] == []
        assert store.read(1) == one


def test_analyzer_versions_are_ambiguous_until_exact_correction_and_never_revive(tmp_path):
    a = duties("a", ["开发订单交易接口。"])
    revised = deepcopy(a)
    revised["analyzer"]["revision"] = "controlled-v2"
    with CandidateStore(tmp_path / "s.db", create=True) as store:
        one = apply(store, batch(store, "one", [a], [create(a)]), [a])
        two = apply(store, batch(store, "two", [revised]), [revised])
        assert research(two)["comparison_work"] == []
        assert research(two)["member_explanations"][0]["eligibility"] == "competing_analysis_versions"
        change = two["report"]["evidence_changes"][digest(revised)]
        assert change["recruitment_content_changed"] is False
        assert change["analyzer_changed"] is True
        assert change["independent_demand"] is None
        op = correction(relation(two, "a"), "corroborates", replacement=dict(analysis_sha256=digest(revised), work_ids=["d1"]))
        three = apply(store, batch(store, "three", [revised], [op]), [revised])
        assert research(three)["comparison_work"] == [ref(revised)]
        four = apply(store, batch(store, "four", [a]), [a])
        assert four["candidates"] == three["candidates"]
        assert store.read(1) == one


def test_recruitment_content_and_analysis_changes_are_reported_separately(tmp_path):
    a = duties("a", ["开发订单交易接口。"])
    changed = duties("a", ["交付教学课程讲义。"])
    with CandidateStore(tmp_path / "s.db", create=True) as store:
        apply(store, batch(store, "one", [a], [create(a)]), [a])
        two = apply(store, batch(store, "two", [changed]), [changed])
        detail = two["report"]["evidence_changes"][digest(changed)]
        assert detail["recruitment_content_changed"] is True
        assert detail["analyzer_changed"] is False
        assert detail["previous_analysis_sha256s"] == [digest(a)]
        assert research(two)["shared_statements"] == []


def test_suggestions_bind_exact_versions_without_trusted_confirmation(tmp_path):
    from app.job_analysis.work_candidates.suggestions import check_suggestion
    a, b = duties("a", ["使用 Java 开发订单接口。"]), duties("b", ["使用 Java 讲授编程课程。"])
    with CandidateStore(tmp_path / "s.db", create=True) as store:
        apply(store, batch(store, "one", [a], [create(a)]), [a])
        two = apply(store, batch(store, "two", [b]), [b])
        suggestion = next(s for s in two["structural_suggestions"] if s["kind"] == "review_split")
        checked = check_suggestion(store, suggestion["id"], two["binding"])
        assert checked["confirmation"] == "unavailable_no_trusted_identity"
        assert suggestion["subjects"]["work-orders"]["candidate_sha256"] == digest(two["candidates"]["work-orders"])
        assert suggestion["subjects"]["work-orders"]["relation_sha256s"]
        assert suggestion["competing_explanations"]
        assert store.read() == two
        three = apply(store, batch(store, "three", operations=[correction(relation(two, "b"), "weakens")]))
        with pytest.raises(ValueError, match="stale"):
            check_suggestion(store, suggestion["id"], two["binding"])
        for forged in (dict(op="confirm", suggestion_id=suggestion["id"], reviewer="owner"),
                       dict(op="merge", candidate_id="work-orders", reviewer="trusted")):
            with pytest.raises(ValueError):
                apply(store, batch(store, "forged", operations=[forged]))
        assert store.read() == three
        assert three["formal_roles"] == []
        assert set(three["candidates"]) == {"work-orders"}


def test_historical_members_are_rechecked_but_not_restored_to_current_scope(tmp_path):
    a = duties("a", ["开发订单交易接口。"])
    b = duties("b", ["开发订单交易接口。", "负责课程教学并授课"])
    with CandidateStore(tmp_path / "s.db", create=True) as store:
        apply(store, batch(store, "one", [a], [create(a)]), [a])
        two = apply(store, batch(store, "two", [b]), [b])
        three = apply(store, batch(store, "three", operations=[correction(relation(two, "b"))]))
        historical = [m for m in research(three)["historical_explanations"] if m["jd_id"] == "b"]
        assert historical
        assert any(r["judgment"] == "not_supported" for m in historical for r in m["role_explanations"])
        assert all(r["analysis_sha256"] != digest(b) for r in research(three)["comparison_work"])


@pytest.mark.parametrize("kind", ["synthetic_control", "external_review_record"])
def test_controlled_and_claimed_external_reviews_never_become_independent_or_human_support(tmp_path, kind):
    import hashlib
    from app.job_analysis.work_candidates.service import review_subject
    a = duties("a", ["开发订单交易接口。"])
    with CandidateStore(tmp_path / "s.db", create=True) as store:
        one = apply(store, batch(store, "one", [a], [create(a)]), [a])
        old = relation(one, "a")
        subject = review_subject(old, one["candidates"]["work-orders"], "corroborates")
        op = correction(old, "corroborates")
        op["verification"] = dict(kind=kind, subject_sha256=subject, document=subject, quote=subject,
                                  document_sha256=hashlib.sha256(subject.encode()).hexdigest(),
                                  reviewer="claimed owner", provider_version="synthetic-control-v1")
        two = apply(store, batch(store, "two", operations=[op]))
        r = research(two)
        assert r["controlled_support_relation_ids"] == ([old["id"]] if kind == "synthetic_control" else [])
        assert r["human_confirmation"] == "not_confirmed"
        assert r["independent_support"] is None
        assert r["formal_identity"] is None


def test_possible_duplicate_suggestion_never_merges_identities(tmp_path):
    a = duties("a", ["开发订单交易接口。"])
    with CandidateStore(tmp_path / "s.db", create=True) as store:
        one = apply(store, batch(store, "one", [a], [create(a), create(a, "other")]), [a])
        suggestion = next(s for s in one["structural_suggestions"] if s["kind"] == "review_overlap")
        assert set(suggestion["subjects"]) == {"work-orders", "other"}
        assert suggestion["evidence"]
        assert len(one["candidates"]) == 2
        assert one["formal_roles"] == []


def test_legacy_p3_upgrade_does_not_use_withdrawn_seeds(tmp_path):
    a, b = duties("a", ["开发订单交易接口。"]), duties("b", ["开发订单交易接口。"])
    with CandidateStore(tmp_path / "s.db", create=True) as store:
        one = apply(store, batch(store, "one", [a], [create(a)]), [a])
        withdrawn = apply(store, batch(store, "two", operations=[correction(relation(one, "a"))]))
        legacy = deepcopy(withdrawn)
        legacy["candidates"]["work-orders"].pop("research")
        # Simulate an actual P3 snapshot using the supported append-only store, never editing old rows.
        legacy["revision"] += 1
        store.append("legacy-projection", digest({"synthetic": "p3-shape"}), legacy)
        old = store.read()
        upgraded = apply(store, batch(store, "upgrade", [b]), [b])
        assert upgraded["report"]["searches"][0]["matches"] == []
        assert len(upgraded["relations"]) == 1
        assert research(upgraded)["comparison_work"] == []
        assert store.read(old["revision"]) == old


@pytest.mark.parametrize("text", ["开发订单交易接口  。", "开发订单\n交易接口。"])
def test_whitespace_republication_preserves_effective_meaning_and_display(tmp_path, text):
    a = duties("a", ["开发订单交易接口。"])
    repost = duties("copy", [text])
    with CandidateStore(tmp_path / "s.db", create=True) as store:
        one = apply(store, batch(store, "one", [a], [create(a)]), [a])
        two = apply(store, batch(store, "two", [repost]), [repost])
        assert len(research(two)["content_groups"]) == 1
        assert research(two)["effective_hypothesis_sha256"] == research(one)["effective_hypothesis_sha256"]
        assert research(two)["description"] == research(one)["description"]
        assert research(two)["version"] == research(one)["version"]
        assert two["report"]["evolution"]["work-orders"]["applied"] is False
        assert store.source("analysis", digest(repost)) == repost


def test_reordered_claims_in_republication_are_audit_changes_only(tmp_path):
    a = duties("a", ["开发订单交易接口。", "执行幂等校验并维护去重记录。"])
    repost = duties("copy", ["开发订单交易接口。", "执行幂等校验并维护去重记录。"])
    repost["claims"].reverse()
    seed = create(a)
    seed["core_work"].append(ref(a, "d2"))
    with CandidateStore(tmp_path / "s.db", create=True) as store:
        one = apply(store, batch(store, "one", [a], [seed]), [a])
        two = apply(store, batch(store, "two", [repost]), [repost])
        assert research(two)["version"] == research(one)["version"]
        assert research(two)["description"] == research(one)["description"]
        assert two["report"]["evolution"]["work-orders"]["applied"] is False
        assert store.source("analysis", digest(repost)) == repost

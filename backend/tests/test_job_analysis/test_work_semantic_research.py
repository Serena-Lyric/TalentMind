"""Synthetic boundary controls, deliberately separate from independent DEV truth."""
import pytest

from app.job_analysis.foundation.inputs import digest
from app.job_analysis.work_candidates.storage import CandidateStore
from test_work_candidates import apply, batch, cleanup_p3_files, correction, create, ref
from test_work_evolution import duties, research, relation


def test_paraphrase_and_stack_difference_are_local_research_with_bound_evidence(tmp_path):
    a = duties("a", ["使用 Java 开发订单接口。"])
    b = duties("b", ["用 Go 实现订单服务接口。"])
    with CandidateStore(tmp_path / "state.db", create=True) as store:
        one = apply(store, batch(store, "one", [a], [create(a)]), [a])
        two = apply(store, batch(store, "two", [b]), [b])
        member = relation(two, "b")
        assert member["discovery"]["kind"] == "automatic_bounded_semantic"
        assert member["discovery"]["baseline"] == one["binding"]
        assert member["formal_identity"] is None
        assert research(two)["semantic_shared_statements"]
        assert research(two)["semantic_shared_statements"][0]["references"]
        assert research(two)["human_confirmation"] == "not_confirmed"
        assert store.read(1) == one


@pytest.mark.parametrize('prefix', ['不负责', '如有需要才', '由开发团队负责', '曾经负责'])
def test_cropped_valid_quote_cannot_drop_source_scope(tmp_path, prefix):
    from test_work_candidates import work
    from test_knowledge_alignment import evidence
    from app.job_analysis.foundation.inputs import InputRecord
    from app.job_analysis.baseline.contract import validate_analysis
    a = work('a', '开发订单接口。')
    b = work('b', prefix + '开发订单接口。')
    b['claims'][0]['text'] = '开发订单接口'
    b['claims'][0]['evidence'] = [evidence(InputRecord.from_row(b['namespace'], b['input_row']), '开发订单接口')]
    validate_analysis(b)
    with CandidateStore(tmp_path / 'state.db', create=True) as store:
        apply(store, batch(store, 'one', [a], [create(a)]), [a])
        result = apply(store, batch(store, 'two', [b]), [b])
        assert not any(r['jd_id'] == 'b' for r in result['relations'].values())


@pytest.mark.parametrize('quote', ['不承担课程教学，仅开发软件', '仅开发软件', '开发软件'])
def test_source_scope_preserves_explicit_affirmed_local_work(tmp_path, quote):
    from test_work_candidates import work
    from test_knowledge_alignment import evidence
    from app.job_analysis.foundation.inputs import InputRecord
    a = work('a', '开发软件。')
    b = work('b', '不承担课程教学，仅开发软件。')
    b['claims'][0]['evidence'] = [evidence(InputRecord.from_row(b['namespace'], b['input_row']), quote)]
    with CandidateStore(tmp_path / 'state.db', create=True) as store:
        apply(store, batch(store, 'one', [a], [create(a)]), [a])
        result = apply(store, batch(store, 'two', [b]), [b])
        assert relation(result, 'b')['work_ids'] == ['d1']
        pairs = result['report']['searches'][0]['matches'][0]['pairs']
        assert all(p['comparison']['left']['matched_source_units'] for p in pairs)


@pytest.mark.parametrize('text,quote', [
    ('如有需要才：\n开发软件。', '开发软件'),
    ('由开发团队负责：\n开发软件。', '开发软件'),
    ('不开发软件，本岗位负责开发订单接口。', '开发软件'),
])
def test_source_scope_cannot_borrow_uncited_affirmation_or_drop_heading(tmp_path, text, quote):
    from test_work_candidates import work
    from test_knowledge_alignment import evidence
    from app.job_analysis.foundation.inputs import InputRecord
    a = work('a', '开发软件。')
    b = work('b', text)
    b['claims'][0]['text'] = '开发软件'
    b['claims'][0]['evidence'] = [evidence(InputRecord.from_row(b['namespace'], b['input_row']), quote)]
    with CandidateStore(tmp_path / 'state.db', create=True) as store:
        apply(store, batch(store, 'one', [a], [create(a)]), [a])
        result = apply(store, batch(store, 'two', [b]), [b])
        assert not any(r['jd_id'] == 'b' for r in result['relations'].values())


@pytest.mark.parametrize("text,core", [
    ("使用 Java 讲授编程课程。", True),
    ("不负责开发订单接口。", True),
    ("如有需要开发订单接口。", True),
    ("为开发人员整理订单接口需求。", True),
    ("协助开发订单接口。", False),
    ("使用 Java 开发自动化测试框架。", True),
    ("使用 Java 开发图像分类算法。", True),
])
def test_related_words_and_non_direct_scope_cannot_create_automatic_member(tmp_path, text, core):
    a = duties("a", ["使用 Java 开发订单接口。"])
    b = duties("b", [text])
    b["claims"][0]["core"] = core
    with CandidateStore(tmp_path / "state.db", create=True) as store:
        apply(store, batch(store, "one", [a], [create(a)]), [a])
        two = apply(store, batch(store, "two", [b]), [b])
        assert not any(r["jd_id"] == "b" for r in two["relations"].values())
        search = two["report"]["searches"][0]
        assert search["lexical_matches"]  # frozen weak baseline still exposes the old lead
        assert search["candidate_checks"]["work-orders"]["eligible"] is False


def test_every_member_is_checked_without_similarity_chain_then_withdrawal_is_consumed(tmp_path):
    a = duties("a", ["开发订单接口。"])
    b = duties("b", ["开发订单接口。", "生成销售报告。"])
    c = duties("c", ["制作销售报表。"])
    with CandidateStore(tmp_path / "state.db", create=True) as store:
        one = apply(store, batch(store, "one", [a], [create(a)]), [a])
        two = apply(store, batch(store, "two", [b], [dict(op="link", candidate_id="work-orders",
                    analysis_sha256=digest(b), work_ids=["d1", "d2"], reason="显式混合职责观察")]), [b])
        three = apply(store, batch(store, "three", [c]), [c])
        assert not any(r["jd_id"] == "c" for r in three["relations"].values())
        check = three["report"]["searches"][0]["candidate_checks"]["work-orders"]
        assert len(check["members"]) == 2
        assert any(not m["supported_duty_ids"] for m in check["members"])
        four = apply(store, batch(store, "four", operations=[correction(relation(three, "a"))]))
        five = apply(store, batch(store, "five", [c]), [c])
        assert relation(five, "c")["discovery"]["baseline"] == four["binding"]
        assert ref(a) not in research(five)["comparison_work"]
        assert store.read(1) == one
        assert store.read(2) == two


def test_partial_core_overlap_does_not_claim_entire_role_coverage(tmp_path):
    a = duties("a", ["开发订单接口。"])
    b = duties("b", ["实现订单接口。", "负责课程教学。"])
    with CandidateStore(tmp_path / "state.db", create=True) as store:
        apply(store, batch(store, "one", [a], [create(a)]), [a])
        two = apply(store, batch(store, "two", [b]), [b])
        member = next(m for m in research(two)["member_explanations"] if m["jd_id"] == "b")
        assert member["unselected_duty_ids"] == ["d2"]
        assert member["semantic_scope"]["uncovered_core_duty_ids"] == ["d2"]
        assert research(two)["whole_group_confirmed"] is False


def test_source_negation_overrides_a_positive_p1_paraphrase(tmp_path):
    a = duties("a", ["开发订单接口。"])
    b = duties("b", ["不负责开发订单接口。"])
    b["claims"][0]["text"] = "开发订单接口。"
    with CandidateStore(tmp_path / "state.db", create=True) as store:
        apply(store, batch(store, "one", [a], [create(a)]), [a])
        two = apply(store, batch(store, "two", [b]), [b])
        assert not any(r["jd_id"] == "b" for r in two["relations"].values())


def test_unresolved_counterevidence_prevents_automatic_expansion(tmp_path):
    a, b, c = [duties(name, ["开发订单接口。"], stack=name) for name in ("a", "b", "c")]
    with CandidateStore(tmp_path / "state.db", create=True) as store:
        apply(store, batch(store, "one", [a], [create(a)]), [a])
        two = apply(store, batch(store, "two", [b]), [b])
        three = apply(store, batch(store, "three", operations=[correction(relation(two, "b"), "weakens")]))
        four = apply(store, batch(store, "four", [c]), [c])
        assert not any(r["jd_id"] == "c" for r in four["relations"].values())
        assert four["report"]["searches"][0]["candidate_checks"]["work-orders"]["counterevidence_relation_ids"]
        assert store.read(3) == three


def test_readonly_candidate_store_reads_while_writer_holds_transaction(tmp_path):
    import sqlite3
    path = tmp_path / "state.db"
    with CandidateStore(path, create=True) as writer:
        baseline = writer.read()
        writer.conn.execute("BEGIN IMMEDIATE")
        try:
            with CandidateStore(path, readonly=True) as reader:
                assert reader.read() == baseline
                with pytest.raises(sqlite3.OperationalError, match="readonly"):
                    reader.put_source("test", {"synthetic": True})
        finally:
            writer.conn.rollback()
    with pytest.raises(ValueError, match="exist"):
        CandidateStore(tmp_path / "missing.db", readonly=True)
    assert not (tmp_path / "missing.db").exists()


def test_private_replay_records_baselines_actual_consumption_and_no_invented_accuracy(tmp_path):
    from app.job_analysis.work_candidates.evaluation import evaluate_analyses
    from test_knowledge_alignment import shipped
    a = duties("a", ["开发订单接口。"])
    b = duties("b", ["实现订单接口。"])
    result = evaluate_analyses([a, b], shipped(), tmp_path / "evaluation", source_bindings=[])
    assert result["real_grouping_human_denominator"] == 0
    assert result["grouping_accuracy"] is None
    assert result["automatic_links"] >= 1
    assert result["maintenance"]["history_preserved"] is True
    assert result["maintenance"]["later_batch_consumed_revised_binding"] is True
    assert result["maintenance"]["withdrawn_relation_not_revived"] is True
    assert result["input_nature"] == "synthetic_mechanism"
    with pytest.raises(FileExistsError):
        evaluate_analyses([a, b], shipped(), tmp_path / "evaluation", source_bindings=[])


def test_replay_uses_delivery_and_exposes_role_and_skill_layers(tmp_path):
    from app.job_analysis.work_candidates.evaluation import evaluate_analyses
    from test_knowledge_alignment import shipped
    a = duties("a", ["开发订单接口。"])
    result = evaluate_analyses([a], shipped(), tmp_path / "delivery", source_bindings=[], via_delivery=True)
    assert result["execution_entry"] == "delivery.execute"
    assert result["rows"][0]["delivery"]["role_assignment"]
    assert result["rows"][0]["skill_alignment"]["state_counts"]
    assert result["maintenance"]["later_batch_consumed_revised_binding"]


def test_explicit_cli_baseline_replays_same_inputs_and_binds_sources(tmp_path):
    from pathlib import Path
    from app.job_analysis.work_candidates.evaluation import evaluate_analyses, replay_cli_baseline
    from test_knowledge_alignment import shipped
    a = duties("a", ["开发订单接口。"])
    evaluate_analyses([a], shipped(), tmp_path / "current", source_bindings=[])
    result = replay_cli_baseline(tmp_path / "current", tmp_path / "baseline",
                                 Path(__file__).resolve().parents[2], shipped().path)
    assert result["batch_count"] == 1
    assert result["source_sha256s"]
    assert result["rows"][0]["analysis_sha256s"] == [digest(a)]
    assert all(c["returncode"] == 0 for c in result["commands"])

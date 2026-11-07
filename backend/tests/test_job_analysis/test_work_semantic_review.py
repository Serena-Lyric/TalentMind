"""PR75 source-object and responsibility regressions through actual consumers."""
from copy import deepcopy
import pytest

from app.job_analysis.baseline.contract import validate_analysis
from app.job_analysis.foundation.inputs import InputRecord
from app.job_analysis.work_candidates.retrieval import compare_work
from app.job_analysis.work_candidates.storage import CandidateStore
from test_knowledge_alignment import evidence
from test_role_research_summary import build
from test_knowledge_roles import analysis_with_duties
from test_work_candidates import apply, batch, cleanup_p3_files, create, work


@pytest.mark.parametrize("text", [
    "编写软件采购合同", "编写软件服务采购合同", "编写软件模块采购说明",
    "优化神经网络", "优化社交网络", "优化网络设备采购计划",
    "编写神经网络采购合同", "维护软件测试报告", "优化卷积网络性能",
])
def test_whole_unknown_object_is_uncovered_in_default_delivery(text):
    result = build(analysis_with_duties([text]))
    assert not result["local_supports"]
    assert result["uncovered_work"][0]["source_gaps"]
    assert any(text in gap["quote"] for gap in result["uncovered_work"][0]["source_gaps"])


@pytest.mark.parametrize("text,reference", [
    ("编写软件代码", "resp-write-program"),
    ("开发软件服务", "resp-software-develop"),
    ("优化通信网络性能", "resp-network-optimize"),
    ("优化网络性能", "resp-network-optimize"),
    ("制作商业智能报告", "resp-bi-report"),
])
def test_direct_objects_keep_default_delivery_support(text, reference):
    result = build(analysis_with_duties([text]))
    assert any(s["reference_id"] == reference for s in result["local_supports"])
    assert not result["uncovered_work"]


@pytest.mark.parametrize("incoming", ["优化神经网络", "优化社交网络", "优化网络设备采购计划"])
def test_unknown_network_compound_does_not_join_real_candidate_store(tmp_path, incoming):
    a, b = work("a", "优化通信网络性能"), work("b", incoming)
    with CandidateStore(tmp_path / "state.db", create=True) as store:
        old = apply(store, batch(store, "one", [a], [create(a)]), [a])
        result = apply(store, batch(store, "two", [b]), [b])
        assert not any(r["jd_id"] == "b" for r in result["relations"].values())
        assert not result["report"]["searches"][0]["matches"]
        assert store.read(1) == old


@pytest.mark.parametrize("quote", ["协助职责：\n开发订单接口", "开发订单接口"])
def test_full_and_short_quote_keep_auxiliary_heading_in_real_batch(tmp_path, quote):
    a = work("a", "开发订单接口")
    b = work("b", "协助职责：\n开发订单接口。\n要求：Python。")
    b["claims"][0].update(core=None, text="开发订单接口")
    b["claims"][0]["evidence"] = [evidence(InputRecord.from_row(b["namespace"], b["input_row"]), quote)]
    validate_analysis(b)
    original = deepcopy(b)
    judgment = compare_work(b["claims"][0], a["claims"][0], b, a)
    assert judgment["left"]["importance"] == "auxiliary"
    assert judgment["state"] == "unresolved"
    summary = build(b)
    assert summary["local_supports"]
    assert {s["importance"] for s in summary["local_supports"]} == {"auxiliary"}
    with CandidateStore(tmp_path / "state.db", create=True) as store:
        apply(store, batch(store, "one", [a], [create(a)]), [a])
        result = apply(store, batch(store, "two", [b]), [b])
        assert not any(r["jd_id"] == "b" for r in result["relations"].values())
    assert b == original


@pytest.mark.parametrize("text,role,reference", [
    ("编写软件采购合同", "ref-software-development", "resp-software-develop"),
    ("优化神经网络", "p0-ref-network-operations", "resp-network-optimize"),
])
def test_new_work_version_cannot_fill_unknown_object_from_two_positive_responses(text, role, reference):
    from app.job_analysis.knowledge.work_comparison import start_work_comparison, add_work_response
    from test_knowledge_context import execute
    from test_knowledge_work_comparison import first, second
    from test_knowledge_local_semantics import binding
    context = execute(analysis_with_duties([text]))
    result = add_work_response(start_work_comparison(context, version=4), "d1", role, reference,
                               first(), second(), binding(), "qwen3-instruct", 1, 1)
    assert result.task_assessments[0].state == "unresolved"
    assert not result.work_candidates


@pytest.mark.parametrize("text,role,reference,input_sha", [
    ("编写软件采购合同", "ref-software-development", "resp-software-develop",
     "835c2ad4bb7df6110ba519737a7048bc4f02a74c370855eecbadacb76422bcb3"),
    ("优化神经网络", "p0-ref-network-operations", "resp-network-optimize",
     "68f8c8b527a649ffd4e33fc1de835db410352f64701746258e8bc06617d9ae7e"),
])
def test_published_v3_interpretation_keeps_pre_fix_input_and_state(text, role, reference, input_sha):
    from app.job_analysis.foundation.inputs import digest
    from app.job_analysis.knowledge.work_comparison import start_work_comparison, add_work_response, WorkComparisonResult
    from test_knowledge_context import execute
    from test_knowledge_work_comparison import first, second
    from test_knowledge_local_semantics import binding
    result = add_work_response(start_work_comparison(execute(analysis_with_duties([text])), version=3),
        "d1", role, reference, first(), second(), binding(), "qwen3-instruct", 1, 1)
    saved = result.model_dump()
    assert digest(result.task_assessments[0].input_json) == input_sha
    assert result.task_assessments[0].state == "machine_supported"  # Historical error, not new support.
    assert WorkComparisonResult.model_validate(saved).model_dump() == saved


def test_understood_prefix_does_not_hide_unknown_second_object(tmp_path):
    a, b = work("a", "开发订单接口"), work("b", "开发订单接口并维护数据库")
    summary = build(b)
    assert summary["local_supports"]
    assert summary["uncovered_work"][0]["source_gaps"]
    with CandidateStore(tmp_path / "state.db", create=True) as store:
        apply(store, batch(store, "one", [a], [create(a)]), [a])
        result = apply(store, batch(store, "two", [b]), [b])
        assert not any(r["jd_id"] == "b" for r in result["relations"].values())


def test_direct_network_paraphrase_still_creates_local_research_relation(tmp_path):
    a, b = work("a", "优化通信网络性能"), work("b", "优化网络性能")
    with CandidateStore(tmp_path / "state.db", create=True) as store:
        apply(store, batch(store, "one", [a], [create(a)]), [a])
        result = apply(store, batch(store, "two", [b]), [b])
        member = next(r for r in result["relations"].values() if r["jd_id"] == "b")
        assert member["discovery"]["kind"] == "automatic_bounded_semantic"


def test_new_independent_heading_ends_auxiliary_context():
    a = work("a", "开发订单接口")
    b = work("b", "协助职责：\n维护网络。\n主要职责：\n开发订单接口。")
    b["claims"][0]["evidence"] = [evidence(InputRecord.from_row(b["namespace"], b["input_row"]), "开发订单接口")]
    validate_analysis(b)
    judgment = compare_work(b["claims"][0], a["claims"][0], b, a)
    assert judgment["left"]["importance"] == "core"
    assert judgment["state"] == "supported"


@pytest.mark.parametrize("text,role,reference", [
    ("编写用户需求规格说明书（SRS）", "p0-ref-programming", "resp-write-design-doc"),
    ("开展系统中间件核心模块开发", "ref-software-development", "resp-software-develop"),
    ("负责商业智能（BI）产品的整体规划、开发与上线工作", "ref-business-intelligence", "resp-bi-tools"),
    ("配合开发团队完成功能实现", "ref-software-development", "resp-software-develop"),
])
def test_v4_keeps_compositional_objects_and_model_only_unknown_work(text, role, reference):
    from app.job_analysis.knowledge.work_comparison import start_work_comparison, add_work_response
    from test_knowledge_context import execute
    from test_knowledge_work_comparison import first, second
    from test_knowledge_local_semantics import binding
    result = add_work_response(start_work_comparison(execute(analysis_with_duties([text])), version=4),
        "d1", role, reference, first(), second(), binding(), "qwen3-instruct", 1, 1)
    assert result.task_assessments[0].state == "machine_supported"


@pytest.mark.parametrize("text,quote,anchor", [
    ("编写软件采购合同", "编写软件", "编写软件代码"),
    ("优化神经网络", "优化神经网络", "优化通信网络性能"),
])
def test_short_quote_cannot_reinterpret_unknown_complete_object(tmp_path, text, quote, anchor):
    a, b = work("a", anchor), work("b", text)
    b["claims"][0]["evidence"] = [evidence(InputRecord.from_row(b["namespace"], b["input_row"]), quote)]
    validate_analysis(b)
    assert not build(b)["local_supports"]
    with CandidateStore(tmp_path / "state.db", create=True) as store:
        apply(store, batch(store, "one", [a], [create(a)]), [a])
        result = apply(store, batch(store, "two", [b]), [b])
        assert not any(r["jd_id"] == "b" for r in result["relations"].values())


def test_uncited_auxiliary_work_cannot_change_prior_core_work(tmp_path):
    a = work("a", "开发订单接口")
    b = work("b", "开发订单接口并协助维护网络")
    b["claims"][0]["evidence"] = [evidence(InputRecord.from_row(b["namespace"], b["input_row"]), "开发订单接口")]
    validate_analysis(b)
    judgment = compare_work(b["claims"][0], a["claims"][0], b, a)
    assert judgment["left"]["importance"] == "core"
    assert judgment["state"] == "supported"
    assert {s["importance"] for s in build(b)["local_supports"]} == {"core"}
    with CandidateStore(tmp_path / "state.db", create=True) as store:
        apply(store, batch(store, "one", [a], [create(a)]), [a])
        result = apply(store, batch(store, "two", [b]), [b])
        assert any(r["jd_id"] == "b" for r in result["relations"].values())


def test_summary_of_historical_v3_does_not_claim_current_parser():
    from app.job_analysis.knowledge.research_summary import build_research_summary
    from test_work_comparison_v3 import result
    assert build_research_summary(result("开发软件"))["method_version"] == "bounded-work-semantics-1"


@pytest.mark.parametrize("quote", ["开发订单接口", "订单接口", "开发订单"])
def test_source_context_cannot_add_uncited_action_or_object(quote):
    a, b = work("a", "开发订单接口"), work("b", "开发订单接口")
    b["claims"][0]["evidence"] = [evidence(InputRecord.from_row(b["namespace"], b["input_row"]), quote)]
    validate_analysis(b)
    result = compare_work(b["claims"][0], a["claims"][0], b, a)
    assert (result["state"] == "supported") is (quote == "开发订单接口")


def test_v4_model_work_keeps_source_heading_importance():
    from app.job_analysis.knowledge.work_comparison import start_work_comparison, add_work_response
    from test_knowledge_context import execute
    from test_knowledge_work_comparison import first, second
    from test_knowledge_local_semantics import binding
    b = work("b", "协助职责：\n开发订单接口。")
    b["claims"][0]["core"] = None
    b["claims"][0]["evidence"] = [evidence(InputRecord.from_row(b["namespace"], b["input_row"]), "开发订单接口")]
    result = add_work_response(start_work_comparison(execute(b), version=4), "d1", "ref-software-development",
        "resp-software-develop", first(), second(), binding(), "qwen3-instruct", 1, 1)
    assert result.work_candidates[0].importance == "auxiliary"
    assert "协助职责" in result.task_assessments[0].primary.prompt


@pytest.mark.parametrize("heading", ["无需承担：", "如果项目需要：", "客户负责："])
def test_v4_model_agreement_cannot_remove_uncited_controlling_heading(heading):
    from app.job_analysis.knowledge.work_comparison import start_work_comparison, add_work_response
    from test_knowledge_context import execute
    from test_knowledge_work_comparison import first, second
    from test_knowledge_local_semantics import binding
    b = work("b", heading + "\n开发订单接口。")
    b["claims"][0]["core"] = None
    b["claims"][0]["evidence"] = [evidence(InputRecord.from_row(b["namespace"], b["input_row"]), "开发订单接口")]
    result = add_work_response(start_work_comparison(execute(b), version=4), "d1", "ref-software-development",
        "resp-software-develop", first(), second(), binding(), "qwen3-instruct", 1, 1)
    assert result.task_assessments[0].state == "unresolved"


def test_unknown_full_object_repetition_remains_literal_observation(tmp_path):
    a, b = work("a", "优化神经网络"), work("b", "优化神经网络")
    with CandidateStore(tmp_path / "state.db", create=True) as store:
        apply(store, batch(store, "one", [a], [create(a)]), [a])
        result = apply(store, batch(store, "two", [b]), [b])
        pair = result['report']['searches'][0]['matches'][0]['pairs'][0]
        assert pair['evidence_nature'] == 'exact_local_text_repetition'
        assert pair['comparison']['state'] == 'unresolved'


@pytest.mark.parametrize('text', [
    '编写软件采购合同及代码', '编写软件采购合同、代码',
    '编写代码及软件采购合同', '编写代码、霁风材料',
])
def test_unknown_coordinated_object_keeps_gap_and_direct_code_support(text):
    result = build(analysis_with_duties([text]))
    assert any(s['reference_id'] == 'resp-write-program' for s in result['local_supports'])
    assert result['uncovered_work'][0]['source_gaps']


def test_two_known_coordinated_software_objects_need_no_unknown_gap():
    result = build(analysis_with_duties(['编写软件代码及应用程序']))
    assert any(s['reference_id'] == 'resp-write-program' for s in result['local_supports'])
    assert not result['uncovered_work']


@pytest.mark.parametrize('text,quote', [
    ('编写软件采购合同及代码', '编写软件'),
    ('编写接口采购合同及接口', '编写接口'),
    ('编写Ｓｏｆｔｗａｒｅ采购合同及代码', '编写Ｓｏｆｔｗａｒｅ'),
])
def test_short_internal_object_cannot_borrow_later_coordinated_code(text, quote):
    b = work('b', text)
    b['claims'][0]['evidence'] = [evidence(InputRecord.from_row(b['namespace'], b['input_row']), quote)]
    validate_analysis(b)
    assert not build(b)['local_supports']


def test_partial_coordinated_object_support_does_not_link_entire_claim(tmp_path):
    a, b = work('a', '编写软件代码'), work('b', '编写软件采购合同及代码')
    with CandidateStore(tmp_path / 'state.db', create=True) as store:
        apply(store, batch(store, 'one', [a], [create(a)]), [a])
        result = apply(store, batch(store, 'two', [b]), [b])
        assert not any(r['jd_id'] == 'b' for r in result['relations'].values())


def test_normalized_object_head_offsets_still_point_to_original_characters():
    from app.job_analysis.knowledge.work_semantics import explain_work
    text = '编写Ｓｏｆｔｗａｒｅ、代码'
    frames = explain_work(text)['frames']
    assert {f['object_quote'] for f in frames} == {'Ｓｏｆｔｗａｒｅ', '代码'}
    assert all(text[f['object_start']:f['object_end']] == f['object_quote'] for f in frames)

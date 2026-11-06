"""Business boundaries for the new task comparison path, without real data."""
from copy import deepcopy
import json

import pytest

from app.job_analysis.knowledge.attribution import read_attribution
from app.job_analysis.knowledge.storage import save_result
from test_knowledge_context import execute
from test_knowledge_local_semantics import binding, response
from test_knowledge_roles import analysis_with_duties


def test_empty_catalog_leaves_role_axes_unrun_and_technology_independent():
    result = execute(analysis_with_duties(["使用Python开发软件服务"]), empty=True)
    assert result.axis_assessments["family"].status == "not_evaluated"
    assert result.axis_assessments["canonical_job"].reason_code == "no_versioned_reference"
    assert result.axis_assessments["technology_tracks"].status == "evaluated"
    assert result.axes.technology_tracks.values == ["Python"]


def test_no_work_facts_are_not_evaluated_as_unknown_work():
    value = analysis_with_duties([])
    result = execute(value)
    assert result.retrieval.status == "facts_unavailable"
    for name in ("family", "canonical_job", "technology_tracks"):
        assert result.axis_assessments[name].status == "not_evaluated"
        assert result.axis_assessments[name].reason_code == "no_work_facts"


def test_goal_work_can_evaluate_technology_without_duty_role_evaluation():
    value = analysis_with_duties(["使用Python开发软件服务"])
    value["claims"][0]["kind"] = "goal"
    result = execute(value)
    assert result.axis_assessments["canonical_job"].status == "not_evaluated"
    assert result.axis_assessments["technology_tracks"].status == "evaluated"
    assert result.axes.technology_tracks.values == ["Python"]


def test_raw_model_suggestions_do_not_enter_business_candidates_or_recalled_set():
    from app.job_analysis.knowledge.local_semantics import apply_response
    result = execute(analysis_with_duties(["将业务流程封装为可调用的工具能力"]))
    out = apply_response(result, response(result), binding())
    assert out.semantic.matches
    assert out.axes == result.axes
    assert out.retrieval == result.retrieval
    assert out.work_units == result.work_units


def test_legacy_raw_suggestion_history_keeps_its_original_reading(tmp_path):
    from app.job_analysis.knowledge.local_semantics import apply_response
    old = execute(analysis_with_duties(["将业务流程封装成工具能力"]))
    old = old.model_copy(update={"explanation_version": "context-work-attribution-3"})
    old = apply_response(old, response(old), binding())
    assert old.axes.canonical_job.candidates
    payload = old.model_dump()
    save_result(tmp_path / "history", payload)
    assert read_attribution(tmp_path / "history").model_dump() == payload


def test_history_cannot_relabel_missing_role_evaluation_as_completed(tmp_path):
    out = execute(analysis_with_duties(["使用Python开发软件服务"]), empty=True)
    payload = out.model_dump()
    payload["axis_assessments"]["family"] = dict(status="evaluated", reason_code="local_work_evidence")
    save_result(tmp_path / "bad", payload)
    with pytest.raises(ValueError):
        read_attribution(tmp_path / "bad")


def pair_response(**updates):
    value = dict(action_relation="supported", object_relation="supported", execution_relation="performs_task",
                 source_action="写成", source_object="业务逻辑", reference_action="开发",
                 reference_object="软件系统", reason="合成对照：将业务规则实现为后端接口是软件开发的一项工作方面。")
    value.update(updates)
    return json.dumps(value, ensure_ascii=False)


def compare_one(value=None, raw=None, *, claim_id="d1", object_raw='{"relation":"operational_component","reason":"合成对象类型对照"}'):
    from app.job_analysis.knowledge.task_comparison import compare_response, start_comparison
    base = execute(value or analysis_with_duties(["将客户订购请求写成服务端可执行的业务逻辑"]))
    result = start_comparison(base)
    return compare_response(result, claim_id, "ref-software-development", "resp-software-develop",
                            raw or pair_response(), binding(), "qwen3-instruct", elapsed_seconds=1.0,
                            object_response=object_raw, object_elapsed_seconds=1.0 if object_raw is not None else 0.0)


def test_pair_comparison_can_explain_nonliteral_work_without_promoting_identity():
    result = compare_one()
    assert result.task_assessments[0].state == "machine_supported"
    assert result.work_candidates[0].role_id == "ref-software-development"
    assert result.task_assessments[0].source_action_evidence.quote == "写成"
    assert result.source_claims[0].text == "将客户订购请求写成服务端可执行的业务逻辑"
    assert result.primary_role_id is None
    assert not result.axes.canonical_job.values
    assert result.unaccounted_work


@pytest.mark.parametrize("updates", [dict(execution_relation="enables_others"),
                                     dict(object_relation="different"), dict(action_relation="unknown")])
def test_pair_rejects_enabling_or_unmatched_work_despite_valid_source_quotes(updates):
    result = compare_one(raw=pair_response(**updates))
    assert result.task_assessments[0].state != "machine_supported"
    assert not result.work_candidates
    assert not any(c.conflicts for c in result.comparisons)


def test_model_quotes_cannot_borrow_objects_from_another_claim():
    value = analysis_with_duties(["实现业务需求文档", "负责维护软件系统"])
    result = compare_one(value, pair_response(source_object="软件系统"))
    assert result.task_assessments[0].state == "failed"
    assert not result.work_candidates


def test_model_cannot_override_negation_or_other_actor_scope():
    value = analysis_with_duties(["客户负责将客户订购请求写成服务端可执行的业务逻辑"])
    result = compare_one(value)
    assert result.task_assessments[0].state != "machine_supported"
    assert not result.work_candidates


def test_checked_history_rejects_upgraded_state_and_keeps_model_out_of_read(tmp_path, monkeypatch):
    result = compare_one(raw=pair_response(object_relation="different"))
    payload = result.model_dump()
    save_result(tmp_path / "good", payload)
    assert read_attribution(tmp_path / "good").model_dump() == payload
    bad = deepcopy(payload)
    bad["task_assessments"][0]["state"] = "machine_supported"
    save_result(tmp_path / "bad", bad)
    with pytest.raises(ValueError):
        read_attribution(tmp_path / "bad")


def test_task_selection_is_auditable_and_never_labels_a_score_as_support():
    from app.job_analysis.knowledge.task_comparison import select_tasks, start_comparison
    result = start_comparison(execute(analysis_with_duties(["把订单处理规则实现为可调用的后端接口"])))
    class Ranker:
        binding = {"id": "synthetic-score-fixture", "revision": "test", "sha256": "a" * 64}
        def rank(self, pairs):
            return [(0.5, False) for _ in pairs]
    selected = select_tasks(result, Ranker(), pairs_per_role=1)
    assert len(selected.selected_pair_ids) == 5
    assert len(selected.proposals) > 5
    assert all(p.claim_id == "d1" for p in selected.proposals)
    assert not result.work_candidates
    assert selected.unchecked_pair_ids


def test_history_cannot_erase_selection_while_keeping_checked_candidates(tmp_path):
    result = compare_one()
    payload = result.model_dump()
    for name in ("proposals", "selected_pair_ids", "unchecked_pair_ids"):
        payload["task_selection"][name] = []
    save_result(tmp_path / "bad", payload)
    with pytest.raises(ValueError):
        read_attribution(tmp_path / "bad")


def test_action_and_object_cannot_be_spliced_across_independent_work():
    result = compare_one(analysis_with_duties(["编写会议纪要，同时审阅软件系统设计文档"]),
                         pair_response(source_action="编写", source_object="软件系统"))
    assert result.task_assessments[0].state != "machine_supported"
    assert not result.work_candidates


def test_pair_budget_is_not_a_hidden_one_task_per_claim_budget():
    from app.job_analysis.knowledge.task_comparison import select_tasks, start_comparison
    result = start_comparison(execute(analysis_with_duties(["负责开发软件服务并分析用户需求"])))
    class Ranker:
        binding = {"id": "synthetic-score-fixture", "revision": "test", "sha256": "a" * 64}
        def rank(self, pairs): return [(0.5, False) for _ in pairs]
    selection = select_tasks(result, Ranker(), pairs_per_role=3)
    selected = [p for p in selection.proposals if p.id in selection.selected_pair_ids
                and p.role_id == "ref-software-development"]
    assert len(selected) == 3
    assert len({p.reference_id for p in selected}) == 3


def test_lexical_and_semantic_priority_lanes_preserve_different_retrieval_opportunities():
    from app.job_analysis.knowledge.task_comparison import select_tasks, start_comparison
    result = start_comparison(execute(analysis_with_duties(["研究外部系统原理", "设计、开发或修改软件系统"])))
    class Ranker:
        binding = {"id": "synthetic-score-fixture", "revision": "test", "sha256": "a" * 64}
        def rank(self, pairs): return [(0.9 if p[0] == "研究外部系统原理" else 0.1, False) for p in pairs]
    selection = select_tasks(result, Ranker(), pairs_per_role=2)
    selected = [p for p in selection.proposals if p.id in selection.selected_pair_ids
                and p.role_id == "ref-software-development"]
    assert {p.claim_id for p in selected} == {"d1", "d2"}
    assert not result.work_candidates


def test_foreign_assessment_identity_is_rejected_as_a_contract_error(tmp_path):
    result = compare_one()
    value = result.model_dump()
    value["task_assessments"][0]["claim_id"] = "foreign-duty"
    from app.job_analysis.knowledge.task_models import pair_identity
    value["task_assessments"][0]["id"] = pair_identity("foreign-duty", "ref-software-development", "resp-software-develop")
    save_result(tmp_path / "bad", value)
    with pytest.raises(ValueError):
        read_attribution(tmp_path / "bad")


def test_pair_source_group_does_not_split_participation_inside_a_word():
    result = compare_one(analysis_with_duties(["参与编写软件系统"]),
                         pair_response(source_action="参与编写", source_object="软件系统"))
    assert result.task_assessments[0].state == "machine_supported"


def test_coordinated_bare_predicates_can_share_the_following_object():
    result = compare_one(analysis_with_duties(["负责设计、开发和维护高效、稳定的软件系统"]),
                         pair_response(source_action="设计、开发和维护", source_object="软件系统"))
    assert result.task_assessments[0].state == "machine_supported"


def test_old_pair_input_retains_its_original_group_guard_and_reading(tmp_path):
    from app.job_analysis.knowledge.task_comparison import start_comparison, compare_response
    base = execute(analysis_with_duties(["负责设计、开发和维护高效、稳定的软件系统"]))
    old = start_comparison(base).model_copy(update={"explanation_version": "task-evidence-attribution-1"})
    old = compare_response(old, "d1", "ref-software-development", "resp-software-develop",
        pair_response(source_action="设计、开发和维护", source_object="软件系统"), binding(), "qwen3-instruct", 1.0)
    assert old.task_assessments[0].state == "unresolved"
    payload = old.model_dump()
    save_result(tmp_path / "old", payload)
    assert read_attribution(tmp_path / "old").model_dump() == payload


def test_history_cannot_call_an_executed_task_selection_not_run(tmp_path):
    result = compare_one()
    payload = result.model_dump()
    payload["task_selection"]["status"] = "not_run"
    save_result(tmp_path / "bad", payload)
    with pytest.raises(ValueError):
        read_attribution(tmp_path / "bad")


def test_separate_object_type_check_blocks_preparation_document_as_software():
    result = compare_one(analysis_with_duties(["编写用户需求说明书，为开发人员实现功能提供依据"]),
        pair_response(source_action="编写", source_object="用户需求说明书"),
        object_raw='{"relation":"supporting_input","reason":"说明书是开发输入，不是软件功能组成"}')
    assert not result.work_candidates
    assert result.task_assessments[0].state == "different_work"
    assert result.task_assessments[0].object_check.judgment.relation == "supporting_input"


def test_missing_object_type_check_is_not_machine_support():
    result = compare_one(object_raw=None)
    assert result.task_assessments[0].state == "unresolved"
    assert result.task_assessments[0].reason_code == "object_check_not_run"
    assert not result.work_candidates


def test_object_check_history_cannot_change_its_bound_objects(tmp_path):
    result = compare_one()
    value = result.model_dump()
    value["task_assessments"][0]["object_check"]["input_json"] = '{}'
    save_result(tmp_path / "bad", value)
    with pytest.raises(ValueError):
        read_attribution(tmp_path / "bad")


def test_object_from_someone_elses_purpose_cannot_attach_to_own_action():
    result = compare_one(analysis_with_duties(["编写用户需求说明书，为其他团队设计软件系统提供依据"]),
                         pair_response(source_action="编写", source_object="软件系统"))
    assert result.task_assessments[0].state != "machine_supported"
    assert not result.work_candidates


def test_reference_quotes_can_use_the_bound_original_task_source():
    result = compare_one(raw=pair_response(reference_action="Design, develop and modify",
                                          reference_object="software systems"))
    assert result.task_assessments[0].state == "machine_supported"
    assert any("software systems" in e.quote for e in result.task_assessments[0].reference_evidence)

"""Source-bound interpretations are not rewritten facts or model-made quotes."""
import json
from copy import deepcopy

import pytest

from app.job_analysis.knowledge.attribution import read_attribution
from app.job_analysis.knowledge.storage import save_result
from test_knowledge_context import execute
from test_knowledge_local_semantics import binding
from test_knowledge_roles import analysis_with_duties


def first(**updates):
    value = dict(action_interpretation="形成模块设计文档", object_interpretation="软件模块设计说明",
        reason="源描述软件模块方案设计并输出设计文档。", action_relation="same_or_specific",
        responsibility_relation="direct_task_aspect", functional_object_relation="same_or_narrower",
        requires_unstated_context=False)
    value.update(updates)
    return json.dumps(value, ensure_ascii=False)


def second(**updates):
    value = dict(reason="原文明确包含模块方案设计及设计文档输出。", relation="direct_same_work",
                 requires_unstated_context=False)
    value.update(updates)
    return json.dumps(value, ensure_ascii=False)


def compare(raw1=None, raw2=None, value=None):
    from app.job_analysis.knowledge.work_comparison import start_work_comparison, add_work_response
    base = execute(value or analysis_with_duties(["结合平台架构完成软件模块方案设计，输出设计文档"]))
    result = start_work_comparison(base)
    return add_work_response(result, "d1", "p0-ref-programming", "resp-write-design-doc",
        raw1 or first(), raw2 or second(), binding(), "qwen3-instruct", 1.0, 1.0)


def test_interpretation_may_paraphrase_but_evidence_is_the_actual_source():
    result = compare()
    assert result.task_assessments[0].state == "machine_supported"
    assert result.task_assessments[0].source_evidence == result.source_claims[0].evidence
    assert "形成模块设计文档" not in result.source_claims[0].text
    assert result.work_candidates[0].mapping_status == "machine_hypothesis"
    assert result.source_claims[0].text == "结合平台架构完成软件模块方案设计，输出设计文档"
    assert not result.formal_statistics_eligible


@pytest.mark.parametrize("verdict", [dict(relation="only_input_or_related"),
                                     dict(requires_unstated_context=True), dict(relation="unknown")])
def test_second_view_cannot_inherit_a_primary_assumption(verdict):
    result = compare(raw2=second(**verdict))
    assert result.task_assessments[0].state != "machine_supported"
    assert not result.work_candidates


def test_reference_domain_and_examples_are_bound_definition_not_source_facts():
    result = compare()
    data = json.loads(result.task_assessments[0].input_json)
    assert data["model_input"]["reference_context"]["goals"]
    assert data["model_input"]["reference_context"]["object_examples"]
    assert data["source_evidence"] == [e.model_dump() for e in result.source_claims[0].evidence]


def test_auxiliary_participation_is_work_but_never_becomes_primary():
    result = compare(value=analysis_with_duties(["协助完成软件模块方案设计，输出设计文档"], core_values=[False]))
    assert result.task_assessments[0].state == "machine_supported"
    assert result.work_candidates[0].importance == "auxiliary"
    assert result.primary_role_id is None
    assert result.source_claims[0].core is False


def test_history_rejects_changed_source_or_upgraded_second_view(tmp_path):
    result = compare(raw2=second(relation="unknown"))
    payload = result.model_dump()
    save_result(tmp_path / "good", payload)
    assert read_attribution(tmp_path / "good").model_dump() == payload
    wrong = deepcopy(payload)
    wrong["task_assessments"][0]["state"] = "machine_supported"
    save_result(tmp_path / "bad", wrong)
    with pytest.raises(ValueError):
        read_attribution(tmp_path / "bad")


def test_missing_or_failed_verification_is_observable(tmp_path):
    from app.job_analysis.knowledge.work_comparison import start_work_comparison, add_work_response
    base = execute(analysis_with_duties(["结合平台架构完成软件模块方案设计，输出设计文档"]))
    result = add_work_response(start_work_comparison(base), "d1", "p0-ref-programming", "resp-write-design-doc",
        first(), None, binding(), "qwen3-instruct", 1.0, 0.0)
    assert result.task_assessments[0].state == "unresolved"
    assert result.task_assessments[0].reason_code == "verification_not_run"
    assert not result.work_candidates


def test_controlled_task_examples_expand_retrieval_without_becoming_support():
    from app.job_analysis.knowledge.work_comparison import start_work_comparison
    from app.job_analysis.knowledge.task_comparison import select_tasks
    result = start_work_comparison(execute(analysis_with_duties(["编码"])))
    class Ranker:
        binding = {"id": "synthetic", "revision": "fixture", "sha256": "a"*64}
        def rank(self, pairs):return [(0.5, False) for _ in pairs]
    selection = select_tasks(result, Ranker(), 2, definition_examples=True)
    assert any(p.id in selection.selected_pair_ids and p.role_id == "p0-ref-programming"
               and p.reference_id == "resp-write-program" for p in selection.proposals)
    assert selection.method == "definition-context-task-budget-1"
    assert not result.work_candidates


def test_model_view_does_not_receive_other_actor_work_as_job_holder_work():
    from app.job_analysis.knowledge.work_comparison import start_work_comparison, work_input_v1
    source = analysis_with_duties(["本人负责数据清洗；客户负责开发软件系统"])
    result = start_work_comparison(execute(source))
    data = work_input_v1(result, "d1", "ref-software-development", "resp-software-develop")
    assert any("客户负责" in e["quote"] for e in data["source_evidence"])
    assert all("客户负责" not in text for text in data["model_input"]["work_texts"])
    assert all(n["scope"] in {"affirmed", "instructional"} for n in data["model_input"]["scope_notes"])


@pytest.mark.parametrize("raw1,raw2,reason", [
    ("not-json", second(), "primary_invalid_or_failed"),
    (first(), "not-json", "verification_invalid_or_failed"),
    (first(reason=" " * 3), second(), "primary_invalid_or_failed"),
])
def test_invalid_responses_remain_failed_instead_of_semantic_counterevidence(raw1, raw2, reason):
    result = compare(raw1, raw2)
    assert result.task_assessments[0].state == "failed"
    assert result.task_assessments[0].reason_code == reason
    assert not result.work_candidates


def test_history_rejects_rewritten_program_bound_quotation(tmp_path):
    value = compare().model_dump()
    value["task_assessments"][0]["source_evidence"][0]["quote"] = "目标任务被伪装为源工作"
    save_result(tmp_path / "bad", value)
    with pytest.raises(ValueError, match="program-bound source"):
        read_attribution(tmp_path / "bad")


@pytest.mark.parametrize("text,scope", [
    ("协助开发团队完成软件系统开发", "affirmed"),
    ("配合开发团队完成软件系统编码", "affirmed"),
    ("配合数据团队完成记录校验", "affirmed"),
    ("配合数据分析团队完成记录校验", "affirmed"),
    ("协助后端团队完成软件系统开发", "affirmed"),
    ("协助客户服务团队完成数据分析", "affirmed"),
    ("协助供应链团队完成记录校验", "affirmed"),
    ("协助供应商团队完成记录校验", "affirmed"),
    ("配合供应团队完成记录校验", "affirmed"),
    ("协助外部供应商团队完成记录校验", "affirmed"),
    ("配合采购供应团队完成记录校验", "affirmed"),
    ("配合供需分析团队完成记录校验", "affirmed"),
    ("协助供给团队完成记录校验", "affirmed"),
    ("开发团队完成软件系统开发", "other_actor"),
    ("数据团队完成软件系统开发", "other_actor"),
    ("安排数据团队完成软件系统开发", "other_actor"),
    ("协助安排数据团队完成记录校验", "other_actor"),
    ("配合讨论后团队完成记录校验", "other_actor"),
    ("本人协助整理资料而客户完成软件系统开发", "other_actor"),
    ("本人协助整理资料但开发团队完成软件系统开发", "other_actor"),
    ("本人协助整理资料以便客户完成软件系统开发", "other_actor"),
    ("本人协助整理资料供客户完成软件系统开发", "other_actor"),
    ("本人协助整理资料供后端团队完成软件系统开发", "other_actor"),
    ("本人协助整理资料供数据团队完成软件系统开发", "other_actor"),
    ("本人协助整理资料供应急团队完成软件系统开发", "other_actor"),
    ("本人协助整理资料供需求团队完成软件系统开发", "other_actor"),
    ("安排开发团队完成软件系统开发", "other_actor"),
    ("若有需要则协助开发团队完成软件系统开发", "conditional"),
])
def test_personal_collaboration_is_distinct_from_delegating_work_to_a_team(text, scope):
    result = execute(analysis_with_duties([text], core_values=[False]))
    assert result.work_units[0].scope == scope
    assert result.work_units[0].importance == "auxiliary"
    if scope == "other_actor":
        assert not any(c.supports for c in result.comparisons)


def test_public_work_method_runs_selected_pairs_and_reads_without_models(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from app.job_analysis.knowledge.attribution import attribute_roles
    from app.job_analysis.knowledge.catalog import load_snapshot
    from app.job_analysis.knowledge.role_policy import load_policy
    from app.job_analysis.knowledge.work_context_models import ModelBinding
    from test_knowledge_context import ROOT
    class Ranker:
        binding = {"id": "synthetic", "revision": "fixture", "sha256": "a" * 64}
        def rank(self, pairs):
            return [(0.5, False) for _ in pairs]
    class Model:
        manifest = SimpleNamespace(binding=ModelBinding.model_validate(binding()), prompt_format="qwen3-instruct")
        calls = 0
        def complete_json(self, prompt, schema):
            self.calls += 1
            assert json.loads(prompt.split("\nDATA_JSON\n")[1])["work_texts"]
            return first(action_relation="different")
    model = Model()
    source = analysis_with_duties(["协助开发团队完成软件系统开发"], core_values=[False])
    result = attribute_roles(source, load_snapshot(ROOT / "catalog/role-references.v3"),
        load_policy(ROOT / "policies/role-attribution.v2.json"), method="work",
        local_model=model, task_retriever=Ranker(), pairs_per_role=2)
    assert model.calls == len(result.task_assessments) == len(result.task_selection.selected_pair_ids) > 0
    assert not result.task_selection.pending_selected_pair_ids
    assert result.source_analysis.model_dump() == source
    assert not result.work_candidates
    assert result.axes == execute(source).axes
    save_result(tmp_path / "result", result.model_dump())
    monkeypatch.setattr(Model, "complete_json", lambda *args: pytest.fail("historical read called a model"))
    assert read_attribution(tmp_path / "result").model_dump() == result.model_dump()


@pytest.mark.parametrize("header,scope", [("如果项目批准：", "conditional"),
    ("能力允许的话可以延伸", "conditional"), ("客户负责：", "other_actor"), ("过去职责：", "historical")])
@pytest.mark.parametrize("split_citations", [False, True])
def test_governing_header_survives_newlines_and_separate_citations(header, scope, split_citations):
    from app.job_analysis.foundation.inputs import InputRecord
    from test_knowledge_alignment import evidence
    body = "开发软件系统并输出设计文档"
    value = analysis_with_duties([header + "\n" + body])
    if split_citations:
        row = InputRecord.from_row(value["namespace"], value["input_row"])
        value["claims"][0]["evidence"] = [evidence(row, header), evidence(row, body)]
    result = compare(value=value)
    assert all(u.scope == scope for u in result.work_units)
    assert result.task_assessments[0].state == "unresolved"
    assert not result.work_candidates
    from app.job_analysis.knowledge.work_comparison import work_input_v2
    view = work_input_v2(result, "d1", "p0-ref-programming", "resp-write-design-doc")["model_input"]
    assert any(header in text for text in view["source_context"])


@pytest.mark.parametrize("header,body,scope", [
    ("如果项目批准：", "本人负责开发软件系统", "conditional"),
    ("如果项目批准：", "当前负责开发软件系统", "conditional"),
    ("过去职责：", "本人负责开发软件系统", "historical"),
    ("过去职责：", "当前负责开发软件系统", "affirmed"),
    ("客户负责：", "本人负责开发软件系统", "affirmed"),
    ("禁止以下工作：", "本人负责开发软件系统", "negated"),
])
def test_changing_actor_does_not_cancel_a_governing_condition_or_past_time(header, body, scope):
    result = execute(analysis_with_duties([header + "\n" + body]))
    assert result.work_units[-1].scope == scope


@pytest.mark.parametrize("header,scope", [("如果项目批准：", "conditional"), ("禁止以下工作：", "negated"),
                                        ("过去职责：", "historical")])
def test_inner_actor_heading_cannot_replace_outer_condition_or_prohibition(header, scope):
    result = execute(analysis_with_duties([header + "\n客户负责：\n需求确认\n本人负责开发软件系统"]))
    assert result.work_units[-1].scope == scope
    assert result.primary_role_id is None


def test_explicit_current_work_can_end_history_and_other_actor_headers():
    result = execute(analysis_with_duties(["过去职责：\n客户负责：\n当前负责开发软件系统"]))
    assert result.work_units[-1].scope == "affirmed"

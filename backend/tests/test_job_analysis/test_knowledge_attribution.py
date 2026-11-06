"""P2-2 business counterexamples; synthetic inputs are not market truth."""
from copy import deepcopy

import pytest

from test_knowledge_roles import analysis_with_duties


def execute(texts, **kwargs):
    from app.job_analysis.knowledge.attribution import attribute_roles
    from app.job_analysis.knowledge.role_policy import load_policy, default_policy_path
    from app.job_analysis.knowledge.catalog import load_snapshot

    policy = load_policy(default_policy_path())
    knowledge = load_snapshot(policy.path.parent.parent / "catalog" / "role-references.v2")
    return attribute_roles(analysis_with_duties(texts, **kwargs), knowledge, policy)


def role(result, role_id):
    return next(item for item in result.comparisons if item.role_id == role_id)


def test_same_title_different_deliveries_retrieves_different_work():
    etl = execute(["负责设计和开发ETL数据管道，交付数据仓库"], row_extra={"job_title": "数据工程师"})
    bi = execute(["负责分析业务指标，交付商业智能分析报告"], row_extra={"job_title": "数据工程师"})
    assert etl.axes.canonical_job.values == ["ref-data-warehousing"]
    assert bi.axes.canonical_job.values == ["ref-business-intelligence"]
    assert etl.primary_role_id != bi.primary_role_id
    assert role(bi, "ref-data-warehousing").judgment == "unresolved"
    assert not role(bi, "ref-data-warehousing").conflicts


@pytest.mark.parametrize("stack", ["Java", "Go", "Python"])
def test_same_service_responsibility_stable_job_independent_tracks(stack):
    result = execute([f"使用{stack}开发订单软件服务，交付可运行应用"], requirement=stack)
    assert result.axes.canonical_job.values == ["ref-software-development"]
    assert result.axes.technology_tracks.values == [stack]
    assert result.axes.seniority.status == "unresolved"
    assert result.semantic_review == "machine_unreviewed"
    assert not result.formal_statistics_eligible


def test_auxiliary_network_work_does_not_compete_with_core_service():
    result = execute(["开发软件服务并交付应用", "偶尔协助监测网络性能"], core_values=[True, False])
    assert result.primary_role_id == "ref-software-development"
    assert "p0-ref-network-operations" in result.auxiliary_role_ids
    assert role(result, "p0-ref-network-operations").judgment == "auxiliary"


def test_parallel_core_deliveries_keep_main_unresolved():
    result = execute(["开发软件服务并交付应用", "分析业务指标并交付商业智能报告"])
    assert result.primary_role_id is None
    assert result.axes.canonical_job.status == "multiple"
    assert result.work_shape == "parallel_core_hypothesis"
    assert result.identity_action == "none"


def test_explicit_multiple_hiring_targets_do_not_create_vacancies():
    result = execute(["开发软件服务并交付应用"], row_extra={"job_title": "招后端工程师两名、测试工程师一名"})
    assert result.work_shape == "multi_position_advertisement"
    assert result.primary_role_id is None
    assert result.axes.canonical_job.status == "unresolved"
    assert result.identity_action == "none"


def test_partial_duties_and_unknown_core_keep_local_family_and_tracks():
    result = execute(["使用Python开发软件服务并交付应用"], core_values=[None], duty_coverage="partial")
    assert result.primary_role_id is None
    assert result.axes.canonical_job.status == "unresolved"
    assert result.axes.family.values == ["software_engineering"]
    assert result.axes.technology_tracks.values == ["Python"]
    assert "p1_duties_partial" in result.limitations


@pytest.mark.parametrize("text", [
    "不承担软件开发，仅进行课程教学",
    "如果客户需要则开发软件服务并交付应用",
    "客户负责开发软件服务并交付应用",
    "具备开发软件服务并交付应用的经验",
    "介绍开发软件服务并交付应用的方法",
    "开发分析报告并整理软件服务资料",
])
def test_scope_and_action_object_counterexamples_do_not_support_work(text):
    result = execute([text])
    assert not role(result, "ref-software-development").supports
    assert result.primary_role_id is None


def test_negated_teaching_is_neither_positive_conflict_nor_lost_development():
    result = execute(["不承担课程教学，仅负责开发软件服务并交付应用"])
    assert result.primary_role_id == "ref-software-development"
    assert not any(item.conflicts for item in result.comparisons)


def test_source_span_and_reference_support_are_auditable():
    result = execute(["主要负责开发软件服务并交付应用"])
    support = role(result, "ref-software-development").supports[0]
    assert support.action == "开发"
    assert support.object == "软件服务"
    assert support.basis == "bounded_pattern_support"
    assert support.jd_evidence.quote == "主要负责开发软件服务"
    assert support.reference_evidence
    assert result.retrieval.checked_role_ids == [item.role_id for item in result.comparisons]
    assert result.retrieval.ranking == "unranked_exhaustive"
    assert result.source_analysis_sha256 and result.policy_sha256 and result.implementation_sha256


def test_missing_delivery_cannot_be_invented_from_duty_or_definition():
    result = execute(["负责开发软件服务"])
    assert result.axes.family.values == ["software_engineering"]
    assert result.axes.canonical_job.status == "unresolved"
    assert "delivery_not_evidenced" in role(result, "ref-software-development").uncertainty


def test_explicit_auxiliary_word_overrides_machine_core_without_rewriting_fact():
    result = execute(["开发软件服务并交付应用", "偶尔协助分析业务指标并交付商业智能报告"])
    assert result.primary_role_id == "ref-software-development"
    assert "ref-business-intelligence" in result.auxiliary_role_ids
    assert result.source_claims[1].core is True


def test_empty_or_narrow_directory_is_observable_not_negative():
    from app.job_analysis.knowledge.attribution import attribute_roles
    from app.job_analysis.knowledge.role_policy import load_policy, default_policy_path, bind_policy
    from app.job_analysis.knowledge.catalog import LoadedSnapshot, load_snapshot
    from app.job_analysis.foundation.inputs import digest

    base = load_policy(default_policy_path())
    original = load_snapshot(base.path.parent.parent / "catalog" / "role-references.v2")
    for ids in [set(), {"p0-ref-programming"}]:
        value = original.snapshot.model_dump()
        value["roles"] = [r for r in value["roles"] if r["id"] in ids]
        knowledge = LoadedSnapshot(original.path, type(original.snapshot).model_validate(value), digest(value))
        policy = deepcopy(base.policy.model_dump())
        policy["knowledge_sha256"] = knowledge.sha256
        policy["roles"] = [r for r in policy["roles"] if r["role_id"] in ids]
        result = attribute_roles(analysis_with_duties(["负责授课并交付教学课程"]), knowledge, bind_policy(policy))
        assert result.primary_role_id is None
        assert not any(item.judgment == "conflict" for item in result.comparisons)
        assert result.retrieval.checked_role_ids == sorted(ids)
        assert result.retrieval.scope_limitation
        assert result.axes.canonical_job.status == "unresolved"


def test_facts_requirements_and_projection_binding_preserved(tmp_path):
    from app.job_analysis.knowledge.attribution import attribute_roles
    from app.job_analysis.knowledge.role_policy import load_policy, default_policy_path
    from app.job_analysis.knowledge.catalog import load_snapshot
    from app.job_analysis.knowledge.candidates import CandidateRegistry

    policy = load_policy(default_policy_path())
    knowledge = load_snapshot(policy.path.parent.parent / "catalog" / "role-references.v2")
    source = analysis_with_duties(["开发软件服务并交付应用"], requirement="Python")
    before = deepcopy(source)
    projection = CandidateRegistry(tmp_path / "registry").project()
    result = attribute_roles(source, knowledge, policy, projection)
    assert source == before
    assert result.alignment.requirements[0].source_requirement == source["claims"][-1]["requirement"]
    assert result.alignment.candidate_projection_sha256 == projection.sha256
    assert result.source_claims[-1].model_dump() == source["claims"][-1]


def test_years_and_proficiency_do_not_imply_seniority():
    result = execute(["开发软件服务并交付应用"], requirement="五年以上工作经验，精通Python")
    assert result.axes.seniority.status == "unresolved"
    assert not result.axes.seniority.values


def test_skills_without_responsibility_cannot_create_compound_career():
    result = execute(["整理招聘材料"], requirement="Python、SQL、Kubernetes")
    assert result.axes.canonical_job.status == "unresolved"
    assert result.work_shape == "unresolved"
    assert result.identity_action == "none"


def test_reverse_action_object_must_not_cross_an_unrelated_work_item():
    result = execute(["配合代码评审与工单定位修改"])
    assert not role(result, "ref-software-development").supports
    assert not role(result, "p0-ref-programming").supports


def test_multiple_technology_tracks_are_independent_of_canonical_job():
    result = execute(["使用Python开发软件服务并交付应用", "使用Java开发应用程序并交付应用"])
    assert result.axes.technology_tracks.values == ["Java", "Python"]
    assert result.axes.canonical_job.values == ["ref-software-development"]


def test_unmatched_core_work_prevents_unique_job_without_excluding_reference():
    result = execute(["开发软件服务并交付应用", "承担课程教学并交付教学大纲"])
    assert result.primary_role_id is None
    assert result.axes.canonical_job.status == "unresolved"
    assert role(result, "ref-software-development").judgment == "core_candidate"
    assert "d2" in role(result, "ref-software-development").uncovered_duty_ids
    assert "unaccounted_core_work" in result.limitations


def test_partial_goal_and_object_coverage_is_reported_independently():
    from app.job_analysis.knowledge.attribution import attribute_roles
    from app.job_analysis.knowledge.role_policy import load_policy, default_policy_path
    from app.job_analysis.knowledge.catalog import load_snapshot
    policy = load_policy(default_policy_path())
    knowledge = load_snapshot(policy.path.parent.parent / "catalog/role-references.v2")
    source = analysis_with_duties(["开发软件服务并交付应用"])
    source["coverage"]["goals"] = {"status": "partial", "reason": "合成目标缺口"}
    source["coverage"]["objects"] = {"status": "not_run", "reason": "合成对象未执行"}
    source["outcome"] = "partial"
    result = attribute_roles(source, knowledge, policy)
    assert "p1_goals_partial" in result.limitations
    assert "p1_objects_not_run" in result.limitations
    assert role(result, "ref-software-development").deliveries
    assert result.axes.family.values == ["software_engineering"]


def test_condition_scope_crossing_comma_cannot_confirm_core_work():
    result = execute(["如果客户需要，开发软件服务并交付应用"])
    assert not role(result, "ref-software-development").supports
    assert result.primary_role_id is None


def test_one_claim_does_not_let_other_work_lend_its_delivery_or_technology():
    result = execute(["开发软件服务；设计数据管道并交付数据服务"])
    assert not role(result, "ref-software-development").deliveries
    assert result.primary_role_id is None
    result = execute(["开发软件服务并交付应用；使用Python整理招聘资料"])
    assert not result.axes.technology_tracks.values


@pytest.mark.parametrize("separator", ["并", "以及", "同时"])
def test_coordinated_new_predicate_has_its_own_work_scope(separator):
    result = execute([f"开发软件服务{separator}设计数据管道并交付数据服务"])
    assert not role(result, "ref-software-development").deliveries
    assert result.primary_role_id is None
    result = execute([f"开发软件服务并交付应用{separator}使用Python整理招聘资料"])
    assert not result.axes.technology_tracks.values
    assert result.primary_role_id is None


def test_auxiliary_clause_without_comma_keeps_core_delivery():
    result = execute(["开发软件服务并交付应用同时协助监测网络性能"])
    assert result.primary_role_id == "ref-software-development"


def test_auxiliary_clause_does_not_erase_separate_core_work_in_same_claim():
    result = execute(["开发软件服务并交付应用，同时协助监测网络性能"])
    assert result.primary_role_id == "ref-software-development"
    assert role(result, "p0-ref-network-operations").judgment == "auxiliary"


def test_single_numbered_position_is_not_multiple_hiring_targets():
    result = execute(["开发软件服务并交付应用"], row_extra={"job_title": "岗位1：软件工程师"})
    assert result.work_shape != "multi_position_advertisement"
    assert result.primary_role_id == "ref-software-development"


def test_other_unmatched_core_task_inside_same_claim_is_visible():
    result = execute(["开发软件服务并交付应用；负责课程授课并交付教学大纲"])
    assert result.primary_role_id is None
    assert result.axes.canonical_job.status == "unresolved"
    assert result.unaccounted_work


def test_explicit_boundary_uses_actual_positive_work_and_both_sources():
    from app.job_analysis.knowledge.attribution import attribute_roles
    from app.job_analysis.knowledge.role_policy import load_policy, default_policy_path, bind_policy
    from app.job_analysis.knowledge.catalog import LoadedSnapshot, load_snapshot
    from app.job_analysis.knowledge.models import validate_snapshot
    from app.job_analysis.foundation.inputs import digest
    policy = load_policy(default_policy_path())
    old = load_snapshot(policy.path.parent.parent / "catalog/role-references.v2")
    snapshot = old.snapshot.model_dump()
    programming = next(r for r in snapshot["roles"] if r["id"] == "ref-software-development")
    programming["boundaries"] = [{
        "id": "synthetic-course-boundary", "text": "合成明确边界：仅以课程教学为主要交付不属此参照",
        "anchors": [["教学"], ["课程"]],
        "evidence": [{"source_id": "src-role-programming", "locator": "synthetic test only, not actual source boundary",
                      "quote": "仅以课程教学为主要交付不属此合成测试参照"}],
    }]
    knowledge = LoadedSnapshot(old.path, validate_snapshot(snapshot), digest(snapshot))
    rules = policy.policy.model_dump()
    rules["knowledge_sha256"] = knowledge.sha256
    rule = next(r for r in rules["roles"] if r["role_id"] == "ref-software-development")
    rule["boundary_frames"] = [{"reference_id": "synthetic-course-boundary", "actions": ["教学"], "objects": ["课程"]}]
    rule["adaptation_note"] = "合成边界机制测试，非实际外部职业边界"
    bound = bind_policy(rules)
    positive = attribute_roles(analysis_with_duties(["承担课程教学"]), knowledge, bound)
    conflict = role(positive, "ref-software-development")
    assert conflict.judgment == "conflict"
    assert conflict.conflicts[0].jd_evidence.quote == "承担课程教学"
    assert conflict.conflicts[0].reference_evidence
    negative = attribute_roles(analysis_with_duties(["不承担课程教学，仅开发软件服务并交付应用"]), knowledge, bound)
    assert not role(negative, "ref-software-development").conflicts


def test_full_stack_title_and_skills_cannot_establish_mature_composite_role():
    result = execute(["开发软件服务并交付应用"], requirement="Java、Python、JavaScript",
                     row_extra={"job_title": "全栈工程师"})
    assert result.work_shape != "composite_hypothesis"
    assert result.axes.canonical_job.values == ["ref-software-development"]


def test_goal_and_object_explanations_keep_source_and_unmatched_context():
    from app.job_analysis.knowledge.attribution import attribute_roles
    from app.job_analysis.knowledge.role_policy import load_policy, default_policy_path
    from app.job_analysis.knowledge.catalog import load_snapshot
    policy = load_policy(default_policy_path())
    knowledge = load_snapshot(policy.path.parent.parent / "catalog/role-references.v2")
    source = analysis_with_duties(["开发软件服务并交付应用", "整理招聘资料"])
    goal = dict(deepcopy(source["claims"][0]), id="g1", kind="goal")
    obj = dict(deepcopy(source["claims"][1]), id="o1", kind="object")
    source["claims"] += [goal, obj]
    result = attribute_roles(source, knowledge, policy)
    comparison = role(result, "ref-software-development")
    assert comparison.goal_claim_ids == ["g1"]
    assert comparison.context_supports[0].claim_id == "g1"
    assert comparison.unmatched_object_claim_ids == ["o1"]


def test_network_reference_requires_network_object_not_any_fault_or_performance():
    result = execute(["排查软件模块故障并监控应用性能"])
    assert not role(result, "p0-ref-network-operations").supports
    assert "infrastructure_operations" not in result.axes.family.values


def test_multi_action_reference_cannot_be_covered_by_dropping_its_second_action():
    result = execute(["负责模块调试、问题定位、故障排查、版本维护"])
    supports = role(result, "p0-ref-programming").supports
    assert not any(s.reference_id == "resp-debug-verify" for s in supports)

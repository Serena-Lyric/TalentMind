"""Review regressions: independent axes and work shape, synthetic only."""
from copy import deepcopy
from pathlib import Path

import pytest

from app.job_analysis.knowledge.attribution import attribute_roles
from app.job_analysis.knowledge.catalog import load_snapshot
from app.job_analysis.knowledge.role_policy import load_policy
from test_knowledge_roles import analysis_with_duties

MODULE = Path(__file__).resolve().parents[2] / "app/job_analysis/knowledge"


def run(texts, *, new_policy=False, **kwargs):
    policy = load_policy(MODULE / "policies" / ("role-attribution.v2.json" if new_policy else "role-attribution.v1.json"))
    knowledge = load_snapshot(MODULE / "catalog" / ("role-references.v3" if new_policy else "role-references.v2"))
    return attribute_roles(analysis_with_duties(texts, **kwargs), knowledge, policy)


def test_technical_work_can_support_track_without_any_role_support():
    result = run(["使用Python清洗采样数据并生成标注数据集"])
    assert not any(c.supports for c in result.comparisons)
    assert result.axes.canonical_job.status == "unresolved"
    assert result.axes.technology_tracks.values == ["Python"]
    candidate = result.axes.technology_tracks.candidates[0]
    assert candidate.claim_ids == ["d1"]
    assert candidate.role_ids == []
    assert candidate.evidence[0].quote == "使用Python清洗采样数据"
    assert result.semantic_review == "machine_unreviewed"


@pytest.mark.parametrize("text", [
    "使用Python清洗采样数据", "利用Python训练预测模型", "基于Python封装计算接口",
])
def test_catalog_empty_does_not_erase_actual_technology_work(text):
    from app.job_analysis.knowledge.catalog import LoadedSnapshot
    from app.job_analysis.knowledge.models import validate_snapshot
    from app.job_analysis.knowledge.role_policy import bind_policy
    from app.job_analysis.foundation.inputs import digest
    old = load_snapshot(MODULE / "catalog/role-references.v2")
    value = old.snapshot.model_dump()
    value["roles"] = []
    knowledge = LoadedSnapshot(old.path, validate_snapshot(value), digest(value))
    policy = load_policy(MODULE / "policies/role-attribution.v1.json").policy.model_dump()
    policy.update(knowledge_sha256=knowledge.sha256, roles=[])
    result = attribute_roles(analysis_with_duties([text]), knowledge, bind_policy(policy))
    assert result.retrieval.status == "empty_catalog"
    assert result.axes.technology_tracks.values == ["Python"]


@pytest.mark.parametrize("text", [
    "如果需要，使用Python清洗采样数据", "不使用Python清洗采样数据",
    "客户负责使用Python清洗采样数据", "具备使用Python清洗采样数据的经验",
    "熟悉Python的数据清洗方法", "介绍使用Python清洗采样数据的方法",
    "使用Python整理招聘资料", "使用Python；清洗采样数据",
    "使用Python排版文档，并训练预测模型",
    "使用Python整理招聘资料后开发软件服务", "使用Python整理招聘资料和开发软件服务",
    "使用Python进行系统开发培训",
])
def test_technology_terms_do_not_outgrow_work_scope(text):
    assert run([text]).axes.technology_tracks.values == []


def test_requirement_alone_is_not_actual_technology_work():
    result = run(["承担项目管理工作"], requirement="Python")
    assert result.axes.technology_tracks.values == []
    assert result.source_claims[-1].requirement.state == "preferred"


def test_goal_with_explicit_technical_work_is_not_gated_by_duty_kind():
    source = analysis_with_duties(["使用Python清洗采样数据"])
    source["claims"][0]["kind"] = "goal"
    policy = load_policy(MODULE / "policies/role-attribution.v1.json")
    knowledge = load_snapshot(MODULE / "catalog/role-references.v2")
    result = attribute_roles(source, knowledge, policy)
    assert not any(c.supports for c in result.comparisons)
    assert result.axes.technology_tracks.values == ["Python"]


def test_explicit_source_technology_surface_can_remain_unreviewed_candidate():
    result = run(["使用VectorFlux训练预测模型"], requirement="VectorFlux")
    assert result.axes.technology_tracks.values == ["VectorFlux"]
    assert result.alignment.alignments[0].state == "unknown"
    assert not result.formal_statistics_eligible


def test_literal_technology_in_work_does_not_require_a_skill_requirement():
    result = run(["使用VectorFlux训练预测模型"], requirement="Python")
    assert result.axes.technology_tracks.values == ["VectorFlux"]
    assert result.axes.technology_tracks.candidates[0].claim_ids == ["d1"]


def test_source_work_usage_survives_p1_paraphrase_omitting_the_tool():
    source = analysis_with_duties(["使用Python清洗采样数据"])
    source["claims"][0]["text"] = "清洗采样数据"
    result = attribute_roles(source, load_snapshot(MODULE / "catalog/role-references.v2"),
                             load_policy(MODULE / "policies/role-attribution.v1.json"))
    assert result.axes.technology_tracks.values == ["Python"]
    assert result.source_claims[0].text == "清洗采样数据"


def test_separate_means_do_not_lend_python_to_java_development():
    result = run(["使用Python整理招聘资料后使用Java开发软件服务"])
    assert result.axes.technology_tracks.values == ["Java"]


def test_training_software_development_is_different_from_development_training():
    assert run(["使用Python开发培训软件"]).axes.technology_tracks.values == ["Python"]


def test_two_technologies_can_be_means_of_the_same_work():
    assert run(["使用Python和Java开发软件服务"]).axes.technology_tracks.values == ["Java", "Python"]


def test_single_weak_role_is_not_mixed_work():
    result = run(["负责开发软件服务"])
    assert result.axes.family.values == ["software_engineering"]
    assert result.axes.canonical_job.status == "unresolved"
    assert result.work_shape == "unresolved"


def test_actual_primary_plus_auxiliary_directions_have_mixed_evidence():
    result = run(["开发软件服务并交付应用", "偶尔协助监测网络性能"], core_values=[True, False])
    assert result.primary_role_id == "ref-software-development"
    assert result.work_shape == "mixed_hypothesis"
    assert len(result.shape_evidence) >= 2


def test_parallel_core_work_keeps_parallel_instead_of_mixed():
    result = run(["开发软件服务并交付应用", "分析业务指标并交付商业智能报告"])
    assert result.work_shape == "parallel_core_hypothesis"
    assert result.primary_role_id is None


def test_two_overlapping_role_labels_do_not_prove_two_work_directions():
    from app.job_analysis.knowledge.role_policy import bind_policy
    knowledge = load_snapshot(MODULE / "catalog/role-references.v2")
    value = load_policy(MODULE / "policies/role-attribution.v1.json").policy.model_dump()
    program = next(r for r in value["roles"] if r["role_id"] == "p0-ref-programming")
    program["family"] = "another-synthetic-family"
    result = attribute_roles(analysis_with_duties(["编写代码"], core_values=[None]), knowledge, bind_policy(value))
    assert len(result.axes.family.values) == 2
    assert result.work_shape == "unresolved"


@pytest.mark.parametrize("text", ["计算服务的设计、开发与维护", "设计、开发和维护计算服务", "计算服务的设计并开发"])
def test_shared_object_in_coordinated_predicates_retains_development(text):
    from app.job_analysis.knowledge.role_policy import Frame
    from app.job_analysis.knowledge.work_evidence import frame_hits
    frame = Frame(reference_id="synthetic-computing", actions=["开发"], objects=["计算服务"])
    assert list(frame_hits(text, frame))


@pytest.mark.parametrize("text", [
    "计算服务的评审与数据管道开发", "开发报表并整理计算服务资料", "计算服务的教学开发",
    "客户负责计算服务的设计、开发与维护", "如果需要，计算服务的设计、开发与维护",
])
def test_shared_object_does_not_cross_new_object_or_unsafe_scope(text):
    from app.job_analysis.knowledge.role_policy import Frame
    from app.job_analysis.knowledge.work_evidence import frame_hits
    frame = Frame(reference_id="synthetic-computing", actions=["开发"], objects=["计算服务"])
    assert not list(frame_hits(text, frame))


def test_shared_predicate_evidence_stops_before_another_auxiliary_task():
    from app.job_analysis.knowledge.role_policy import Frame
    from app.job_analysis.knowledge.work_evidence import frame_hits
    text = "计算服务的设计并开发同时协助监测网络性能"
    matches = list(frame_hits(text, Frame(reference_id="test", actions=["开发"], objects=["计算服务"])))
    assert matches
    assert all(not auxiliary and "协助" not in text[start:end] for start, end, _, _, auxiliary in matches)


def test_new_reference_uses_sourced_bi_maintenance_without_core_promotion():
    result = run(["负责商业智能平台的日常维护和管理"], new_policy=True, core_values=[None])
    comparison = next(c for c in result.comparisons if c.role_id == "ref-business-intelligence")
    assert comparison.supports
    assert comparison.supports[0].reference_id == "resp-bi-maintain"
    assert "Task ID 16139" in comparison.supports[0].reference_evidence[0].locator
    assert result.axes.family.values == ["data_ai"]
    assert result.axes.canonical_job.status == "unresolved"
    assert result.work_shape == "unresolved"


def test_new_policy_program_implementation_is_local_not_approved_identity():
    result = run(["负责业务代码实现"], new_policy=True, core_values=[None])
    comparison = next(c for c in result.comparisons if c.role_id == "p0-ref-programming")
    assert comparison.supports
    assert comparison.judgment == "hypothesis"
    assert result.primary_role_id is None
    assert not result.formal_statistics_eligible


def test_v2_track_support_must_belong_to_its_actual_work_claim():
    from app.job_analysis.knowledge.attribution_models import AttributionResult
    result = run(["使用Python清洗采样数据"])
    value = result.model_dump()
    requirement_id = value["source_analysis"]["claims"][-1]["id"]
    value["axes"]["technology_tracks"]["candidates"][0]["claim_ids"] = [requirement_id]
    with pytest.raises(ValueError):
        AttributionResult.model_validate(value)


def test_v1_historical_shape_is_read_without_running_v2_classification():
    from app.job_analysis.knowledge.attribution_models import AttributionResult
    value = run(["负责开发软件服务"]).model_dump()
    value.update(explanation_version="bounded-work-attribution-1", work_shape="mixed_hypothesis")
    historic = AttributionResult.model_validate(value)
    assert historic.work_shape == "mixed_hypothesis"

from copy import deepcopy
from pathlib import Path

from app.job_analysis.knowledge.research_summary import build_delivery_research
from app.job_analysis.knowledge.catalog import load_snapshot
from test_knowledge_roles import analysis_with_duties

KNOWLEDGE = Path(__file__).resolve().parents[2] / "app/job_analysis/knowledge/catalog"


def build(source):
    return build_delivery_research(source, load_snapshot(KNOWLEDGE / "role-references.v3"))


def test_delivery_actually_evaluates_source_work_and_keeps_independent_axes():
    source = analysis_with_duties(["实现订单服务接口", "维护商业智能平台", "讲授软件开发课程"])
    original = deepcopy(source)
    result = build(source)
    assert result["status"] == "bounded_research_completed"
    assert result["local_supports"]
    assert any(s["claim_id"] == "d1" and s["role_id"] == "ref-software-development" for s in result["local_supports"])
    assert not any(s["claim_id"] == "d3" for s in result["local_supports"])
    assert result["axes"]["seniority"]["status"] == "not_evaluated"
    assert len(result["axes"]["family"]["candidates"]) >= 2
    assert result["primary_role_id"] is None
    assert result["formal_statistics_eligible"] is False
    assert result["coverage"]["checked_pairs"] == result["coverage"]["pool_pairs"]
    assert result["knowledge_gaps"]
    assert source == original


def test_delivery_does_not_treat_model_material_as_software_implementation():
    result = build(analysis_with_duties(["构建标注测试集并设计评分口径"]))
    assert not any(s["role_id"] == "ref-software-development" for s in result["local_supports"])
    assert result["uncovered_work"]
    assert result["evidence_kind"] == "bounded_offline_rules"
    assert result["model_calls"] == 0


def test_small_catalog_is_used_as_supplied_and_does_not_borrow_extra_roles():
    knowledge = load_snapshot(KNOWLEDGE / "backend-foundations.v1")
    result = build_delivery_research(analysis_with_duties(["开发软件服务"]), knowledge)
    assert result["knowledge_sha256"] == knowledge.sha256
    assert set(result["reference_role_ids"]) == {r.id for r in knowledge.snapshot.roles}
    assert result["policy_revision"] == "unconfigured-knowledge-1"


def test_partial_support_keeps_unrecognized_tail_in_delivery_uncovered_work():
    result = build(analysis_with_duties(["开发订单接口并主持部门会议"]))
    assert result["local_supports"]
    assert result["uncovered_work"][0]["claim_id"] == "d1"
    assert result["uncovered_work"][0]["reason"] == "partial_source_work_uncovered"
    assert any("主持部门会议" in gap["quote"] for gap in result["uncovered_work"][0]["source_gaps"])

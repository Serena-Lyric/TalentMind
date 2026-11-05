"""P2-1 role comparison follows responsibilities and explicit boundaries only."""
from copy import deepcopy
from pathlib import Path
import pytest

from app.job_analysis.foundation.inputs import InputRecord
from app.job_analysis.knowledge.catalog import load_snapshot
from test_knowledge_alignment import analysis_with, evidence


BACKEND = Path(__file__).resolve().parents[2]
SHIPPED_CATALOG = BACKEND / "app/job_analysis/knowledge/catalog/backend-foundations.v1"


def shipped():
    return load_snapshot(SHIPPED_CATALOG)


def analysis_with_duties(duty_texts, *, requirement="Python", state="preferred", jd_id="roles-one",
                         core_values=None, duty_coverage="complete", row_extra=None):
    raw = "职责：" + "；".join(duty_texts) + "。要求：" + requirement + "。"
    value = analysis_with(
        [requirement],
        raw_text=raw,
        state=state,
        row_extra=row_extra,
        jd_id=jd_id,
    )
    record = InputRecord.from_row(value["namespace"], value["input_row"])
    requirement_claim = deepcopy(value["claims"][0])
    requirement_claim["text"] = raw
    requirement_claim["evidence"][0] = evidence(record, raw)
    requirement_claim["requirement"]["scope_evidence"] = [evidence(record, raw)]
    duties = []
    for index, (text, core) in enumerate(zip(duty_texts, core_values or [True] * len(duty_texts)), 1):
        duties.append({
            "id": f"d{index}",
            "kind": "duty",
            "text": text,
            "evidence": [evidence(record, text)],
            "requirement": None,
            "core": core,
            "reason": "合成职责测试",
        })
    value["claims"] = [*duties, requirement_claim]
    if duty_coverage != "complete":
        value["coverage"]["duties"] = {"status": duty_coverage,
                                       "reason": "职责覆盖仅用于定向反例"}
        value["outcome"] = "partial"
    return value


def by_role(result, role_id):
    return next(item for item in result.comparisons if item.role_id == role_id)


def test_same_tool_different_work_is_not_supported_as_same_role():
    from app.job_analysis.knowledge.roles import compare_roles

    result = compare_roles(analysis_with_duties(["负责Java课程教学并批改作业"], requirement="Java"), shipped())
    programming = by_role(result, "p0-ref-programming")
    assert programming.judgment == "unresolved"
    assert programming.uncovered_duty_ids == ["d1"]
    assert not programming.covered_duty_ids


def test_explicit_boundary_can_reject_but_directory_gap_cannot():
    from app.job_analysis.knowledge.roles import compare_roles

    teaching = compare_roles(analysis_with_duties(["负责课程教学并授课"]), shipped())
    rejected = by_role(teaching, "test-ref-excludes-teaching")
    missing = by_role(compare_roles(analysis_with_duties(["整理招聘资料"]), shipped()), "p0-ref-programming")
    assert rejected.judgment == "not_supported"
    assert rejected.conflicts[0].boundary_id == "boundary-not-course-delivery"
    assert rejected.conflicts[0].boundary_evidence[0].source_id == "src-synthetic-test"
    assert rejected.conflicts[0].duty_evidence[0].quote == "负责课程教学并授课"
    assert missing.judgment == "unresolved"
    assert not missing.conflicts


def test_same_responsibilities_with_different_requirement_stacks_are_compared_by_work():
    from app.job_analysis.knowledge.roles import compare_roles

    python = compare_roles(analysis_with_duties(["编写并调试订单服务代码"], requirement="Python"), shipped())
    go = compare_roles(analysis_with_duties(["编写并调试订单服务代码"], requirement="Go"), shipped())
    assert by_role(python, "p0-ref-programming").judgment == "supported"
    assert by_role(go, "p0-ref-programming").judgment == "supported"
    assert python.comparisons[-1].reason == go.comparisons[-1].reason


def test_comparison_declares_exact_checked_scope_and_analysis_version():
    from app.job_analysis.knowledge.roles import compare_roles

    source = analysis_with_duties(["整理招聘资料"])
    result = compare_roles(source, shipped())
    assert result.checked_role_ids == sorted(role.id for role in shipped().snapshot.roles)
    assert result.retrieval_scope == "all_roles_in_bound_snapshot"
    assert result.source_analysis_sha256
    assert result.knowledge_sha256 == shipped().sha256
    assert "outside" in result.scope_limitation


def test_profile_preserves_preferred_state_and_never_claims_universal_requirement():
    from app.job_analysis.knowledge.alignment import align_analysis
    from app.job_analysis.knowledge.profile import build_profile
    from app.job_analysis.knowledge.roles import compare_roles

    source = analysis_with_duties(["编写代码并核验模块功能"])
    knowledge = shipped()
    alignment = align_analysis(source, knowledge)
    comparisons = compare_roles(source, knowledge)
    profile = build_profile("p0-ref-programming", comparisons, [alignment])
    assert profile.mode == "candidate_profile"
    assert profile.role_maturity == "candidate"
    assert profile.claim_scope == "linked_members_only"
    assert profile.knowledge_id == knowledge.snapshot.id
    assert profile.knowledge_revision == knowledge.snapshot.revision
    assert profile.knowledge_sha256 == knowledge.sha256
    assert profile.not_market_statistics is True
    assert profile.not_formal_role is True
    assert profile.members[0].requirements[0].state == "preferred"
    assert profile.members[0].requirements[0].members == ["Python"]
    assert profile.members[0].requirements[0].combination == "single"


def test_profile_is_reproducible_from_the_same_bound_inputs():
    from app.job_analysis.knowledge.alignment import align_analysis
    from app.job_analysis.knowledge.profile import build_profile
    from app.job_analysis.knowledge.roles import compare_roles

    source = analysis_with_duties(["编写代码并核验模块功能"])
    knowledge = shipped()
    alignment = align_analysis(source, knowledge)
    comparisons = compare_roles(source, knowledge)
    first = build_profile("p0-ref-programming", comparisons, [alignment])
    second = build_profile("p0-ref-programming", comparisons, [alignment])
    assert first == second


def test_profile_rejects_alignment_from_a_different_knowledge_version():
    import pytest
    from app.job_analysis.knowledge.alignment import align_analysis
    from app.job_analysis.knowledge.profile import build_profile
    from app.job_analysis.knowledge.roles import compare_roles
    from test_knowledge_versions import loaded_variant, with_python_alias

    source = analysis_with_duties(["编写代码并核验模块功能"])
    knowledge = shipped()
    mismatch = loaded_variant(with_python_alias)
    comparisons = compare_roles(source, knowledge)
    different_alignment = align_analysis(source, mismatch)
    with pytest.raises(ValueError, match="knowledge"):
        build_profile("p0-ref-programming", comparisons, [different_alignment])


def test_negated_boundary_text_is_not_an_explicit_role_conflict():
    from app.job_analysis.knowledge.roles import compare_roles

    source = analysis_with_duties(["不承担课程教学，仅负责代码开发"])
    result = compare_roles(source, shipped())
    boundary_role = by_role(result, "test-ref-excludes-teaching")
    assert boundary_role.judgment == "unresolved"
    assert boundary_role.conflicts == []


def test_partial_duty_coverage_cannot_support_role_and_profile_member():
    from app.job_analysis.knowledge.alignment import align_analysis
    from app.job_analysis.knowledge.profile import build_profile
    from app.job_analysis.knowledge.roles import compare_roles

    source = analysis_with_duties(["编写代码"], duty_coverage="partial")
    knowledge = shipped()
    comparison = compare_roles(source, knowledge)
    programming = by_role(comparison, "p0-ref-programming")
    profile = build_profile("p0-ref-programming", comparison, [align_analysis(source, knowledge)])
    assert programming.judgment == "unresolved"
    assert "coverage" in programming.reason
    assert profile.members == []


@pytest.mark.parametrize("core", [None, False])
def test_unproven_or_noncore_duty_cannot_support_role(core):
    from app.job_analysis.knowledge.roles import compare_roles

    result = compare_roles(analysis_with_duties(["编写代码"], core_values=[core]), shipped())
    programming = by_role(result, "p0-ref-programming")
    assert programming.judgment == "unresolved"
    assert "core" in programming.reason
import pytest

def test_profile_binds_one_candidate_projection_and_rejects_mixed_versions(tmp_path):
    import pytest
    from app.job_analysis.knowledge.alignment import align_analysis
    from app.job_analysis.knowledge.candidates import CandidateRegistry
    from app.job_analysis.knowledge.profile import build_profile
    from app.job_analysis.knowledge.roles import compare_roles

    knowledge = shipped()
    registry = CandidateRegistry(tmp_path / "registry")
    empty = registry.project()
    source = analysis_with_duties(
        ["编写代码并核验模块功能"], requirement="Flink SQL", jd_id="profile-candidate",
        row_extra={"source_identity": "profile-employer-a"},
    )
    supporting = analysis_with_duties(
        ["开发软件模块并验证功能"], requirement="Flink SQL", jd_id="profile-support",
        row_extra={"source_identity": "profile-employer-b"},
    )
    registry.observe(source, align_analysis(source, knowledge))
    registry.observe(supporting, align_analysis(supporting, knowledge))
    projection = registry.project()
    comparison = compare_roles(source, knowledge)
    without_candidates = align_analysis(source, knowledge, candidate_projection=empty)
    with_candidates = align_analysis(source, knowledge, candidate_projection=projection)
    with pytest.raises(ValueError, match="candidate projection"):
        build_profile("p0-ref-programming", comparison, [without_candidates, with_candidates])

    profile = build_profile("p0-ref-programming", comparison, [with_candidates])
    assert profile.candidate_projection_id == projection.projection.id
    assert profile.candidate_projection_revision == projection.projection.revision
    assert profile.candidate_projection_sha256 == projection.sha256

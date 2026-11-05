"""Candidate governance is append-only, evidence-bound and never auto-formal."""
from pathlib import Path

import pytest

from app.job_analysis.knowledge.alignment import align_analysis
from app.job_analysis.knowledge.catalog import load_snapshot
from test_knowledge_alignment import analysis_with


BACKEND = Path(__file__).resolve().parents[2]
SHIPPED_CATALOG = BACKEND / "app/job_analysis/knowledge/catalog/backend-foundations.v1"


def shipped():
    return load_snapshot(SHIPPED_CATALOG)


def unknown_case(surface="Flink SQL", *, raw_text=None, source="BOSS", jd_id="governance-one", **overrides):
    value = analysis_with(
        [surface],
        raw_text=raw_text or f"要求：熟悉 {surface}。",
        source=source,
        jd_id=jd_id,
        **overrides,
    )
    return value, align_analysis(value, shipped())


def test_unknown_with_capability_context_creates_candidate_without_formal_admission(tmp_path):
    from app.job_analysis.knowledge.candidates import CandidateRegistry, admission_decision

    analysis, alignment = unknown_case()
    registry = CandidateRegistry(tmp_path / "registry")
    record = registry.observe(analysis, alignment)[0]
    assert record.surface == "Flink SQL"
    assert record.status == "observing"
    assert record.version == 1
    assert record.independent_evidence == 1
    decision = admission_decision(record)
    assert decision.allowed is False
    assert decision.status == "formal_admission_disabled"


def test_noncability_and_contextless_company_name_do_not_create_skill_candidates(tmp_path):
    from app.job_analysis.knowledge.candidates import CandidateRegistry

    registry = CandidateRegistry(tmp_path / "registry")
    education, education_alignment = unknown_case(
        "本科",
        raw_text="学历要求：本科。",
        target="education",
        category=None,
        jd_id="education",
    )
    company, company_alignment = unknown_case(
        "星河科技",
        raw_text="公司简介：星河科技。",
        jd_id="company",
    )
    assert not registry.observe(education, education_alignment)
    assert not registry.observe(company, company_alignment)


def test_republished_identical_content_does_not_add_independent_evidence(tmp_path):
    from app.job_analysis.knowledge.candidates import CandidateRegistry

    first_analysis, first_alignment = unknown_case(source="BOSS", jd_id="same-content-1")
    second_analysis, second_alignment = unknown_case(source="Zhaopin", jd_id="same-content-2")
    registry = CandidateRegistry(tmp_path / "registry")
    first = registry.observe(first_analysis, first_alignment)[0]
    second = registry.observe(second_analysis, second_alignment)[0]
    assert second.candidate_id == first.candidate_id
    assert second.version == 2
    assert second.independent_evidence == 1
    assert len(second.referenced_observations) == 2
    assert second.verification_strength == "single_independent_context"


def test_revision_appends_version_preserves_old_head_and_keeps_hypotheses(tmp_path):
    from app.job_analysis.knowledge.candidates import CandidateRegistry

    analysis, alignment = unknown_case()
    registry = CandidateRegistry(tmp_path / "registry")
    first = registry.observe(analysis, alignment)[0]
    second_analysis, second_alignment = unknown_case(
        raw_text="任职要求：掌握 Flink SQL。",
        source="Zhaopin",
        jd_id="governance-two",
    )
    second = registry.revise(
        first.candidate_id,
        "经上下文补充后的候选描述",
        "补充新的独立上下文证据",
        analysis=second_analysis,
        alignment=second_alignment,
        competing_hypotheses=["流式数据处理能力", "具体SQL方言"],
    )
    assert second.version == 2
    assert second.description == "经上下文补充后的候选描述"
    assert second.competing_hypotheses == ["流式数据处理能力", "具体SQL方言"]
    assert len(second.referenced_observations) == 2
    assert registry.read(first.candidate_id, 1) == first
    assert registry.read(first.candidate_id).version == 2


def test_ambiguous_alignment_is_not_converted_to_candidate(tmp_path):
    from app.job_analysis.knowledge.candidates import CandidateRegistry

    analysis, _ = unknown_case("Kubernetes 或 容器编排")
    alignment = align_analysis(analysis, shipped())
    registry = CandidateRegistry(tmp_path / "registry")
    assert not registry.observe(analysis, alignment)


def test_dispute_then_withdrawal_preserves_the_original_observation(tmp_path):
    from app.job_analysis.knowledge.candidates import CandidateRegistry

    analysis, alignment = unknown_case()
    registry = CandidateRegistry(tmp_path / "registry")
    original = registry.observe(analysis, alignment)[0]
    disputed = registry.mark_disputed(
        original.candidate_id,
        "新证据显示该表达可能指代两个不同对象",
        competing_hypotheses=["能力A", "能力B"],
    )
    withdrawn = registry.withdraw(
        original.candidate_id,
        "后续反证表明该表达不是能力名称",
    )
    assert disputed.status == "disputed"
    assert withdrawn.status == "withdrawn"
    assert registry.read(original.candidate_id, 1) == original
    assert registry.read(original.candidate_id, 2) == disputed


def _observe_case(registry, *, raw_text, source_identity, jd_id, target="capability",
                  category="technical_skill", source="BOSS"):
    analysis = analysis_with(
        ["Flink SQL"],
        raw_text=raw_text,
        target=target,
        category=category,
        source=source,
        jd_id=jd_id,
        row_extra={"source_identity": source_identity} if source_identity else None,
    )
    alignment = align_analysis(analysis, shipped())
    return analysis, registry.observe(analysis, alignment)[0]


def test_known_independent_sources_automatically_corroborate_and_project_candidate(tmp_path):
    from app.job_analysis.knowledge.candidates import CandidateRegistry

    registry = CandidateRegistry(tmp_path / "registry")
    first = _observe_case(
        registry,
        raw_text="要求：使用 Flink SQL 开发实时数据任务。",
        source_identity="employer-a",
        jd_id="corroborate-one",
    )[1]
    second = _observe_case(
        registry,
        raw_text="岗位需要具备 Flink SQL 实现流式任务的能力。",
        source_identity="employer-b",
        jd_id="corroborate-two",
        source="Zhaopin",
    )[1]
    assert second.candidate_id == first.candidate_id
    assert second.status == "corroborated"
    assert second.independent_evidence == 2
    assert second.source_identity_count == 2
    assert second.evidence_quality == "independent_consistent"
    assert second.formal_admission_allowed is False

    projection = registry.project()
    assert len(projection.snapshot.concepts) == 1
    assert projection.snapshot.concepts[0].maturity == "candidate"
    assert projection.snapshot.formal_admission_allowed is False


def test_same_source_rewrite_does_not_become_corroborated(tmp_path):
    from app.job_analysis.knowledge.candidates import CandidateRegistry

    registry = CandidateRegistry(tmp_path / "registry")
    first = _observe_case(
        registry,
        raw_text="要求：使用 Flink SQL 开发实时数据任务。",
        source_identity="employer-a",
        jd_id="same-source-one",
    )[1]
    second = _observe_case(
        registry,
        raw_text="要求：使用 Flink SQL 开发实时数据任务！",
        source_identity="employer-a",
        jd_id="same-source-two",
        source="Zhaopin",
    )[1]
    assert second.candidate_id == first.candidate_id
    assert second.status == "observing"
    assert second.source_identity_count == 1
    assert second.evidence_quality == "same_source_only"
    assert registry.project().snapshot.concepts == []


def test_unknown_source_independence_does_not_become_corroborated(tmp_path):
    from app.job_analysis.knowledge.candidates import CandidateRegistry

    registry = CandidateRegistry(tmp_path / "registry")
    first_analysis, first_alignment = unknown_case(source="BOSS", jd_id="unknown-source-one")
    second_analysis, second_alignment = unknown_case(
        raw_text="任职要求：掌握 Flink SQL。",
        source="Zhaopin",
        jd_id="unknown-source-two",
    )
    first = registry.observe(first_analysis, first_alignment)[0]
    second = registry.observe(second_analysis, second_alignment)[0]
    assert first.candidate_id == second.candidate_id
    assert second.status == "observing"
    assert second.source_identity_count == 0
    assert second.evidence_quality == "source_independence_unverified"
    assert registry.project().snapshot.concepts == []


def test_corroborated_candidate_is_available_only_in_matching_context(tmp_path):
    from app.job_analysis.knowledge.candidates import CandidateRegistry

    registry = CandidateRegistry(tmp_path / "registry")
    _observe_case(registry, raw_text="要求：使用 Flink SQL 开发实时数据任务。",
                  source_identity="employer-a", jd_id="projection-one")
    dev_analysis, dev = _observe_case(
        registry,
        raw_text="岗位需要具备 Flink SQL 实现流式任务的能力。",
        source_identity="employer-b",
        jd_id="projection-two",
        source="Zhaopin",
    )
    projection = registry.project()
    result = align_analysis(dev_analysis, shipped(), candidate_projection=projection)
    decision = result.alignments[0]
    assert decision.state == "exact_synonym"
    assert decision.knowledge_status == "candidate"
    assert decision.concept_source == "candidate"
    assert decision.concept_id.startswith("candidatec-")
    assert result.candidate_projection_sha256 == projection.sha256

    education = analysis_with(["Flink SQL"], raw_text="学历要求：Flink SQL。",
                              target="education", category=None, jd_id="education-context")
    assert align_analysis(education, shipped(), candidate_projection=projection).alignments[0].state == "unknown"

    teaching = analysis_with(["Flink SQL"], raw_text="要求：讲授 Flink SQL 课程。",
                             jd_id="teaching-context")
    assert align_analysis(teaching, shipped(), candidate_projection=projection).alignments[0].state == "unknown"


def test_same_surface_usage_contexts_remain_separate_without_false_conflict(tmp_path):
    from app.job_analysis.knowledge.candidates import CandidateRegistry

    registry = CandidateRegistry(tmp_path / "registry")
    dev_one, _ = _observe_case(
        registry,
        raw_text="要求：使用 Flink SQL 开发实时数据任务。",
        source_identity="dev-employer-a",
        jd_id="dev-one",
    )
    _observe_case(registry, raw_text="岗位需要具备 Flink SQL 实现流式任务的能力。",
                  source_identity="dev-employer-b", jd_id="dev-two", source="Zhaopin")
    teach_one, _ = _observe_case(
        registry,
        raw_text="要求：讲授 Flink SQL 课程。",
        source_identity="teach-employer-a",
        jd_id="teach-one",
        source="Liepin",
    )
    _observe_case(registry, raw_text="岗位职责包括培训 Flink SQL 课程。",
                  source_identity="teach-employer-b", jd_id="teach-two", source="Liepin")
    projection = registry.project()
    assert len(projection.snapshot.concepts) == 2
    assert all(item.status == "corroborated" for item in projection.snapshot.concepts)
    dev_decision = align_analysis(dev_one, shipped(), candidate_projection=projection).alignments[0]
    teach_decision = align_analysis(teach_one, shipped(), candidate_projection=projection).alignments[0]
    assert dev_decision.state == teach_decision.state == "exact_synonym"
    assert dev_decision.concept_id != teach_decision.concept_id

def test_cross_source_near_rewrite_is_treated_as_possible_republish(tmp_path):
    from app.job_analysis.knowledge.candidates import CandidateRegistry

    registry = CandidateRegistry(tmp_path / "registry")
    first = _observe_case(
        registry,
        raw_text="要求：使用 Flink SQL 开发实时数据任务。",
        source_identity="employer-a",
        jd_id="near-copy-one",
    )[1]
    second = _observe_case(
        registry,
        raw_text="要求：使用 Flink SQL 开发实时数据任务！",
        source_identity="employer-b",
        jd_id="near-copy-two",
        source="Zhaopin",
    )[1]
    assert second.candidate_id == first.candidate_id
    assert second.status == "observing"
    assert second.source_identity_count == 2
    assert second.evidence_quality == "likely_republished"
    assert registry.project().snapshot.concepts == []


def _corroborated_candidate(registry):
    _observe_case(registry, raw_text="要求：使用 Flink SQL 开发实时数据任务。",
                  source_identity="employer-a", jd_id="dispute-one")
    analysis, candidate = _observe_case(
        registry, raw_text="岗位需要具备 Flink SQL 实现流式任务的能力。",
        source_identity="employer-b", jd_id="dispute-two",
    )
    assert candidate.status == "corroborated"
    return analysis, candidate


def test_single_disputed_candidate_cannot_be_exact_in_alignment_or_profile(tmp_path):
    from app.job_analysis.foundation.inputs import digest
    from app.job_analysis.knowledge.candidates import CandidateRegistry, load_projection
    from app.job_analysis.knowledge.models import AlignmentResult
    from app.job_analysis.knowledge.profile import build_profile
    from app.job_analysis.knowledge.roles import compare_roles
    from app.job_analysis.knowledge.storage import read_result, save_result
    from test_knowledge_roles import analysis_with_duties

    registry = CandidateRegistry(tmp_path / "registry")
    _, candidate = _corroborated_candidate(registry)
    source = analysis_with_duties(["编写代码并核验模块功能"], requirement="Flink SQL")
    source_before = digest(source)
    old_projection = registry.project()
    old_alignment = align_analysis(source, shipped(), candidate_projection=old_projection)
    assert old_alignment.alignments[0].state == "exact_synonym"
    save_result(tmp_path / "old-alignment", old_alignment.model_dump())

    disputed = registry.mark_disputed(
        candidate.candidate_id, "表达含义尚未确定", ["流式处理能力", "企业内部工具"],
    )
    new_projection = registry.project()
    assert len(new_projection.projection.concepts) == 1
    assert new_projection.projection.concepts[0].status == "disputed"
    new_alignment = align_analysis(source, shipped(), candidate_projection=new_projection)
    decision = new_alignment.alignments[0]
    assert decision.state == "unknown"
    assert decision.concept_id is None
    assert decision.concept_source is None
    assert decision.candidate_concept_ids == []
    assert decision.knowledge_status == "unknown"
    assert decision.candidate_id == disputed.candidate_id
    assert decision.candidate_version_sha256 == digest(disputed.model_dump())
    assert "disputed" in decision.reason
    assert new_alignment.requirements[0].source_requirement == old_alignment.requirements[0].source_requirement
    assert new_alignment.source_analysis_sha256 == old_alignment.source_analysis_sha256
    assert digest(source) == source_before

    comparison = compare_roles(source, shipped())
    profile = build_profile("p0-ref-programming", comparison, [new_alignment])
    member = profile.members[0].requirements[0].alignments[0]
    assert member.state == "unknown"
    assert member.concept_id is None
    assert profile.candidate_projection_sha256 == new_projection.sha256
    assert registry.read(candidate.candidate_id, candidate.version) == candidate
    assert registry.read(candidate.candidate_id, disputed.version) == disputed
    assert load_projection(registry.root / "projections" / old_projection.sha256) == old_projection
    assert AlignmentResult.model_validate(read_result(tmp_path / "old-alignment")) == old_alignment


@pytest.mark.parametrize("protected_status", ["disputed", "withdrawn"])
def test_ordinary_observation_cannot_release_protected_candidate_status(tmp_path, protected_status):
    from app.job_analysis.knowledge.candidates import CandidateRegistry

    registry = CandidateRegistry(tmp_path / "registry")
    _, candidate = _corroborated_candidate(registry)
    disputed = registry.mark_disputed(candidate.candidate_id, "含义冲突待核查", ["义项A", "义项B"])
    protected = (disputed if protected_status == "disputed"
                 else registry.withdraw(candidate.candidate_id, "反证后撤回"))
    analysis, observed = _observe_case(
        registry, raw_text="使用 Flink SQL 开发数据应用，要求能够处理复杂事件。",
        source_identity="employer-c", jd_id="dispute-three",
    )
    assert observed.status == protected_status
    assert observed.reason == protected.reason
    assert observed.description == protected.description
    assert observed.competing_hypotheses == protected.competing_hypotheses
    assert observed.competing_candidate_ids == protected.competing_candidate_ids
    assert observed.version == protected.version + 1
    assert len(observed.referenced_observations) == len(protected.referenced_observations) + 1
    assert registry.read(candidate.candidate_id, candidate.version) == candidate
    assert registry.read(candidate.candidate_id, protected.version) == protected
    projection = registry.project()
    assert align_analysis(analysis, shipped(), candidate_projection=projection).alignments[0].state == "unknown"
    if protected_status == "withdrawn":
        assert projection.projection.concepts == []

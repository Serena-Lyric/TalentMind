"""Candidate governance is append-only, evidence-bound and never auto-formal."""
from pathlib import Path

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
    second = registry.revise(
        first.candidate_id,
        "经上下文补充后的候选描述",
        "补充同一能力的上下文说明",
        competing_hypotheses=["流式数据处理能力", "具体SQL方言"],
    )
    assert second.version == 2
    assert second.description == "经上下文补充后的候选描述"
    assert second.competing_hypotheses == ["流式数据处理能力", "具体SQL方言"]
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

"""P2-1 alignment preserves P1 semantics and never infers fuzzy synonyms."""
from copy import deepcopy
from pathlib import Path

from app.job_analysis.foundation.inputs import InputRecord, digest
from app.job_analysis.knowledge.catalog import load_snapshot


BACKEND = Path(__file__).resolve().parents[2]
SHIPPED_CATALOG = BACKEND / "app/job_analysis/knowledge/catalog/backend-foundations.v1"


def shipped():
    return load_snapshot(SHIPPED_CATALOG)


def evidence(record, quote, occurrence=None):
    text = record.payload["raw_text"]
    positions = []
    start = 0
    while (found := text.find(quote, start)) >= 0:
        positions.append(found)
        start = found + 1
    index = 0 if occurrence is None else occurrence
    start = positions[index]
    return {
        "namespace": record.namespace,
        "jd_id": record.jd_id,
        "fingerprint": record.fingerprint,
        "field": "raw_text",
        "start": start,
        "end": start + len(quote),
        "quote": quote,
    }


def version(name):
    return {"id": name, "revision": "1", "sha256": "a" * 64}


def analysis_with(
    members,
    *,
    raw_text=None,
    combination=None,
    state="required",
    target="capability",
    category="technical_skill",
    degree=None,
    degree_polarity=None,
    condition=None,
    jd_id="alignment-one",
    source="synthetic",
):
    quote = raw_text or "要求：" + "、".join(members) + "。"
    row = {
        "id": jd_id,
        "source": source,
        "job_title": "合成开发岗位",
        "raw_text": quote,
    }
    record = InputRecord.from_row("synthetic", row)
    requirement = {
        "state": state,
        "target": target,
        "category": category,
        "members": members,
        "combination": combination or ("single" if len(members) == 1 else "all_of"),
        "open_set": False,
        "degree": degree,
        "degree_polarity": degree_polarity,
        "condition": condition,
        "reason": "保留P1机器候选语义，非人工真值",
        "scope_evidence": [evidence(record, quote)],
    }
    claim_evidence = evidence(record, quote)
    coverage = {name: {"status": "complete", "reason": "合成测试输入"} for name in
                ("goals", "objects", "duties", "requirements", "relations", "classification")}
    return {
        "contract_version": "m2-semantic-0.2",
        "namespace": "synthetic",
        "jd_id": str(row["id"]),
        "input_row": row,
        "input_sha256": record.fingerprint,
        "input_version": "synthetic-alignment-v1",
        "analyzer": version("synthetic-analyzer"),
        "model": version("synthetic-model"),
        "prompt": version("synthetic-prompt"),
        "configuration": version("synthetic-config"),
        "knowledge": [],
        "outcome": "complete",
        "coverage": coverage,
        "claims": [{
            "id": "r1",
            "kind": "requirement",
            "text": quote,
            "evidence": [claim_evidence],
            "requirement": requirement,
            "core": None,
            "reason": "合成P1事实",
        }],
        "alignments": [],
        "relations": [],
        "role_judgments": [],
        "semantic_review": "machine_unreviewed",
    }


def mixed_analysis():
    raw = "仅限后端时熟悉 Java 或 Python。"
    return analysis_with(
        ["Java", "Python"],
        raw_text=raw,
        combination="any_of",
        degree="熟悉",
        degree_polarity="affirmed",
        condition="仅限后端",
    )


def test_alignment_preserves_every_p1_requirement_field_and_never_rewrites_input():
    from app.job_analysis.knowledge.alignment import align_analysis

    source = mixed_analysis()
    before = deepcopy(source)
    result = align_analysis(source, shipped())
    original = original_requirement(source)
    assert result.requirements[0].source_requirement == original
    assert result.requirements[0].source_requirement["combination"] == "any_of"
    assert result.requirements[0].source_requirement["degree"] == "熟悉"
    assert result.requirements[0].source_requirement["degree_polarity"] == "affirmed"
    assert result.requirements[0].source_requirement["condition"] == "仅限后端"
    assert result.semantic_review == "machine_unreviewed"
    assert result.source_analysis_sha256 == digest(source)
    assert result.input_sha256 == source["input_sha256"]
    assert source == before


def test_exact_alias_merges_but_typescript_keeps_its_own_identity():
    from app.job_analysis.knowledge.alignment import align_analysis

    result = align_analysis(analysis_with(["JS", "JavaScript", "TypeScript"], combination="all_of"), shipped())
    members = {item.member: item for item in result.alignments}
    assert members["JS"].state == "exact_synonym"
    assert members["JS"].concept_id == members["JavaScript"].concept_id == "concept-javascript"
    assert members["TypeScript"].concept_id == "concept-typescript"
    assert members["TypeScript"].concept_id != members["JavaScript"].concept_id
    assert any(relation.kind == "narrower_than" and relation.concept_id == "concept-javascript"
               for relation in members["TypeScript"].related_concepts)


def test_kubernetes_and_container_orchestration_are_related_not_aliases():
    from app.job_analysis.knowledge.alignment import align_analysis

    result = align_analysis(analysis_with(["Kubernetes", "容器编排"], combination="all_of"), shipped())
    members = {item.member: item for item in result.alignments}
    assert members["Kubernetes"].concept_id == "concept-kubernetes"
    assert members["容器编排"].concept_id == "concept-container-orchestration"
    assert any(relation.kind == "related_to" and relation.concept_id == "concept-container-orchestration"
               for relation in members["Kubernetes"].related_concepts)


def test_name_similarity_and_common_words_cannot_create_an_alias():
    from app.job_analysis.knowledge.alignment import align_analysis

    result = align_analysis(analysis_with(["Java Script 开发"]), shipped())
    decision = result.alignments[0]
    assert decision.state == "unknown"
    assert decision.concept_id is None
    assert "fuzzy" in decision.reason


def test_atomic_member_with_multiple_known_concepts_is_ambiguous_not_split():
    from app.job_analysis.knowledge.alignment import align_analysis

    result = align_analysis(analysis_with(["Kubernetes 或 容器编排"]), shipped())
    decision = result.alignments[0]
    assert decision.state == "ambiguous"
    assert decision.concept_id is None
    assert decision.candidate_concept_ids == ["concept-container-orchestration", "concept-kubernetes"]
    assert result.requirements[0].source_requirement["members"] == ["Kubernetes 或 容器编排"]


def test_partial_source_outcome_and_coverage_remain_visible():
    from app.job_analysis.knowledge.alignment import align_analysis

    source = mixed_analysis()
    source["outcome"] = "partial"
    source["coverage"]["requirements"] = {
        "status": "partial",
        "reason": "one source requirement remained only partially interpreted",
    }
    result = align_analysis(source, shipped())
    assert result.source_outcome == "partial"
    assert result.source_coverage["requirements"].status == "partial"
    assert result.source_coverage["requirements"].reason.startswith("one source")


def test_alignment_reader_rejects_a_tampered_source_requirement_shape():
    import pytest
    from app.job_analysis.knowledge.alignment import align_analysis
    from app.job_analysis.knowledge.models import AlignmentResult

    value = align_analysis(mixed_analysis(), shipped()).model_dump()
    value["requirements"][0]["source_requirement"]["target"] = "education"
    with pytest.raises(ValueError):
        AlignmentResult.model_validate(value)


def test_alignment_reader_requires_all_six_source_coverage_dimensions():
    import pytest
    from app.job_analysis.knowledge.alignment import align_analysis
    from app.job_analysis.knowledge.models import AlignmentResult

    value = align_analysis(mixed_analysis(), shipped()).model_dump()
    value["source_coverage"].pop("classification")
    with pytest.raises(ValueError, match="coverage"):
        AlignmentResult.model_validate(value)


def original_requirement(analysis):
    return next(claim for claim in analysis["claims"] if claim["kind"] == "requirement")["requirement"]

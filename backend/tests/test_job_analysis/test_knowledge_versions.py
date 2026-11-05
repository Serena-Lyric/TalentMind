"""Knowledge changes create new explanations without rewriting P1 or old results."""
from copy import deepcopy
from pathlib import Path

from app.job_analysis.foundation.inputs import digest
from app.job_analysis.knowledge.catalog import LoadedSnapshot, load_snapshot
from app.job_analysis.knowledge.models import validate_snapshot
from test_knowledge_alignment import analysis_with


BACKEND = Path(__file__).resolve().parents[2]
SHIPPED_CATALOG = BACKEND / "app/job_analysis/knowledge/catalog/backend-foundations.v1"


def shipped():
    return load_snapshot(SHIPPED_CATALOG)


def loaded_variant(change):
    base = shipped()
    value = base.snapshot.model_dump()
    change(value)
    model = validate_snapshot(value)
    return LoadedSnapshot(base.path, model, digest(model.model_dump()))


def with_python_alias(value):
    python = next(item for item in value["concepts"] if item["id"] == "concept-python")
    python["aliases"].append({
        "term": "Python 3",
        "scope": "Version-qualified exact expression",
        "evidence": [{
            "source_id": "src-python-docs",
            "locator": "Fixture alias",
            "quote": "Python 是一门易于学习、功能强大的编程语言。",
        }],
    })
    value["revision"] = "backend-foundations-2"


def test_new_alias_changes_alignment_but_not_p1_input_or_old_result():
    from app.job_analysis.knowledge.alignment import align_analysis

    source = analysis_with(["Python 3"])
    before = deepcopy(source["claims"])
    old = align_analysis(source, shipped())
    new = align_analysis(source, loaded_variant(with_python_alias))
    assert old.alignments[0].state == "unknown"
    assert new.alignments[0].concept_id == "concept-python"
    assert new.source_analysis_sha256 == old.source_analysis_sha256
    assert source["claims"] == before
    assert old.knowledge_revision == "backend-foundations-1"
    assert new.knowledge_revision == "backend-foundations-2"


def test_impact_locator_marks_only_observations_touched_by_alias_change():
    from app.job_analysis.knowledge.alignment import align_analysis
    from app.job_analysis.knowledge.impact import locate_impact

    hit_source = analysis_with(["Python 3"], jd_id="hit")
    miss_source = analysis_with(["Go"], jd_id="miss")
    old = shipped()
    new = loaded_variant(with_python_alias)
    records = [align_analysis(hit_source, old), align_analysis(miss_source, old)]
    report = locate_impact(old, new, records)
    assert report.conservative is False
    assert report.changed_aliases == ["python 3"]
    assert report.affected == [
        f"synthetic:hit:{records[0].source_analysis_sha256[:12]}"
    ]


def test_impact_falls_back_to_all_when_snapshot_change_scope_is_unknown():
    from app.job_analysis.knowledge.alignment import align_analysis
    from app.job_analysis.knowledge.impact import locate_impact

    def purpose_only(value):
        value["purpose"] = "无法由结构差异可靠判断影响的说明变化"
        value["revision"] = "backend-foundations-purpose-only"

    source_one = analysis_with(["Python"], jd_id="one")
    source_two = analysis_with(["Go"], jd_id="two")
    old = shipped()
    new = loaded_variant(purpose_only)
    records = [align_analysis(source_one, old), align_analysis(source_two, old)]
    report = locate_impact(old, new, records)
    assert report.conservative is True
    assert report.affected == [
        f"synthetic:{record.jd_id}:{record.source_analysis_sha256[:12]}" for record in records
    ]


def test_redeliver_is_a_new_bound_alignment():
    from app.job_analysis.knowledge.impact import redeliver

    source = analysis_with(["Python 3"])
    old = shipped()
    new = loaded_variant(with_python_alias)
    redelivered = redeliver(source, new)
    assert redelivered.knowledge_sha256 == new.sha256
    assert redelivered.alignments[0].concept_id == "concept-python"
    assert old.sha256 != new.sha256


def test_relation_basis_change_marks_related_observations_for_realignment():
    from app.job_analysis.knowledge.alignment import align_analysis
    from app.job_analysis.knowledge.impact import locate_impact

    def relation_change(value):
        relation = next(item for item in value["relations"] if item["source_id"] == "concept-typescript")
        relation["basis"] = "修订后的关系说明"
        value["revision"] = "backend-foundations-relation-2"

    source = analysis_with(["TypeScript"])
    old = shipped()
    new = loaded_variant(relation_change)
    record = align_analysis(source, old)
    report = locate_impact(old, new, [record])
    assert report.changed_relations
    assert report.changed_concept_ids == []
    assert report.conservative is False
    assert report.affected == [f"synthetic:{record.jd_id}:{record.source_analysis_sha256[:12]}"]


def test_source_metadata_change_is_conservative():
    from app.job_analysis.knowledge.alignment import align_analysis
    from app.job_analysis.knowledge.impact import locate_impact

    def source_change(value):
        value["sources"][0]["retrieved_on"] = "2026-11-05"
        value["revision"] = "backend-foundations-source-2"

    source = analysis_with(["Python"])
    old = shipped()
    new = loaded_variant(source_change)
    record = align_analysis(source, old)
    report = locate_impact(old, new, [record])
    assert report.conservative is True
    assert report.affected == [f"synthetic:{record.jd_id}:{record.source_analysis_sha256[:12]}"]


def test_added_relation_affects_old_alignment_even_when_other_endpoint_was_absent():
    from app.job_analysis.knowledge.alignment import align_analysis
    from app.job_analysis.knowledge.impact import locate_impact

    def add_relation(value):
        value["relations"].append({
            "source_id": "concept-python",
            "target_id": "concept-javascript",
            "kind": "related_to",
            "basis": "新增关系",
            "evidence": [{
                "source_id": "src-python-docs",
                "locator": "fixture relation",
                "quote": "Python 是一门易于学习、功能强大的编程语言。",
            }],
        })
        value["revision"] = "backend-foundations-added-relation"

    source = analysis_with(["Python"])
    old = shipped()
    new = loaded_variant(add_relation)
    record = align_analysis(source, old)
    assert record.alignments[0].related_concepts == []
    report = locate_impact(old, new, [record])
    assert report.changed_relations
    assert report.conservative is False
    assert report.affected == [f"synthetic:{record.jd_id}:{record.source_analysis_sha256[:12]}"]


def test_deleted_relation_affects_old_neighbor_alignment():
    from app.job_analysis.knowledge.alignment import align_analysis
    from app.job_analysis.knowledge.impact import locate_impact

    def delete_relation(value):
        value["relations"] = [item for item in value["relations"]
                              if item["source_id"] != "concept-typescript"]
        value["revision"] = "backend-foundations-deleted-relation"

    source = analysis_with(["TypeScript"])
    old = shipped()
    new = loaded_variant(delete_relation)
    record = align_analysis(source, old)
    assert record.alignments[0].related_concepts
    report = locate_impact(old, new, [record])
    assert report.changed_relations
    assert report.affected == [f"synthetic:{record.jd_id}:{record.source_analysis_sha256[:12]}"]


def test_impact_rejects_alignment_not_bound_to_old_knowledge_sha():
    import pytest
    from app.job_analysis.knowledge.alignment import align_analysis
    from app.job_analysis.knowledge.impact import locate_impact

    record = align_analysis(analysis_with(["Python"]), loaded_variant(with_python_alias))
    with pytest.raises(ValueError, match="old knowledge"):
        locate_impact(shipped(), loaded_variant(with_python_alias), [record])

def _candidate_projection_pair(tmp_path):
    from app.job_analysis.knowledge.candidates import CandidateRegistry
    from app.job_analysis.knowledge.alignment import align_analysis

    registry = CandidateRegistry(tmp_path / "candidate-registry")
    empty = registry.project()
    sources = []
    for identity, text, jd_id, platform in (
        ("employer-a", "要求：使用 Flink SQL 开发实时数据任务。", "p-one", "BOSS"),
        ("employer-b", "岗位需要具备 Flink SQL 实现流式任务的能力。", "p-two", "Zhaopin"),
    ):
        analysis = analysis_with(
            ["Flink SQL"], raw_text=text, source=platform, jd_id=jd_id,
            row_extra={"source_identity": identity},
        )
        registry.observe(analysis, align_analysis(analysis, shipped()))
        sources.append(analysis)
    return registry, empty, registry.project(), sources[0]


def test_candidate_projection_addition_enters_impact_scope_with_static_knowledge_unchanged(tmp_path):
    from app.job_analysis.knowledge.alignment import align_analysis
    from app.job_analysis.knowledge.impact import locate_impact

    registry, empty, projected, source = _candidate_projection_pair(tmp_path)
    old_record = align_analysis(source, shipped(), candidate_projection=empty)
    assert old_record.alignments[0].state == "unknown"
    report = locate_impact(
        shipped(), shipped(), [old_record],
        old_candidate_projection=empty, new_candidate_projection=projected,
    )
    assert report.candidate_projection_changed is True
    assert report.changed_candidate_concept_ids
    assert report.affected == [f"synthetic:{old_record.jd_id}:{old_record.source_analysis_sha256[:12]}"]


def test_candidate_projection_withdrawal_enters_impact_scope(tmp_path):
    from app.job_analysis.knowledge.alignment import align_analysis
    from app.job_analysis.knowledge.impact import locate_impact

    registry, empty, projected, source = _candidate_projection_pair(tmp_path)
    old_record = align_analysis(source, shipped(), candidate_projection=projected)
    for concept in projected.projection.concepts:
        registry.withdraw(concept.candidate_id, "反证后撤回")
    withdrawn = registry.project()
    report = locate_impact(
        shipped(), shipped(), [old_record],
        old_candidate_projection=projected, new_candidate_projection=withdrawn,
    )
    assert report.candidate_projection_changed is True
    assert report.changed_candidate_concept_ids
    assert report.affected == [f"synthetic:{old_record.jd_id}:{old_record.source_analysis_sha256[:12]}"]


def test_impact_rejects_alignment_bound_to_different_old_candidate_projection(tmp_path):
    import pytest
    from app.job_analysis.knowledge.alignment import align_analysis
    from app.job_analysis.knowledge.impact import locate_impact

    _registry, empty, projected, source = _candidate_projection_pair(tmp_path)
    record = align_analysis(source, shipped(), candidate_projection=projected)
    with pytest.raises(ValueError, match="old candidate projection"):
        locate_impact(shipped(), shipped(), [record],
                      old_candidate_projection=empty, new_candidate_projection=projected)

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

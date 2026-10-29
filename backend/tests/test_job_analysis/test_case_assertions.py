"""Only provenance/completeness is tested; synthetic examples do not certify semantics."""
import hashlib
import json

import pytest

from app.job_analysis.foundation.inputs import InputRecord


def fixture():
    row = {"id": "synthetic-1", "source": "synthetic", "job_title": "测试", "raw_text": "维护接口"}
    record = InputRecord.from_row("synthetic", row)
    ev = {"field": "raw_text", "start": 0, "end": 4, "quote": "维护接口", "input_sha256": record.fingerprint}
    annotation = {"sample_id": "DEV-01", "status": "human_reviewed", "input_sha256": record.fingerprint, "annotation_version": "synthetic-v1", "human_labels": [{"unit_id": "D01", "dimension": "duty", "text": "维护接口", "evidence": [ev]}, {"unit_id": "R01", "dimension": "requirement", "text": "要求说明", "evidence": [ev]}]}
    raw = json.dumps(annotation, ensure_ascii=False).encode()
    case = {"schema_version": "p0-case-assertions-1", "sample_id": "DEV-01", "namespace": "synthetic", "jd_id": "synthetic-1", "input_version": "snapshot-v1", "input_sha256": record.fingerprint, "annotation_sha256": hashlib.sha256(raw).hexdigest(), "annotation_version": "synthetic-v1", "business_status": "pending_review", "coverage": {"D01": "A", "R01": "D"}, "assertions": []}
    for kind, unit in [("A", "D01"), ("D", "R01")]:
        case["assertions"].append({"id": "DEV-01-" + kind + "01", "class": kind, "unit_ids": [unit], "support_unit_ids": [], "evidence_unit_ids": [unit], "evidence": [ev], "criterion": "保留原职责及作用域", "equivalence_rule": "允许有理由的等价拆并改写，仍记录每个人工单位的漏误提"})
    return case, row, raw


def validate(case, row, annotation):
    from app.job_analysis.baseline.case_assertions import validate_case_assertions
    return validate_case_assertions(case, row, annotation)


def test_bound_proposals_cover_every_applicable_unit_without_becoming_approved_truth():
    case, row, annotation = fixture()
    result = validate(case, row, annotation)
    assert result == {"sample_id": "DEV-01", "assertions": {"A": 1, "B": 0, "C": 0, "D": 1}, "applicable_units": 2, "business_status": "pending_review", "semantic_result": "not_run"}


@pytest.mark.parametrize("damage", ["annotation_hash", "input_hash", "foreign_unit", "missing_coverage", "overlapping_class", "evidence_quote", "invented_support", "self_approved", "source_summary"])
def test_unbound_incomplete_or_self_approved_mapping_is_rejected(damage):
    case, row, annotation = fixture()
    if damage == "annotation_hash": case["annotation_sha256"] = "0" * 64
    elif damage == "input_hash": case["input_sha256"] = "0" * 64
    elif damage == "foreign_unit": case["assertions"][0]["unit_ids"] = ["D99"]
    elif damage == "missing_coverage": del case["coverage"]["R01"]
    elif damage == "overlapping_class": case["coverage"]["R01"] = "A"
    elif damage == "evidence_quote": case["assertions"][0]["evidence"][0]["quote"] = "并非原文"
    elif damage == "invented_support": case["assertions"][0]["support_unit_ids"] = ["D99"]
    elif damage == "source_summary": case["assertions"][0]["source_summaries"] = {"D01": "伪造的人类标签"}
    else: case["business_status"] = "approved"
    with pytest.raises(ValueError): validate(case, row, annotation)


def test_holdout_mapping_is_rejected_before_source_manifest_is_opened(tmp_path, monkeypatch):
    from pathlib import Path
    from app.job_analysis.baseline.case_assertions import audit_case_assertions
    case, _, _ = fixture()
    case["sample_id"] = "HOLD-01"
    path = tmp_path / "proposal.json"
    path.write_text(json.dumps(case), encoding="utf-8")
    monkeypatch.setattr(Path, "read_bytes", lambda *args: pytest.fail("source manifest must not be opened"))
    with pytest.raises(ValueError, match="case_scope_must_be_existing_DEV"):
        audit_case_assertions(path, tmp_path / "forbidden-manifest.json")


@pytest.mark.parametrize("wrong_version", [False, True])
def test_file_reader_binds_declared_content_version_as_well_as_digest(tmp_path, wrong_version):
    from app.job_analysis.baseline.case_assertions import audit_case_assertions
    case, row, raw = fixture()
    ann = json.loads(raw)
    ann.update(reviewer="Synthetic human", reviewed_at="synthetic-test-event", confirmation_source="synthetic-test-only", scope="full_input", disputes=[])
    raw = json.dumps(ann).encode()
    case["annotation_sha256"] = hashlib.sha256(raw).hexdigest()
    row_raw = json.dumps(row).encode()
    (tmp_path / "snapshot.json").write_bytes(row_raw)
    (tmp_path / "annotation.json").write_bytes(raw)
    manifest = {"schema_version": "m2-p0-bundle-0.1", "version": "synthetic", "namespace": "synthetic", "files": {"snapshot.json": hashlib.sha256(row_raw).hexdigest(), "annotation.json": hashlib.sha256(raw).hexdigest()}, "samples": [{"id": "DEV-01", "split": "development", "content_version": "snapshot-v1", "snapshot": "snapshot.json", "annotation": "annotation.json", "input_sha256": case["input_sha256"]}]}
    mraw = json.dumps(manifest).encode()
    (tmp_path / "manifest.json").write_bytes(mraw)
    case["source_manifest_sha256"] = hashlib.sha256(mraw).hexdigest()
    if wrong_version: case["input_version"] = "unrelated-version"
    (tmp_path / "case.json").write_text(json.dumps(case), encoding="utf-8")
    if wrong_version:
        with pytest.raises(ValueError, match="case_content_version_mismatch"):
            audit_case_assertions(tmp_path / "case.json", tmp_path / "manifest.json")
    else:
        assert audit_case_assertions(tmp_path / "case.json", tmp_path / "manifest.json")["business_status"] == "pending_review"

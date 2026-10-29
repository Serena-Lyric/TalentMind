"""Approval binds immutable conditions to a separate owner receipt; no real JD text."""
import hashlib
import json
import copy
from pathlib import Path

import pytest

from app.job_analysis.foundation.inputs import InputRecord


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(value, ensure_ascii=False, indent=2).encode()
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def packet(tmp_path):
    source = tmp_path / "source"
    draft = tmp_path / "draft"
    samples, source_files, case_files, cases = [], {}, {}, {}
    for i in range(1, 9):
        sid = f"DEV-{i:02d}"
        row = {"id": sid, "source": "synthetic", "job_title": "测试", "raw_text": f"维护接口{i}"}
        fingerprint = InputRecord.from_row("synthetic", row).fingerprint
        ev = dict(field="raw_text", start=0, end=4, quote="维护接口", input_sha256=fingerprint)
        annotation = dict(sample_id=sid, status="human_reviewed", annotation_version="synthetic-v1",
                          input_sha256=fingerprint, reviewer="Synthetic owner", reviewed_at="synthetic-event",
                          confirmation_source="synthetic-only", scope="full_input", disputes=[],
                          human_labels=[dict(unit_id="D01", dimension="duty", evidence=[ev])])
        snapshot, ann = f"snapshots/{sid}.json", f"annotations/{sid}.json"
        source_files[snapshot] = write_json(source / snapshot, row)
        source_files[ann] = write_json(source / ann, annotation)
        samples.append(dict(id=sid, split="development", content_version="input-v1", snapshot=snapshot,
                            annotation=ann, input_sha256=fingerprint))
        cases[sid] = dict(schema_version="p0-case-assertions-1", sample_id=sid, namespace="synthetic",
                          jd_id=sid, business_status="pending_review", input_version="input-v1",
                          input_sha256=fingerprint, annotation_sha256=source_files[ann],
                          annotation_version="synthetic-v1", coverage={"D01": "A"},
                          assertions=[dict(id=f"{sid}-A01", **{"class": "A"}, unit_ids=["D01"],
                                           support_unit_ids=[], evidence_unit_ids=["D01"], evidence=[ev],
                                           criterion="覆盖接口维护", equivalence_rule="允许同义改写")])
    # Forbidden entries deliberately have no backing files. An implicit full audit fails.
    samples.append(dict(id="HOLD-01", split="holdout", snapshot="snapshots/HOLD-01.json",
                        annotation="annotations/HOLD-01.json"))
    manifest = source / "manifest.json"
    msha = write_json(manifest, dict(schema_version="m2-p0-bundle-0.1", version="synthetic-v1",
                                    namespace="synthetic", samples=samples, files=source_files))
    for sid, case in cases.items():
        case["source_manifest_sha256"] = msha
        name = f"cases/{sid}.json"
        case_files[name] = write_json(draft / name, case)
    index = draft / "index.json"
    isha = write_json(index, dict(version="synthetic-draft-v1", business_status="pending_review",
                                  cases=list(cases), files=case_files, source_manifest_sha256=msha))
    receipt = tmp_path / "owner-receipt.json"
    write_json(receipt, dict(record_type="owner_signoff_receipt", owner_identity="Synthetic owner",
                            confirmation_source="synthetic-test-only", confirmation_quote="同意这份条件",
                            confirmation_date_client_timezone="2026-10-29",
                            transcribed_at_utc="2026-10-29T06:00:00+00:00",
                            approved_version="synthetic-draft-v1", approved_index_sha256=isha,
                            scope=["core_assertion_sets", "semantic_equivalence_scope_and_metric_denominators",
                                   "minimal_supplement_strategy"]))
    return index, manifest, receipt, tmp_path / "approved"


def create(args):
    from app.job_analysis.baseline.approved_assertions import create_approved_assertions
    return create_approved_assertions(*args)


def audit(args):
    from app.job_analysis.baseline.approved_assertions import audit_approved_assertions
    index, manifest, receipt, target = args
    return audit_approved_assertions(target / "release.json", manifest, receipt)


def test_approved_read_preserves_signed_bytes_and_uses_only_DEV(tmp_path, monkeypatch):
    args = packet(tmp_path)
    index, _, _, target = args
    before = {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*.json")}
    original = Path.read_bytes

    def guard(path):
        assert "HOLD" not in path.name
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", guard)
    result = create(args)
    assert result["business_status"] == "approved"
    assert result["samples"] == 8 and result["applicable_units"] == 8
    assert result["assertions"] == {"A": 8, "B": 0, "C": 0, "D": 0}
    assert result["semantic_result"] == "not_run"
    assert audit(args) == result
    for name, raw in before.items():
        assert (tmp_path / name).read_bytes() == raw
    assert (target / "cases/DEV-01.json").read_bytes() == (index.parent / "cases/DEV-01.json").read_bytes()


@pytest.mark.parametrize("damage", ["missing_scope", "missing_owner", "wrong_index", "wrong_version", "blank_quote"])
def test_unsigned_or_unbound_conditions_cannot_be_promoted(tmp_path, damage):
    args = packet(tmp_path)
    receipt = json.loads(args[2].read_text(encoding="utf-8"))
    if damage == "missing_scope": receipt["scope"] = []
    elif damage == "missing_owner": receipt["owner_identity"] = ""
    elif damage == "wrong_index": receipt["approved_index_sha256"] = "0" * 64
    elif damage == "wrong_version": receipt["approved_version"] = "another-draft"
    else: receipt["confirmation_quote"] = ""
    write_json(args[2], receipt)
    with pytest.raises(ValueError): create(args)
    assert not args[3].exists()


@pytest.mark.parametrize("damage", ["criterion", "source", "receipt", "release_status", "condition_files", "approval_scope"])
def test_approved_reader_rejects_modified_payload_source_or_receipt(tmp_path, damage):
    args = packet(tmp_path)
    create(args)
    if damage == "criterion": path = args[3] / "cases/DEV-01.json"
    elif damage == "source": path = args[1].parent / "snapshots/DEV-01.json"
    elif damage == "receipt": path = args[2]
    else: path = args[3] / "release.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if damage == "release_status": data["business_status"] = "pending_review"
    elif damage == "condition_files": data["condition_files"] = ["owner-questions.json"]
    elif damage == "approval_scope": data["approval_scope"] = "formal_knowledge_and_P0_closure"
    else: data["tampered"] = True
    write_json(path, data)
    with pytest.raises(ValueError): audit(args)


def test_matching_missing_versions_do_not_constitute_an_approval(tmp_path):
    args = packet(tmp_path)
    index = json.loads(args[0].read_text(encoding="utf-8"))
    del index["version"]
    digest = write_json(args[0], index)
    receipt = json.loads(args[2].read_text(encoding="utf-8"))
    del receipt["approved_version"]
    receipt["approved_index_sha256"] = digest
    write_json(args[2], receipt)
    with pytest.raises(ValueError): create(args)


@pytest.mark.parametrize("damage", ["missing", "duplicate", "holdout", "escape"])
def test_bad_scope_or_registry_is_rejected_before_payload_read(tmp_path, monkeypatch, damage):
    args = packet(tmp_path)
    index = json.loads(args[0].read_text(encoding="utf-8"))
    if damage == "missing": index["cases"].pop()
    elif damage == "duplicate": index["cases"][-1] = "DEV-01"
    elif damage == "holdout": index["cases"][-1] = "HOLD-01"
    else: index["files"]["../outside.json"] = "0" * 64
    isha = write_json(args[0], index)
    receipt = json.loads(args[2].read_text(encoding="utf-8"))
    receipt["approved_index_sha256"] = isha
    write_json(args[2], receipt)
    allowed = {args[0], args[1], args[2]}
    original = Path.read_bytes

    def guard(path):
        assert path in allowed, "invalid registry opened a payload"
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", guard)
    with pytest.raises(ValueError): create(args)
    assert not args[3].exists()


def test_existing_release_directory_is_never_overwritten(tmp_path):
    args = packet(tmp_path)
    create(args)
    before = (args[3] / "release.json").read_bytes()
    with pytest.raises(FileExistsError): create(args)
    assert (args[3] / "release.json").read_bytes() == before


def test_signed_cached_conditions_are_validated_even_if_file_changes_during_read(tmp_path, monkeypatch):
    from app.job_analysis.baseline import case_assertions
    args = packet(tmp_path)
    create(args)
    path = args[3] / "cases/DEV-01.json"
    original_read, original_validate = Path.read_bytes, case_assertions.validate_case_assertions
    changed = False

    def mutate_after_signed_read(p):
        nonlocal changed
        raw = original_read(p)
        if p == path and not changed:
            data = json.loads(raw)
            data["assertions"][0]["criterion"] = "UNSIGNED CONDITION"
            p.write_text(json.dumps(data), encoding="utf-8")
            changed = True
        return raw

    def validate_signed(case, row, annotation):
        assert case["assertions"][0]["criterion"] == "覆盖接口维护", "validated a different version than the signed bytes"
        return original_validate(case, row, annotation)

    monkeypatch.setattr(Path, "read_bytes", mutate_after_signed_read)
    monkeypatch.setattr(case_assertions, "validate_case_assertions", validate_signed)
    assert audit(args)["business_status"] == "approved"
    assert changed
    # A subsequent read sees the changed file and must reject it.
    with pytest.raises(ValueError): audit(args)


def test_approved_CLI_requires_separate_receipt_and_sanitizes_rejection(tmp_path, monkeypatch, capsys):
    from app.job_analysis.baseline.__main__ import main
    args = packet(tmp_path)
    create(args)
    command = ["baseline", "approved-assertions", str(args[3] / "release.json"), "--manifest", str(args[1])]
    monkeypatch.setattr("sys.argv", command)
    assert main() == 1
    assert json.loads(capsys.readouterr().out)["status"] == "rejected"
    monkeypatch.setattr("sys.argv", command + ["--approval", str(args[2])])
    assert main() == 0
    output = json.loads(capsys.readouterr().out)
    assert output["business_status"] == "approved" and output["samples"] == 8


def extend_with_signed_supplement(args):
    index_path, manifest_path, receipt_path, _ = args
    index = json.loads(index_path.read_text(encoding="utf-8"))
    baseline_raw = index_path.read_bytes()
    baseline_cases = {sid: (index_path.parent / f"cases/{sid}.json").read_bytes() for sid in index["cases"]}
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    row = {"id": "DEV-09", "source": "synthetic", "job_title": "测试", "raw_text": "维护接口9"}
    fp = InputRecord.from_row("synthetic", row).fingerprint
    ev = dict(field="raw_text", start=0, end=4, quote="维护接口", input_sha256=fp)
    ann = json.loads((manifest_path.parent / "annotations/DEV-08.json").read_text(encoding="utf-8"))
    ann.update(sample_id="DEV-09", input_sha256=fp)
    ann["human_labels"][0]["evidence"] = [ev]
    snapshot, annotation = "snapshots/DEV-09.json", "annotations/DEV-09.json"
    manifest["files"][snapshot] = write_json(manifest_path.parent / snapshot, row)
    manifest["files"][annotation] = write_json(manifest_path.parent / annotation, ann)
    manifest["samples"].append(dict(id="DEV-09", split="development", snapshot=snapshot, annotation=annotation,
                                    content_version="input-v1", input_sha256=fp))
    msha = write_json(manifest_path, manifest)
    for sid in index["cases"]:
        path = index_path.parent / f"cases/{sid}.json"
        case = json.loads(path.read_text(encoding="utf-8"))
        case["source_manifest_sha256"] = msha
        index["files"][f"cases/{sid}.json"] = write_json(path, case)
    case = copy.deepcopy(case)
    case.update(sample_id="DEV-09", jd_id="DEV-09", input_sha256=fp,
                annotation_sha256=manifest["files"][annotation])
    case["assertions"][0].update(id="DEV-09-A01", evidence=[ev])
    index["files"]["cases/DEV-09.json"] = write_json(index_path.parent / "cases/DEV-09.json", case)
    baseline = index_path.parent / "provenance/baseline-index.json"
    baseline.parent.mkdir()
    baseline.write_bytes(baseline_raw)
    index["files"]["provenance/baseline-index.json"] = hashlib.sha256(baseline_raw).hexdigest()
    for sid, raw in baseline_cases.items():
        name = f"provenance/baseline-cases/{sid}.json"
        path = index_path.parent / name
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(raw)
        index["files"][name] = hashlib.sha256(raw).hexdigest()
    mapping = dict(proposed_sample_id="DEV-09", input_sha256=fp, content_version="input-v1",
                   source_snapshot_sha256=manifest["files"][snapshot],
                   assertions=case["assertions"], coverage=case["coverage"])
    raw = (manifest_path.parent / snapshot).read_bytes()
    (index_path.parent / "provenance/supplement-snapshot.json").write_bytes(raw)
    index["files"]["provenance/supplement-snapshot.json"] = hashlib.sha256(raw).hexdigest()
    map_sha = write_json(index_path.parent / "provenance/supplement-map.json", mapping)
    index["files"]["provenance/supplement-map.json"] = map_sha
    index.update(version="synthetic-draft-v2", source_manifest_sha256=msha)
    index["cases"].append("DEV-09")
    isha = write_json(index_path, index)
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt.update(approved_version=index["version"], approved_index_sha256=isha,
                   approved_sample_ids=index["cases"],
                   approval_derivation=dict(baseline_index_sha256=hashlib.sha256(baseline_raw).hexdigest(),
                                            supplement_map_sha256=map_sha,
                                            generation_consent_quote="同意按固定补样映射生成新版本，原八例不覆盖"))
    write_json(receipt_path, receipt)
    return args


def test_signed_supplement_can_extend_without_changing_original_conditions(tmp_path):
    args = extend_with_signed_supplement(packet(tmp_path))
    result = create(args)
    assert result["samples"] == 9 and result["applicable_units"] == 9
    assert result["assertions"]["A"] == 9
    assert audit(args) == result


@pytest.mark.parametrize("damage", ["baseline_condition", "supplement_condition", "scope_authorization"])
def test_derived_release_cannot_change_old_or_new_signed_conditions(tmp_path, damage):
    args = extend_with_signed_supplement(packet(tmp_path))
    index = json.loads(args[0].read_text(encoding="utf-8"))
    if damage != "scope_authorization":
        name = "cases/DEV-01.json" if damage == "baseline_condition" else "cases/DEV-09.json"
        case = json.loads((args[0].parent / name).read_text(encoding="utf-8"))
        case["assertions"][0]["criterion"] = "UNSIGNED"
        index["files"][name] = write_json(args[0].parent / name, case)
    isha = write_json(args[0], index)
    receipt = json.loads(args[2].read_text(encoding="utf-8"))
    receipt["approved_index_sha256"] = isha
    if damage == "scope_authorization": del receipt["approval_derivation"]
    write_json(args[2], receipt)
    with pytest.raises(ValueError): create(args)


def test_supplement_identity_cannot_be_replaced_while_keeping_payload_fingerprint(tmp_path):
    args = extend_with_signed_supplement(packet(tmp_path))
    index = json.loads(args[0].read_text(encoding="utf-8"))
    manifest = json.loads(args[1].read_text(encoding="utf-8"))
    snapshot = args[1].parent / "snapshots/DEV-09.json"
    row = json.loads(snapshot.read_text(encoding="utf-8"))
    row["id"] = "UNAPPROVED-REPLACEMENT-ID"
    manifest["files"]["snapshots/DEV-09.json"] = write_json(snapshot, row)
    msha = write_json(args[1], manifest)
    index["source_manifest_sha256"] = msha
    for sid in index["cases"]:
        name = f"cases/{sid}.json"
        case = json.loads((args[0].parent / name).read_text(encoding="utf-8"))
        case["source_manifest_sha256"] = msha
        if sid == "DEV-09": case["jd_id"] = row["id"]
        index["files"][name] = write_json(args[0].parent / name, case)
    isha = write_json(args[0], index)
    receipt = json.loads(args[2].read_text(encoding="utf-8"))
    receipt["approved_index_sha256"] = isha
    write_json(args[2], receipt)
    with pytest.raises(ValueError): create(args)

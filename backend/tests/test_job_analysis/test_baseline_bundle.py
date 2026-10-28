"""A damaged/missing private packet must never silently become another baseline."""
import hashlib
import json

import pytest


def fingerprint(row):
    payload = {k: v for k, v in row.items() if k not in {"id", "crawled_at"}}
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def bundle(tmp_path):
    samples = []
    files = {}
    for sample_id, split, text in [("a", "development", "职责：开发任务调度"), ("b", "holdout", "职责：维护网络设备")]:
        name = sample_id + ".json"
        row = {"id": sample_id, "source": "synthetic", "job_title": "测试", "raw_text": text}
        raw = json.dumps(row, ensure_ascii=False).encode()
        (tmp_path / name).write_bytes(raw)
        files[name] = hashlib.sha256(raw).hexdigest()
        samples.append({"id": sample_id, "split": split, "snapshot": name, "input_sha256": fingerprint(row), "annotation": sample_id + "-annotation.json"})
        ann = {"sample_id": sample_id, "input_sha256": fingerprint(row), "status": "pending", "reviewer": None, "reviewed_at": None, "confirmation_source": None, "scope": "none", "human_labels": [], "disputes": []}
        raw = json.dumps(ann).encode()
        (tmp_path / samples[-1]["annotation"]).write_bytes(raw)
        files[samples[-1]["annotation"]] = hashlib.sha256(raw).hexdigest()
    manifest = {"schema_version": "m2-p0-bundle-0.1", "version": "synthetic-v1", "namespace": "test", "archive_sha256": None, "files": files, "samples": samples}
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return manifest


def audit(tmp_path):
    from app.job_analysis.baseline.bundle import audit_bundle
    return audit_bundle(tmp_path / "manifest.json")


def test_pending_human_annotations_have_no_truth_denominator(tmp_path):
    bundle(tmp_path)
    assert audit(tmp_path) == {"samples": 2, "development": 1, "holdout": 1, "human_reviewed": 0, "semantic_metrics": "not_computable"}


def test_selected_audit_never_opens_unselected_material(tmp_path, monkeypatch):
    from pathlib import Path
    from app.job_analysis.baseline.bundle import audit_bundle
    bundle(tmp_path)
    original_read = Path.read_bytes

    def guarded_read(path):
        assert path.name not in {"b.json", "b-annotation.json"}, "unselected sample was opened"
        return original_read(path)

    monkeypatch.setattr(Path, "read_bytes", guarded_read)
    result = audit_bundle(tmp_path / "manifest.json", sample_ids=["a"])
    assert result["samples"] == 1
    assert result["holdout"] == 0
    assert result["audit_scope"] == ["a"]
    assert result["integrity_scope"] == "selected_snapshot_and_annotation_files_only"


@pytest.mark.parametrize("selection", [[], ["missing"], ["a", "a"]])
def test_invalid_selected_scope_does_not_fall_back_to_full_bundle(tmp_path, selection):
    from app.job_analysis.baseline.bundle import audit_bundle
    bundle(tmp_path)
    with pytest.raises(ValueError):
        audit_bundle(tmp_path / "manifest.json", sample_ids=selection)


def test_selected_audit_rejects_archive_before_reading_any_material(tmp_path, monkeypatch):
    from pathlib import Path
    from app.job_analysis.baseline.bundle import BundleError, audit_bundle

    def forbidden_read(*args, **kwargs):
        pytest.fail("conflicting scope must be rejected before reading files")

    monkeypatch.setattr(Path, "read_bytes", forbidden_read)
    monkeypatch.setattr(Path, "read_text", forbidden_read)
    with pytest.raises(BundleError, match="selected_audit_cannot_read_archive"):
        audit_bundle(tmp_path / "manifest.json", archive=tmp_path / "archive.zip", sample_ids=["a"])


def test_wrong_human_label_quote_is_not_hidden_by_a_valid_annotation_hash(tmp_path):
    from app.job_analysis.baseline.bundle import audit_bundle
    manifest = bundle(tmp_path)
    name = "a-annotation.json"
    ann = json.loads((tmp_path / name).read_text())
    ann.update(status="human_reviewed", reviewer="Synthetic human", reviewed_at="2026-10-28T08:00:00+08:00", confirmation_source="synthetic-test-event", scope="full_input")
    ann["human_labels"] = [{"unit_id": "D01", "evidence": [{"field": "raw_text", "start": 3, "end": 5, "quote": "错误", "input_sha256": ann["input_sha256"]}]}]
    raw = json.dumps(ann, ensure_ascii=False).encode()
    (tmp_path / name).write_bytes(raw)
    manifest["files"][name] = hashlib.sha256(raw).hexdigest()
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError):
        audit_bundle(tmp_path / "manifest.json")


def test_partial_review_labels_are_preserved_without_full_recall_claim(tmp_path):
    manifest = bundle(tmp_path)
    name = "a-annotation.json"
    ann = json.loads((tmp_path / name).read_text())
    ann.update(status="partial", scope="one_statement", human_labels=[{"label": "required"}])
    raw = json.dumps(ann).encode()
    (tmp_path / name).write_bytes(raw)
    manifest["files"][name] = hashlib.sha256(raw).hexdigest()
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    assert audit(tmp_path)["human_reviewed"] == 0


def test_annotation_from_other_input_version_is_rejected(tmp_path):
    manifest = bundle(tmp_path)
    name = "a-annotation.json"
    ann = json.loads((tmp_path / name).read_text())
    ann["input_sha256"] = "0" * 64
    raw = json.dumps(ann).encode()
    (tmp_path / name).write_bytes(raw)
    manifest["files"][name] = hashlib.sha256(raw).hexdigest()
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError):
        audit(tmp_path)


@pytest.mark.parametrize("where", ["sample", "annotation"])
def test_missing_input_binding_cannot_count_as_human_truth(tmp_path, where):
    manifest = bundle(tmp_path)
    name = "a-annotation.json"
    ann = json.loads((tmp_path / name).read_text())
    ann.update(status="human_reviewed", reviewer="Synthetic human", reviewed_at="2026-10-28T08:00:00+08:00", confirmation_source="synthetic-test-event", scope="full_input")
    if where == "sample":
        del manifest["samples"][0]["input_sha256"]
    else:
        del ann["input_sha256"]
    raw = json.dumps(ann).encode()
    (tmp_path / name).write_bytes(raw)
    manifest["files"][name] = hashlib.sha256(raw).hexdigest()
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError):
        audit(tmp_path)


def test_source_change_does_not_split_the_same_analysis_identity(tmp_path):
    manifest = bundle(tmp_path)
    row = json.loads((tmp_path / "b.json").read_text(encoding="utf-8"))
    row.update(id="a", source="another-source")
    raw = json.dumps(row, ensure_ascii=False).encode()
    (tmp_path / "b.json").write_bytes(raw)
    manifest["files"]["b.json"] = hashlib.sha256(raw).hexdigest()
    manifest["samples"][1]["input_sha256"] = fingerprint(row)
    ann = json.loads((tmp_path / "b-annotation.json").read_text())
    ann["input_sha256"] = fingerprint(row)
    raw = json.dumps(ann).encode()
    (tmp_path / "b-annotation.json").write_bytes(raw)
    manifest["files"]["b-annotation.json"] = hashlib.sha256(raw).hexdigest()
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError):
        audit(tmp_path)


def test_cli_rejects_private_input_without_echoing_it(tmp_path, monkeypatch, capsys):
    from app.job_analysis.baseline.__main__ import main
    path = tmp_path / "bad.json"
    path.write_text('{"private_text":"DO-NOT-ECHO-THIS"}', encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["baseline", "analysis", str(path)])
    assert main() == 1
    result = capsys.readouterr().out
    assert "DO-NOT-ECHO-THIS" not in result
    assert json.loads(result)["status"] == "rejected"


@pytest.mark.parametrize("damage,reason", [("missing", "bundle_artifact_missing"), ("changed", "bundle_artifact_digest_mismatch")])
def test_cli_reports_safe_actionable_bundle_diagnostics(tmp_path, monkeypatch, capsys, damage, reason):
    from app.job_analysis.baseline.__main__ import main
    bundle(tmp_path)
    if damage == "missing":
        (tmp_path / "a.json").unlink()
    else:
        (tmp_path / "a.json").write_text("PRIVATE-CONTENT-DO-NOT-ECHO", encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["baseline", "bundle", str(tmp_path / "manifest.json")])
    assert main() == 1
    result = capsys.readouterr().out
    assert "PRIVATE-CONTENT" not in result
    assert json.loads(result)["reason"] == reason


@pytest.mark.parametrize("damage", ["annotation_root", "null_labels", "labels_container", "label_item", "evidence_container", "evidence_item"])
def test_cli_rejects_malformed_human_label_shapes_without_echoing_private_data(tmp_path, monkeypatch, capsys, damage):
    from app.job_analysis.baseline.__main__ import main
    manifest = bundle(tmp_path)
    name = "a-annotation.json"
    ann = json.loads((tmp_path / name).read_text())
    if damage == "annotation_root":
        ann = ["NEVER-ECHO-PRIVATE"]
    else:
        ann["human_labels"] = {"null_labels": None, "labels_container": {}, "label_item": ["NEVER-ECHO-PRIVATE"], "evidence_container": [{"evidence": {}}], "evidence_item": [{"evidence": ["NEVER-ECHO-PRIVATE"]}]}[damage]
    raw = json.dumps(ann).encode()
    (tmp_path / name).write_bytes(raw)
    manifest["files"][name] = hashlib.sha256(raw).hexdigest()
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["baseline", "bundle", str(tmp_path / "manifest.json"), "--samples", "a"])
    assert main() == 1
    captured = capsys.readouterr()
    assert "NEVER-ECHO-PRIVATE" not in captured.out + captured.err
    assert json.loads(captured.out)["reason"] == ("annotation_structure_invalid" if damage == "annotation_root" else "annotation_label_structure_invalid")


@pytest.mark.parametrize("damage", ["missing", "changed_bytes", "path_escape", "duplicate_body", "duplicate_identity", "fake_review"])
def test_broken_or_leaking_bundle_fails_closed(tmp_path, damage):
    manifest = bundle(tmp_path)
    if damage == "missing":
        (tmp_path / "a.json").unlink()
    elif damage == "changed_bytes":
        (tmp_path / "a.json").write_text("{}", encoding="utf-8")
    elif damage == "path_escape":
        manifest["files"]["../escape.json"] = "0" * 64
    elif damage in {"duplicate_body", "duplicate_identity"}:
        row = json.loads((tmp_path / "b.json").read_text(encoding="utf-8"))
        if damage == "duplicate_body":
            row["raw_text"] = "职责：开发 任务调度"
        else:
            row["id"] = "a"
        raw = json.dumps(row, ensure_ascii=False).encode()
        (tmp_path / "b.json").write_bytes(raw)
        manifest["files"]["b.json"] = hashlib.sha256(raw).hexdigest()
        manifest["samples"][1]["input_sha256"] = fingerprint(row)
        ann = json.loads((tmp_path / "b-annotation.json").read_text())
        ann["input_sha256"] = fingerprint(row)
        raw = json.dumps(ann).encode()
        (tmp_path / "b-annotation.json").write_bytes(raw)
        manifest["files"]["b-annotation.json"] = hashlib.sha256(raw).hexdigest()
    else:
        name = "a-annotation.json"
        ann = json.loads((tmp_path / name).read_text())
        ann.update(status="human_reviewed", reviewer="Agent", human_labels=[{"label": "required"}])
        raw = json.dumps(ann).encode()
        (tmp_path / name).write_bytes(raw)
        manifest["files"][name] = hashlib.sha256(raw).hexdigest()
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError):
        audit(tmp_path)

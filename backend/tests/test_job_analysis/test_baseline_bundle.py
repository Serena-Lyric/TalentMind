"""A damaged/missing private packet must never silently become another baseline."""
import hashlib
import json

import pytest


def bundle(tmp_path):
    samples = []
    files = {}
    for sample_id, split, text in [("a", "development", "职责：开发任务调度"), ("b", "holdout", "职责：维护网络设备")]:
        name = sample_id + ".json"
        raw = json.dumps({"id": sample_id, "source": "synthetic", "job_title": "测试", "raw_text": text}, ensure_ascii=False).encode()
        (tmp_path / name).write_bytes(raw)
        files[name] = hashlib.sha256(raw).hexdigest()
        samples.append({"id": sample_id, "split": split, "snapshot": name, "annotation": sample_id + "-annotation.json"})
        ann = {"sample_id": sample_id, "status": "pending", "reviewer": None, "reviewed_at": None, "confirmation_source": None, "scope": "none", "human_labels": [], "disputes": []}
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


def test_cli_rejects_private_input_without_echoing_it(tmp_path, monkeypatch, capsys):
    from app.job_analysis.baseline.__main__ import main
    path = tmp_path / "bad.json"
    path.write_text('{"private_text":"DO-NOT-ECHO-THIS"}', encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["baseline", "analysis", str(path)])
    assert main() == 1
    result = capsys.readouterr().out
    assert "DO-NOT-ECHO-THIS" not in result
    assert json.loads(result)["status"] == "rejected"


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

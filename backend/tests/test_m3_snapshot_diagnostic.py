import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


def test_snapshot_diagnosis_is_read_only_and_reports_old_truncation():
    from app.graph.diagnose_snapshot import diagnose_snapshot

    path = Path(__file__).resolve().parents[2] / "exchange/m3/graph.json"
    before = path.read_bytes()
    report = diagnose_snapshot(path)
    assert path.read_bytes() == before
    assert report["snapshot_sha256"] == hashlib.sha256(before).hexdigest()
    assert report["before"]["nodes"] == 7845
    assert report["before"]["edges"] == 11412
    assert report["before"]["related_to"] == 7
    assert report["legacy_complete"]["related_to"] == 41
    assert len(report["legacy_complete"]["missing_from_snapshot"]) == 34
    assert report["audit"]["legacy_id_collisions"]
    assert any(x["legacy_id"] == "skill:c" for x in report["audit"]["legacy_id_collisions"])
    assert report == diagnose_snapshot(path)


def test_diagnostic_and_pure_builder_import_without_any_service_dependencies():
    code = '''
import builtins, sys
original = builtins.__import__
def guarded(name, *args, **kwargs):
    if name.startswith(("sqlalchemy", "neo4j", "app.db", "app.config")):
        raise AssertionError("service dependency loaded: " + name)
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
from app.graph.diagnose_snapshot import diagnose_snapshot
from app.integration.rebuild_m2_graph import build_graph_data
assert build_graph_data([], [])["nodes"] == []
from pathlib import Path
assert diagnose_snapshot(Path(sys.argv[1]))["before"]["related_to"] == 7
'''
    path = Path(__file__).resolve().parents[2] / "exchange/m3/graph.json"
    result = subprocess.run([sys.executable, "-c", code, str(path)], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("issue", ["duplicate_node", "dangling_edge", "duplicate_edge"])
def test_diagnostic_rejects_corrupt_snapshot(tmp_path, issue):
    from app.graph.diagnose_snapshot import diagnose_snapshot

    data = {"nodes": [{"id": "job:j-1", "type": "job"}], "edges": []}
    if issue == "duplicate_node":
        data["nodes"] *= 2
    else:
        data["edges"] = [{"source": "job:j-1", "target": "missing" if issue == "dangling_edge" else "job:j-1", "type": "RELATED_TO"}]
        if issue == "duplicate_edge":
            data["edges"] *= 2
    path = tmp_path / "snapshot.json"
    try:
        path.write_text(json.dumps(data), encoding="utf-8")
        with pytest.raises(ValueError, match="integrity"):
            diagnose_snapshot(path)
    finally:
        path.unlink(missing_ok=True)


def test_real_cli_only_writes_report_to_stdout():
    path = Path(__file__).resolve().parents[2] / "exchange/m3/graph.json"
    before = path.read_bytes()
    result = subprocess.run([sys.executable, "-m", "app.graph.diagnose_snapshot", str(path)],
                            capture_output=True, text=True, encoding="utf-8", timeout=30,
                            env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["before"]["related_to"] == 7
    assert path.read_bytes() == before

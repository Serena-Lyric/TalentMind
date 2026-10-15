import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from test_foundation_inputs import area, jd, load
from test_foundation_runner import FakeAnalyzer, execute


def cli(*arguments):
    return subprocess.run([sys.executable, "-m", "app.job_analysis.foundation", *map(str, arguments)],
                          capture_output=True, text=True, encoding="utf-8")


def test_cli_offline_run_reuses_and_replays_with_explicit_paths(area):
    load(area, [jd()])
    args = ["run", "--input", area / "input.json", "--state", area / "state.sqlite3",
            "--output", area / "out", "--dataset", "fixture"]
    first = cli(*args)
    assert first.returncode == 0, first.stderr
    info = json.loads(first.stdout)
    artifact = json.loads(Path(info["output"]).read_text(encoding="utf-8"))
    assert artifact["analysis_manifest"]["dependencies"]["model"] == "offline-demo"
    assert artifact["business"]["matched_facts"] == 1
    again = cli(*args)
    assert again.returncode == 0, again.stderr
    assert json.loads(again.stdout)["aggregate_id"] == info["aggregate_id"]
    replay = cli("replay", "--state", area / "state.sqlite3", "--aggregate", info["aggregate_id"], "--output", area / "replay")
    assert replay.returncode == 0, replay.stderr
    assert json.loads(Path(json.loads(replay.stdout)["output"]).read_text(encoding="utf-8"))["business"] == artifact["business"]


def test_cli_invalid_input_is_nonzero_and_leaves_error_without_success(area):
    path = area / "bad.json"
    path.write_text("not json", encoding="utf-8")
    result = cli("run", "--input", path, "--state", area / "state.sqlite3", "--output", area / "out", "--dataset", "fixture")
    assert result.returncode != 0 and "invalid" in result.stderr.lower()
    assert not (area / "out").exists()


def test_protected_repository_outputs_refused_before_creating_files(area):
    from app.job_analysis.foundation.store import AnalysisStore
    root = Path(__file__).resolve().parents[3]
    with pytest.raises(ValueError):
        AnalysisStore(root / "exchange" / "m2" / "prohibited.sqlite3")
    with pytest.raises(ValueError):
        execute(area, output=root / "exchange" / "m2")
    assert not (root / "exchange" / "m2" / "prohibited.sqlite3").exists()


def test_failed_output_can_resume_without_reextracting(area, monkeypatch):
    import app.job_analysis.foundation.runner as runner
    from app.job_analysis.foundation.store import AnalysisStore
    analyzer = FakeAnalyzer()
    real_replace = os.replace
    monkeypatch.setattr(runner.os, "replace", lambda *args: (_ for _ in ()).throw(OSError("publication failed")))
    with AnalysisStore(area / "state.sqlite3") as store:
        with pytest.raises(OSError):
            runner.execute(store, load(area, [jd()]), analyzer, output=area / "out", aggregate_revision="v2")
        run = store.conn.execute("SELECT id FROM runs").fetchone()[0]
        assert store.run(run)["status"] == "publication_failed"
        assert store.run(run)["error"] == "artifact_publish_failed"
    monkeypatch.setattr(runner.os, "replace", real_replace)
    with AnalysisStore(area / "state.sqlite3") as store:
        result = runner.resume(store, run, analyzer, output=area / "out")
        assert result["aggregate_version"]["revision"] == "v2"
        assert len(analyzer.seen) == 1


@pytest.mark.parametrize("phase", ["after_prepare", "after_start", "after_analyze", "before_commit", "after_commit", "after_aggregate", "after_stage_output", "after_output"])
def test_abrupt_process_exit_recovery(area, phase):
    from app.job_analysis.foundation.runner import resume
    from app.job_analysis.foundation.store import AnalysisStore
    load(area, [jd(), jd(id=2)])
    script = """
import os, sys
from pathlib import Path
sys.path.insert(0, str(Path('tests/test_job_analysis').resolve()))
from test_foundation_runner import FakeAnalyzer
from app.job_analysis.foundation.inputs import read_snapshot
from app.job_analysis.foundation.store import AnalysisStore
from app.job_analysis.foundation import runner
root = Path(sys.argv[1])
runner.checkpoint = lambda stage: os._exit(77) if stage == sys.argv[2] else None
with AnalysisStore(root / 'state.sqlite3') as store:
    runner.execute(store, read_snapshot(root / 'input.json', 'fixture'), FakeAnalyzer(), output=root / 'out')
"""
    child = subprocess.run([sys.executable, "-c", script, str(area), phase], capture_output=True, text=True)
    assert child.returncode == 77, child.stderr
    with AnalysisStore(area / "state.sqlite3") as store:
        run = store.conn.execute("SELECT id FROM runs").fetchone()[0]
        result = resume(store, run, FakeAnalyzer(), output=area / "out")
        assert result["business"]["completed_records"] == 2
        assert store.conn.execute("SELECT count(*) FROM facts").fetchone()[0] == 2
        assert store.conn.execute("SELECT count(*) FROM attempts WHERE status='running'").fetchone()[0] == 0
        assert not list((area / "out").glob("*.tmp"))

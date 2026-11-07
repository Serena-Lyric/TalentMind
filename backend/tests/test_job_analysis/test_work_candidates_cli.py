"""Actual subprocess calls with private temporary SQLite, inputs and crash recovery."""
import json
import os
from pathlib import Path
import subprocess
import sys

from app.job_analysis.foundation.inputs import digest
from test_work_candidates import batch, cleanup_p3_files, correction, create, work

BACKEND = Path(__file__).resolve().parents[2]
KNOWLEDGE = BACKEND / "app/job_analysis/knowledge/catalog/backend-foundations.v1"


def cli(*args, success=True):
    result = subprocess.run([sys.executable, "-m", "app.job_analysis.work_candidates", *map(str, args)],
                            cwd=BACKEND, capture_output=True, text=True, encoding="utf-8")
    if success:
        assert result.returncode == 0, (result.stdout, result.stderr)
    else:
        assert result.returncode != 0
    return json.loads(result.stdout)


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    return path


def request(state, name, values=(), operations=()):
    return dict(schema_version="m2-work-batch-1", batch_id=name, baseline=state["binding"],
                operation_version="synthetic-cli-1", analysis_sha256s=sorted({digest(v) for v in values}),
                operations=list(operations))


def test_cli_two_batches_correction_restart_and_versioned_readback(tmp_path):
    state = tmp_path / "state.db"
    initial = cli("init", "--state", state)
    a = work(text="使用 Java 开发订单接口。")
    b = work("two", "使用 Go 实现订单接口。", title="平台研发")
    first_input = write(tmp_path / "a.json", a)
    second_input = write(tmp_path / "b.json", b)
    first = write(tmp_path / "one.json", request(initial, "one", [a], [create(a)]))
    one = cli("apply", "--state", state, "--batch", first, "--analysis", first_input, "--knowledge", KNOWLEDGE)
    second = write(tmp_path / "two.json", request(one, "two", [b]))
    two = cli("apply", "--state", state, "--batch", second, "--analysis", second_input, "--knowledge", KNOWLEDGE)
    assert two["candidates"]["work-orders"]["version"] == 2
    assert len(two["relations"]) == 2
    # These all run in new processes and do not reconstruct facts or re-execute retrieval.
    assert cli("show", "--state", state, "--revision", 1) == one
    assert cli("show", "--state", state) == two
    assert len(cli("history", "--state", state, "--candidate", "work-orders")["history"]) == 2
    jd = cli("jd", "--state", state, "--namespace", "synthetic", "--jd-id", "two")
    assert len(jd["relations"]) == 1
    assert jd["analysis_sha256s"] == [digest(b)]
    assert cli("source", "--state", state, "--kind", "analysis", "--sha256", digest(a)) == a
    old_relation = jd["relations"][0]
    third = write(tmp_path / "three.json", request(two, "three", operations=[correction(old_relation)]))
    three = cli("apply", "--state", state, "--batch", third, "--knowledge", KNOWLEDGE)
    assert three["relations"][old_relation["id"]]["state"] == "withdrawn"
    assert cli("apply", "--state", state, "--batch", second, "--analysis", second_input, "--knowledge", KNOWLEDGE) == two
    assert cli("show", "--state", state) == three
    assert cli("jd", "--state", state, "--namespace", "synthetic", "--jd-id", "two", "--revision", 2) == jd


def test_cli_reads_manifest_bound_p1_run_and_does_not_emit_validation_text_on_error(tmp_path):
    from app.job_analysis.understanding.storage import save_run
    from test_understanding import draft, run
    value = run(draft())
    p1 = tmp_path / "p1"
    save_run(p1, value)
    state = tmp_path / "state.db"
    zero = cli("init", "--state", state)
    source = write(tmp_path / "batch.json", request(zero, "one", [value["analysis"]]))
    one = cli("apply", "--state", state, "--batch", source, "--analysis", p1, "--knowledge", KNOWLEDGE)
    assert one["report"]["inputs"][digest(value["analysis"])]["outcome"] == value["analysis"]["outcome"]
    (p1 / "run.json").write_text("private broken body", encoding="utf-8")
    rejected = cli("apply", "--state", state, "--batch", source, "--analysis", p1, "--knowledge", KNOWLEDGE, success=False)
    assert rejected == dict(status="rejected", reason="invalid_input_or_registry")
    assert cli("show", "--state", state) == one


def test_sqlite_hard_exit_before_commit_rolls_back_then_exact_retry_recovers(tmp_path):
    from app.job_analysis.work_candidates.storage import CandidateStore
    state = tmp_path / "state.db"
    a = work()
    with CandidateStore(state, create=True) as store:
        zero = store.read()
        source = write(tmp_path / "batch.json", batch(store, "one", [a], [create(a)]))
    input_path = write(tmp_path / "a.json", a)
    script = """
import os, sys
from pathlib import Path
from app.job_analysis.foundation.inputs import parse_json, digest
from app.job_analysis.knowledge.catalog import load_snapshot
from app.job_analysis.work_candidates.storage import CandidateStore
from app.job_analysis.work_candidates.service import apply_batch
request = parse_json(Path(sys.argv[2]).read_text(encoding='utf-8'))
a = parse_json(Path(sys.argv[3]).read_text(encoding='utf-8'))
with CandidateStore(sys.argv[1]) as store:
    append = store.append
    def crash(*args):
        append(*args)
        os._exit(73)
    store.append = crash
    apply_batch(store, request, {digest(a): a}, load_snapshot(sys.argv[4]))
"""
    stopped = subprocess.run([sys.executable, "-c", script, str(state), str(source), str(input_path), str(KNOWLEDGE)], cwd=BACKEND)
    assert stopped.returncode == 73
    with CandidateStore(state) as store:
        assert store.read() == zero
        assert store.conn.execute("SELECT count(*) FROM sources").fetchone()[0] == 0
    one = cli("apply", "--state", state, "--batch", source, "--analysis", input_path, "--knowledge", KNOWLEDGE)
    assert one["binding"]["revision"] == 1
    assert len(one["relations"]) == 1


def test_cli_refuses_public_repository_outputs_and_missing_registry(tmp_path):
    from uuid import uuid4
    public = BACKEND / "app" / ("p3-forbidden-" + uuid4().hex + ".db")
    assert cli("init", "--state", public, success=False)["status"] == "rejected"
    assert not public.exists()
    missing = tmp_path / "missing.db"
    assert cli("show", "--state", missing, success=False)["status"] == "rejected"
    assert not missing.exists()


def test_commit_survives_exit_before_output_and_retry_returns_identical_batch(tmp_path):
    from app.job_analysis.work_candidates.storage import CandidateStore
    state = tmp_path / "state.db"
    a = work()
    with CandidateStore(state, create=True) as store:
        source = write(tmp_path / "batch.json", batch(store, "one", [a], [create(a)]))
    input_path = write(tmp_path / "a.json", a)
    script = """
import os, sys
from pathlib import Path
from app.job_analysis.foundation.inputs import parse_json, digest
from app.job_analysis.knowledge.catalog import load_snapshot
from app.job_analysis.work_candidates.storage import CandidateStore
from app.job_analysis.work_candidates.service import apply_batch
a = parse_json(Path(sys.argv[3]).read_text(encoding='utf-8'))
with CandidateStore(sys.argv[1]) as store:
    apply_batch(store, parse_json(Path(sys.argv[2]).read_text(encoding='utf-8')),
                {digest(a): a}, load_snapshot(sys.argv[4]))
    os._exit(74)
"""
    stopped = subprocess.run([sys.executable, "-c", script, str(state), str(source), str(input_path), str(KNOWLEDGE)], cwd=BACKEND)
    assert stopped.returncode == 74
    persisted = cli("show", "--state", state)
    retried = cli("apply", "--state", state, "--batch", source, "--analysis", input_path, "--knowledge", KNOWLEDGE)
    assert persisted == retried
    assert retried["binding"]["revision"] == 1
    assert len(retried["relations"]) == 1

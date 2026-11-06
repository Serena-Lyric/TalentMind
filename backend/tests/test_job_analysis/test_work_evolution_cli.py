"""Actual P4 processes and isolated SQLite; no models, services or real JD."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from app.job_analysis.foundation.inputs import digest
from app.job_analysis.work_candidates.storage import CandidateStore
from test_work_candidates import cleanup_p3_files, correction, create
from test_work_candidates_cli import BACKEND, KNOWLEDGE, cli, request, write
from test_work_evolution import duties, research


def test_permanent_demo_runs_six_batches_via_cli_and_reopens_history(tmp_path):
    from app.job_analysis.work_candidates.demo import run_demo
    root = tmp_path / "demo"
    summary = run_demo(root, KNOWLEDGE)
    assert summary["batches"] == 6
    assert summary["research_versions"] == [1, 2, 3, 4, 5, 5]
    assert summary["third_batch_used_second_effective_work"] is True
    assert summary["exact_retry_preserved_head"] is True
    assert summary["historical_readback"] is True
    assert summary["real_human_grouping_denominator"] == 0
    assert summary["real_semantic_accuracy"] == "unverified"
    with CandidateStore(root / "state.db") as store:
        assert store.read()["revision"] == 6
        assert research(store.read(2))["description"] != research(store.read(1))["description"]
        assert research(store.read(6))["comparison_work"] == research(store.read(1))["comparison_work"]
        assert store.conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    with pytest.raises(FileExistsError):
        run_demo(root, KNOWLEDGE)


@pytest.mark.parametrize("phase", ["before_commit", "after_commit"])
def test_evolution_crash_and_exact_retry_commit_once(tmp_path, phase):
    state = tmp_path / "state.db"
    zero = cli("init", "--state", state)
    a = duties("a", ["开发订单交易接口。"])
    b = duties("b", ["开发订单交易接口。", "执行幂等校验并维护去重记录。"])
    a_file, b_file = write(tmp_path / "a.json", a), write(tmp_path / "b.json", b)
    first = write(tmp_path / "one.json", request(zero, "one", [a], [create(a)]))
    one = cli("apply", "--state", state, "--batch", first, "--analysis", a_file, "--knowledge", KNOWLEDGE)
    op = dict(op="link", candidate_id="work-orders", analysis_sha256=digest(b), work_ids=["d1", "d2"], reason="受控局部补充")
    second = write(tmp_path / "two.json", request(one, "two", [b], [op]))
    with CandidateStore(state) as store:
        source_count = store.conn.execute("SELECT count(*) FROM sources").fetchone()[0]
    script = """
import os, sys
from pathlib import Path
from app.job_analysis.foundation.inputs import parse_json, digest
from app.job_analysis.knowledge.catalog import load_snapshot
from app.job_analysis.work_candidates.storage import CandidateStore
from app.job_analysis.work_candidates.service import apply_batch
with CandidateStore(sys.argv[1]) as store:
    if sys.argv[5] == 'before_commit':
        append = store.append
        def crash(*args):
            append(*args)
            os._exit(73)
        store.append = crash
    command = parse_json(Path(sys.argv[2]).read_text(encoding='utf-8'))
    a = parse_json(Path(sys.argv[3]).read_text(encoding='utf-8'))
    apply_batch(store, command, {digest(a): a}, load_snapshot(sys.argv[4]))
    os._exit(74)
"""
    stopped = subprocess.run([sys.executable, "-c", script, str(state), str(second), str(b_file), str(KNOWLEDGE), phase], cwd=BACKEND)
    assert stopped.returncode == (73 if phase == "before_commit" else 74)
    with CandidateStore(state) as store:
        if phase == "before_commit":
            assert store.read() == one
            assert store.conn.execute("SELECT count(*) FROM sources").fetchone()[0] == source_count
        else:
            assert research(store.read())["version"] == 2
    two = cli("apply", "--state", state, "--batch", second, "--analysis", b_file, "--knowledge", KNOWLEDGE)
    assert research(two)["version"] == 2
    assert two["candidates"]["work-orders"]["version"] == 2
    assert cli("apply", "--state", state, "--batch", second, "--analysis", b_file, "--knowledge", KNOWLEDGE) == two
    assert cli("show", "--state", state, "--revision", 1) == one
    with CandidateStore(state) as store:
        assert len(store.history("work-orders")) == 2
        assert store.conn.execute("SELECT count(*) FROM batches").fetchone()[0] == 3
        assert store.source("analysis", digest(b)) == b


def test_cli_suggestion_checks_exact_binding_and_no_confirmation_command(tmp_path):
    state = tmp_path / "s.db"
    initial = cli("init", "--state", state)
    a = duties("a", ["开发订单交易接口。"])
    af = write(tmp_path / "a.json", a)
    bf = write(tmp_path / "one.json", request(initial, "one", [a], [create(a), create(a, "other")]))
    one = cli("apply", "--state", state, "--batch", bf, "--analysis", af, "--knowledge", KNOWLEDGE)
    suggestion = next(s for s in one["structural_suggestions"] if s["kind"] == "review_overlap")
    binding = write(tmp_path / "binding.json", one["binding"])
    result = cli("suggestion", "--state", state, "--id", suggestion["id"], "--baseline", binding)
    assert result["confirmation"] == "unavailable_no_trusted_identity"
    assert cli("show", "--state", state) == one
    second = write(tmp_path / "two.json", request(one, "two"))
    cli("apply", "--state", state, "--batch", second, "--knowledge", KNOWLEDGE)
    assert cli("suggestion", "--state", state, "--id", suggestion["id"], "--baseline", binding, success=False)["status"] == "rejected"

"""Immutable synthetic history, attributed reviews, replay and old-layer isolation."""
from dataclasses import replace
import json
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

from test_foundation_inputs import area
from test_role_governance import catalog, source, submission, candidate, no_network


def run(store, batch, marks=None, **kwargs):
    from app.job_analysis.role_classification.governance.runner import execute
    return execute(store, batch, submission(batch.records[0]) if marks is None else marks, catalog(), **kwargs)


def event(report, **changes):
    return dict(target_kind="candidate", target_id="candidate-a", result_version=report["members"][0]["result_version"],
        decision="reviewed_accepted", reviewer="Synthetic Reviewer", basis="合成审查，仅验证保存",
        evidence_refs=[report["members"][0]["body"]["candidates"][0]["evidence"][0]],
        supersedes=None, formal_admitted=False) | changes


def test_run_reuse_observation_and_history_replay(area):
    from app.job_analysis.role_classification.governance.store import CanonicalStore
    from app.job_analysis.role_classification.governance.runner import replay
    batch = source(area)
    with CanonicalStore(area / "state.db") as store:
        first = run(store, batch)
        second = run(store, batch)
        assert second["members"][0]["result_id"] == first["members"][0]["result_id"]
        assert second["members"][0]["reused"] is True
        changed_time = source(area, crawled_at="2026-10-16T10:00:00+08:00")
        third = run(store, changed_time)
        assert third["members"][0]["reused"] is True
        assert third["members"][0]["observation"] != first["members"][0]["observation"]
        assert replay(store, first["run_id"]) == first
        assert store.conn.execute("SELECT COUNT(*) FROM b32_results").fetchone()[0] == 1


@pytest.mark.parametrize("change", ["claim", "revision", "catalog", "input", "identity"])
def test_dependency_changes_append_without_rewriting_history(area, change):
    from app.job_analysis.role_classification.governance.store import CanonicalStore
    from app.job_analysis.role_classification.governance.runner import execute, replay
    batch = source(area)
    with CanonicalStore(area / "state.db") as store:
        first = run(store, batch)
        marks, config, revision = submission(batch.records[0]), catalog(), "v1"
        if change == "claim":
            marks["annotations"][0]["candidates"][0]["proposed_name"] = "另一合成名"
        elif change == "revision":
            revision = "v2"
        elif change == "catalog":
            config["revision"] = "empty-v2"
        else:
            batch = source(area, **(dict(requirements="新输入") if change == "input" else dict(id=2)))
            marks = submission(batch.records[0])
        next_run = execute(store, batch, marks, config, revision=revision)
        assert next_run["members"][0]["result_id"] != first["members"][0]["result_id"]
        assert next_run["members"][0]["reused"] is False
        assert replay(store, first["run_id"]) == first


def test_actual_source_change_invalidates_b32_only(area, monkeypatch):
    import shutil
    from app.job_analysis.role_classification.governance import runner
    from app.job_analysis.role_classification.governance.store import CanonicalStore
    batch = source(area)
    root = Path(runner.__file__).resolve().parents[2]
    copied = area / "copied"
    for path in runner.version_manifest(catalog(), "v1")["source_sha256"]:
        target = copied / path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / path, target)
    monkeypatch.setattr(runner, "__file__", str(copied / "role_classification/governance/runner.py"))
    with CanonicalStore(area / "state.db") as store:
        first = run(store, batch)
        path = copied / "role_classification/governance/validation.py"
        path.write_bytes(path.read_bytes() + b"\n# source revision\n")
        second = run(store, batch)
        assert second["version_id"] != first["version_id"]
        assert not second["members"][0]["reused"]


def test_review_is_immutable_attributed_and_never_admits_to_formal_catalog(area):
    from app.job_analysis.role_classification.governance.store import CanonicalStore
    from app.job_analysis.role_classification.governance.runner import replay, review_export
    with CanonicalStore(area / "state.db") as store:
        report = run(store, source(area))
        result = report["members"][0]["result_id"]
        accepted = store.record_review(result, event(report))
        store.record_review(result, event(report, decision="withdrawn", supersedes=accepted))
        reviews = store.reviews(result)
        assert [r["event"]["decision"] for r in reviews] == ["reviewed_accepted", "withdrawn"]
        assert all(r["event"]["formal_admitted"] is False for r in reviews)
        assert replay(store, report["run_id"]) == report
        exported = review_export(store, report["run_id"])
        assert exported["members"][0]["reviews"] == reviews
        assert exported["formal_jobs"] == [] and exported["formal_admitted"] is False
        assert report["members"][0]["body"]["candidates"][0]["review_status"] == "pending_review"
        for table in ("b32_versions", "b32_inputs", "b32_results", "b32_reports", "b32_reviews"):
            with pytest.raises(sqlite3.IntegrityError):
                store.conn.execute(f"DELETE FROM {table}")
            column = "manifest" if table == "b32_versions" else "path" if table == "b32_inputs" else "body"
            with pytest.raises(sqlite3.IntegrityError):
                store.conn.execute(f"UPDATE {table} SET {column}={column}")
            with pytest.raises(sqlite3.IntegrityError):
                store.conn.execute(f"INSERT OR REPLACE INTO {table} SELECT * FROM {table}")


@pytest.mark.parametrize("change", [dict(reviewer="  "), dict(basis=" "), dict(evidence_refs=[]),
    dict(target_id="missing"), dict(target_kind="relation"), dict(result_version="0" * 64),
    dict(formal_admitted=True), dict(decision="withdrawn"), dict(supersedes="review-missing")])
def test_invalid_review_never_leaves_an_event(area, change):
    from app.job_analysis.role_classification.governance.store import CanonicalStore
    with CanonicalStore(area / "state.db") as store:
        report = run(store, source(area))
        with pytest.raises(ValueError):
            store.record_review(report["members"][0]["result_id"], event(report, **change))
        assert store.conn.execute("SELECT COUNT(*) FROM b32_reviews").fetchone()[0] == 0


def test_review_evidence_rejects_foreign_source_and_wrong_offsets(area):
    from app.job_analysis.role_classification.governance.store import CanonicalStore
    with CanonicalStore(area / "state.db") as store:
        report = run(store, source(area))
        for change in (dict(jd_id="other"), dict(start=1)):
            mark = event(report)
            mark["evidence_refs"][0] = mark["evidence_refs"][0] | change
            with pytest.raises(ValueError):
                store.record_review(report["members"][0]["result_id"], mark)
        assert store.conn.execute("SELECT COUNT(*) FROM b32_reviews").fetchone()[0] == 0


@pytest.mark.parametrize("stage", ["after_result", "before_commit", "after_commit"])
def test_exception_boundaries_rollback_or_replay(area, monkeypatch, stage):
    from app.job_analysis.role_classification.governance import runner
    from app.job_analysis.role_classification.governance.store import CanonicalStore
    def stop(point):
        if point == stage:
            raise RuntimeError("interrupted")
    monkeypatch.setattr(runner, "checkpoint", stop)
    with CanonicalStore(area / "state.db") as store:
        with pytest.raises(RuntimeError):
            run(store, source(area))
        rows = store.conn.execute("SELECT run_id FROM b32_reports").fetchall()
        if stage == "after_commit":
            assert runner.replay(store, rows[0][0])["members"]
        else:
            for table in ("snapshots", "b32_versions", "b32_inputs", "b32_results", "b32_reports"):
                assert store.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0


@pytest.mark.parametrize("stage", ["after_result", "before_commit", "after_commit", "after_output"])
def test_real_process_death_recovers_without_partial_history(area, stage):
    from app.job_analysis.role_classification.governance.store import CanonicalStore
    from app.job_analysis.role_classification.governance.runner import replay
    batch = source(area)
    (area / "claims.json").write_text(json.dumps(submission(batch.records[0]), ensure_ascii=False), encoding="utf-8")
    script = """
import os, sys, json
from pathlib import Path
from app.job_analysis.foundation.inputs import read_snapshot
from app.job_analysis.role_classification.governance import runner
from app.job_analysis.role_classification.governance.store import CanonicalStore
root, stage = Path(sys.argv[1]), sys.argv[2]
runner.checkpoint = lambda point: os._exit(71) if point == stage else None
with CanonicalStore(root/'state.db') as store:
    runner.execute(store, read_snapshot(root/'input.json','fixture'), json.loads((root/'claims.json').read_text(encoding='utf-8')),
        dict(schema_version='b32-catalog-1', revision='empty-v1', formal_jobs=[]), output=root/'out')
"""
    done = subprocess.run([sys.executable, "-X", "utf8", "-c", script, str(area), stage], capture_output=True)
    assert done.returncode == 71, done.stderr.decode()
    with CanonicalStore(area / "state.db") as store:
        rows = store.conn.execute("SELECT run_id FROM b32_reports").fetchall()
        if stage in ("after_commit", "after_output"):
            assert len(rows) == 1 and len(replay(store, rows[0][0])["members"]) == 1
        else:
            assert len(rows) == 0
        resumed = run(store, batch)
        assert resumed["members"][0]["reused"] == (stage in ("after_commit", "after_output"))
        assert store.conn.execute("SELECT COUNT(*) FROM b32_results").fetchone()[0] == 1


def test_publish_failure_can_replay_without_current_input_or_catalog(area, monkeypatch):
    from app.job_analysis.role_classification.governance import runner
    from app.job_analysis.role_classification.governance.store import CanonicalStore
    from app.job_analysis.foundation.runner import publish
    def fail(*args):
        raise OSError("publication failed")
    batch = source(area)
    with CanonicalStore(area / "state.db") as store:
        with monkeypatch.context() as patch:
            patch.setattr(runner, "publish", fail)
            with pytest.raises(OSError):
                run(store, batch, output=area / "out")
        run_id = store.conn.execute("SELECT run_id FROM b32_reports").fetchone()[0]
        batch.path.unlink()
        original = runner.replay(store, run_id)
        publish(original, area / "restored", run_id)
        assert json.loads((area / "restored" / f"{run_id}.json").read_text(encoding="utf-8")) == original


@pytest.mark.parametrize("kind", ["bytes", "namespace", "records", "duplicate"])
def test_forged_source_batch_is_atomically_rejected(area, kind):
    from app.job_analysis.role_classification.governance.store import CanonicalStore
    batch = source(area)
    batch = replace(batch, **(dict(raw_bytes=b"[]") if kind == "bytes" else dict(namespace="other") if kind == "namespace" else
        dict(records=()) if kind == "records" else dict(records=batch.records * 2)))
    with CanonicalStore(area / "state.db") as store:
        with pytest.raises(ValueError):
            run(store, batch, submission(source(area).records[0]))
        assert store.conn.execute("SELECT COUNT(*) FROM b32_reports").fetchone()[0] == 0


def test_all_old_layers_rows_manifests_and_replays_remain_unchanged(area):
    from app.job_analysis.foundation.store import AnalysisStore
    from app.job_analysis.foundation.__main__ import LiteralDemoAnalyzer
    from app.job_analysis.foundation.runner import execute as a
    from app.job_analysis.screening.store import ScreeningStore
    from app.job_analysis.screening.runner import execute as b1
    from app.job_analysis.semantics.store import SemanticStore
    from app.job_analysis.semantics.runner import execute as b2
    from app.job_analysis.governance.store import GovernanceStore
    from app.job_analysis.governance.runner import execute as b22, replay as replay22
    from app.job_analysis.role_classification.store import RoleStore
    from app.job_analysis.role_classification.runner import execute as b30, replay as replay30, version_manifest as manifest30
    from app.job_analysis.role_classification.proposals.store import ProposalStore
    from app.job_analysis.role_classification.proposals.runner import execute as b31, replay as replay31, version_manifest as manifest31
    from app.job_analysis.role_classification.governance.store import CanonicalStore
    from test_role_classification import taxonomy, annotation
    from test_role_proposals import config, CATALOG
    state, batch = area / "state.db", source(area)
    before_manifests = manifest30(taxonomy(), "v1"), manifest31(config(), "v1")
    with AnalysisStore(state) as store:
        a(store, batch, LiteralDemoAnalyzer())
    with ScreeningStore(state) as store:
        scope = json.loads((CATALOG.parents[2] / "screening/software-related.offline.json").read_text(encoding="utf-8"))
        b1(store, batch.path, batch.namespace, scope=scope)
    with SemanticStore(state) as store:
        semantics = b2(store, batch)
    with GovernanceStore(state) as store:
        old22 = b22(store, semantics["run_id"])
    with RoleStore(state) as store:
        old30 = b30(store, batch, [annotation(batch.records[0])], taxonomy())
    with ProposalStore(state) as store:
        old31 = b31(store, batch, config())
        with store.conn:
            store.conn.execute("UPDATE runs SET status='running'")
        tables = [r[0] for r in store.conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        before = {t: [tuple(r) for r in store.conn.execute(f'SELECT * FROM "{t}"')] for t in tables}
    with CanonicalStore(state) as store:
        new = run(store, batch)
        store.record_review(new["members"][0]["result_id"], event(new))
        for table, rows in before.items():
            assert [tuple(r) for r in store.conn.execute(f'SELECT * FROM "{table}"')] == rows, table
        assert replay22(store, old22["run_id"]) == old22
        assert replay30(store, old30["run_id"]) == old30
        assert replay31(store, old31["run_id"]) == old31
        assert (manifest30(taxonomy(), "v1"), manifest31(config(), "v1")) == before_manifests
        assert store.conn.execute("PRAGMA user_version").fetchone()[0] == 1


@pytest.mark.parametrize("change", ["claim", "rules"])
def test_review_cannot_be_copied_to_changed_result_dependencies(area, change):
    from app.job_analysis.role_classification.governance.store import CanonicalStore
    with CanonicalStore(area / "state.db") as store:
        batch = source(area)
        first = run(store, batch)
        marks = submission(batch.records[0])
        if change == "claim":
            marks["annotations"][0]["candidates"][0]["proposed_name"] = "另一个合成提案"
        second = run(store, batch, marks, revision="v2" if change == "rules" else "v1")
        with pytest.raises(ValueError):
            store.record_review(second["members"][0]["result_id"], event(first))


def test_same_name_across_jds_is_visible_in_catalog_audit(area):
    from app.job_analysis.foundation.inputs import read_snapshot
    from app.job_analysis.role_classification.governance.store import CanonicalStore
    batch = source(area)
    rows = json.loads(batch.raw_bytes)
    batch.path.write_text(json.dumps(rows + [rows[0] | dict(id=2)], ensure_ascii=False), encoding="utf-8")
    batch = read_snapshot(batch.path, "fixture")
    marks = submission(batch.records[0])
    other = submission(batch.records[1], [candidate(batch.records[1], "candidate-b")])["annotations"][0]
    marks["annotations"].append(other)
    with CanonicalStore(area / "state.db") as store:
        report = run(store, batch, marks)
        assert any(a["name"] == "甲岗" and a["candidate_ids"] == ["candidate-a", "candidate-b"] for a in report["catalog_audit"])


def test_review_exports_preserve_historical_event_cutoff_and_are_replayable(area):
    from app.job_analysis.role_classification.governance.store import CanonicalStore
    from app.job_analysis.role_classification.governance.runner import replay, review_export
    with CanonicalStore(area / "state.db") as store:
        report = run(store, source(area))
        result = report["members"][0]["result_id"]
        store.record_review(result, event(report, decision="deferred"))
        first = review_export(store, report["run_id"])
        store.record_review(result, event(report, decision="reviewed_rejected"))
        assert len(review_export(store, report["run_id"])["members"][0]["reviews"]) == 2
        assert len(replay(store, first["export_id"])["members"][0]["reviews"]) == 1
        with pytest.raises(sqlite3.IntegrityError):
            store.conn.execute("INSERT OR REPLACE INTO b32_exports SELECT * FROM b32_exports")


def test_cli_run_replay_review_export_and_input_path_protection(area, capsys):
    from app.job_analysis.role_classification.governance.__main__ import main
    batch = source(area)
    claims, config, state = area / "claims.json", area / "catalog.json", area / "state.db"
    claims.write_text(json.dumps(submission(batch.records[0]), ensure_ascii=False), encoding="utf-8")
    config.write_text(json.dumps(catalog()), encoding="utf-8")
    args = ["--state", str(state), "--output", str(area / "out")]
    inputs = ["--input", str(batch.path), "--dataset", "fixture", "--submission", str(claims), "--catalog", str(config)]
    assert main(["run", *args, *inputs]) == 0
    run_id = json.loads(capsys.readouterr().out)["run_id"]
    report = json.loads((area / "out" / f"{run_id}.json").read_text(encoding="utf-8"))
    review = area / "review.json"
    review.write_text(json.dumps(event(report), ensure_ascii=False), encoding="utf-8")
    assert main(["review", "--state", str(state), "--result", report["members"][0]["result_id"], "--event", str(review)]) == 0
    capsys.readouterr()
    assert main(["export-reviews", *args, "--run", run_id]) == 0
    export_id = json.loads(capsys.readouterr().out)["export_id"]
    exported = json.loads((area / "out" / f"{export_id}.json").read_text(encoding="utf-8"))
    assert len(exported["members"][0]["reviews"]) == 1
    for path in (batch.path, claims, config):
        path.unlink()
    assert main(["replay", "--state", str(state), "--output", str(area / "replay"), "--run", run_id]) == 0
    assert (area / "out" / f"{run_id}.json").read_bytes() == (area / "replay" / f"{run_id}.json").read_bytes()
    # Replay must protect original input paths even after those files disappear.
    assert main(["replay", "--state", str(state), "--output", str(area), "--run", run_id]) == 2

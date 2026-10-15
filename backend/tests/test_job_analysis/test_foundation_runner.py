import json
import sqlite3

import pytest

from test_foundation_inputs import area, jd, load
from test_foundation_validation import claim, response, spec


class FakeAnalyzer:
    """The only substituted boundary is extraction; persistence/validation are real."""
    def __init__(self, output=None, error=None):
        self.spec = spec()
        self.output = output
        self.error = error
        self.seen = []

    def analyze(self, record):
        self.seen.append(record.payload)
        if self.error:
            raise self.error
        if self.output is not None:
            return self.output
        return response([claim(evidence=dict(namespace=record.namespace, jd_id=record.jd_id,
                                             field="raw_text", quote=record.payload["raw_text"]))])


def execute(area, rows=None, analyzer=None, **options):
    from app.job_analysis.foundation.runner import execute as run
    from app.job_analysis.foundation.store import AnalysisStore
    with AnalysisStore(area / "state.sqlite3") as store:
        return run(store, load(area, rows or [jd()]), analyzer or FakeAnalyzer(), **options)


def test_first_run_and_unchanged_run_keep_full_facts_without_extraction(area):
    analyzer = FakeAnalyzer()
    first = execute(area, [jd(), jd(id=2)], analyzer)
    second = execute(area, [jd()], analyzer)
    assert len(analyzer.seen) == 2
    assert second["business"] == first["business"]
    assert second["business"]["jd_records"] == 2
    assert second["business"]["completed_records"] == 2
    assert second["business"]["matched_facts"] == 2
    assert [m["attempt_id"] for m in first["members"]] == [m["attempt_id"] for m in second["members"]]


@pytest.mark.parametrize("change", [dict(job_title="Changed"), dict(duties="Changed"),
    dict(experience="Changed"), dict(raw_text="x" * 2001 + "Changed")])
def test_updated_input_preserves_old_attempt_and_evidence(area, change):
    first = execute(area)
    second = execute(area, [jd() | change])
    assert first["members"][0]["snapshot_id"] != second["members"][0]["snapshot_id"]
    from app.job_analysis.foundation.aggregate import replay
    from app.job_analysis.foundation.store import AnalysisStore
    with AnalysisStore(area / "state.sqlite3") as store:
        assert replay(store, first["aggregate_id"])["business"] == first["business"]
        assert store.attempt(first["members"][0]["attempt_id"])["facts"][0]["claim"]["evidence"]["quote"] == "Use Python"


def test_observation_change_reuses_but_is_saved(area):
    analyzer = FakeAnalyzer()
    execute(area, analyzer=analyzer)
    result = execute(area, [jd(crawled_at="2026-10-16")], analyzer)
    assert len(analyzer.seen) == 1
    from app.job_analysis.foundation.store import AnalysisStore
    with AnalysisStore(area / "state.sqlite3") as store:
        assert [o["crawled_at"] for o in store.observations("fixture", "1")] == ["2026-10-15T08:00:00+08:00", "2026-10-16"]


def test_versions_and_force_use_current_inputs(area):
    analyzer = FakeAnalyzer()
    first = execute(area, analyzer=analyzer)
    second = execute(area, analyzer=analyzer, aggregate_revision="v2")
    assert len(analyzer.seen) == 1 and first["business"] == second["business"]
    assert first["aggregate_version"] != second["aggregate_version"]
    third = execute(area, analyzer=analyzer, analysis_revision="v2")
    assert len(analyzer.seen) == 2
    assert first["members"][0]["analysis_version"] != third["members"][0]["analysis_version"]
    execute(area, [jd(duties="new duties", experience="new conditions")], analyzer, force=True)
    assert analyzer.seen[-1]["duties"] == "new duties"
    assert analyzer.seen[-1]["experience"] == "new conditions"


@pytest.mark.parametrize("analyzer", [FakeAnalyzer(error=RuntimeError("api_key=never-store")),
    FakeAnalyzer(output=""), FakeAnalyzer(output="not json")])
def test_failures_recorded_retryable_and_not_verified(area, analyzer):
    failed = execute(area, analyzer=analyzer)
    assert failed["business"]["failed_records"] == 1 and failed["business"]["matched_facts"] == 0
    assert failed["members"][0]["eligibility"] == "excluded"
    assert "never-store" not in json.dumps(failed)
    recovered = execute(area)
    assert recovered["business"]["completed_records"] == 1


def test_force_failure_does_not_silently_choose_prior_success(area):
    first = execute(area)
    failed = execute(area, analyzer=FakeAnalyzer(error=RuntimeError()), force=True)
    assert failed["business"]["failed_records"] == 1
    assert failed["members"][0]["attempt_id"] != first["members"][0]["attempt_id"]


def test_partial_valid_facts_and_zero_are_distinct(area):
    partial = execute(area, analyzer=FakeAnalyzer(response([claim(), claim(evidence=None)])))
    assert partial["business"]["partial_records"] == 1
    assert partial["business"]["matched_facts"] == 1
    assert partial["members"][0]["eligibility"] == "incomplete"
    zero = execute(area, analyzer=FakeAnalyzer(response([])))
    assert zero["business"]["completed_zero_skill_records"] == 1
    assert zero["business"]["failed_records"] == 0


@pytest.mark.parametrize("phase", ["after_prepare", "after_start", "after_analyze", "before_commit", "after_commit", "after_aggregate", "after_output"])
def test_interrupt_resume_commits_facts_once_and_keeps_all_members(area, monkeypatch, phase):
    import app.job_analysis.foundation.runner as runner
    from app.job_analysis.foundation.store import AnalysisStore
    fired = False
    def crash(stage):
        nonlocal fired
        if stage == phase and not fired:
            fired = True
            raise KeyboardInterrupt()
    monkeypatch.setattr(runner, "checkpoint", crash)
    analyzer = FakeAnalyzer()
    with AnalysisStore(area / "state.sqlite3") as store:
        with pytest.raises(KeyboardInterrupt):
            runner.execute(store, load(area, [jd(), jd(id=2)]), analyzer, output=area / "out")
        run_id = store.conn.execute("SELECT id FROM runs ORDER BY rowid DESC LIMIT 1").fetchone()[0]
    monkeypatch.setattr(runner, "checkpoint", lambda _: None)
    with AnalysisStore(area / "state.sqlite3") as store:
        resumed = runner.resume(store, run_id, analyzer, output=area / "out")
        assert resumed["business"]["completed_records"] == 2
        assert store.conn.execute("SELECT count(*) FROM attempts WHERE status='completed'").fetchone()[0] == 2
        assert store.conn.execute("SELECT count(*) FROM facts").fetchone()[0] == 2
        assert store.run(run_id)["status"] == "completed"
        assert json.loads((area / "out" / (run_id + ".json")).read_text(encoding="utf-8"))["business"] == resumed["business"]


def test_terminal_attempt_and_version_cannot_be_relabelled(area):
    result = execute(area)
    from app.job_analysis.foundation.store import AnalysisStore
    with AnalysisStore(area / "state.sqlite3") as store:
        with pytest.raises(sqlite3.IntegrityError):
            store.conn.execute("UPDATE attempts SET version_id='new' WHERE id=?", (result["members"][0]["attempt_id"],))
        with pytest.raises(sqlite3.IntegrityError):
            store.conn.execute("UPDATE versions SET manifest='{}'")


def test_store_excludes_concurrent_owner(area):
    from app.job_analysis.foundation.store import AnalysisStore
    with AnalysisStore(area / "state.sqlite3"):
        with pytest.raises(ValueError):
            with AnalysisStore(area / "state.sqlite3"):
                pass


def test_resume_rejects_changed_dependencies_and_does_not_relabel(area):
    import app.job_analysis.foundation.runner as runner
    from app.job_analysis.foundation.store import AnalysisStore
    from app.job_analysis.foundation.models import analysis_version
    from test_foundation_validation import spec
    with AnalysisStore(area / "state.sqlite3") as store:
        run = store.ingest(load(area, [jd()]), analysis_version("v1", spec(), runner.dictionary()))
        analyzer = FakeAnalyzer()
        analyzer.spec = analyzer.spec.model_copy(update={"model": "different"})
        with pytest.raises(ValueError):
            runner.resume(store, run, analyzer)
        assert store.conn.execute("SELECT count(*) FROM attempts").fetchone()[0] == 0


def test_same_members_reordered_reaggregate_identically(area):
    first = execute(area, [jd(), jd(id=2)])
    second = execute(area, [jd(id=2), jd()])
    assert first["aggregate_id"] == second["aggregate_id"]
    assert first["members"] == second["members"]
    assert first["business_sha256"] == second["business_sha256"]


def test_ingest_transaction_rolls_back_heads_and_observations(area):
    from app.job_analysis.foundation.store import AnalysisStore
    with AnalysisStore(area / "state.sqlite3") as store:
        store.conn.execute("CREATE TRIGGER inject_failure BEFORE INSERT ON observations BEGIN SELECT RAISE(ABORT,'synthetic'); END")
        with pytest.raises(sqlite3.IntegrityError):
            store.ingest(load(area, [jd()]))
        for table in ("runs", "snapshots", "heads", "observations"):
            assert store.conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 0


def test_new_incremental_batch_cannot_change_older_frozen_run(area):
    import app.job_analysis.foundation.runner as runner
    from app.job_analysis.foundation.models import analysis_version
    from app.job_analysis.foundation.store import AnalysisStore
    with AnalysisStore(area / "state.sqlite3") as store:
        run = store.ingest(load(area, [jd()]), analysis_version("v1", spec(), runner.dictionary()))
        runner.execute(store, load(area, [jd(raw_text="Use SQL")]), FakeAnalyzer())
        old = runner.resume(store, run, FakeAnalyzer())
        assert old["members"][0]["facts"][0]["claim"]["evidence"]["quote"] == "Use Python"
        assert store.heads("fixture")[0]["payload"]["raw_text"] == "Use SQL"


def test_hardlinked_state_alias_cannot_take_over_an_active_owner(area):
    import os
    from app.job_analysis.foundation.store import AnalysisStore
    with AnalysisStore(area / "state.sqlite3") as owner:
        owner.conn.execute("INSERT INTO versions VALUES ('fixture','{}')")
        owner.conn.commit()
        alias = area / "alias.sqlite3"
        os.link(owner.path, alias)
        try:
            with pytest.raises(ValueError):
                with AnalysisStore(alias):
                    pass
        finally:
            alias.unlink()


def test_terminal_attempt_cannot_accept_additional_facts(area):
    result = execute(area)
    from app.job_analysis.foundation.aggregate import replay
    from app.job_analysis.foundation.store import AnalysisStore
    attempt_id = result["members"][0]["attempt_id"]
    with AnalysisStore(area / "state.sqlite3") as store:
        with pytest.raises(sqlite3.IntegrityError):
            store.conn.execute("INSERT INTO facts(attempt_id,ordinal,body) VALUES (?,999,'{}')", (attempt_id,))
        assert replay(store, result["aggregate_id"])["business"] == result["business"]


def test_dictionary_used_for_normalization_matches_frozen_manifest(area, monkeypatch):
    import app.job_analysis.foundation.runner as runner
    calls = 0
    def changing_dictionary():
        nonlocal calls
        calls += 1
        return [{"canonical": "python"}] if calls <= 2 else [{"canonical": "sql"}]
    monkeypatch.setattr(runner, "dictionary", changing_dictionary)
    result = execute(area)
    assert result["members"][0]["facts"][0]["canonical_name"] == "python"


@pytest.mark.parametrize("table", ["versions", "snapshots", "facts", "aggregates", "attempts"])
def test_sqlite_replace_cannot_bypass_immutable_history(area, table):
    execute(area)
    from app.job_analysis.foundation.store import AnalysisStore
    with AnalysisStore(area / "state.sqlite3") as store:
        row = store.conn.execute(f"SELECT * FROM {table} LIMIT 1").fetchone()
        columns = list(row.keys())
        values = list(row)
        with pytest.raises(sqlite3.IntegrityError):
            store.conn.execute(f"INSERT OR REPLACE INTO {table} ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})", values)

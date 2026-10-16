"""Synthetic assertions exercise storage/evidence, never classification accuracy."""
import copy
from contextlib import closing
import json
import socket
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from test_foundation_inputs import area, load
from app.job_analysis.foundation.inputs import InputRecord


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("external/service network prohibited")
    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked)


def record(**changes):
    return InputRecord.from_row("fixture", dict(id=1, source="synthetic", job_title="示例甲",
        raw_text="职责示例乙；协助示例丙；方向甲与方向乙；级别甲。", duties="职责示例乙") | changes)


def evidence(item, field="raw_text", quote="示例乙"):
    text = item.payload[field]
    start = text.index(quote)
    return dict(namespace=item.namespace, jd_id=item.jd_id, fingerprint=item.fingerprint,
                field=field, start=start, end=start + len(quote), quote=quote)


def decision(value=None, refs=None, state=None):
    return dict(state=state or ("known" if value else "unknown"), value=value,
                candidates=[], evidence=refs or [], reason="显式合成断言，非识别结果")


def taxonomy(**changes):
    return dict(schema_version="b30-taxonomy-1", revision="synthetic-v1", mode="synthetic_example",
        job_family=["family-a"], canonical_job=["role-a", "role-b", "role-c"],
        technology_tracks=["track-a", "track-b"], seniority=["level-a"]) | changes


def annotation(item=None):
    item = item or record()
    return dict(namespace=item.namespace, jd_id=item.jd_id, fingerprint=item.fingerprint,
        origin="synthetic_assertion", author="fixture-author", review_status="pending_review",
        job_family=decision(), canonical_job=decision(), technology_tracks=[],
        technology_tracks_status="unknown", seniority=decision(), auxiliary_roles=[],
        material_kind="undetermined", material_evidence=[], conflicts=[], notes="待产品规则确认")


def validated(item, data, config=None):
    from app.job_analysis.role_classification.validation import validate_annotation
    return validate_annotation(item, data, config or taxonomy())


def test_unknown_dimensions_and_empty_taxonomy_preserve_source():
    item = record()
    data = annotation(item)
    original = copy.deepcopy(data)
    empty = taxonomy(mode="empty", job_family=[], canonical_job=[], technology_tracks=[], seniority=[])
    result = validated(item, data, empty)
    assert result["annotation"] == original == data
    assert result["source_payload"] == item.payload
    assert result["title_evidence"]["quote"] == "示例甲"
    assert result["duties_evidence"]["quote"] == "职责示例乙"
    assert result["classification_complete"] is False
    assert result["semantic_validation"] == "not_performed"
    assert result["formal_statistics_eligible"] is False


def test_multi_tracks_seniority_and_primary_auxiliary_are_independent():
    item = record()
    data = annotation(item)
    data.update(job_family=decision("family-a", [evidence(item)]),
        canonical_job=decision("role-b", [evidence(item)]),
        seniority=decision("level-a", [evidence(item, quote="级别甲")]),
        technology_tracks_status="known", material_kind="hybrid_role",
        material_evidence=[evidence(item)],
        technology_tracks=[decision("track-a", [evidence(item, quote="方向甲")]),
                           decision("track-b", [evidence(item, quote="方向乙")])],
        auxiliary_roles=[dict(primary="role-b", role=decision("role-c", [evidence(item, quote="示例丙")]),
                              evidence=[evidence(item, quote="协助示例丙")])])
    body = validated(item, data)
    assert body["annotation"] == data
    assert body["classification_complete"] is False  # assertions are still pending review
    assert "vacancy_count" not in body


def test_multiple_positions_and_title_duties_conflict_remain_unresolved():
    item = record()
    data = annotation(item)
    data["material_kind"] = "possible_multiple_positions"
    data["material_evidence"] = [evidence(item)]
    data["canonical_job"] = decision(refs=[evidence(item, "job_title", "示例甲"), evidence(item)], state="unresolved")
    data["canonical_job"]["candidates"] = ["role-a", "role-b"]
    data["conflicts"] = [dict(dimension="canonical_job", title=evidence(item, "job_title", "示例甲"),
                             duties=evidence(item, "duties", "职责示例乙"), reason="标题职责不同，尚未裁决")]
    body = validated(item, data)
    assert body["annotation"]["conflicts"] == data["conflicts"]
    assert body["annotation"]["canonical_job"]["value"] is None
    assert body["requires_review"] is True
    assert "vacancy_count" not in body


@pytest.mark.parametrize("mutation", [
    lambda d: d.update(jd_id="other"),
    lambda d: d.update(namespace="other"),
    lambda d: d.update(fingerprint="0" * 64),
    lambda d: d.update(review_status="approved"),
    lambda d: d.update(formal_statistics_eligible=True),
    lambda d: d["canonical_job"].update(state="known", value="role-a", evidence=[]),
    lambda d: d["canonical_job"].update(value="role-a"),
    lambda d: d["canonical_job"].update(candidates=["not-in-taxonomy"]),
    lambda d: d.update(technology_tracks_status="known"),
    lambda d: d.update(material_kind="possible_multiple_positions"),
])
def test_malformed_identity_states_and_unlicensed_values_rejected(mutation):
    item = record()
    data = annotation(item)
    mutation(data)
    with pytest.raises(ValueError):
        validated(item, data)


@pytest.mark.parametrize("change", [dict(jd_id="2"), dict(namespace="other"),
    dict(fingerprint="0" * 64), dict(start=999), dict(end=999), dict(start=True),
    dict(start=0, end=1), dict(quote="伪造"), dict(field="source"), dict(quote=" ")])
def test_foreign_or_fabricated_character_spans_rejected(change):
    item = record()
    ref = evidence(item) | change
    data = annotation(item)
    data["canonical_job"] = decision("role-a", [ref])
    with pytest.raises(ValueError):
        validated(item, data)


@pytest.mark.parametrize("config", [taxonomy(mode="production"), taxonomy(mode="empty"),
    taxonomy(canonical_job=["role-a", "role-a"]), taxonomy(seniority=[" "]),
    taxonomy(extra="unexpected")])
def test_taxonomy_cannot_claim_production_or_silently_normalize_invalid_values(config):
    with pytest.raises(ValueError):
        validated(record(), annotation(), config)


def test_conflict_cannot_keep_confirmed_value_and_auxiliary_needs_primary_link():
    item = record()
    data = annotation(item)
    data["canonical_job"] = decision("role-a", [evidence(item)])
    data["conflicts"] = [dict(dimension="canonical_job", title=evidence(item, "job_title", "示例甲"),
        duties=evidence(item, "duties", "职责示例乙"), reason="未解决")]
    with pytest.raises(ValueError):
        validated(item, data)
    data["conflicts"] = []
    data["auxiliary_roles"] = [dict(primary="role-b", role=decision("role-c", [evidence(item)]),
                                    evidence=[evidence(item)])]
    with pytest.raises(ValueError):
        validated(item, data)


def inputs(area, rows=None):
    return load(area, rows or [dict(id=1, source="synthetic", job_title="示例甲", raw_text="职责示例乙")])


def execute(store, batch, annotations=None, **kwargs):
    from app.job_analysis.role_classification.runner import execute as run
    return run(store, batch, [annotation(batch.records[0])] if annotations is None else annotations,
               kwargs.pop("taxonomy", taxonomy()), **kwargs)


def test_reuse_observations_versions_and_historical_replay(area):
    from app.job_analysis.role_classification.store import RoleStore
    from app.job_analysis.role_classification.runner import replay
    batch = inputs(area)
    with RoleStore(area / "state.sqlite3") as store:
        first = execute(store, batch)
        second = execute(store, batch)
        assert first["members"][0]["result_id"] == second["members"][0]["result_id"]
        assert second["members"][0]["reused"] is True
        changed = execute(store, batch, taxonomy=taxonomy(revision="synthetic-v2"))
        assert changed["version_id"] != first["version_id"]
        assert changed["members"][0]["result_id"] != first["members"][0]["result_id"]
        marked = annotation(batch.records[0])
        marked["notes"] = "新标注"
        revised = execute(store, batch, [marked])
        assert revised["members"][0]["result_id"] != first["members"][0]["result_id"]
        observed = inputs(area, [dict(id=1, source="synthetic", job_title="示例甲", raw_text="职责示例乙", crawled_at="new-observation")])
        again = execute(store, observed)
        assert again["members"][0]["result_id"] == first["members"][0]["result_id"]
        assert again["members"][0]["observation"] == "new-observation"
        assert replay(store, first["run_id"]) == first
        assert store.conn.execute("SELECT COUNT(*) FROM b30_reports").fetchone()[0] == 5


def test_partial_missing_annotation_is_saved_and_no_implicit_incremental_members(area):
    from app.job_analysis.role_classification.store import RoleStore
    batch = inputs(area, [dict(id=i, source="synthetic", job_title="示例甲", raw_text="职责示例乙") for i in (1, 2)])
    with RoleStore(area / "state.db") as store:
        report = execute(store, batch)
        assert [m["status"] for m in report["members"]] == ["assertion_saved", "not_annotated"]
        assert report["members"][1]["body"] is None
        assert report["audit"] == dict(jd_records=2, assertion_saved=1, not_annotated=1)
        assert report["formal_statistics_eligible"] is False
        smaller = execute(store, inputs(area))
        assert len(smaller["members"]) == 1


@pytest.mark.parametrize("kind", ["duplicate", "foreign", "fingerprint"])
def test_bad_annotation_batch_rolls_back_without_rows(area, kind):
    from app.job_analysis.role_classification.store import RoleStore
    batch = inputs(area)
    item = annotation(batch.records[0])
    annotations = [item, item] if kind == "duplicate" else [item | {"jd_id": "other"}]
    if kind == "fingerprint":
        annotations = [item | {"fingerprint": "0" * 64}]
    with RoleStore(area / "state.db") as store:
        with pytest.raises(ValueError):
            execute(store, batch, annotations)
        assert store.conn.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0] == 0
        assert store.conn.execute("SELECT COUNT(*) FROM b30_reports").fetchone()[0] == 0


def test_committed_history_is_immutable_including_replace(area):
    from app.job_analysis.role_classification.store import RoleStore
    with RoleStore(area / "state.db") as store:
        execute(store, inputs(area))
        for table in ("b30_versions", "b30_results", "b30_reports", "b30_inputs"):
            for sql in (f"DELETE FROM {table}", f"UPDATE {table} SET rowid=rowid", f"INSERT OR REPLACE INTO {table} SELECT * FROM {table}"):
                with pytest.raises(sqlite3.IntegrityError):
                    with store.conn:
                        store.conn.execute(sql)


def test_b3_open_preserves_running_a_and_legacy_rejected(area):
    from app.job_analysis.foundation.store import AnalysisStore
    from app.job_analysis.role_classification.store import RoleStore
    batch = inputs(area)
    state = area / "state.db"
    with AnalysisStore(state) as store:
        run_id = store.ingest(batch)
        with store.conn:
            store.conn.execute("UPDATE runs SET status='running' WHERE id=?", (run_id,))
        before_rows = {table: [tuple(r) for r in store.conn.execute(f"SELECT * FROM {table}")] for table in
                       ("runs", "snapshots", "heads", "observations", "attempts", "facts", "tasks")}
    with RoleStore(state) as store:
        execute(store, batch)
        for table, expected in before_rows.items():
            assert [tuple(r) for r in store.conn.execute(f"SELECT * FROM {table}")] == expected
        assert store.conn.execute("PRAGMA user_version").fetchone()[0] == 1
    legacy = area / "legacy.db"
    with closing(sqlite3.connect(legacy)) as conn:
        conn.execute("CREATE TABLE legacy (body TEXT)")
        conn.commit()
    with pytest.raises(ValueError):
        RoleStore(legacy)


@pytest.mark.parametrize("stage", ["after_result", "before_commit", "after_commit"])
def test_transaction_failure_and_restart(area, monkeypatch, stage):
    from app.job_analysis.role_classification import runner
    from app.job_analysis.role_classification.store import RoleStore
    batch = inputs(area)
    def fail(point):
        if point == stage:
            raise RuntimeError("interrupted")
    with RoleStore(area / "state.db") as store:
        monkeypatch.setattr(runner, "checkpoint", fail)
        with pytest.raises(RuntimeError):
            execute(store, batch)
        count = 1 if stage == "after_commit" else 0
        assert store.conn.execute("SELECT COUNT(*) FROM b30_reports").fetchone()[0] == count
        assert store.conn.execute("SELECT COUNT(*) FROM b30_results").fetchone()[0] == count
        monkeypatch.setattr(runner, "checkpoint", lambda _: None)
        retry = execute(store, batch)
        assert retry["members"][0]["reused"] == bool(count)


def test_cli_strict_files_and_replay_without_current_taxonomy(area):
    from app.job_analysis.role_classification.__main__ import main
    batch = inputs(area)
    marks, config = area / "annotations.json", area / "taxonomy.json"
    marks.write_text(json.dumps(dict(schema_version="b30-annotations-1", annotations=[annotation(batch.records[0])])), encoding="utf-8")
    config.write_text(json.dumps(taxonomy()), encoding="utf-8")
    state, output = area / "state.db", area / "output"
    args = ["run", "--input", str(batch.path), "--dataset", "fixture", "--annotations", str(marks),
            "--taxonomy", str(config), "--state", str(state), "--output", str(output)]
    assert main(args) == 0
    artifact = next(output.glob("*.json"))
    original = json.loads(artifact.read_text(encoding="utf-8"))
    marks.unlink()
    config.unlink()
    assert main(["replay", "--run", original["run_id"], "--state", str(state), "--output", str(area / "replay")]) == 0
    assert json.loads((area / "replay" / artifact.name).read_text(encoding="utf-8")) == original
    marks.write_text('{"schema_version":"b30-annotations-1","annotations":[],"annotations":[]}', encoding="utf-8")
    config.write_text(json.dumps(taxonomy()), encoding="utf-8")
    assert main(args) == 2
    assert len(list(output.glob("*.json"))) == 1


def test_new_content_identity_and_code_revision_invalidate_result(area, monkeypatch):
    from app.job_analysis.role_classification import runner
    from app.job_analysis.role_classification.store import RoleStore
    with RoleStore(area / "state.db") as store:
        old = execute(store, inputs(area))
        changed = execute(store, inputs(area, [dict(id=1, source="synthetic", job_title="新标题", raw_text="职责示例乙")]))
        assert changed["members"][0]["result_id"] != old["members"][0]["result_id"]
        assert execute(store, inputs(area), revision="v2")["version_id"] != old["version_id"]
        manifest = runner.version_manifest
        monkeypatch.setattr(runner, "version_manifest", lambda t, r: manifest(t, r) | {"actual_code_change": "simulated"})
        assert execute(store, inputs(area))["version_id"] != old["version_id"]


def test_existing_a_b1_b2_governance_runs_and_facts_unchanged(area):
    from app.job_analysis.foundation.store import AnalysisStore
    from app.job_analysis.foundation.__main__ import LiteralDemoAnalyzer
    from app.job_analysis.foundation.runner import execute as run_a
    from app.job_analysis.screening.store import ScreeningStore
    from app.job_analysis.screening.runner import execute as run_b1
    from app.job_analysis.semantics.store import SemanticStore
    from app.job_analysis.semantics.runner import execute as run_b2
    from app.job_analysis.governance.store import GovernanceStore
    from app.job_analysis.governance.runner import execute as run_b22
    from app.job_analysis.role_classification.store import RoleStore
    batch = inputs(area)
    state = area / "state.db"
    with AnalysisStore(state) as store:
        run_a(store, batch, LiteralDemoAnalyzer())
    with ScreeningStore(state) as store:
        scope = json.loads((Path(__file__).resolve().parents[2] / "app/job_analysis/screening/software-related.offline.json").read_text(encoding="utf-8"))
        run_b1(store, batch.path, batch.namespace, scope=scope)
    with SemanticStore(state) as store:
        b2 = run_b2(store, batch)
    with GovernanceStore(state) as store:
        run_b22(store, b2["run_id"])
        tables = [r[0] for r in store.conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        before = {t: [tuple(r) for r in store.conn.execute(f'SELECT * FROM "{t}"')] for t in tables}
    with RoleStore(state) as store:
        execute(store, batch)
        for table, rows in before.items():
            assert [tuple(r) for r in store.conn.execute(f'SELECT * FROM "{table}"')] == rows


def test_forged_input_batch_bytes_and_records_rejected(area):
    from dataclasses import replace
    from app.job_analysis.role_classification.store import RoleStore
    batch = inputs(area)
    with RoleStore(area / "state.db") as store:
        with pytest.raises(ValueError):
            execute(store, replace(batch, raw_bytes=b'[]'))
        assert store.conn.execute("SELECT COUNT(*) FROM b30_reports").fetchone()[0] == 0


def test_publication_failure_replay_uses_saved_document(area, monkeypatch):
    from app.job_analysis.role_classification import runner
    from app.job_analysis.role_classification.store import RoleStore
    batch = inputs(area)
    with RoleStore(area / "state.db") as store:
        original = runner.publish
        def fail(*args):
            raise OSError("publication failed")
        monkeypatch.setattr(runner, "publish", fail)
        with pytest.raises(OSError):
            execute(store, batch, output=area / "output")
        run_id = store.conn.execute("SELECT run_id FROM b30_reports").fetchone()[0]
        saved = runner.replay(store, run_id)
        monkeypatch.setattr(runner, "publish", original)
        artifact = original(saved, area / "output", run_id)
        assert json.loads(artifact.read_text(encoding="utf-8")) == saved
        artifact.write_text("different", encoding="utf-8")
        with pytest.raises(ValueError):
            original(saved, area / "output", run_id)


@pytest.mark.parametrize("stage", ["after_result", "before_commit", "after_commit", "after_stage_output", "after_output"])
def test_real_process_exit_atomicity(area, stage):
    batch = inputs(area)
    script = '''
import os, sys
from app.job_analysis.foundation.inputs import read_snapshot
from app.job_analysis.role_classification import runner
from app.job_analysis.foundation import runner as publication
from app.job_analysis.role_classification.store import RoleStore
def stop(point):
    if point == sys.argv[2]: os._exit(73)
runner.checkpoint = publication.checkpoint = stop
with RoleStore(sys.argv[3]) as store:
    runner.execute(store, read_snapshot(sys.argv[1], 'fixture'), [],
        dict(schema_version='b30-taxonomy-1', revision='v1', mode='empty', job_family=[], canonical_job=[], technology_tracks=[], seniority=[]), output=sys.argv[4])
'''
    state, output = area / "state.db", area / "output"
    # An empty annotation still saves a result for every source member.
    result = subprocess.run([sys.executable, "-c", script, str(batch.path), stage, str(state), str(output)], capture_output=True)
    assert result.returncode == 73, result.stderr
    from app.job_analysis.role_classification.store import RoleStore
    from app.job_analysis.role_classification.runner import replay
    from app.job_analysis.foundation.runner import publish
    with RoleStore(state) as store:
        rows = store.conn.execute("SELECT run_id FROM b30_reports").fetchall()
        assert len(rows) == (0 if stage in ("after_result", "before_commit") else 1)
        if rows:
            body = replay(store, rows[0][0])
            publish(body, output, body["run_id"])
            assert not list(output.glob("*.tmp"))
        else:
            assert store.conn.execute("SELECT COUNT(*) FROM b30_results").fetchone()[0] == 0
            execute(store, batch)

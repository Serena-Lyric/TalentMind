"""Synthetic snapshots only; no production imports, services or model calls."""
import json
import shutil
import tempfile
from contextlib import closing
from pathlib import Path

import pytest


@pytest.fixture
def area():
    path = Path(tempfile.mkdtemp(prefix="talentmind-m2-test-"))
    try:
        yield path
    finally:
        shutil.rmtree(path)
        assert not path.exists()


def jd(**changes):
    row = dict(id=1, source="synthetic", source_detail="fixture", job_title="Engineer",
               raw_text="Use Python", duties="Build services", experience="3 years",
               crawled_at="2026-10-15T08:00:00+08:00", quality=0.8, dup_group="same")
    return row | changes


def load(area, rows, suffix=".json"):
    from app.job_analysis.foundation.inputs import read_snapshot
    path = area / ("input" + suffix)
    path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    return read_snapshot(path, "fixture")


def test_preserves_fields_and_observation_without_mutating_source(area):
    batch = load(area, [jd(cross_source=1, requirements="SQL", custom={"x": 2})])
    record = batch.records[0]
    assert record.jd_id == "1" and record.namespace == "fixture"
    assert record.payload["requirements"] == "SQL"
    assert record.payload["custom"] == {"x": 2}
    assert "crawled_at" not in record.payload
    assert record.observation == "2026-10-15T08:00:00+08:00"
    assert json.loads(batch.raw_bytes)[0] == jd(cross_source=1, requirements="SQL", custom={"x": 2})


@pytest.mark.parametrize("change", [dict(job_title="Senior Engineer"), dict(duties="Test"),
    dict(experience="5 years"), dict(requirements="SQL"), dict(source_detail="new"),
    dict(quality=0.9), dict(custom=1), dict(raw_text="x" * 2001 + "B")])
def test_every_analysis_input_change_invalidates(area, change):
    before = load(area, [jd(raw_text="x" * 2001 + "A")]).records[0]
    after = load(area, [jd(raw_text="x" * 2001 + "A") | change]).records[0]
    assert before.fingerprint != after.fingerprint


def test_time_and_identity_separate_from_content(area):
    a, b = load(area, [jd(), jd(id=2, crawled_at="2026-10-16")]).records
    assert a.fingerprint == b.fingerprint and a.jd_id != b.jd_id


def test_jsonl_and_stable_key_order(area):
    from app.job_analysis.foundation.inputs import read_snapshot
    a = load(area, [jd()]).records[0]
    path = area / "input.jsonl"
    path.write_text(json.dumps(dict(reversed(list(jd().items())))) + "\n", encoding="utf-8")
    assert read_snapshot(path, "fixture").records[0].fingerprint == a.fingerprint


@pytest.mark.parametrize("rows", [[], {}, [None], [jd(id=None)], [jd(id=True)],
    [jd(raw_text=None)], [jd(job_title="")], [jd(source="")], [jd(), jd()],
    [jd(quality=float("nan"))], [jd(api_key="never-log-this")]])
def test_invalid_records_fail_explicitly(area, rows):
    with pytest.raises(ValueError):
        load(area, rows)


@pytest.mark.parametrize("suffix,body", [(".sql", "INSERT"), (".json", ""),
    (".json", "[{"), (".json", '[{"id":1,"id":2}]'),
    (".jsonl", '{"id":1}\nnot json')])
def test_bad_format_is_not_empty_success(area, suffix, body):
    from app.job_analysis.foundation.inputs import read_snapshot
    path = area / ("bad" + suffix)
    path.write_text(body, encoding="utf-8")
    with pytest.raises(ValueError):
        read_snapshot(path, "fixture")


def test_store_persists_snapshots_observations_and_dataset_identity(area):
    from app.job_analysis.foundation.store import AnalysisStore
    a = load(area, [jd()])
    db = area / "new.sqlite3"
    with AnalysisStore(db) as store:
        run = store.ingest(a)
        store.ingest(load(area, [jd(crawled_at="2026-10-16")]))
        other = type(a)("other", a.path, a.raw_bytes,
                        tuple(type(a.records[0]).from_row("other", jd()) for _ in range(1)))
        store.ingest(other)
        assert len(store.heads("fixture")) == len(store.heads("other")) == 1
        assert len(store.observations("fixture", "1")) == 2
        assert store.run(run)["input_sha256"] == a.digest
    with AnalysisStore(db) as store:
        assert store.heads("fixture")[0]["payload"]["duties"] == "Build services"


def test_legacy_database_rejected_without_changes(area):
    import sqlite3
    from app.job_analysis.foundation.store import AnalysisStore
    path = area / "legacy.db"
    with closing(sqlite3.connect(path)) as conn:
        conn.execute("CREATE TABLE records (id INTEGER)")
    before = path.read_bytes()
    with pytest.raises(ValueError):
        with AnalysisStore(path):
            pass
    assert path.read_bytes() == before


def test_existing_unidentified_empty_sqlite_is_not_adopted(area):
    import sqlite3
    from app.job_analysis.foundation.store import AnalysisStore
    path = area / "foreign.sqlite3"
    with closing(sqlite3.connect(path)) as conn:
        conn.execute("PRAGMA application_id=1234")
    before = path.read_bytes()
    with pytest.raises(ValueError):
        with AnalysisStore(path):
            pass
    assert path.read_bytes() == before

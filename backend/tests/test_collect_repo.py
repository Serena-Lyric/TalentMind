from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.collect.repository import build_insert_params, save_rows, save_incremental_jd_rows


def test_build_insert_params_maps_fields():
    row = {
        "source": "linkedin", "job_title": "AI Engineer", "raw_text": "Build AI systems",
        "duties": "Design and implement", "experience": "3-5年",
        "quality": 0.8, "dup_group": "abc123",
        "crawled_at": datetime(2026, 7, 24, tzinfo=timezone.utc),
        "status": "cleaned",
    }
    p = build_insert_params(row)
    assert p["source"] == "linkedin"
    assert p["job_title"] == "AI Engineer"
    assert p["raw_text"] == "Build AI systems"
    assert p["duties"] == "Design and implement"
    assert p["experience"] == "3-5年"
    assert p["quality"] == 0.8
    assert p["dup_group"] == "abc123"
    assert p["status"] == "cleaned"


def test_build_insert_params_defaults():
    row = {"raw_text": "x"}
    p = build_insert_params(row)
    assert p["source"] == ""
    assert p["quality"] == 0.0
    assert p["status"] == "cleaned"
    assert p["identity_status"] == "unknown"
    assert p["content_eligible"] is None
    assert p["identity_evidence"] == ""


def test_build_insert_params_maps_identity_metadata():
    p = build_insert_params({
        'raw_text': '负责平台开发',
        'identity_status': 'pending',
        'content_eligible': True,
        'identity_evidence': '{"binding_policy":"zhaopin-dom-panel-v1"}',
    })
    assert p['identity_status'] == 'pending'
    assert p['content_eligible'] is True
    assert p['identity_evidence'] == '{"binding_policy":"zhaopin-dom-panel-v1"}'


class FakeDB:
    def __init__(self):
        self.saved = []
        self.committed = 0

    def execute(self, stmt, params=None):
        if params:
            self.saved.append(params)

    def commit(self):
        self.committed += 1


def test_save_rows_batches_commits():
    db = FakeDB()
    rows = [{"raw_text": f"jd_{i}"} for i in range(2500)]
    count = save_rows(db, rows, batch_size=1000)
    assert count == 2500
    assert len(db.saved) == 2500
    assert db.committed == 3   # 1000 + 1000 + 500 → 3 commits


def test_save_empty_rows():
    db = FakeDB()
    count = save_rows(db, [], batch_size=1000)
    assert count == 0
    assert db.committed == 0


def _engine_with_schema(tmp_path, *, identity=False):
    path = tmp_path / ('new.sqlite3' if identity else 'old.sqlite3')
    engine = create_engine('sqlite:///' + str(path))
    extra = (', identity_status TEXT NOT NULL DEFAULT \'unknown\', '
             'content_eligible BOOLEAN NULL, identity_evidence TEXT NULL') if identity else ''
    with engine.begin() as db:
        db.exec_driver_sql(
            'CREATE TABLE jd_pool (id INTEGER PRIMARY KEY AUTOINCREMENT, source TEXT, '
            'source_detail TEXT, job_title TEXT, raw_text TEXT, duties TEXT, experience TEXT, '
            'quality FLOAT, dup_group TEXT, crawled_at DATETIME, status TEXT' + extra + ')'
        )
    return engine, path


def test_old_schema_rejects_pending_without_silent_evidence_loss(tmp_path):
    engine, path = _engine_with_schema(tmp_path)
    try:
        with Session(engine) as db:
            with pytest.raises(RuntimeError, match='identity_schema_migration_required'):
                save_rows(db, [{
                    'source': 'zhaopin', 'source_detail': 'dom://zhaopin/' + 'a' * 64,
                    'job_title': 'Python', 'raw_text': '负责平台开发',
                    'identity_status': 'pending', 'content_eligible': True,
                    'identity_evidence': '{}',
                }])
        with engine.connect() as db:
            assert db.execute(text('SELECT COUNT(*) FROM jd_pool')).scalar() == 0
    finally:
        engine.dispose()
        path.unlink(missing_ok=True)


def test_old_schema_still_accepts_legacy_unknown_rows(tmp_path):
    engine, path = _engine_with_schema(tmp_path)
    try:
        with Session(engine) as db:
            assert save_rows(db, [{
                'source': 'hn', 'source_detail': 'u',
                'job_title': 'role', 'raw_text': 'role body',
            }]) == 1
        with engine.connect() as db:
            assert db.execute(text('SELECT COUNT(*) FROM jd_pool')).scalar() == 1
    finally:
        engine.dispose()
        path.unlink(missing_ok=True)


def test_new_schema_persists_identity_content_and_evidence(tmp_path):
    engine, path = _engine_with_schema(tmp_path, identity=True)
    try:
        with Session(engine) as db:
            row = {
                'source': 'zhaopin', 'source_detail': 'dom://zhaopin/' + 'b' * 64,
                'job_title': 'Python', 'raw_text': '负责平台开发',
                'identity_status': 'pending', 'content_eligible': True,
                'identity_evidence': '{"binding_policy":"zhaopin-dom-panel-v1"}',
            }
            saved = []
            assert save_incremental_jd_rows(
                db, [row], created_ids=set(), on_saved=saved.append
            ) == 1
            assert saved[0]['identity_status'] == 'pending'
            assert saved[0]['content_eligible'] is True
        with engine.connect() as db:
            stored = db.execute(text(
                'SELECT identity_status, content_eligible, identity_evidence FROM jd_pool'
            )).mappings().one()
        assert stored['identity_status'] == 'pending'
        assert stored['content_eligible'] == 1
        assert stored['identity_evidence'] == '{"binding_policy":"zhaopin-dom-panel-v1"}'
    finally:
        engine.dispose()
        path.unlink(missing_ok=True)

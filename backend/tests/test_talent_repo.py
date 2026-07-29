import json
from datetime import datetime, timezone
from app.collect.repository import build_talent_insert_params, save_talent_rows


def test_build_talent_insert_params_maps_fields():
    row = {
        "source": "github", "identity_hint": "octocat", "raw_text": "Python dev",
        "skills_hint": ["Python", "Go"], "experience_hint": "5 years",
        "quality": 0.7, "dup_group": "abc123",
        "crawled_at": datetime(2026, 7, 29, tzinfo=timezone.utc),
        "status": "cleaned",
    }
    p = build_talent_insert_params(row)
    assert p["source"] == "github"
    assert p["identity_hint"] == "octocat"
    assert p["raw_text"] == "Python dev"
    assert json.loads(p["skills_hint"]) == ["Python", "Go"]
    assert p["experience_hint"] == "5 years"
    assert p["quality"] == 0.7
    assert p["status"] == "cleaned"


def test_build_talent_insert_params_defaults():
    row = {"raw_text": "x"}
    p = build_talent_insert_params(row)
    assert p["source"] == ""
    assert p["identity_hint"] == ""
    assert json.loads(p["skills_hint"]) == []
    assert p["quality"] == 0.0
    assert p["status"] == "cleaned"


def test_build_talent_insert_params_truncates_identity_hint():
    row = {"raw_text": "x", "identity_hint": "a" * 200}
    p = build_talent_insert_params(row)
    assert len(p["identity_hint"]) == 128


class FakeDB:
    def __init__(self):
        self.saved = []
        self.committed = 0

    def execute(self, stmt, params=None):
        if params:
            self.saved.append(params)

    def commit(self):
        self.committed += 1


def test_save_talent_rows_batches_commits():
    db = FakeDB()
    rows = [{"raw_text": f"talent_{i}"} for i in range(1500)]
    count = save_talent_rows(db, rows, batch_size=1000)
    assert count == 1500
    assert len(db.saved) == 1500
    assert db.committed == 2   # 1000 + 500 -> 2 commits


def test_save_empty_talent_rows():
    db = FakeDB()
    count = save_talent_rows(db, [], batch_size=1000)
    assert count == 0
    assert db.committed == 0

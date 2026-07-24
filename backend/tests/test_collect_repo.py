from datetime import datetime, timezone
from app.collect.repository import build_insert_params, save_rows


def test_build_insert_params_maps_fields():
    row = {
        "source": "dataset", "job_title": "AI Engineer", "raw_text": "Build AI systems",
        "duties": "Design and implement", "experience": "3-5年",
        "quality": 0.8, "dup_group": "abc123",
        "crawled_at": datetime(2026, 7, 24, tzinfo=timezone.utc),
        "status": "cleaned",
    }
    p = build_insert_params(row)
    assert p["source"] == "dataset"
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

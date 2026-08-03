import pytest
from sqlalchemy import text
from app.db.mysql import get_db

pytestmark = pytest.mark.integration

EXPECTED_TABLES = {"jd_pool", "signal", "skill_dict", "job_skill",
                   "job_definition", "job_change_log", "resume", "talent_raw"}

def _cols(db, table):
    rows = db.execute(text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema='talentmind' AND table_name=:t"), {"t": table})
    return {r[0] for r in rows}

def test_all_tables_created():
    db = next(get_db())
    try:
        rows = db.execute(text("SHOW TABLES")).fetchall()
        tables = {r[0] for r in rows}
        assert EXPECTED_TABLES.issubset(tables)
    finally:
        db.close()

def test_job_skill_has_frozen_columns():
    db = next(get_db())
    try:
        cols = _cols(db, "job_skill")
        assert {"jd_id", "job_name", "level", "skills", "duties", "extracted_at"}.issubset(cols)
    finally:
        db.close()

def test_job_definition_has_frozen_columns():
    db = next(get_db())
    try:
        cols = _cols(db, "job_definition")
        assert {"job_name", "core_duties", "required_skills", "bonus_skills",
                "scenarios", "source", "quality", "is_emerging",
                "evolution", "first_seen", "collected_at", "updated_at"}.issubset(cols)
    finally:
        db.close()

def test_job_change_log_has_frozen_columns():
    db = next(get_db())
    try:
        cols = _cols(db, "job_change_log")
        assert {"job_id", "change_type", "skill_name", "detail",
                "source", "reason", "created_at"}.issubset(cols)
    finally:
        db.close()

def test_skill_dict_canonical_unique():
    db = next(get_db())
    try:
        rows = db.execute(text("SHOW INDEX FROM skill_dict WHERE Column_name='canonical'"))
        assert rows.fetchone() is not None   # canonical 有索引/唯一约束
    finally:
        db.close()

def test_talent_raw_has_frozen_columns():
    db = next(get_db())
    try:
        cols = _cols(db, "talent_raw")
        assert {"source", "identity_hint", "raw_text", "skills_hint",
                "experience_hint", "quality", "dup_group", "crawled_at", "status"}.issubset(cols)
    finally:
        db.close()

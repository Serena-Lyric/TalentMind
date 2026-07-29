import pytest
from sqlalchemy import text
from app.db.mysql import get_db
from app.collect.schema import RawJD, RawTalent
from app.collect.pipeline import run_pipeline

pytestmark = pytest.mark.integration


def test_talent_raw_to_database(tmp_path):
    """端到端: RawTalent → clean_talent → dedup → talent_raw"""
    db = next(get_db())
    try:
        db.execute(text("DELETE FROM talent_raw WHERE source='github'"))
        db.commit()

        raws = [
            RawTalent(
                source="github",
                raw_text="Experienced Python developer with 5 open source repos",
                identity_hint="octocat",
                skills_hint=["Python", "Go"],
                experience_hint="5 years",
            ),
        ]
        stats = run_pipeline(db, raws)
        assert stats["talent_saved"] == 1
        assert stats["jd_saved"] == 0

        row = db.execute(text(
            "SELECT identity_hint, raw_text, skills_hint, status FROM talent_raw "
            "WHERE source='github' AND identity_hint='octocat'"
        )).fetchone()
        assert row is not None
        assert row[0] == "octocat"
        assert "Python developer" in row[1]
        assert row[3] == "cleaned"
    finally:
        db.close()


def test_mixed_batch_saves_to_both_tables_independently():
    """混合批次: RawJD 进 jd_pool, RawTalent 进 talent_raw, 互不干扰"""
    db = next(get_db())
    try:
        db.execute(text("DELETE FROM jd_pool WHERE source='dataset' AND job_title='Mixed Batch JD'"))
        db.execute(text("DELETE FROM talent_raw WHERE source='github' AND identity_hint='mixed_batch_user'"))
        db.commit()

        raws = [
            RawJD(source="dataset", job_title="Mixed Batch JD", raw_html="Build systems."),
            RawTalent(source="github", raw_text="Go developer", identity_hint="mixed_batch_user"),
        ]
        stats = run_pipeline(db, raws)
        assert stats["jd_saved"] == 1
        assert stats["talent_saved"] == 1
        assert stats["saved"] == 2

        jd_count = db.execute(text(
            "SELECT COUNT(*) FROM jd_pool WHERE source='dataset' AND job_title='Mixed Batch JD'"
        )).scalar()
        talent_count = db.execute(text(
            "SELECT COUNT(*) FROM talent_raw WHERE source='github' AND identity_hint='mixed_batch_user'"
        )).scalar()
        assert jd_count == 1
        assert talent_count == 1
    finally:
        db.close()

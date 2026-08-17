import pytest
from sqlalchemy import text
from app.db.mysql import get_db
from app.collect.schema import RawJD, RawTalent
from app.collect.pipeline import run_pipeline

pytestmark = pytest.mark.integration


def test_talent_raw_to_database(tmp_path):
    """端到端: RawTalent -> clean_talent -> dedup -> talent_raw

    测试数据清理规范（D37）：只按 identity_hint 精确清理，禁止按 source 全量删除
    （曾因 DELETE WHERE source='github' 可能误删生产 talent_raw）；finally 必定清理。
    """
    TEST_IDENTITY = "octocat"

    def _cleanup(db):
        db.execute(text(
            "DELETE FROM talent_raw WHERE source='github' AND identity_hint=:h"
        ), {"h": TEST_IDENTITY})
        db.commit()

    db = next(get_db())
    try:
        _cleanup(db)

        raws = [
            RawTalent(
                source="github",
                raw_text="Experienced Python developer with 5 open source repos",
                identity_hint=TEST_IDENTITY,
                skills_hint=["Python", "Go"],
                experience_hint="5 years",
            ),
        ]
        stats = run_pipeline(db, raws)
        assert stats["talent_saved"] == 1
        assert stats["jd_saved"] == 0

        row = db.execute(text(
            "SELECT identity_hint, raw_text, skills_hint, status FROM talent_raw "
            "WHERE source='github' AND identity_hint=:h"
        ), {"h": TEST_IDENTITY}).fetchone()
        assert row is not None
        assert row[0] == TEST_IDENTITY
        assert "Python developer" in row[1]
        assert row[3] == "cleaned"
    finally:
        _cleanup(db)
        db.close()

def test_mixed_batch_saves_to_both_tables_independently():
    """混合批次: RawJD 进 jd_pool, RawTalent 进 talent_raw, 互不干扰

    测试数据清理规范（D37）：按夹具特征精确清理（job_title / identity_hint）；
    finally 中必定清理，失败也不残留。
    """
    db = next(get_db())
    try:
        db.execute(text("DELETE FROM jd_pool WHERE source='linkedin' AND job_title='Mixed Batch JD'"))
        db.execute(text("DELETE FROM talent_raw WHERE source='github' AND identity_hint='mixed_batch_user'"))
        db.commit()

        raws = [
            RawJD(source="linkedin", job_title="Mixed Batch JD", raw_html="Build systems."),
            RawTalent(source="github", raw_text="Go developer", identity_hint="mixed_batch_user"),
        ]
        stats = run_pipeline(db, raws)
        assert stats["jd_saved"] == 1
        assert stats["talent_saved"] == 1
        assert stats["saved"] == 2

        jd_count = db.execute(text(
            "SELECT COUNT(*) FROM jd_pool WHERE source='linkedin' AND job_title='Mixed Batch JD'"
        )).scalar()
        talent_count = db.execute(text(
            "SELECT COUNT(*) FROM talent_raw WHERE source='github' AND identity_hint='mixed_batch_user'"
        )).scalar()
        assert jd_count == 1
        assert talent_count == 1
    finally:
        db.execute(text("DELETE FROM jd_pool WHERE source='linkedin' AND job_title='Mixed Batch JD'"))
        db.execute(text("DELETE FROM talent_raw WHERE source='github' AND identity_hint='mixed_batch_user'"))
        db.commit()
        db.close()

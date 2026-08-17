import csv
import pytest
from sqlalchemy import text
from app.db.mysql import get_db
from app.collect.fetchers.dataset import load_csv_posting, load_skill_map, load_job_skills
from app.collect.pipeline import run_pipeline

pytestmark = pytest.mark.integration


def test_csv_to_jd_pool_via_pipeline(tmp_path):
    """端到端: CSV -> RawJD -> clean -> dedup -> jd_pool

    测试数据清理规范（D37）：只按测试夹具特征精确清理，禁止按 source 全量删除
    （曾因 DELETE WHERE source='linkedin' 误删生产 jd_pool，见
    docs/superpowers/traps/2026-08-16-integration-test-wiped-jd-pool.md）。
    测试前清旧残留保证可重复运行；finally 中必定清理本次产出，失败也不残留。
    """
    TEST_TITLES = ("AI应用工程师", "后端工程师")

    def _cleanup_fixture(db):
        db.execute(text(
            "DELETE FROM jd_pool WHERE source='linkedin' "
            "AND job_title IN (:t1, :t2)"
        ), {"t1": TEST_TITLES[0], "t2": TEST_TITLES[1]})
        db.commit()

    postings_csv = tmp_path / "postings.csv"
    with open(postings_csv, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["job_id", "title", "description", "formatted_experience_level"])
        w.writerow(["1", "AI应用工程师", "Job description负责 RAG 与 LLM 应用开发", "3-5年"])
        w.writerow(["2", "后端工程师", "We need a backend developer.", "Entry level"])

    skills_csv = tmp_path / "skills.csv"
    with open(skills_csv, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["skill_abr", "skill_name"])
        w.writerow(["ENG", "Engineering"])
        w.writerow(["PRJM", "Project Management"])

    job_skills_csv = tmp_path / "job_skills.csv"
    with open(job_skills_csv, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["job_id", "skill_abr"])
        w.writerow(["1", "ENG"])
        w.writerow(["1", "PRJM"])

    db = next(get_db())
    try:
        _cleanup_fixture(db)

        raws = load_csv_posting(str(postings_csv), limit=0)
        assert len(raws) == 2

        skill_map = load_skill_map(str(skills_csv))
        job_skill_map = load_job_skills(str(job_skills_csv))

        stats = run_pipeline(db, raws, job_skill_map=job_skill_map, skill_map=skill_map)
        assert stats["saved"] == 2

        # 只统计本次夹具行，避免与生产 jd_pool（source 同样为 linkedin）混算
        cnt = db.execute(text(
            "SELECT COUNT(*) FROM jd_pool WHERE source='linkedin' AND status='cleaned' "
            "AND job_title IN (:t1, :t2)"
        ), {"t1": TEST_TITLES[0], "t2": TEST_TITLES[1]}).scalar()
        assert cnt == 2

        text_with_skills = db.execute(text(
            "SELECT raw_text FROM jd_pool WHERE job_title='AI应用工程师'"
        )).scalar()
        assert "Engineering" in text_with_skills
        assert "Project Management" in text_with_skills

        assert "Job description" not in text_with_skills
        assert "负责 RAG" in text_with_skills
    finally:
        _cleanup_fixture(db)
        db.close()

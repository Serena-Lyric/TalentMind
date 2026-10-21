from pathlib import Path

from app.collect.schema import RawJD, RawTalent


def test_rawtalent_minimal_construction():
    t = RawTalent(source="github", raw_text="Python developer, 5 repos")
    assert t.source == "github"
    assert t.raw_text == "Python developer, 5 repos"
    assert t.identity_hint == ""
    assert t.skills_hint is None
    assert t.experience_hint == ""


def test_rawtalent_full_construction():
    t = RawTalent(
        source="resume_dataset",
        raw_text="5 years backend experience",
        identity_hint="user_123",
        skills_hint=["Python", "Django"],
        experience_hint="5 years backend",
    )
    assert t.identity_hint == "user_123"
    assert t.skills_hint == ["Python", "Django"]
    assert t.experience_hint == "5 years backend"


def test_rawjd_unaffected_by_rawtalent_addition():
    # 回归防护：RawJD 字段不受本次修改影响
    jd = RawJD(source="linkedin", job_title="AI Engineer", raw_html="desc")
    assert jd.source == "linkedin"
    assert jd.job_id == ""
    assert jd.raw_skills is None


def test_jd_pool_identity_contract_and_additive_migration_are_declared():
    root = Path(__file__).resolve().parents[2]
    ddl = (root / 'backend/app/contracts/ddl.sql').read_text(encoding='utf-8')
    migration_path = root / 'backend/app/contracts/migrations/2026-10-21-jd-pool-identity-status.sql'
    assert "identity_status VARCHAR(16) NOT NULL DEFAULT 'unknown'" in ddl
    assert 'content_eligible TINYINT(1) NULL DEFAULT NULL' in ddl
    assert 'identity_evidence TEXT NULL' in ddl
    assert migration_path.exists()
    migration = migration_path.read_text(encoding='utf-8')
    assert 'ALTER TABLE jd_pool' in migration
    assert 'DROP COLUMN' not in migration.upper()

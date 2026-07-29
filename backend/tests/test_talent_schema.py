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
    jd = RawJD(source="dataset", job_title="AI Engineer", raw_html="desc")
    assert jd.source == "dataset"
    assert jd.job_id == ""
    assert jd.raw_skills is None

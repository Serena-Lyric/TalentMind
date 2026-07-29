from app.collect.schema import RawTalent
from app.collect.talent_cleaner import clean_talent


def test_clean_talent_produces_talent_raw_row():
    raw = RawTalent(
        source="github",
        raw_text="  Python developer with 5 repos  ",
        identity_hint="  octocat  ",
        skills_hint=["Python", "Go"],
        experience_hint="  5 years  ",
    )
    row = clean_talent(raw)
    assert row["source"] == "github"
    assert row["identity_hint"] == "octocat"
    assert row["raw_text"] == "Python developer with 5 repos"
    assert row["skills_hint"] == ["Python", "Go"]
    assert row["experience_hint"] == "5 years"
    assert row["status"] == "cleaned"
    assert row["crawled_at"] is not None


def test_clean_talent_defaults_none_skills_hint_to_empty_list():
    raw = RawTalent(source="resume_dataset", raw_text="text")
    row = clean_talent(raw)
    assert row["skills_hint"] == []
    assert row["identity_hint"] == ""
    assert row["experience_hint"] == ""


def test_clean_talent_strips_whitespace_only_raw_text():
    raw = RawTalent(source="github", raw_text="   \n  ")
    row = clean_talent(raw)
    assert row["raw_text"] == ""

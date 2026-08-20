import csv
from app.collect.fetchers.dataset import (
    iter_csv_postings,
    load_csv_posting,
    load_skill_map,
    load_job_skills,
)
from app.collect.schema import RawJD


class TestLoadCsvPosting:
    def test_loads_rows_as_rawjd(self, tmp_path):
        f = tmp_path / "postings.csv"
        f.write_text(
            "job_id,title,description,formatted_experience_level\n"
            "123,AI Engineer,We need an AI engineer.,Mid-Senior level\n"
            "456,Backend Dev,Build APIs.,\n",
            encoding="utf-8",
        )
        rows = load_csv_posting(str(f), limit=0)
        assert len(rows) == 2
        assert isinstance(rows[0], RawJD)
        assert rows[0].job_title == "AI Engineer"
        assert rows[0].source == "linkedin"
        assert rows[0].raw_html == "We need an AI engineer."
        assert rows[0].experience == "Mid-Senior level"
        assert rows[0].job_id == "123"

    def test_respects_limit(self, tmp_path):
        f = tmp_path / "postings.csv"
        lines = ["job_id,title,description,formatted_experience_level\n"]
        for i in range(20):
            lines.append(f"{i},Job {i},Description {i},\n")
        f.write_text("".join(lines), encoding="utf-8")
        rows = load_csv_posting(str(f), limit=5)
        assert len(rows) == 5

    def test_supports_offset_for_resume(self, tmp_path):
        f = tmp_path / "postings.csv"
        lines = ["job_id,title,description,formatted_experience_level\n"]
        for i in range(5):
            lines.append(f"{i},Job {i},Description {i},\n")
        f.write_text("".join(lines), encoding="utf-8")

        rows = list(iter_csv_postings(str(f), offset=2, limit=2))

        assert [row.job_id for row in rows] == ["2", "3"]

    def test_skips_empty_title(self, tmp_path):
        f = tmp_path / "postings.csv"
        f.write_text(
            "job_id,title,description,formatted_experience_level\n"
            "1,,Empty title,\n"
            "2,Valid Job,Has description,\n",
            encoding="utf-8",
        )
        rows = load_csv_posting(str(f), limit=0)
        assert len(rows) == 1
        assert rows[0].job_title == "Valid Job"

    def test_handles_multiline_description(self, tmp_path):
        f = tmp_path / "postings.csv"
        f.write_text(
            'job_id,title,description,formatted_experience_level\n'
            '1,Engineer,"Line 1\nLine 2\nLine 3",Entry level\n',
            encoding="utf-8",
        )
        rows = load_csv_posting(str(f), limit=0)
        assert len(rows) == 1
        assert "Line 1" in rows[0].raw_html
        assert "Line 3" in rows[0].raw_html


class TestLoadSkillMap:
    def test_loads_abr_to_name(self, tmp_path):
        f = tmp_path / "skills.csv"
        f.write_text(
            "skill_abr,skill_name\nPRJM,Project Management\nENG,Engineering\n",
            encoding="utf-8",
        )
        m = load_skill_map(str(f))
        assert m == {"PRJM": "Project Management", "ENG": "Engineering"}


class TestLoadJobSkills:
    def test_loads_job_to_skill_list(self, tmp_path):
        f = tmp_path / "job_skills.csv"
        f.write_text(
            "job_id,skill_abr\n100,PRJM\n100,ENG\n200,PRJM\n",
            encoding="utf-8",
        )
        m = load_job_skills(str(f))
        assert m == {"100": ["PRJM", "ENG"], "200": ["PRJM"]}

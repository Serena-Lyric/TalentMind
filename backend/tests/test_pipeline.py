from app.collect.pipeline import run_pipeline, enrich_skills
from app.collect.schema import RawJD, RawTalent


class FakeDB:
    def __init__(self):
        self.saved = []
        self.committed = 0

    def execute(self, stmt, params=None):
        if params:
            self.saved.append(params)

    def commit(self):
        self.committed += 1


class TestEnrichSkills:
    def test_appends_skill_names_to_raw_text(self):
        rows = [
            {"raw_text": "Build AI systems.", "_job_id": "100"},
            {"raw_text": "Manage projects.", "_job_id": "200"},
        ]
        job_skill_map = {"100": ["ENG", "PRJM"], "200": ["MGMT"]}
        skill_map = {"ENG": "Engineering", "PRJM": "Project Management", "MGMT": "Management"}
        enriched = enrich_skills(rows, job_skill_map, skill_map)
        assert "Engineering" in enriched[0]["raw_text"]
        assert "Project Management" in enriched[0]["raw_text"]
        assert "Management" in enriched[1]["raw_text"]

    def test_removes_job_id_key_after_enrich(self):
        rows = [{"raw_text": "x", "_job_id": "100"}]
        job_skill_map = {"100": ["ENG"]}
        skill_map = {"ENG": "Engineering"}
        enriched = enrich_skills(rows, job_skill_map, skill_map)
        assert "_job_id" not in enriched[0]

    def test_skips_when_job_id_not_found(self):
        rows = [{"raw_text": "x", "_job_id": "999"}]
        enriched = enrich_skills(rows, {}, {})
        assert enriched[0]["raw_text"] == "x"

    def test_skips_when_no_job_id_key(self):
        rows = [{"raw_text": "x"}]
        enriched = enrich_skills(rows, {}, {})
        assert enriched[0]["raw_text"] == "x"


class TestRunPipeline:
    def test_pipeline_cleans_dedups_saves(self):
        db = FakeDB()
        raws = [
            RawJD(source="github", job_title="AI工程师",
                  raw_html="负责 RAG 开发 熟悉 Python 的候选人", experience="3-5年"),
            RawJD(source="linkedin", job_title="AI工程师",
                  raw_html="负责RAG开发,熟悉Python的候选人", experience="3-5年"),
        ]
        stats = run_pipeline(db, raws)
        assert stats["saved"] == 2
        assert db.saved[0]["dup_group"] == db.saved[1]["dup_group"]
        assert db.saved[0]["quality"] > 0

    def test_pipeline_with_skill_enrichment(self):
        db = FakeDB()
        raws = [
            RawJD(source="linkedin", job_title="AI Engineer",
                  raw_html="Build AI systems.", job_id="100"),
        ]
        job_skill_map = {"100": ["ENG"]}
        skill_map = {"ENG": "Engineering"}
        stats = run_pipeline(db, raws, job_skill_map=job_skill_map, skill_map=skill_map)
        assert stats["saved"] == 1
        assert "Engineering" in db.saved[0]["raw_text"]


class TestRunPipelineRouting:
    def test_routes_talent_raws_to_talent_saved(self):
        db = FakeDB()
        raws = [
            RawTalent(source="github", raw_text="Python developer with 5 repos"),
            RawTalent(source="resume_dataset", raw_text="Python developer with five repos"),
        ]
        stats = run_pipeline(db, raws)
        assert stats["talent_saved"] == 2
        assert stats["jd_saved"] == 0
        assert stats["saved"] == 2

    def test_routes_mixed_raws_to_both_sides(self):
        db = FakeDB()
        raws = [
            RawJD(source="linkedin", job_title="AI Engineer", raw_html="Build AI systems."),
            RawTalent(source="github", raw_text="Python developer with 5 repos"),
        ]
        stats = run_pipeline(db, raws)
        assert stats["jd_saved"] == 1
        assert stats["talent_saved"] == 1
        assert stats["saved"] == 2

    def test_empty_raws_returns_zero_stats(self):
        db = FakeDB()
        stats = run_pipeline(db, [])
        assert stats == {"saved": 0, "jd_saved": 0, "talent_saved": 0, "groups": 0}

import pytest

from app.collect.pipeline import run_pipeline, enrich_skills
from app.collect.fetchers.boss import normalize_boss_job
from app.collect.fetchers.job_sites import SITES, normalize_job
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


@pytest.mark.parametrize("source", ["boss", "zhaopin", "liepin"])
@pytest.mark.parametrize("record,detail,valid", [
    ({"description": "任职要求：熟悉 Java、Spring Boot、MySQL"}, {}, True),
    ({"description": "负责后端开发"}, {}, True),
    ({"description": "任职要求：熟悉 Java", "company": "", "salary": "", "location": ""}, {}, True),
    ({"description": "扫码领取优惠券，限时促销，欢迎购买！"}, {}, False),
    ({"description": "Java 培训招生，零基础包就业，加微信咨询"}, {}, False),
    ({}, {}, False),
    ({"company": "示例公司", "salary": "20-30K", "location": "北京", "tags": ["本科", "3-5年"],
      "company_info": "我们熟悉 Java，负责软件开发，拥有优秀团队。"}, {}, False),
    ({"description": "薪资：20-30K\n福利待遇：五险一金、双休、带薪年假"}, {}, False),
    ({"description": "职位描述：暂无，详情面议"}, {}, False),
    ({"description": "欢迎加入我们！五险一金，周末双休，带薪年假"}, {}, False),
    ({}, {"description": "任职要求：熟悉 Java"}, True),
    ({"description": "负责广告投放系统开发，熟悉 Java；提供岗前培训"}, {}, True),
    ({"description": "协助整理实验记录并跟进样品流转"}, {}, True),
    ({"tags": ["Java", "Spring Boot", "MySQL"]}, {}, True),
    ({"description": "福利待遇：五险一金 任职要求：熟悉 Java"}, {}, True),
    ({"description": "公司简介：我们熟悉 Java，负责软件开发。"}, {}, False),
    ({"description": "公司简介：我们提供软件服务。任职要求：熟悉 Java"}, {}, True),
    ({"description": "本文仅供产品宣传，并非招聘信息"}, {}, False),
    ({"description": "扫码加群，加微信咨询"}, {}, False),
    ({"description": "公司简介：我们提供软件服务。\n岗位职责\n熟悉 Java"}, {}, True),
    ({"description": "扫码领取优惠券，参与限时促销，欢迎购买！"}, {}, False),
    ({"description": "Java 开发工程师，五险一金，双休"}, {}, False),
    ({"description": "详情请咨询"}, {}, False),
    ({"description": "招聘中，欢迎投递简历"}, {}, False),
    ({"description": "Java 开发工程师，10-15K，深圳"}, {}, False),
    ({"description": "待遇优厚，工作轻松"}, {}, False),
    ({"description": "岗位长期招聘，投递简历请联系HR"}, {}, False),
    ({"description": "职位描述：公司简介页面开发"}, {}, True),
    ({"description": "岗位职责：公司介绍页的开发"}, {}, True),
    ({"description": "职位描述：公司简介页面改版与维护"}, {}, True),
    ({"description": "熟悉 Java，10-15K，深圳，详情请咨询"}, {}, True),
    ({"description": "负责招聘流程管理，欢迎投递简历"}, {}, True),
    ({"description": "Java 开发工程师，10-15K，深圳，梳理实验记录并跟进样品流转"}, {}, True),
])
def test_cn_jd_validity_before_insert(source, record, detail, valid):
    """真实适配→清洗→入库参数；仅数据库连接使用内存替身。"""
    card = {"url": "/job_detail/test.html" if source == "boss" else "/job/test",
            "title": "Java 开发工程师", **record}
    raw = (normalize_boss_job(card, detail) if source == "boss"
           else normalize_job(SITES[source], card, detail))
    assert raw is not None
    db = FakeDB()
    stats = run_pipeline(db, [raw])
    assert stats["jd_saved"] == int(valid)
    assert len(db.saved) == int(valid)
    if valid:
        assert db.saved[0]["job_title"] == "Java 开发工程师"
        assert db.saved[0]["source"] == source
    else:
        assert stats["groups"] == 0
        assert db.committed == 0


def test_cn_filter_does_not_change_other_sources_or_talent_routing():
    db = FakeDB()
    stats = run_pipeline(db, [
        RawJD(source="boss", job_title="Java 工程师", raw_html=""),
        RawJD(source="linkedin", job_title="Engineer", raw_html=""),
        RawTalent(source="github", raw_text="Python developer"),
    ])
    assert stats == {"saved": 2, "jd_saved": 1, "talent_saved": 1, "groups": 2}
    assert [row["source"] for row in db.saved] == ["linkedin", "github"]


@pytest.mark.parametrize("title,description", [
    ("", "熟悉 Java"),
    ("Java 工程师", "公司简介：\n我们熟悉 Java\n负责软件开发"),
    ("Java 工程师", "Java 工程师"),
    ("Java 工程师", "Java 工程师："),
    ("Java 工程师", "职位描述：---"),
])
def test_cn_missing_job_content_never_reaches_insert(title, description):
    db = FakeDB()
    stats = run_pipeline(db, [RawJD(source="boss", job_title=title, raw_html=description)])
    assert stats["jd_saved"] == 0
    assert db.saved == []


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

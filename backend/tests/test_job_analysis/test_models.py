"""测试数据模型。"""
from app.job_analysis.models import (
    JdRecord, ExtractionResult, SkillEntry, EvolutionInfo,
    MergedJobDefinition, MergedJobSkill, JobChangeLog,
    PipelineStats, CostInfo,
)


def test_jd_record():
    r = JdRecord(
        id=1, source="test", job_title="AI Engineer",
        raw_text="We need an AI engineer", duties="Build AI",
        experience="3 years", quality=0.8, dup_group="g1",
        crawled_at="2026-01-01", status="cleaned",
    )
    assert r.id == 1
    assert r.job_title == "AI Engineer"
    assert r.quality == 0.8


def test_skill_entry_normalize():
    s = SkillEntry(name="  Python  ", confidence=0.9, evidence="test",
                   is_required=True)
    assert s.name == "python"


def test_skill_entry_clamp():
    s = SkillEntry(name="py", confidence=1.5, evidence="test", is_required=True)
    assert s.confidence == 1.0
    s2 = SkillEntry(name="py", confidence=-0.5, evidence="test",
                    is_required=True)
    assert s2.confidence == 0.0


def test_job_name_validation():
    r = ExtractionResult(
        jd_id=1, job_name="急招!高薪!!RAG工程师", core_duties="test",
        required_skills=[SkillEntry(name="py", confidence=0.9,
                                     evidence="test", is_required=True)],
        quality=0.8, collected_at="2026-01-01",
    )
    assert r.job_name == "RAG工程师"  # 去除营销前缀和!


def test_evolution_defaults():
    e = EvolutionInfo()
    assert e.stage == "growth"
    assert e.stage_confidence == 0.5
    assert e.indicators == {}


def test_job_change_log():
    log = JobChangeLog(
        job_id="AI Engineer", change_type="added", object_type="skill",
        skill_name="python", detail={"old": None, "new": {"confidence": 0.9}},
        source=["Boss直聘"], reason="新JD要求", created_at="2026-01-01",
    )
    assert log.skill_name == "python"
    assert log.change_type == "added"


def test_pipeline_stats_defaults():
    stats = PipelineStats()
    assert stats.total == 0
    assert stats.final_job_definitions == 0
    assert stats.cost.total_tokens == 0

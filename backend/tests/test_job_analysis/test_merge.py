"""测试合并层。"""
from app.job_analysis.models import (
    ExtractionResult, EvolutionInfo, SkillEntry,
    MergedJobDefinition, MergedJobSkillDetail, MergedJobSkill,
)
from app.job_analysis.merge import merge_jobs


def make_extraction(
    jd_id=1, job_name="AI Engineer", core_duties="Build AI systems",
    required_skills=None, bonus_skills=None,
    scenarios=None, source="test", quality=0.8,
    collected_at="2026-01-01", is_emerging=False,
    evolution=None, verdict="pass",
):
    return ExtractionResult(
        jd_id=jd_id, job_name=job_name, core_duties=core_duties,
        required_skills=required_skills or [],
        bonus_skills=bonus_skills or [],
        scenarios=scenarios or ["AI"],
        source=source, quality=quality, collected_at=collected_at,
        is_emerging=is_emerging,
        evolution=evolution or EvolutionInfo(
            stage="growth", stage_confidence=0.5),
        verdict=verdict,
    )


def test_single_record():
    r = make_extraction(
        required_skills=[SkillEntry(name="python", confidence=0.9,
                                     evidence="JD: Python", is_required=True)],
        bonus_skills=[SkillEntry(name="docker", confidence=0.6,
                                  evidence="JD: Docker", is_required=False)],
    )
    defs, skills = merge_jobs([r])
    assert len(defs) == 1
    assert defs[0].job_name == "AI Engineer"
    assert defs[0].required_skills == ["python"]
    assert defs[0].bonus_skills == ["docker"]
    assert defs[0].quality == 0.8
    assert defs[0].source_jd_count == 1
    assert len(skills) == 1
    assert len(skills[0].skills) == 2


def test_merge_same_job_name():
    r1 = make_extraction(
        jd_id=1, job_name="AI Engineer",
        required_skills=[SkillEntry(name="python", confidence=0.9,
                                     evidence="JD1: Python", is_required=True)],
        bonus_skills=[SkillEntry(name="docker", confidence=0.6,
                                  evidence="JD1: Docker", is_required=False)],
        quality=0.8,
    )
    r2 = make_extraction(
        jd_id=2, job_name="AI Engineer",
        required_skills=[SkillEntry(name="python", confidence=0.7,
                                     evidence="JD2: Python", is_required=True),
                         SkillEntry(name="langchain", confidence=0.85,
                                     evidence="JD2: LangChain",
                                     is_required=True)],
        bonus_skills=[SkillEntry(name="docker", confidence=0.5,
                                  evidence="JD2: Docker", is_required=False)],
        quality=0.6,
    )
    defs, skills = merge_jobs([r1, r2])
    assert len(defs) == 1
    d = defs[0]
    # skills 并集
    assert set(d.required_skills) == {"python", "langchain"}
    assert set(d.bonus_skills) == {"docker"}
    # source_jd_count
    assert d.source_jd_count == 2
    # 保留 confidence 最高的 evidence
    s = {sk.name: sk for sk in skills[0].skills}
    assert s["python"].confidence == 0.9
    assert "JD1" in s["python"].evidence


def test_merge_case_insensitive():
    r1 = make_extraction(job_name="AI Engineer")
    r2 = make_extraction(job_name="ai engineer")
    defs, _ = merge_jobs([r1, r2])
    assert len(defs) == 1


def test_merge_skip_manual():
    r1 = make_extraction(verdict="pass")
    r2 = make_extraction(verdict="manual")
    defs, _ = merge_jobs([r1, r2])
    assert len(defs) == 1
    assert defs[0].source_jd_count == 1


def test_merge_is_emerging():
    r1 = make_extraction(is_emerging=False)
    r2 = make_extraction(is_emerging=True)
    defs, _ = merge_jobs([r1, r2])
    assert defs[0].is_emerging


def test_merge_sources_union():
    r1 = make_extraction(source="Boss直聘")
    r2 = make_extraction(source="猎聘")
    defs, _ = merge_jobs([r1, r2])
    assert set(defs[0].source) == {"Boss直聘", "猎聘"}

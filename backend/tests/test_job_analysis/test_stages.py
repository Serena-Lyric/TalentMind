"""Stage 模块测试 —— 测试 prompt 构建和响应解析（不依赖 API）。"""
import pytest
from app.job_analysis.models import JdRecord, SkillEntry
from app.job_analysis.stage1_relevance import (
    build_relevance_prompt, parse_relevance_response, RELEVANCE_SCHEMA,
)
from app.job_analysis.stage2_quality import (
    build_quality_prompt, parse_quality_response, QUALITY_SCHEMA,
)
from app.job_analysis.stage3_extract import (
    build_extract_prompt, parse_extraction_response, _build_skill_entries,
    _validate_extraction, EXTRACT_SCHEMA,
)


def make_record(**kwargs):
    defaults = dict(
        id=1, source="test", job_title="AI Engineer",
        raw_text="We need an AI engineer with Python and ML experience",
        duties="Build AI models", experience="3 years", quality=0.8,
        dup_group="", crawled_at="2026-01-01", status="cleaned",
    )
    defaults.update(kwargs)
    return JdRecord(**defaults)


# ── Stage 1 ──

def test_build_relevance_prompt():
    r = make_record()
    prompt = build_relevance_prompt(r)
    assert "AI Engineer" in prompt
    assert "raw_text" in prompt
    assert "TECHNOLOGY" in prompt


def test_relevance_schema():
    assert RELEVANCE_SCHEMA["type"] == "object"
    assert "is_relevant" in RELEVANCE_SCHEMA["required"]


def test_parse_relevance_pass():
    resp = {"is_relevant": True, "confidence": 0.9, "evidence": "AI",
            "reasoning": "Core AI work"}
    result = parse_relevance_response(1, resp, "test-model")
    assert result.verdict == "pass"
    assert result.is_relevant


def test_parse_relevance_reject():
    resp = {"is_relevant": False, "confidence": 0.9, "evidence": "real estate",
            "reasoning": "Not IT"}
    result = parse_relevance_response(1, resp, "test-model")
    assert result.verdict == "reject"


def test_parse_relevance_low_confidence():
    resp = {"is_relevant": True, "confidence": 0.5, "evidence": "...",
            "reasoning": "uncertain"}
    result = parse_relevance_response(1, resp, "test-model")
    assert result.verdict == "manual"


# ── Stage 2 ──

def test_build_quality_prompt():
    r = make_record()
    prompt = build_quality_prompt(r)
    assert "AI Engineer" in prompt
    assert "quality" in prompt


def test_quality_schema():
    assert QUALITY_SCHEMA["type"] == "object"
    assert "quality" in QUALITY_SCHEMA["required"]


def test_parse_quality_pass():
    resp = {
        "quality": 0.8,
        "dimensions": {"completeness": 0.8, "clarity": 0.8, "tech_depth": 0.8,
                        "freshness": 0.8, "originality": 0.8},
        "weak_points": "none",
    }
    result = parse_quality_response(1, resp, "test-model")
    assert result.verdict == "pass"
    assert result.quality == 0.8


def test_parse_quality_reject():
    resp = {
        "quality": 0.3,
        "dimensions": {"completeness": 0.3, "clarity": 0.3, "tech_depth": 0.3,
                        "freshness": 0.3, "originality": 0.3},
        "weak_points": "too vague",
    }
    result = parse_quality_response(1, resp, "test-model")
    assert result.verdict == "reject"


# ── Stage 3 ──

def test_build_extract_prompt():
    r = make_record()
    prompt = build_extract_prompt(r)
    assert "AI Engineer" in prompt
    assert "job_name" in prompt


def test_extract_schema():
    assert EXTRACT_SCHEMA["type"] == "object"
    assert "job_name" in EXTRACT_SCHEMA["required"]


def test_build_skill_entries_no_dict():
    raw = [{"name": "python", "confidence": 0.9, "evidence": "JD: Python",
            "is_required": True}]
    req, bonus, unknown = _build_skill_entries(raw)
    assert len(req) == 1
    assert req[0].name == "python"
    assert len(bonus) == 0


def test_build_skill_entries_mixed():
    """D31：词表外技能进 unknown，不进正式技能。"""
    raw = [
        {"name": "python", "confidence": 0.9, "evidence": "JD: Python",
         "is_required": True},
        {"name": "cobol", "confidence": 0.8, "evidence": "JD: COBOL",
         "is_required": False},
    ]
    req, bonus, unknown = _build_skill_entries(raw)
    assert len(req) == 1
    assert req[0].name == "python"
    assert len(bonus) == 0
    assert "cobol" in unknown


def test_build_skill_entries_alias_mapped():
    """D31：别名（如 k8s / springboot）应映射到 canonical。"""
    raw = [
        {"name": "k8s", "confidence": 0.9, "evidence": "JD: K8s",
         "is_required": True},
        {"name": "springboot", "confidence": 0.8, "evidence": "JD: Spring Boot",
         "is_required": True},
    ]
    req, bonus, unknown = _build_skill_entries(raw)
    assert len(req) == 2
    names = {s.name for s in req}
    assert names == {"kubernetes", "spring boot"}
    assert len(unknown) == 0


def test_parse_extraction_response():
    resp = {
        "job_name": "AI Engineer",
        "core_duties": "Build AI systems",
        "skills": [{"name": "python", "confidence": 0.9,
                     "evidence": "JD: Python required", "is_required": True}],
        "scenarios": ["Enterprise AI"],
        "is_emerging": True,
        "evolution": {"stage": "growth", "stage_confidence": 0.6,
                       "indicators": {"jd_count": 1}},
    }
    result = parse_extraction_response(
        1, resp, 0.8, "2026-01-01", "Boss直聘", "test-model",
    )
    assert result.job_name == "AI Engineer"
    assert result.verdict == "pass"
    assert result.source == "Boss直聘"
    assert result.is_emerging


def test_validate_extraction_empty_job_name():
    from app.job_analysis.stage3_extract import ExtractionResult
    r = ExtractionResult(
        jd_id=1, job_name="", core_duties="duties",
        required_skills=[SkillEntry(name="py", confidence=0.9,
                                     evidence="test", is_required=True)],
        quality=0.8, collected_at="2026-01-01",
    )
    errors = _validate_extraction(r)
    assert any("job_name" in e for e in errors)


def test_validate_extraction_no_skills():
    from app.job_analysis.stage3_extract import ExtractionResult
    r = ExtractionResult(
        jd_id=1, job_name="Engineer", core_duties="duties",
        quality=0.8, collected_at="2026-01-01",
    )
    errors = _validate_extraction(r)
    assert any("no skills" in e for e in errors)

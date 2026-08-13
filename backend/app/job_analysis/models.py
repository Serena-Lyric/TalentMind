"""JD Filter 数据模型 —— Pydantic v2，所有管道阶段统一类型。"""
from __future__ import annotations
from pydantic import BaseModel, Field, field_validator
from typing import Optional
import re


# ── 输入 ──

class JdRecord(BaseModel):
    id: int
    source: str
    job_title: str
    raw_text: str
    duties: str
    experience: str
    quality: float
    dup_group: str
    crawled_at: str
    status: str


# ── 被拒记录 ──

class RejectedItem(BaseModel):
    jd_id: int
    rule_id: str
    stage: str = "rules"
    detail: str = ""
    kept_jd_id: Optional[int] = None


# ── 模型1 输出 ──

class RelevanceResult(BaseModel):
    jd_id: int
    is_relevant: bool
    confidence: float
    evidence: str
    reasoning: str
    verdict: str
    model: str = ""


# ── 模型2 输出 ──

class QualityDimensions(BaseModel):
    completeness: float
    clarity: float
    tech_depth: float
    freshness: float
    originality: float


class QualityFlags(BaseModel):
    stale_tech: Optional[str] = None
    copied_pattern: Optional[str] = None
    skill_inflation: Optional[str] = None

    @field_validator("stale_tech", "copied_pattern", "skill_inflation", mode="before")
    @classmethod
    def coerce_to_str(cls, v):
        if v is None:
            return None
        if isinstance(v, bool):
            return str(v) if v else None
        if isinstance(v, str):
            return v if v.strip() else None
        return str(v) if v else None


class QualityResult(BaseModel):
    jd_id: int
    quality: float
    dimensions: QualityDimensions
    flags: Optional[QualityFlags] = None
    weak_points: str = ""
    verdict: str
    model: str = ""


# ── 模型3 输出 ──

class SkillEntry(BaseModel):
    name: str
    confidence: float
    evidence: str
    is_required: bool

    @field_validator("confidence")
    @classmethod
    def clamp_confidence(cls, v: float) -> float:
        return max(0.0, min(1.0, v))

    @field_validator("name")
    @classmethod
    def normalize_name(cls, v: str) -> str:
        return v.strip().lower()


class EvolutionInfo(BaseModel):
    stage: str = "growth"
    stage_confidence: float = 0.5
    indicators: dict = Field(default_factory=dict)


class ExtractionResult(BaseModel):
    jd_id: int
    job_name: str
    core_duties: str
    required_skills: list[SkillEntry] = Field(default_factory=list)
    bonus_skills: list[SkillEntry] = Field(default_factory=list)
    scenarios: list[str] = Field(default_factory=list)
    source: str = ""
    quality: float = 0.0
    collected_at: str = ""
    is_emerging: bool = False
    evolution: EvolutionInfo = Field(default_factory=lambda: EvolutionInfo(
        stage="growth", stage_confidence=0.5, indicators={}
    ))
    unknown_skills: list[str] = Field(default_factory=list)
    verdict: str = "pass"
    model: str = ""

    @field_validator("job_name")
    @classmethod
    def validate_job_name(cls, v: str) -> str:
        v = v.strip()
        # 去除所有感叹号（中英文）
        v = re.sub(r"[!！]+", "", v)
        # 去除营销关键词
        v = re.sub(r"(急招|高薪|诚聘|急聘|高薪诚聘|五险一金|双休)", "", v)
        return v.strip()


# ── 合并层输出 ──

class MergedJobSkill(BaseModel):
    skill_id: str
    name: str
    weight: float = 0.0
    confidence: float = 0.0
    evidence: str = ""
    evidence_jd_count: int = 1
    is_required: bool = False


class MergedJobDefinition(BaseModel):
    job_name: str
    core_duties: str
    required_skills: list[str] = Field(default_factory=list)
    bonus_skills: list[str] = Field(default_factory=list)
    scenarios: list[str] = Field(default_factory=list)
    source: list[str] = Field(default_factory=list)
    quality: float = 0.0
    is_emerging: bool = False
    evolution: EvolutionInfo = Field(default_factory=EvolutionInfo)
    first_seen: str = ""
    collected_at: str = ""
    updated_at: str = ""
    source_jd_count: int = 0


class MergedJobSkillDetail(BaseModel):
    job_name: str
    skills: list[MergedJobSkill] = Field(default_factory=list)


# ── 对比层输出 ──

class JobChangeLog(BaseModel):
    job_id: str
    change_type: str
    object_type: str = "skill"
    skill_name: str = ""
    detail: dict = Field(default_factory=dict)
    source: list[str] = Field(default_factory=list)
    reason: str = ""
    created_at: str = ""


# ── 人工复核 ──

class ManualReviewItem(BaseModel):
    jd_id: int
    stage: str
    reason: str
    model_output: dict = Field(default_factory=dict)
    review_status: str = "pending"
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[str] = None
    modified_fields: Optional[dict] = None


# ── 统计报告 ──

class CostInfo(BaseModel):
    total_tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    estimated_cost_usd: float = 0.0
    api_calls: int = 0


class PipelineStats(BaseModel):
    total: int = 0
    rules_rejected: int = 0
    stage1_passed: int = 0
    stage1_rejected: int = 0
    stage1_manual: int = 0
    stage2_passed: int = 0
    stage2_rejected: int = 0
    stage2_manual: int = 0
    stage3_passed: int = 0
    stage3_manual: int = 0
    final_job_definitions: int = 0
    change_logs: int = 0
    accuracy: Optional[float] = None
    cost: CostInfo = Field(default_factory=CostInfo)

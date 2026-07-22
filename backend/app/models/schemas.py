# backend/app/models/schemas.py  【契约冻结:加字段自由,改/删须全队通知】
from pydantic import BaseModel
from typing import Optional

class SkillItem(BaseModel):
    skill_id: int
    name: str
    weight: float = 0.0
    confidence: Optional[float] = None   # 无数据支撑时省略
    evidence: Optional[str] = None

class JobSkillOut(BaseModel):
    job_name: str
    level: str
    skills: list[SkillItem]
    duties: str = ""

class EmergingJobOut(BaseModel):
    job_name: str
    definition: str
    core_skills: list[str]
    evolution: dict           # {stage: str, growth_rate?: float}

class ResumeOut(BaseModel):
    resume_id: int
    raw_format: str
    skills: list[SkillItem]
    experience: list[dict]

class MatchResult(BaseModel):
    target_job: str
    score: int
    matched: list[str]
    missing: list[str]
    path: list[dict] = []     # 岗位路径推荐;不含"预计X个月"等无依据数字

class GraphNode(BaseModel):
    id: str
    label: str
    type: str                 # Domain/JobFamily/Job/Skill

class GraphEdge(BaseModel):
    source: str
    target: str
    rel: str                  # REQUIRES/RELATED_TO/BELONGS_TO/PART_OF
    weight: Optional[float] = None

class GraphView(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]

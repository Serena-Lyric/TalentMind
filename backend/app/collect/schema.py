from dataclasses import dataclass, field


@dataclass
class RawJD:
    source: str
    job_title: str
    raw_html: str              # CSV 中为 description 原文
    duties: str = ""
    experience: str = ""
    job_id: str = ""           # 新增：用于 join job_skills，不写入 jd_pool
    raw_skills: list[str] | None = None  # 新增：技能名列表


@dataclass
class RawTalent:
    source: str
    raw_text: str
    identity_hint: str = ""
    skills_hint: list[str] | None = None
    experience_hint: str = ""

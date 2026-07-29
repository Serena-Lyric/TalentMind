from datetime import datetime, timezone
from app.collect.schema import RawTalent


def clean_talent(raw: RawTalent) -> dict:
    """人才侧清洗：仅做通用文本规整，不做 JD 式职责段落提取。

    _extract_duties/_extract_experience (cleaner.py) 是岗位专用逻辑，
    识别 "Responsibilities:" 等岗位JD段落标题，不适用于简历/GitHub文本。
    """
    return {
        "source": raw.source,
        "identity_hint": raw.identity_hint.strip(),
        "raw_text": (raw.raw_text or "").strip(),
        "skills_hint": raw.skills_hint or [],
        "experience_hint": raw.experience_hint.strip(),
        "crawled_at": datetime.now(timezone.utc),
        "status": "cleaned",
    }

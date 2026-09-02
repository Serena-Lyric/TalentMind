"""学习路径 API：只接受简历推荐结果传入的目标岗位 ID。"""
from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

from fastapi import APIRouter, Body
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.db.mysql import SessionLocal
from app.matching.canonical import to_canonical
from app.response import BizError, ok

router = APIRouter()


class LearningPathRequest(BaseModel):
    job_id: int
    resume_skills: list[str] = Field(default_factory=list)


def _list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return []
    return _list(parsed)


def _job(db, job_id: int):
    return db.execute(text("""
        SELECT id, job_name, name_en, job_name_zh, category, required_skills, bonus_skills, source, evolution
        FROM job_definition WHERE id=:id
    """), {"id": job_id}).mappings().first()


def _skill_item(name: str, category: str, priority: str, reason: str, status: str = "not_started") -> dict:
    return {"name": name, "category": category, "priority": priority, "reason": reason, "status": status}


def _category(name: str) -> str:
    from app.matching.skill_extractor import get_skill_category
    return get_skill_category(name)


def _canonical_skills(values: list[str]) -> dict[str, str]:
    return {str(value): to_canonical(str(value)) for value in values if str(value).strip()}


@router.get("/learning/jobs")
def learning_jobs():
    db = SessionLocal()
    try:
        rows = db.execute(text("SELECT id, job_name, name_en, job_name_zh, category, source FROM job_definition ORDER BY job_name")).mappings().all()
        return ok([{"value": str(row["id"]), "label": row.get("job_name_zh") or row["job_name"], "name_en": row.get("name_en") or row["job_name"], "category": row.get("category") or "", "source": _list(row["source"])} for row in rows])
    finally:
        db.close()


@router.get("/learning/job-skills/{job_id}")
def learning_job_skills(job_id: int):
    db = SessionLocal()
    try:
        row = _job(db, job_id)
        if not row:
            raise BizError(4041, "岗位不存在")
        required = _list(row["required_skills"])
        bonus = _list(row["bonus_skills"])
        return ok({
            "job_id": str(row["id"]), "job_title": row.get("job_name_zh") or row["job_name"], "job_name_en": row.get("name_en") or row["job_name"], "category": row.get("category") or "",
            "core_skills": [_skill_item(name, _category(name), "high", "岗位必备技能") for name in required],
            "bonus_skills": [_skill_item(name, _category(name), "medium", "岗位加分技能") for name in bonus],
        })
    finally:
        db.close()


@router.post("/learning/generate-path")
def generate_learning_path(payload: LearningPathRequest = Body(...)):
    db = SessionLocal()
    try:
        row = _job(db, payload.job_id)
        if not row:
            raise BizError(4041, "岗位不存在")
        required = _list(row["required_skills"])
        bonus = _list(row["bonus_skills"])
    finally:
        db.close()

    resume_skills = {to_canonical(skill) for skill in payload.resume_skills if str(skill).strip()}
    required_map = _canonical_skills(required)
    bonus_map = _canonical_skills(bonus)
    mastered_required = [name for name, canonical in required_map.items() if canonical in resume_skills]
    mastered_bonus = [name for name, canonical in bonus_map.items() if canonical in resume_skills]
    missing_required = [name for name, canonical in required_map.items() if canonical not in resume_skills]
    missing_bonus = [name for name, canonical in bonus_map.items() if canonical not in resume_skills]
    missing = [_skill_item(name, _category(name), "high", "岗位必备技能缺口") for name in missing_required] + [_skill_item(name, _category(name), "medium", "岗位加分技能缺口") for name in missing_bonus]
    grouped: dict[str, list[dict]] = defaultdict(list)
    for item in missing:
        grouped[item["category"]].append(item)
    stages = [{"stage": index, "title": "基础补齐" if index == 1 else "岗位核心" if index == 2 else "进阶加分", "category": category, "skills": items} for index, (category, items) in enumerate(grouped.items(), start=1)]
    mastered = mastered_required + mastered_bonus
    return ok({
        "job_id": str(row["id"]), "job_title": row.get("job_name_zh") or row["job_name"], "job_name_en": row.get("name_en") or row["job_name"], "category": row.get("category") or "",
        "mastered_skills": mastered, "missing_skills": missing,
        "core_skills": [_skill_item(skill, _category(skill), "high", "岗位必备技能", "completed" if required_map[skill] in resume_skills else "not_started") for skill in required],
        "bonus_skills": [_skill_item(skill, _category(skill), "medium", "岗位加分技能", "completed" if bonus_map[skill] in resume_skills else "not_started") for skill in bonus],
        "stages": stages, "source": "job_definition.required_skills + bonus_skills",
    })

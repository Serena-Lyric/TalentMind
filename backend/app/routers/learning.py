# -*- coding: utf-8 -*-
"""学习路径 API：只接受简历推荐结果传入的目标岗位 ID。

2026-09-04 升级：路径阶段按"学习优先级"（必备缺口 → 加分缺口）而非技能类别硬编；
每条缺口技能给出数据可溯源的针对性改进建议（类别/别名/JD 证据/简历同类别衔接）。
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.db.mysql import SessionLocal
from app.matching.canonical import to_canonical
from app.response import BizError, ok

router = APIRouter()

_SKILL_SEED_PATH = Path(__file__).resolve().parents[1] / "skills" / "skill_dict_seed.json"
_seed_cache: dict[str, dict] | None = None
_EVIDENCE_MAX = 110


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
        SELECT id, job_name, name_en, job_name_zh, category, required_skills, bonus_skills,
               source, evolution, m2_job_id
        FROM job_definition WHERE id=:id
    """), {"id": job_id}).mappings().first()


def _category(name: str) -> str:
    from app.matching.skill_extractor import get_skill_category
    return get_skill_category(name)


def _seed() -> dict[str, dict]:
    """skill_dict seed（canonical -> item）。懒加载一次。"""
    global _seed_cache
    if _seed_cache is None:
        items = json.loads(_SKILL_SEED_PATH.read_text(encoding="utf-8"))
        _seed_cache = {str(item.get("canonical", "")).strip().lower(): item for item in items}
    return _seed_cache


def _skill_meta(name: str) -> tuple[str, list[str]]:
    """返回 (category, aliases)。优先 skill_dict seed，其次关键词抽取类别。"""
    lowered = str(name or "").strip().lower()
    seed_item = _seed().get(lowered) if lowered else None
    if seed_item:
        cat = str(seed_item.get("category") or "其他")
        aliases = [str(a) for a in (seed_item.get("aliases") or []) if str(a).strip()]
        return cat, aliases
    return _category(lowered), []


def _canonical_skills(values: list[str]) -> dict[str, str]:
    return {str(value): to_canonical(str(value)) for value in values if str(value).strip()}


def _evidence_map(db, row: Any) -> dict[str, str]:
    """job_skill.skills[].evidence（JD 原文证据）按 canonical_name 建索引。"""
    m2 = (row.get("m2_job_id") if isinstance(row, dict) else getattr(row, "m2_job_id", None)) or ""
    if not m2:
        return {}
    row_sk = db.execute(text(
        "SELECT skills FROM job_skill WHERE m2_job_id=:m LIMIT 1"
    ), {"m": m2}).mappings().first()
    if not row_sk or not row_sk["skills"]:
        return {}
    try:
        items = json.loads(row_sk["skills"])
    except (TypeError, json.JSONDecodeError):
        return {}
    out: dict[str, str] = {}
    for item in items:
        canonical = str(item.get("canonical_name") or "").strip().lower()
        evidence = str(item.get("evidence") or "").strip()
        if canonical and evidence:
            out.setdefault(canonical, evidence)
    return out


def _gap_item(
    name: str,
    canonical: str,
    priority: str,
    reason: str,
    resume_by_category: dict[str, set[str]],
    evidence_map: dict[str, str],
) -> dict:
    """构造一条缺口技能及其针对性建议（全部字段有真实数据出处，不编造）。"""
    category, aliases = _skill_meta(name)
    display = aliases[0] if aliases else name
    bridge: list[str] = []
    if category and category != "其他":
        bridge = sorted(resume_by_category.get(category, set()) - {canonical})
    evidence = (evidence_map.get(canonical) or "").strip()
    priority_label = "必备" if priority == "high" else "加分"

    text = f"“{display}”是该岗位的{priority_label}技能，当前简历未命中"
    if not aliases and category == "其他" and not evidence:
        text += "；技能词典未收录该写法，建议按岗位职责描述与真实项目实践补足"
    if bridge:
        text += f"；你可基于已掌握的同类技能（{'、'.join(bridge[:3])}）顺延补齐"
    if evidence:
        shown = evidence if len(evidence) <= _EVIDENCE_MAX else evidence[:_EVIDENCE_MAX] + "…"
        text += f"；岗位依据：{shown}"
    text += "。"

    return {
        "name": name,
        "display_name": display,
        "category": category,
        "aliases": aliases,
        "priority": priority,
        "reason": reason,
        "evidence": evidence,
        "bridge_skills": bridge,
        "suggestion": text,
    }

_BASE_CATEGORIES = {"编程语言", "数据库"}
_CORE_CATEGORIES = {"后端框架", "前端技术", "大数据/云", "DevOps/运维", "软件工程"}
_BASE_TOOLS = {"linux", "shell", "bash", "git", "powershell", "sql", "vim"}


def _phase_for(item: dict) -> str:
    """缺口技能 -> 学习阶段（启发式分层；加分项恒为最后阶段）。"""
    if item.get("priority") != "high":
        return "bonus"
    category = str(item.get("category") or "其他")
    name = str(item.get("name") or "").strip().lower()
    if category in _BASE_CATEGORIES or name in _BASE_TOOLS:
        return "base"
    if category in _CORE_CATEGORIES:
        return "core"
    return "advanced"


def build_learning_path(
    *,
    job_id: str,
    job_title: str,
    job_name_en: str,
    category: str,
    required: list[str],
    bonus: list[str],
    resume_skills: list[str],
    evidence_map: dict[str, str] | None = None,
) -> dict:
    """纯函数：由岗位必备/加分技能 + 简历技能 + JD 证据生成学习路径。"""
    evidence_map = evidence_map or {}
    resume_set = {to_canonical(skill) for skill in resume_skills if str(skill).strip()}
    required_map = _canonical_skills(required)
    bonus_map = _canonical_skills(bonus)

    # 简历技能按类别归档（用于"同类别衔接"建议）
    resume_by_category: dict[str, set[str]] = defaultdict(set)
    for raw in resume_skills:
        raw = str(raw).strip()
        if not raw:
            continue
        canonical = to_canonical(raw)
        cat, _ = _skill_meta(canonical)
        resume_by_category[cat].add(canonical)

    mastered_required = [n for n, c in required_map.items() if c in resume_set]
    missing_required = [n for n, c in required_map.items() if c not in resume_set]
    mastered_bonus = [n for n, c in bonus_map.items() if c in resume_set]
    missing_bonus = [n for n, c in bonus_map.items() if c not in resume_set]

    def gap_item(name: str, canonical: str, priority: str, reason: str) -> dict:
        return _gap_item(name, canonical, priority, reason, resume_by_category, evidence_map)

    required_gaps = [
        gap_item(n, required_map[n], "high", "岗位必备技能缺口")
        for n in missing_required
    ]
    bonus_gaps = [
        gap_item(n, bonus_map[n], "medium", "岗位加分技能缺口")
        for n in missing_bonus
    ]

    # 2026-09-04 方案 A：按技能"学习性质"把缺口排成分层路径（基础->核心->专项->加分），不再把必备/加分各堆成一堆。
    # 说明：推荐顺序为启发式分层，非技能依赖图谱（图谱暂无 Skill-Skill 依赖边）。
    phase_meta = [
        ("base", "基础与工具", "先掌握通用底座（语言/数据库/系统工具），具备独立动手基础"),
        ("core", "核心框架与平台", "学习该岗位的主干框架、中间件与平台能力"),
        ("advanced", "岗位专项", "聚焦本岗位特有的领域/技术方向"),
        ("bonus", "加分拓展", "必备能力达标后按需拓展的加分项"),
    ]
    buckets: dict[str, list[dict]] = {"base": [], "core": [], "advanced": [], "bonus": []}
    for item in required_gaps:
        buckets[_phase_for(item)].append(item)
    for item in bonus_gaps:
        buckets["bonus"].append(item)
    stages: list[dict] = []
    for phase, title, description in phase_meta:
        items = buckets[phase]
        if not items:
            continue
        stages.append({
            "stage": len(stages) + 1,
            "phase": phase,
            "title": title,
            "description": description,
            "skills": items,
        })

    missing = required_gaps + bonus_gaps
    at_standard = not missing
    mastered = mastered_required + mastered_bonus
    return {
        "job_id": str(job_id),
        "job_title": job_title,
        "job_name_en": job_name_en,
        "category": category,
        "mastered_skills": mastered,
        "missing_skills": missing,
        "core_skills": [
            {"name": s, "category": _skill_meta(s)[0], "priority": "high", "reason": "岗位必备技能",
             "status": "completed" if required_map[s] in resume_set else "not_started"}
            for s in required
        ],
        "bonus_skills": [
            {"name": s, "category": _skill_meta(s)[0], "priority": "medium", "reason": "岗位加分技能",
             "status": "completed" if bonus_map[s] in resume_set else "not_started"}
            for s in bonus
        ],
        "stages": stages,
        "overview": {
            "mastered_required": len(mastered_required),
            "mastered_bonus": len(mastered_bonus),
            "missing_required": len(missing_required),
            "missing_bonus": len(missing_bonus),
            "at_standard": at_standard,
        },
        "source": "job_definition.required_skills + bonus_skills + job_skill.evidence",
    }


@router.get("/learning/jobs")
def learning_jobs():
    db = SessionLocal()
    try:
        rows = db.execute(text(
            "SELECT id, job_name, name_en, job_name_zh, category, source FROM job_definition ORDER BY job_name"
        )).mappings().all()
        return ok([{
            "value": str(row["id"]),
            "label": row.get("job_name_zh") or row["job_name"],
            "name_en": row.get("name_en") or row["job_name"],
            "category": row.get("category") or "",
            "source": _list(row["source"]),
        } for row in rows])
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
            "job_id": str(row["id"]),
            "job_title": row.get("job_name_zh") or row["job_name"],
            "job_name_en": row.get("name_en") or row["job_name"],
            "category": row.get("category") or "",
            "core_skills": [{"name": name, "category": _skill_meta(name)[0], "priority": "high",
                             "reason": "岗位必备技能", "aliases": _skill_meta(name)[1]} for name in required],
            "bonus_skills": [{"name": name, "category": _skill_meta(name)[0], "priority": "medium",
                              "reason": "岗位加分技能", "aliases": _skill_meta(name)[1]} for name in bonus],
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
        evidence_map = _evidence_map(db, row)
    finally:
        db.close()

    data = build_learning_path(
        job_id=str(row["id"]),
        job_title=row.get("job_name_zh") or row["job_name"],
        job_name_en=row.get("name_en") or row["job_name"],
        category=row.get("category") or "",
        required=required,
        bonus=bonus,
        resume_skills=payload.resume_skills,
        evidence_map=evidence_map,
    )
    return ok(data)
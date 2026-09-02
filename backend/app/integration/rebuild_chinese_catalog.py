"""Rebuild the structured job catalog from Chinese-platform JD rows.

M2's English-platform output has been archived outside the database. This catalog is a
small deterministic bridge for the current system: it only derives job_definition and
job_skill from jd_pool rows whose source is boss, zhaopin, or liepin.
"""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from sqlalchemy import text

from app.db.mysql import SessionLocal
from app.matching.canonical import to_canonical
from app.matching.skill_extractor import extract_skills

CHINESE_SOURCES = ("boss", "zhaopin", "liepin")
SEED_PATH = Path(__file__).resolve().parents[1] / "skills" / "skill_dict_seed.json"


def _canonical_set() -> set[str]:
    data = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    return {str(item["canonical"]).lower() for item in data}


def normalize_title(value: str) -> str:
    """Collapse whitespace without altering Chinese or technical title punctuation."""
    return re.sub(r"\s+", " ", (value or "").strip())


def _date_text(value: Any) -> str | None:
    if not value:
        return None
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return str(value)


def _skills_for_row(row: dict[str, Any], valid_skills: set[str]) -> list[str]:
    content = " ".join(str(row.get(key) or "") for key in ("job_title", "raw_text", "duties"))
    result: list[str] = []
    for value in extract_skills(content):
        canonical = to_canonical(value)
        if canonical in valid_skills and canonical not in result:
            result.append(canonical)
    return result


def build_catalog(rows: Iterable[dict[str, Any]], valid_skills: set[str] | None = None) -> list[dict[str, Any]]:
    """Aggregate Chinese-platform JD rows into deterministic job definitions."""
    valid_skills = valid_skills or _canonical_set()
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        title = normalize_title(str(row.get("job_title") or ""))
        if title:
            grouped[title].append(dict(row))

    catalog: list[dict[str, Any]] = []
    for title in sorted(grouped):
        items = grouped[title]
        skill_counts: Counter[str] = Counter()
        skill_evidence: dict[str, list[str]] = defaultdict(list)
        sources = sorted({str(row.get("source") or "") for row in items if row.get("source")})
        duties = [str(row.get("duties") or "").strip() for row in items if str(row.get("duties") or "").strip()]
        raw_texts = [str(row.get("raw_text") or "").strip() for row in items if str(row.get("raw_text") or "").strip()]
        for row in items:
            skills = _skills_for_row(row, valid_skills)
            for skill in skills:
                skill_counts[skill] += 1
                skill_evidence[skill].append(str(row.get("id")))
        ranked = [skill for skill, _ in skill_counts.most_common(20)]
        required_count = max(1, (len(ranked) + 1) // 2) if ranked else 0
        required = ranked[:required_count]
        bonus = ranked[required_count:]
        dates = [row.get("crawled_at") for row in items if row.get("crawled_at")]
        quality_values = [float(row.get("quality") or 0) for row in items]
        catalog.append({
            "job_name": title,
            "core_duties": max(duties or raw_texts or [""], key=len)[:4000],
            "required_skills": required,
            "bonus_skills": bonus,
            "scenarios": [],
            "source": sources,
            "quality": round(sum(quality_values) / len(quality_values), 4) if quality_values else 0,
            "is_emerging": False,
            "evolution": {},
            "first_seen": _date_text(min(dates)) if dates else None,
            "collected_at": _date_text(max(dates)) if dates else None,
            "updated_at": _date_text(max(dates)) if dates else None,
            "_row_count": len(items),
            "_skill_evidence": {skill: skill_evidence[skill] for skill in ranked},
        })
    return catalog


def rebuild_catalog(session=None) -> dict[str, int]:
    db = session or SessionLocal()
    try:
        rows = db.execute(text("""
            SELECT id, source, job_title, raw_text, duties, experience, quality, crawled_at
            FROM jd_pool WHERE source IN ('boss', 'zhaopin', 'liepin') ORDER BY id
        """)).mappings().all()
        catalog = build_catalog(rows)

        db.execute(text("DELETE FROM job_change_log"))
        db.execute(text("DELETE FROM job_skill"))
        db.execute(text("DELETE FROM job_definition"))
        inserted_defs = 0
        inserted_skills = 0
        skill_ids = {
            row["canonical"]: row["id"]
            for row in db.execute(text("SELECT id, canonical FROM skill_dict")).mappings().all()
        }
        for item in catalog:
            db.execute(text("""
                INSERT INTO job_definition
                (job_name, core_duties, required_skills, bonus_skills, scenarios, source,
                 quality, is_emerging, evolution, first_seen, collected_at, updated_at)
                VALUES (:job_name, :core_duties, :required_skills, :bonus_skills, :scenarios, :source,
                        :quality, :is_emerging, :evolution, :first_seen, :collected_at, :updated_at)
            """), {
                "job_name": item["job_name"],
                "core_duties": item["core_duties"],
                "required_skills": json.dumps(item["required_skills"], ensure_ascii=False),
                "bonus_skills": json.dumps(item["bonus_skills"], ensure_ascii=False),
                "scenarios": "[]",
                "source": json.dumps(item["source"], ensure_ascii=False),
                "quality": item["quality"],
                "is_emerging": 0,
                "evolution": "{}",
                "first_seen": item["first_seen"],
                "collected_at": item["collected_at"],
                "updated_at": item["updated_at"],
            })
            job_id = db.execute(text("SELECT LAST_INSERT_ID()")).scalar()
            inserted_defs += 1
            entries = []
            for skill in item["required_skills"]:
                entries.append({
                    "skill_id": skill_ids.get(skill), "name": skill, "weight": 1.0,
                    "confidence": round(len(item["_skill_evidence"][skill]) / item["_row_count"], 4),
                    "evidence": f"中文平台 JD 聚合命中 {len(item['_skill_evidence'][skill])} 条",
                    "is_required": True,
                })
            for skill in item["bonus_skills"]:
                entries.append({
                    "skill_id": skill_ids.get(skill), "name": skill, "weight": 0.6,
                    "confidence": round(len(item["_skill_evidence"][skill]) / item["_row_count"], 4),
                    "evidence": f"中文平台 JD 聚合命中 {len(item['_skill_evidence'][skill])} 条",
                    "is_required": False,
                })
            db.execute(text("""
                INSERT INTO job_skill (jd_id, job_name, skills, duties, extracted_at)
                VALUES (:jd_id, :job_name, :skills, :duties, :extracted_at)
            """), {
                "jd_id": job_id,
                "job_name": item["job_name"],
                "skills": json.dumps(entries, ensure_ascii=False),
                "duties": item["core_duties"],
                "extracted_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            })
            inserted_skills += 1
        db.commit()
        return {"source_rows": len(rows), "job_definition": inserted_defs, "job_skill": inserted_skills}
    except Exception:
        db.rollback()
        raise
    finally:
        if session is None:
            db.close()


if __name__ == "__main__":
    print(json.dumps(rebuild_catalog(), ensure_ascii=False, indent=2))
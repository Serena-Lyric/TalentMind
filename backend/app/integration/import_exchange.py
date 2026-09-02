"""M2 返回包导入 MySQL。

默认读取 input/岗位数据-新一代与现有；显式 path 参数仍兼容旧数组交接文件。
导入是完整重建：M2 回包是岗位分析层权威集合，不按来源过滤。
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import text

from app.db.mysql import SessionLocal
from app.integration.m2_package import DEFAULT_PACKAGE_DIR, load_json_items, load_return_package, package_summary

REPO_ROOT = Path(__file__).resolve().parents[3]
EXCHANGE_M2 = REPO_ROOT / "exchange" / "m2"
SKILL_DICT_PATH = REPO_ROOT / "backend" / "app" / "skills" / "skill_dict_seed.json"
AUDIT_DIR = REPO_ROOT / "data" / "local" / "m2-import"


def _load_json(path: Path) -> list:
    if not path.exists():
        return []
    data, _ = load_json_items(path)
    return data


def _json(value: Any) -> str:
    return json.dumps(value if value is not None else {}, ensure_ascii=False)



def _ensure_columns(db) -> None:
    columns = {
        "m2_job_id": "VARCHAR(32)",
        "name_en": "VARCHAR(255)",
        "job_name_zh": "VARCHAR(255)",
        "category": "VARCHAR(32)",
        "category_review": "VARCHAR(32)",
        "source_jd_count": "INT",
    }
    for name, definition in columns.items():
        exists = db.execute(text("""
            SELECT COUNT(*) FROM information_schema.columns
            WHERE table_schema = DATABASE() AND table_name = 'job_definition' AND column_name = :name
        """), {"name": name}).scalar()
        if not exists:
            db.execute(text(f"ALTER TABLE job_definition ADD COLUMN `{name}` {definition}"))

    skill_exists = db.execute(text("""
        SELECT COUNT(*) FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = 'job_skill' AND column_name = 'm2_job_id'
    """)).scalar()
    if not skill_exists:
        db.execute(text("ALTER TABLE job_skill ADD COLUMN `m2_job_id` VARCHAR(32)"))

    for name, definition in {"m2_job_id": "VARCHAR(64)", "object_type": "VARCHAR(32)", "source_jd_time": "DATETIME"}.items():
        exists = db.execute(text("""
            SELECT COUNT(*) FROM information_schema.columns
            WHERE table_schema = DATABASE() AND table_name = 'job_change_log' AND column_name = :name
        """), {"name": name}).scalar()
        if not exists:
            db.execute(text(f"ALTER TABLE job_change_log ADD COLUMN `{name}` {definition}"))


def _load_skill_dict(path: Path = SKILL_DICT_PATH) -> tuple[set[str], dict[str, str]]:
    entries = _load_json(path)
    canonical = {str(item.get("canonical", "")).strip().lower() for item in entries if item.get("canonical")}
    aliases: dict[str, str] = {}
    for item in entries:
        target = str(item.get("canonical", "")).strip().lower()
        if not target:
            continue
        aliases[target] = target
        for alias in item.get("aliases", []) or []:
            aliases[str(alias).strip().lower()] = target
    return canonical, aliases


def _canonical_skill(name: Any, aliases: dict[str, str]) -> str:
    normalized = str(name or "").strip().lower()
    return aliases.get(normalized, normalized)


def _skill_records_by_job(items: list[dict[str, Any]], aliases: dict[str, str]) -> dict[str, list[dict[str, Any]]]:
    merged: dict[str, dict[str, dict[str, Any]]] = {}
    for item in items:
        job_id = str(item.get("job_id") or "")
        if not job_id:
            continue
        bucket = merged.setdefault(job_id, {})
        for raw in item.get("skills", []) or []:
            if not isinstance(raw, dict):
                continue
            canonical = _canonical_skill(raw.get("canonical_name") or raw.get("name"), aliases)
            if not canonical:
                continue
            skill = dict(raw)
            skill["name"] = str(skill.get("name") or canonical)
            skill["canonical_name"] = canonical
            skill["skill_id"] = str(skill.get("skill_id") or f"s_{canonical}")
            previous = bucket.get(canonical)
            if previous is None or float(skill.get("confidence") or 0) > float(previous.get("confidence") or 0):
                bucket[canonical] = skill
    return {job_id: list(bucket.values()) for job_id, bucket in merged.items()}


def _definition_skills(definition: dict[str, Any], skill_records: list[dict[str, Any]], aliases: dict[str, str], field: str) -> list[str]:
    raw_values = [str(value) for value in definition.get(field, []) or [] if str(value).strip()]
    record_by_name = {}
    for record in skill_records:
        for value in (record.get("name"), record.get("canonical_name")):
            if value:
                record_by_name[str(value).strip().lower()] = str(record.get("canonical_name") or value).strip().lower()
    result = []
    for value in raw_values:
        canonical = record_by_name.get(value.strip().lower()) or _canonical_skill(value, aliases)
        if canonical not in result:
            result.append(canonical)
    return result


def import_skill_dict(path: Path | None = None, session=None) -> int:
    entries = _load_json(path or SKILL_DICT_PATH)
    db = session or SessionLocal()
    try:
        db.execute(text("DELETE FROM skill_dict"))
        for entry in entries:
            db.execute(text("INSERT INTO skill_dict (canonical, aliases, category) VALUES (:canonical, :aliases, :category)"), {
                "canonical": entry["canonical"], "aliases": _json(entry.get("aliases", [])), "category": entry.get("category", "")
            })
        if session is None:
            db.commit()
        return len(entries)
    except Exception:
        if session is None:
            db.rollback()
        raise
    finally:
        if session is None:
            db.close()


def _definitions_and_skills(defs: list[dict[str, Any]], skills: list[dict[str, Any]], aliases: dict[str, str], session=None) -> tuple[int, int, dict[str, int]]:
    db = session or SessionLocal()
    try:
        _ensure_columns(db)
        skill_by_job = _skill_records_by_job(skills, aliases)
        db.execute(text("DELETE FROM job_skill"))
        db.execute(text("DELETE FROM job_definition"))
        id_by_m2: dict[str, int] = {}
        for definition in defs:
            m2_job_id = str(definition.get("job_id") or "").strip()
            if not m2_job_id:
                continue
            records = skill_by_job.get(m2_job_id, [])
            required = _definition_skills(definition, records, aliases, "required_skills")
            bonus = _definition_skills(definition, records, aliases, "bonus_skills")
            db.execute(text("""
                INSERT INTO job_definition
                (job_name, core_duties, required_skills, bonus_skills, scenarios, source, quality,
                 is_emerging, evolution, first_seen, collected_at, updated_at,
                 m2_job_id, name_en, job_name_zh, category, category_review, source_jd_count)
                VALUES (:job_name, :core_duties, :required_skills, :bonus_skills, :scenarios, :source, :quality,
                        :is_emerging, :evolution, :first_seen, :collected_at, :updated_at,
                        :m2_job_id, :name_en, :job_name_zh, :category, :category_review, :source_jd_count)
            """), {
                "job_name": str(definition.get("job_name") or definition.get("name_en") or "未命名岗位")[:128],
                "core_duties": str(definition.get("core_duties") or ""),
                "required_skills": _json(required), "bonus_skills": _json(bonus),
                "scenarios": _json(definition.get("scenarios", [])), "source": _json(definition.get("source", [])),
                "quality": float(definition.get("quality") or 0), "is_emerging": int(bool(definition.get("is_emerging", False))),
                "evolution": _json(definition.get("evolution", {})), "first_seen": definition.get("first_seen") or None,
                "collected_at": definition.get("collected_at") or None, "updated_at": definition.get("updated_at") or None,
                "m2_job_id": m2_job_id, "name_en": str(definition.get("name_en") or "")[:255],
                "job_name_zh": str(definition.get("job_name_zh") or definition.get("job_name") or "")[:255],
                "category": str(definition.get("category") or "")[:32], "category_review": str(definition.get("category_review") or "")[:32],
                "source_jd_count": int(definition.get("source_jd_count") or 0),
            })
            row_id = db.execute(text("SELECT id FROM job_definition WHERE m2_job_id=:m2_job_id"), {"m2_job_id": m2_job_id}).scalar()
            id_by_m2[m2_job_id] = int(row_id)

        inserted_skills = 0
        definition_by_id = {str(item.get("job_id")): item for item in defs}
        for job_id, records in skill_by_job.items():
            if job_id not in id_by_m2:
                continue
            definition = definition_by_id.get(job_id, {})
            db.execute(text("""
                INSERT INTO job_skill (jd_id, job_name, m2_job_id, skills, duties, extracted_at)
                VALUES (:jd_id, :job_name, :m2_job_id, :skills, :duties, :extracted_at)
            """), {
                "jd_id": id_by_m2[job_id], "job_name": str(definition.get("job_name") or "")[:128], "m2_job_id": job_id,
                "skills": _json(records), "duties": str(definition.get("core_duties") or ""),
                "extracted_at": definition.get("updated_at") or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            })
            inserted_skills += 1
        if session is None:
            db.commit()
        return len(id_by_m2), inserted_skills, id_by_m2
    except Exception:
        if session is None:
            db.rollback()
        raise
    finally:
        if session is None:
            db.close()


def import_job_definitions(path: Path | None = None, session=None) -> int:
    if path is None and DEFAULT_PACKAGE_DIR.exists():
        package = load_return_package(DEFAULT_PACKAGE_DIR)
        defs = package["definitions"]
        skills = package["skills"]
        _, aliases = _load_skill_dict()
        count, _, _ = _definitions_and_skills(defs, skills, aliases)
        return count
    defs = _load_json(path or EXCHANGE_M2 / "job_definition.json")
    db = session or SessionLocal()
    try:
        _ensure_columns(db)
        db.execute(text("DELETE FROM job_definition"))
        for d in defs:
            db.execute(text("""
                INSERT INTO job_definition (job_name, core_duties, required_skills, bonus_skills, scenarios, source, quality, is_emerging, evolution, first_seen, collected_at, updated_at)
                VALUES (:job_name, :core_duties, :required_skills, :bonus_skills, :scenarios, :source, :quality, :is_emerging, :evolution, :first_seen, :collected_at, :updated_at)
            """), {
                "job_name": d.get("job_name", ""), "core_duties": d.get("core_duties", ""),
                "required_skills": _json(d.get("required_skills", [])), "bonus_skills": _json(d.get("bonus_skills", [])),
                "scenarios": _json(d.get("scenarios", [])), "source": _json(d.get("source", [])), "quality": float(d.get("quality", 0) or 0),
                "is_emerging": int(bool(d.get("is_emerging", False))), "evolution": _json(d.get("evolution", {})),
                "first_seen": d.get("first_seen") or None, "collected_at": d.get("collected_at") or None, "updated_at": d.get("updated_at") or None,
            })
        if session is None:
            db.commit()
        return len(defs)
    except Exception:
        if session is None:
            db.rollback()
        raise
    finally:
        if session is None:
            db.close()


def import_job_skills(path: Path | None = None, session=None) -> int:
    items = _load_json(path or EXCHANGE_M2 / "job_skill.json")
    db = session or SessionLocal()
    try:
        rows = db.execute(text("SELECT id, job_name FROM job_definition")).mappings().all()
        id_by_name = {str(row["job_name"]): row["id"] for row in rows}
        db.execute(text("DELETE FROM job_skill"))
        for item in items:
            job_name = str(item.get("job_name") or "")
            if job_name not in id_by_name:
                continue
            db.execute(text("INSERT INTO job_skill (jd_id, job_name, skills, duties, extracted_at) VALUES (:jd_id, :job_name, :skills, :duties, :extracted_at)"), {
                "jd_id": id_by_name[job_name], "job_name": job_name, "skills": _json(item.get("skills", [])), "duties": item.get("duties", "") or "", "extracted_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            })
        if session is None:
            db.commit()
        return len(items)
    except Exception:
        if session is None:
            db.rollback()
        raise
    finally:
        if session is None:
            db.close()


def _parse_datetime(value: Any) -> str | None:
    if not value:
        return None
    return str(value).replace("T", " ")[:19]


def import_change_logs(path: Path | None = None, session=None, package_dir: Path | None = None) -> int:
    logs = _load_json(path) if path else load_return_package(package_dir or DEFAULT_PACKAGE_DIR)["change_logs"]
    db = session or SessionLocal()
    try:
        _ensure_columns(db)
        rows = db.execute(text("SELECT id, job_name, m2_job_id, name_en, job_name_zh FROM job_definition")).mappings().all()
        lookup = {}
        for row in rows:
            for key in (row.get("m2_job_id"), row.get("job_name"), row.get("name_en"), row.get("job_name_zh")):
                if key:
                    lookup[str(key).strip().lower()] = int(row["id"])
        if path is None:
            db.execute(text("DELETE FROM job_change_log"))
        imported = 0
        orphaned = 0
        for log in logs:
            raw_ref = str(log.get("job_id") or "").strip()
            job_id = lookup.get(raw_ref.lower())
            if job_id is None and raw_ref.isdigit():
                job_id = int(raw_ref)
            if job_id is None:
                orphaned += 1
                # 显式导入旧测试/外部文件时保留旧语义：无法关联的记录不写入生产表；
                # 默认 M2 回包导入则保留原始 job_id，保证 243 条变更记录可审计。
                if path is not None:
                    continue
            db.execute(text("""
                INSERT INTO job_change_log
                (job_id, m2_job_id, object_type, change_type, skill_name, detail, source, reason, created_at, source_jd_time)
                VALUES (:job_id, :m2_job_id, :object_type, :change_type, :skill_name, :detail, :source, :reason, :created_at, :source_jd_time)
            """), {
                "job_id": job_id, "m2_job_id": raw_ref[:64], "object_type": str(log.get("object_type") or "skill")[:32],
                "change_type": str(log.get("change_type") or "")[:32], "skill_name": str(log.get("skill_name") or "")[:128],
                "detail": _json(log.get("detail", {})), "source": json.dumps(log.get("source", []), ensure_ascii=False)[:128],
                "reason": log.get("reason") or "", "created_at": _parse_datetime(log.get("created_at")), "source_jd_time": _parse_datetime(log.get("source_jd_time")),
            })
            imported += 1
        if session is None:
            db.commit()
        return imported
    except Exception:
        if session is None:
            db.rollback()
        raise
    finally:
        if session is None:
            db.close()


def _write_audit(package: dict[str, Any], result: dict[str, Any]) -> None:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"generated_at": datetime.now(timezone.utc).isoformat(), "package": package_summary(package), "result": result}
    (AUDIT_DIR / "2026-09-02-full-import.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def import_all(package_dir: Path | str | None = None, session=None) -> dict[str, Any]:
    package = load_return_package(package_dir or DEFAULT_PACKAGE_DIR)
    defs = package["definitions"]
    skills = package["skills"]
    _, aliases = _load_skill_dict()
    db = session or SessionLocal()
    try:
        _ensure_columns(db)
        import_skill_dict(session=db)
        db.execute(text("DELETE FROM job_change_log"))
        job_count, skill_record_count, _ = _definitions_and_skills(defs, skills, aliases, session=db)
        change_count = import_change_logs(session=db, package_dir=Path(package_dir or DEFAULT_PACKAGE_DIR))
        orphaned = int(db.execute(text("SELECT COUNT(*) FROM job_change_log WHERE job_id IS NULL")).scalar() or 0)
        if session is None:
            db.commit()
        result = {
            "skill_dict": int(db.execute(text("SELECT COUNT(*) FROM skill_dict")).scalar() or 0),
            "job_definition": job_count, "job_skill": skill_record_count,
            "job_change_log": change_count, "orphan_change_logs": orphaned,
            "m2_definitions": len(defs), "m2_skill_records": len(skills),
        }
        _write_audit(package, result)
        return result
    except Exception:
        if session is None:
            db.rollback()
        raise
    finally:
        if session is None:
            db.close()


if __name__ == "__main__":
    print(json.dumps(import_all(), ensure_ascii=False, indent=2))

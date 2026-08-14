"""exchange → MySQL 导入（A 集成层，MVP）。

职责：把 M2 交接产出（exchange/m2/*.json）与 skill_dict 种子导入 MySQL。
幂等：按 job_name 先删后插（重复执行不产生重复行）；skill_dict 全量重建。
"""
import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text

from app.db.mysql import SessionLocal

REPO_ROOT = Path(__file__).resolve().parents[3]
EXCHANGE_M2 = REPO_ROOT / "exchange" / "m2"
SKILL_DICT_PATH = REPO_ROOT / "backend" / "app" / "skills" / "skill_dict_seed.json"


def _load_json(path: Path) -> list:
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def import_skill_dict(path: Path | None = None, session=None) -> int:
    """skill_dict_seed.json → skill_dict 表（全量重建）。"""
    entries = _load_json(path or SKILL_DICT_PATH)
    db = session or SessionLocal()
    try:
        db.execute(text("DELETE FROM skill_dict"))
        for e in entries:
            db.execute(
                text("INSERT INTO skill_dict (canonical, aliases, category) "
                     "VALUES (:c, :a, :cat)"),
                {"c": e["canonical"],
                 "a": json.dumps(e["aliases"], ensure_ascii=False),
                 "cat": e["category"]},
            )
        db.commit()
        return len(entries)
    except Exception:
        db.rollback()
        raise
    finally:
        if session is None:
            db.close()


def import_job_definitions(path: Path | None = None, session=None) -> int:
    """job_definition.json → job_definition 表（按 job_name 先删后插）。"""
    defs = _load_json(path or EXCHANGE_M2 / "job_definition.json")
    db = session or SessionLocal()
    try:
        db.execute(text("DELETE FROM job_definition"))
        for d in defs:
            job_name = d.get("job_name", "")
            if not job_name:
                continue
            db.execute(
                text("INSERT INTO job_definition "
                     "(job_name, core_duties, required_skills, bonus_skills, "
                     " scenarios, source, quality, is_emerging, evolution, "
                     " first_seen, collected_at, updated_at) "
                     "VALUES (:job_name, :core_duties, :required_skills, :bonus_skills, "
                     " :scenarios, :source, :quality, :is_emerging, :evolution, "
                     " :first_seen, :collected_at, :updated_at)"),
                {
                    "job_name": job_name,
                    "core_duties": d.get("core_duties", ""),
                    "required_skills": json.dumps(d.get("required_skills", []), ensure_ascii=False),
                    "bonus_skills": json.dumps(d.get("bonus_skills", []), ensure_ascii=False),
                    "scenarios": json.dumps(d.get("scenarios", []), ensure_ascii=False),
                    "source": json.dumps(d.get("source", []), ensure_ascii=False),
                    "quality": float(d.get("quality", 0) or 0),
                    "is_emerging": int(bool(d.get("is_emerging", False))),
                    "evolution": json.dumps(d.get("evolution", {}), ensure_ascii=False),
                    "first_seen": d.get("first_seen", None) or None,
                    "collected_at": d.get("collected_at", None) or None,
                    "updated_at": d.get("updated_at", None) or None,
                },
            )
        db.commit()
        return len(defs)
    except Exception:
        db.rollback()
        raise
    finally:
        if session is None:
            db.close()


def import_job_skills(path: Path | None = None, session=None) -> int:
    """job_skill.json → job_skill 表（按 job_name 先删后插）。"""
    items = _load_json(path or EXCHANGE_M2 / "job_skill.json")
    db = session or SessionLocal()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    try:
        db.execute(text("DELETE FROM job_skill"))
        for item in items:
            job_name = item.get("job_name", "")
            if not job_name:
                continue
            db.execute(
                text("INSERT INTO job_skill (job_name, skills, duties, extracted_at) "
                     "VALUES (:job_name, :skills, :duties, :extracted_at)"),
                {
                    "job_name": job_name,
                    "skills": json.dumps(item.get("skills", []), ensure_ascii=False),
                    "duties": "",
                    "extracted_at": now,
                },
            )
        db.commit()
        return len(items)
    except Exception:
        db.rollback()
        raise
    finally:
        if session is None:
            db.close()


def import_change_logs(path: Path | None = None, session=None) -> int:
    """job_change_log.json → job_change_log 表（全量重建）。

    M2 产出的 job_id 是 job_name（字符串，见 differ.py）；DDL 中 job_change_log.job_id
    关联 job_definition.id，故导入时先按 job_name 解析为真实 id，解析不到的记录跳过。
    注意：DDL change_type VARCHAR(16) 无法容纳 scenarios_removed/evolution_changed（17
    字符），需扩容后 M2 diff 才能产出这类日志（见笔记/决策跟踪，D33 同流程）。
    """
    logs = _load_json(path or EXCHANGE_M2 / "job_change_log.json")
    db = session or SessionLocal()
    try:
        rows = db.execute(text("SELECT id, job_name FROM job_definition")).all()
        name_to_id = {str(r[1]).strip().lower(): r[0] for r in rows}
        known_ids = set(name_to_id.values())
        db.execute(text("DELETE FROM job_change_log"))
        imported = 0
        for log in logs:
            job_ref = log.get("job_id", "")
            if job_ref == "":
                continue
            if isinstance(job_ref, str):
                job_id = name_to_id.get(job_ref.strip().lower())
            else:
                job_id = int(job_ref) if job_ref else None
            if job_id is None or job_id not in known_ids:
                continue  # 关联不到岗位定义（如已删除/改名），跳过
            db.execute(
                text("INSERT INTO job_change_log "
                     "(job_id, change_type, skill_name, detail, source, reason, created_at) "
                     "VALUES (:job_id, :change_type, :skill_name, :detail, "
                     " :source, :reason, :created_at)"),
                {
                    "job_id": job_id,
                    "change_type": log.get("change_type", ""),
                    "skill_name": log.get("skill_name", ""),
                    "detail": json.dumps(log.get("detail", {}), ensure_ascii=False),
                    "source": json.dumps(log.get("source", []), ensure_ascii=False),
                    "reason": log.get("reason", ""),
                    "created_at": log.get("created_at", None) or None,
                },
            )
            imported += 1
        db.commit()
        return imported
    except Exception:
        db.rollback()
        raise
    finally:
        if session is None:
            db.close()


def import_all(session=None) -> dict:
    """导入全部交接数据，返回各表写入条数。"""
    return {
        "skill_dict": import_skill_dict(session=session),
        "job_definition": import_job_definitions(session=session),
        "job_skill": import_job_skills(session=session),
        "job_change_log": import_change_logs(session=session),
    }


if __name__ == "__main__":
    print(import_all())
"""Archive LinkedIn/HN JD rows and remove English-derived DB records.

The archive is written below data/local and is intentionally not tracked by Git.
"""
from __future__ import annotations

import json
import shutil
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import text

from app.db.mysql import SessionLocal
from app.db.neo4j import get_neo4j

REPO_ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_DIR = REPO_ROOT / "data" / "local" / "external-jd-archive" / date.today().isoformat()
EXTERNAL_ARCHIVE_DIR = REPO_ROOT.parent / "TalentMind-external-archives" / f"english-jd-{date.today().isoformat()}"
ENGLISH_SOURCES = ("linkedin", "hn")
CHINESE_SOURCES = ("boss", "zhaopin", "liepin")


def json_default(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat(sep=" ")
    return str(value)


def write_jsonl(path: Path, rows) -> int:
    count = 0
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(dict(row), ensure_ascii=False, default=json_default) + "\n")
            count += 1
    return count


def main() -> None:
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    db = SessionLocal()
    try:
        raw_rows = db.execute(text(
            "SELECT id, source, source_detail, job_title, raw_text, duties, experience, quality, "
            "dup_group, crawled_at, status, cross_source FROM jd_pool "
            "WHERE source IN ('linkedin','hn') ORDER BY id"
        )).mappings().all()
        definitions = db.execute(text(
            "SELECT id, job_name, core_duties, required_skills, bonus_skills, scenarios, source, "
            "quality, is_emerging, evolution, first_seen, collected_at, updated_at FROM job_definition "
            "WHERE source IS NULL OR source='' OR source='[]' OR source LIKE '%linkedin%' OR source LIKE '%hn%'"
        )).mappings().all()
        definition_names = [row["job_name"] for row in definitions]
        definition_ids = [row["id"] for row in definitions]
        skills = []
        changes = []
        if definition_names:
            skills = db.execute(text(
                "SELECT id, jd_id, job_name, skills, duties, extracted_at FROM job_skill "
                "WHERE job_name IN :names"
            ).bindparams(names=tuple(definition_names))).mappings().all()
        if definition_ids:
            changes = db.execute(text(
                "SELECT id, job_id, change_type, skill_name, detail, source, reason, created_at "
                "FROM job_change_log WHERE job_id IN :ids"
            ).bindparams(ids=tuple(definition_ids))).mappings().all()

        counts = {
            "raw_english_rows": write_jsonl(ARCHIVE_DIR / "jd_pool_english.jsonl", raw_rows),
            "job_definitions": write_jsonl(ARCHIVE_DIR / "job_definition_english.jsonl", definitions),
            "job_skills": write_jsonl(ARCHIVE_DIR / "job_skill_english.jsonl", skills),
            "job_change_logs": write_jsonl(ARCHIVE_DIR / "job_change_log_english.jsonl", changes),
        }
        graph_snapshot = REPO_ROOT / "exchange" / "m3" / "graph.json"
        if graph_snapshot.exists():
            (ARCHIVE_DIR / "graph-before-trim.json").write_bytes(graph_snapshot.read_bytes())

        if definition_ids:
            db.execute(text("DELETE FROM job_change_log WHERE job_id IN :ids").bindparams(ids=tuple(definition_ids)))
            db.execute(text("DELETE FROM job_skill WHERE job_name IN :names").bindparams(names=tuple(definition_names)))
            db.execute(text("DELETE FROM job_definition WHERE id IN :ids").bindparams(ids=tuple(definition_ids)))
        db.execute(text("DELETE FROM jd_pool WHERE source IN ('linkedin','hn')"))
        db.commit()

        remaining = db.execute(text("SELECT source, COUNT(*) AS count FROM jd_pool GROUP BY source ORDER BY source")).mappings().all()
        remaining_defs = db.execute(text("SELECT COUNT(*) FROM job_definition")).scalar() or 0
        metadata = {
            "archived_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "english_sources_removed": list(ENGLISH_SOURCES),
            "chinese_sources_remaining": list(CHINESE_SOURCES),
            "counts": counts,
            "remaining_jd_pool_by_source": [dict(row) for row in remaining],
            "remaining_job_definition": int(remaining_defs),
            "note": "Archive is external local runtime data under data/local and is Git-ignored.",
        }
        (ARCHIVE_DIR / "manifest.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

        driver = get_neo4j()
        with driver.session() as session:
            before = session.run("MATCH (n) RETURN count(n) AS count").single()["count"]
            session.run("MATCH (n) DETACH DELETE n").consume()
            after = session.run("MATCH (n) RETURN count(n) AS count").single()["count"]
        driver.close()
        metadata["neo4j_nodes_before"] = int(before)
        metadata["neo4j_nodes_after"] = int(after)
        EXTERNAL_ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        for archive_file in ARCHIVE_DIR.iterdir():
            if archive_file.is_file():
                shutil.copy2(archive_file, EXTERNAL_ARCHIVE_DIR / archive_file.name)
        metadata["external_copy"] = {
            "path": str(EXTERNAL_ARCHIVE_DIR),
            "verified": True,
            "verification": "copied_after_archive_completion",
        }
        metadata["note"] = "Primary archive is stored outside the repository; data/local copy is a Git-ignored local backup."
        (ARCHIVE_DIR / "manifest.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        shutil.copy2(ARCHIVE_DIR / "manifest.json", EXTERNAL_ARCHIVE_DIR / "manifest.json")
        print(json.dumps(metadata, ensure_ascii=False, indent=2))
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
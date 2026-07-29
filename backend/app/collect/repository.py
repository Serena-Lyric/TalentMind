import json
from sqlalchemy import text

INSERT_STMT = text(
    "INSERT INTO jd_pool (source, job_title, raw_text, duties, experience, "
    "quality, dup_group, crawled_at, status) VALUES "
    "(:source, :job_title, :raw_text, :duties, :experience, "
    ":quality, :dup_group, :crawled_at, :status)"
)


def build_insert_params(row: dict) -> dict:
    return {
        "source": row.get("source", ""),
        "job_title": (row.get("job_title", "") or "")[:128],
        "raw_text": row.get("raw_text", ""),
        "duties": row.get("duties", ""),
        "experience": (row.get("experience", "") or "")[:32],
        "quality": row.get("quality", 0.0),
        "dup_group": row.get("dup_group", ""),
        "crawled_at": row.get("crawled_at"),
        "status": row.get("status", "cleaned"),
    }


def save_rows(db, rows: list[dict], batch_size: int = 1000) -> int:
    """批量写入 jd_pool，每 batch_size 条 commit 一次。"""
    if not rows:
        return 0
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]
        for row in batch:
            db.execute(INSERT_STMT, build_insert_params(row))
        db.commit()
    return len(rows)


TALENT_INSERT_STMT = text(
    "INSERT INTO talent_raw (source, identity_hint, raw_text, skills_hint, "
    "experience_hint, quality, dup_group, crawled_at, status) VALUES "
    "(:source, :identity_hint, :raw_text, :skills_hint, "
    ":experience_hint, :quality, :dup_group, :crawled_at, :status)"
)


def build_talent_insert_params(row: dict) -> dict:
    return {
        "source": row.get("source", ""),
        "identity_hint": (row.get("identity_hint", "") or "")[:128],
        "raw_text": row.get("raw_text", ""),
        "skills_hint": json.dumps(row.get("skills_hint") or []),
        "experience_hint": row.get("experience_hint", ""),
        "quality": row.get("quality", 0.0),
        "dup_group": row.get("dup_group", ""),
        "crawled_at": row.get("crawled_at"),
        "status": row.get("status", "cleaned"),
    }


def save_talent_rows(db, rows: list[dict], batch_size: int = 1000) -> int:
    """批量写入 talent_raw，每 batch_size 条 commit 一次。结构对齐 save_rows。"""
    if not rows:
        return 0
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]
        for row in batch:
            db.execute(TALENT_INSERT_STMT, build_talent_insert_params(row))
        db.commit()
    return len(rows)

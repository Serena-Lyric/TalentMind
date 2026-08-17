import json
from datetime import datetime, timezone
from sqlalchemy import text

INSERT_STMT = text(
    "INSERT INTO jd_pool (source, source_detail, job_title, raw_text, duties, experience, "
    "quality, dup_group, crawled_at, status) VALUES "
    "(:source, :source_detail, :job_title, :raw_text, :duties, :experience, "
    ":quality, :dup_group, :crawled_at, :status)"
)


def build_insert_params(row: dict) -> dict:
    return {
        "source": row.get("source", ""),
        "source_detail": (row.get("source_detail", "") or "")[:128],
        "job_title": (row.get("job_title", "") or "")[:128],
        "raw_text": row.get("raw_text", ""),
        "duties": row.get("duties", ""),
        "experience": row.get("experience", "") or "",
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

SIGNAL_INSERT_STMT = text(
    "INSERT INTO `signal` (skill_or_job, signal_type, metric, value, captured_at, source) "
    "VALUES (:k, :t, :m, :v, :c, :s)"
)


def save_signals(db, signals: list, batch_size: int = 1000) -> int:
    """批量写入 signal 表（D39 多源）。同一次抓取按 (key, source, metric) 去重后写入。"""
    if not signals:
        return 0
    now = datetime.now(timezone.utc)
    seen: set[tuple] = set()
    dedup: list = []
    for s in signals:
        key = (s.skill_or_job, s.source, s.metric)
        if key in seen:
            continue
        seen.add(key)
        dedup.append(s)
    params = [
        {"k": (s.skill_or_job or "")[:128], "t": (s.signal_type or "")[:16],
         "m": (s.metric or "")[:16], "v": float(s.value),
         "c": now, "s": (s.source or "")[:32]}
        for s in dedup
    ]
    for i in range(0, len(params), batch_size):
        db.execute(SIGNAL_INSERT_STMT, params[i:i + batch_size])
        db.commit()
    return len(params)

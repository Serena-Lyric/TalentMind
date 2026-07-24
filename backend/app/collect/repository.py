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

import json
from datetime import datetime, timezone
from sqlalchemy import inspect, text

from app.collect.identity import IDENTITY_STATUSES

INSERT_STMT = text(
    "INSERT INTO jd_pool (source, source_detail, job_title, raw_text, duties, experience, "
    "quality, dup_group, crawled_at, status) VALUES "
    "(:source, :source_detail, :job_title, :raw_text, :duties, :experience, "
    ":quality, :dup_group, :crawled_at, :status)"
)

IDENTITY_INSERT_STMT = text(
    "INSERT INTO jd_pool (source, source_detail, job_title, raw_text, duties, experience, "
    "quality, dup_group, crawled_at, status, identity_status, content_eligible, identity_evidence) VALUES "
    "(:source, :source_detail, :job_title, :raw_text, :duties, :experience, "
    ":quality, :dup_group, :crawled_at, :status, :identity_status, :content_eligible, :identity_evidence)"
)

IDENTITY_COLUMNS = ('identity_status', 'content_eligible', 'identity_evidence')


def build_insert_params(row: dict) -> dict:
    identity_status = row.get("identity_status", "unknown") or "unknown"
    if identity_status not in IDENTITY_STATUSES:
        raise ValueError("invalid identity_status")
    evidence = row.get("identity_evidence", "") or ""
    if isinstance(evidence, dict):
        evidence = json.dumps(evidence, ensure_ascii=False, sort_keys=True)
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
        "identity_status": identity_status,
        "content_eligible": row.get("content_eligible"),
        "identity_evidence": evidence,
    }


def schema_capabilities(db) -> dict[str, bool]:
    """Detect additive identity columns without assuming a migrated database."""
    get_bind = getattr(db, "get_bind", None)
    if not callable(get_bind):
        return {name: False for name in IDENTITY_COLUMNS}
    try:
        columns = {column["name"] for column in inspect(get_bind()).get_columns("jd_pool")}
    except Exception:
        return {name: False for name in IDENTITY_COLUMNS}
    return {name: name in columns for name in IDENTITY_COLUMNS}


def _needs_identity_columns(params: dict) -> bool:
    return bool(
        params.get("identity_status", "unknown") != "unknown"
        or params.get("content_eligible") is not None
        or params.get("identity_evidence")
    )


def insert_statement(db, params: list[dict]):
    capabilities = schema_capabilities(db)
    if all(capabilities.values()):
        return IDENTITY_INSERT_STMT
    if any(_needs_identity_columns(item) for item in params):
        raise RuntimeError("identity_schema_migration_required")
    return INSERT_STMT


def save_rows(db, rows: list[dict], batch_size: int = 1000) -> int:
    """批量写入 jd_pool，每 batch_size 条 commit 一次。"""
    if not rows:
        return 0
    params = [build_insert_params(row) for row in rows]
    statement = insert_statement(db, params)
    for i in range(0, len(rows), batch_size):
        for row in params[i:i + batch_size]:
            db.execute(statement, row)
        db.commit()
    return len(rows)


def save_incremental_jd_rows(db, rows: list[dict], *, created_ids: set[int], allow_updates: bool = False, on_saved=None) -> int:
    """逐条提交，返回新增数；详情只补本轮新增行或可识别的历史纯列表行。

    不提供并发唯一性保证（既有契约无唯一键）；调用方须串行采集。
    """
    saved = 0
    params_list = [build_insert_params(row) for row in rows]
    capabilities = schema_capabilities(db)
    statement = insert_statement(db, params_list)
    identity_update = ""
    if all(capabilities.values()):
        identity_update = (", identity_status=:identity_status, content_eligible=:content_eligible, "
                           "identity_evidence=:identity_evidence")
    for row in rows:
        params = build_insert_params(row)
        try:
            existing = db.execute(text(
                "SELECT id, raw_text, duties FROM jd_pool "
                "WHERE source=:source AND source_detail=:source_detail ORDER BY id LIMIT 1"
            ), params).mappings().first()
            if existing is None:
                result = db.execute(statement, params)
                db.commit()
                created_ids.add(result.lastrowid)
                saved += 1
                if on_saved:
                    on_saved({**params, 'jd_pool_id': result.lastrowid, 'outcome': 'inserted'})
                continue
            old_text = existing["raw_text"] or ""
            has_description = "职位描述:" in params["raw_text"] or "职位描述：" in params["raw_text"]
            metadata_keys = {"公司", "薪资", "地点", "经验", "学历", "公司规模", "公司阶段", "行业", "技能标签", "福利"}
            metadata_only = bool(old_text.strip()) and all(
                line.strip().replace("：", ":", 1).partition(":")[0] in metadata_keys
                for line in old_text.splitlines() if line.strip()
            )
            if (allow_updates and has_description and params["raw_text"] != old_text
                    and (existing["id"] in created_ids or (metadata_only and not existing["duties"]))):
                result = db.execute(text(
                    "UPDATE jd_pool SET job_title=:job_title, raw_text=:raw_text, duties=:duties, "
                    "experience=:experience, quality=:quality, dup_group=:dup_group" + identity_update + " "
                    "WHERE id=:id AND source=:source AND source_detail=:source_detail AND raw_text=:old_text"
                ), {**params, "id": existing["id"], "old_text": existing["raw_text"]})
                db.commit()
                if on_saved:
                    on_saved({**params, 'jd_pool_id': existing['id'],
                              'outcome': 'updated' if result.rowcount == 1 else 'skipped'})
            elif on_saved:
                on_saved({'source_detail': params['source_detail'], 'jd_pool_id': existing['id'], 'outcome': 'skipped'})
        except Exception:
            db.rollback()
            raise
    return saved


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

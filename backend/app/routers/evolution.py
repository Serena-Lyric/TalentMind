"""岗位能力动态只读 API。

数据来源为冻结契约中的 job_change_log 和 job_definition；无记录时返回空数组，
前端不得用演示记录填充。
"""
from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter
from sqlalchemy import text

from app.db.mysql import SessionLocal
from app.response import BizError, ok

router = APIRouter()


def _detail(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if not value:
        return {}
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return {"value": str(value)}


@router.get("/evolution/timeline/{job_id}")
def evolution_timeline(job_id: int):
    db = SessionLocal()
    try:
        job = db.execute(text("SELECT id, job_name, name_en, job_name_zh, category FROM job_definition WHERE id=:id"), {"id": job_id}).mappings().first()
        if not job:
            raise BizError(4041, "岗位不存在")
        rows = db.execute(text(
            "SELECT id, m2_job_id, object_type, change_type, skill_name, detail, source, reason, created_at, source_jd_time "
            "FROM job_change_log WHERE job_id=:id ORDER BY created_at DESC, id DESC"
        ), {"id": job_id}).mappings().all()
        records = []
        for row in rows:
            created = row["created_at"]
            records.append({
                "id": str(row["id"]),
                "job_id": str(job["id"]),
                "job_title": job.get("job_name_zh") or job["job_name"],
                "job_name_en": job.get("name_en") or job["job_name"],
                "category": job.get("category") or "",
                "version": len(records) + 1,
                "m2_job_id": row.get("m2_job_id") or "",
                "object_type": row.get("object_type") or "skill",
                "change_type": row["change_type"],
                "skill_name": row["skill_name"],
                "detail": _detail(row["detail"]),
                "source": row["source"] or "",
                "reason": row["reason"] or "",
                "summary": f"{row['change_type']}：{row['skill_name']}" if row["skill_name"] else row["change_type"],
                "created_at": created.isoformat() if hasattr(created, "isoformat") else str(created or ""),
                "source_jd_time": row.get("source_jd_time").isoformat() if hasattr(row.get("source_jd_time"), "isoformat") else str(row.get("source_jd_time") or ""),
            })
        return ok({
            "job_id": str(job["id"]),
            "job_title": job.get("job_name_zh") or job["job_name"],
            "job_name_en": job.get("name_en") or job["job_name"],
            "category": job.get("category") or "",
            "records": records,
            "current_version": len(records),
            "total_changes": len(records),
        })
    finally:
        db.close()


@router.get("/evolution/sources/stats")
def evolution_source_stats():
    db = SessionLocal()
    try:
        rows = db.execute(text(
            "SELECT COALESCE(NULLIF(source,''),'未标注') AS name, COUNT(*) AS count "
            "FROM job_change_log GROUP BY COALESCE(NULLIF(source,''),'未标注') ORDER BY count DESC"
        )).mappings().all()
        return ok([{"name": row["name"], "count": int(row["count"])} for row in rows])
    finally:
        db.close()
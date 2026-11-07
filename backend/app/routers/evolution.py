"""岗位能力动态只读 API。

数据来源为冻结契约中的 job_change_log 和 job_definition；无记录时返回空数组，
前端不得用演示记录填充。
"""
from __future__ import annotations

import json
import hashlib
from functools import lru_cache
from pathlib import Path
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


def _time(value: Any) -> str:
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    return str(value or '').replace(' ', 'T')


def change_fingerprint(row) -> str:
    """Match reviewed content, never a mutable database ID or a trend keyword."""
    value = {key: row.get(key) or '' for key in ('m2_job_id', 'object_type', 'change_type', 'skill_name', 'reason')}
    value.update(detail=_detail(row.get('detail')), source=_detail(row.get('source')),
                 created_at=_time(row.get('created_at')), source_jd_time=_time(row.get('source_jd_time')))
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


@lru_cache
def _demo_provenance():
    return json.loads((Path(__file__).resolve().parents[1] / 'contracts/evolution-demo-provenance.json').read_text(encoding='utf-8'))


def describe_change(row) -> dict:
    detail = _detail(row.get('detail'))
    detail = detail if isinstance(detail, dict) else {}
    manifest = _demo_provenance()
    index = manifest['records'].get(change_fingerprint(row))
    profile = row.get('source') == 'talentmind:profile-edit/v1' and detail.get('change_nature') == 'profile_edit'
    return {
        'change_nature': 'historical_demo' if index is not None else 'profile_edit' if profile else 'unverified_history',
        'provenance': {'baseline_index': index, 'baseline_sha256': manifest['baseline_sha256'], 'reference': manifest['reference']} if index is not None else None,
        'before': detail.get('before', detail.get('old_value')),
        'after': detail.get('after', detail.get('new_value')),
        'comparison_available': any(key in detail for key in ('before', 'after', 'old_value', 'new_value')),
        'previous_version': detail.get('before_version') if profile else None,
        'version': detail.get('after_version') if profile else None,
        'market_change_verified': False,
    }


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
                **describe_change(row),
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
            "current_version": None,
            "total_changes": len(records),
        })
    finally:
        db.close()

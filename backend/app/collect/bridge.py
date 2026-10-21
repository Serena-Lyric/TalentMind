"""Private storage and ingestion for explicit normal-browser captures."""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.collect import control
from app.collect.bridge_schema import BridgeCapture, BridgeSessionCreate, validate_capture
from app.collect.cleaner import clean, is_valid_jd
from app.collect.fetchers.boss import normalize_boss_job, normalize_url
from app.collect.pipeline import run_pipeline
from app.collect.repository import save_incremental_jd_rows, schema_capabilities

_REPO_ROOT = Path(__file__).resolve().parents[3]
_STATE_DIR = _REPO_ROOT / "data" / "local" / "collection"
_SESSIONS_DIR = _STATE_DIR / "bridge"
_LOCK = threading.RLock()
_RUN_ID = re.compile(r"bridge-[a-f0-9]{32}")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _session_path(run_id: str) -> Path:
    if not _RUN_ID.fullmatch(run_id):
        raise ValueError("无效桥接任务 ID")
    return _SESSIONS_DIR / f"{run_id}.json"


def _event_path(run_id: str) -> Path:
    if not _RUN_ID.fullmatch(run_id):
        raise ValueError("无效桥接任务 ID")
    return _STATE_DIR / f"{run_id}.events.jsonl"


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _save_session(session: dict[str, Any]) -> None:
    _atomic_json(_session_path(session["run_id"]), session)


def _load_session(run_id: str) -> dict[str, Any]:
    path = _session_path(run_id)
    if not path.exists():
        raise ValueError("桥接任务不存在")
    return json.loads(path.read_text(encoding="utf-8"))


def _digest(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _observation_key(url: str) -> str:
    stable = normalize_url(url) or url
    return "boss:" + hashlib.sha256(stable.encode("utf-8")).hexdigest()[:20]


def _emit(run_id: str, event: str, **payload: Any) -> dict[str, Any]:
    value = {"event": event, "platform": "boss", "observed_at": _now(), **payload}
    path = _event_path(run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, default=str) + "\n")
    return value


def _history_task(session: dict[str, Any]) -> dict[str, Any]:
    summary = {
        key: session.get(key)
        for key in (
            "listed", "details", "detail_attempted", "detail_obtained", "content_eligible",
            "identity_pending", "identity_verified", "complete", "inserted", "updated",
            "new", "skipped", "rejected", "failed", "unattempted",
        )
    }
    return {
        **session,
        "pid": None,
        "next_run_at": None,
        "database_new_count": session.get("inserted", 0),
        "quality_metrics_available": True,
        "identity_metrics_available": True,
        "log_path": str(_session_path(session["run_id"])),
        "log_status": "parsed",
        "log_summary": summary,
        "raw_log_tail": list(session.get("event_tail") or [])[-30:],
    }


def _sync_history(session: dict[str, Any]) -> None:
    control.upsert_external_task(_history_task(session))


def _empty_session(payload: BridgeSessionCreate) -> dict[str, Any]:
    return {
        "run_id": f"bridge-{uuid.uuid4().hex}",
        "platform": payload.platform,
        "mode": "bridge",
        "status": "waiting_for_capture",
        "keywords": [payload.keyword],
        "cities": [{"name": payload.city_name, "code": payload.city_code}],
        "current_keyword": payload.keyword,
        "current_city": payload.city_name,
        "pages": payload.pages,
        "detail_limit": payload.detail_limit,
        "max_jobs": payload.max_jobs,
        "started_at": _now(),
        "updated_at": _now(),
        "finished_at": None,
        "stop_reason": None,
        "last_error": None,
        "browser_page_status": "user_managed",
        "cdp_status": "not_used",
        "listed": 0,
        "details": 0,
        "detail_attempted": 0,
        "detail_obtained": 0,
        "content_eligible": 0,
        "identity_pending": 0,
        "identity_verified": 0,
        "complete": 0,
        "inserted": 0,
        "updated": 0,
        "new": 0,
        "skipped": 0,
        "rejected": 0,
        "failed": 0,
        "unattempted": 0,
        "rejection_reasons": {},
        "list_items": [],
        "list_urls": [],
        "detail_urls": [],
        "detail_results": {},
        "captures": {},
        "event_tail": [],
    }


def create_session(payload: dict[str, Any]) -> dict[str, Any]:
    parsed = BridgeSessionCreate.model_validate(payload)
    status = control.get_status()
    if not status.get("finished_at") and status.get("status") in {
        "preparing", "waiting_for_browser", "running", "stopping", "waiting_next_round",
    }:
        raise RuntimeError("已有采集任务正在运行")
    session = _empty_session(parsed)
    with _LOCK:
        _save_session(session)
        _sync_history(session)
    return {"run_id": session["run_id"], "session": session}


def get_session(run_id: str) -> dict[str, Any]:
    with _LOCK:
        return _load_session(run_id)


def list_sessions(limit: int = 20) -> list[dict[str, Any]]:
    with _LOCK:
        if not _SESSIONS_DIR.exists():
            return []
        sessions = []
        for path in _SESSIONS_DIR.glob("bridge-*.json"):
            try:
                sessions.append(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, ValueError):
                continue
    sessions.sort(key=lambda item: str(item.get("started_at") or ""), reverse=True)
    return sessions[:limit]


def _record_tail(session: dict[str, Any], kind: str, detail: str = "") -> None:
    line = f"{session['updated_at']} {kind}{(': ' + detail) if detail else ''}"
    session["event_tail"] = [*(session.get("event_tail") or []), line][-30:]


def _list_result(session: dict[str, Any], capture: BridgeCapture) -> dict[str, Any]:
    previous = {item["url"]: item for item in session.get("list_items") or []}
    for item in capture.items:
        value = item.model_dump(mode="json")
        previous[value["url"]] = value
    items = list(previous.values())[: int(session["max_jobs"])]
    jobs = [
        {**item, "_observation_key": _observation_key(item["url"]), "_list_url": capture.page_url}
        for item in items
    ]
    session["list_items"] = items
    session["list_urls"] = [item["url"] for item in items]
    session["listed"] = len(items)
    session["unattempted"] = max(0, len(items) - int(session.get("detail_attempted") or 0))
    _emit(session["run_id"], "listed", jobs=jobs)
    _record_tail(session, "listed", str(len(items)))
    return {"outcome": "listed", "listed": len(items)}


def _reject(session: dict[str, Any], reason: str) -> dict[str, Any]:
    session["rejected"] = int(session.get("rejected") or 0) + 1
    reasons = session.setdefault("rejection_reasons", {})
    reasons[reason] = int(reasons.get(reason, 0) or 0) + 1
    return {"outcome": "rejected", "reason": reason}


def _detail_rejection(job: dict[str, Any], detail: dict[str, Any]) -> str | None:
    if detail.get("challenge_detected"):
        return "security_verification"
    if not str(detail.get("description") or "").strip():
        return "empty_detail"
    if detail.get("description_truncated"):
        return "truncated_description"
    if " ".join(str(detail.get("title") or "").split()) != " ".join(str(job.get("title") or "").split()):
        return "title_mismatch"
    if normalize_url(str(detail.get("url") or "")) != normalize_url(str(job.get("url") or "")):
        return "identity_mismatch"
    raw = normalize_boss_job(job, detail)
    if raw is None or not is_valid_jd(clean(raw)):
        return "invalid_detail_body"
    return None


def _database_provider():
    from app.db.mysql import get_db
    return get_db()


_get_db = _database_provider


def _persist_detail(
    session: dict[str, Any],
    capture: BridgeCapture,
    job: dict[str, Any],
    detail: dict[str, Any],
    evidence: dict[str, Any],
) -> dict[str, Any]:
    provider = _get_db()
    db = next(provider)
    saved: dict[str, Any] = {}
    persisted_events: list[dict[str, Any]] = []
    try:
        raw = normalize_boss_job(job, detail)
        if raw is None:
            raise ValueError("invalid_detail_body")
        capabilities = schema_capabilities(db)
        if all(capabilities.values()):
            raw.identity_status = "verified"
            raw.content_eligible = True
            raw.identity_evidence = json.dumps(evidence, ensure_ascii=False, sort_keys=True)
        raw.observation_key = job["_observation_key"]

        def on_saved(item: dict[str, Any]) -> None:
            nonlocal saved
            saved = dict(item)
            saved.update(
                identity_status="verified",
                content_eligible=True,
                identity_evidence=evidence,
                observation_key=job["_observation_key"],
                job_title=job.get("title"),
                crawled_at=_now(),
            )
            persisted_events.append(saved)
            _emit(session["run_id"], "persisted", items=[saved])

        def saver(transaction, rows):
            return save_incremental_jd_rows(
                transaction,
                rows,
                created_ids=set(),
                on_saved=on_saved,
            )

        result = run_pipeline(db, [raw], jd_saver=saver)
        if not persisted_events:
            raise RuntimeError("valid_detail_not_persisted")
        outcome = str(saved.get("outcome") or "")
        counter = outcome if outcome in {"inserted", "updated", "skipped"} else "failed"
        session[counter] = int(session.get(counter) or 0) + 1
        session["new"] = session["inserted"]
        session["detail_results"][normalize_url(str(detail["url"]))] = {
            "outcome": outcome,
            "jd_pool_id": saved.get("jd_pool_id"),
        }
        _record_tail(session, "persisted", outcome)
        return {
            "outcome": outcome,
            "jd_pool_id": saved.get("jd_pool_id"),
            "saved": result.get("jd_saved", 0),
        }
    except Exception:
        db.rollback()
        raise
    finally:
        provider.close()


def _detail_result(session: dict[str, Any], capture: BridgeCapture) -> dict[str, Any]:
    detail = capture.detail
    if detail is None:
        raise ValueError("detail capture missing detail")
    payload = detail.model_dump(mode="json")
    stable_url = normalize_url(str(payload["url"]))
    existing = session.get("detail_results", {}).get(stable_url)
    if existing:
        session["skipped"] = int(session.get("skipped") or 0) + 1
        skipped = {**existing, "outcome": "skipped"}
        _emit(session["run_id"], "persisted", items=[{
            **skipped,
            "source_detail": stable_url,
            "job_title": payload.get("title"),
            "identity_status": "verified",
            "content_eligible": True,
            "observation_key": _observation_key(stable_url),
            "outcome": "skipped",
        }])
        _record_tail(session, "persisted", "duplicate_detail_url")
        return skipped

    detail_urls = list(session.get("detail_urls") or [])
    if stable_url not in detail_urls:
        if len(detail_urls) >= int(session["detail_limit"]):
            return _reject(session, "bridge_session_limit_reached")
        detail_urls.append(stable_url)
        session["detail_urls"] = detail_urls
        session["detail_attempted"] = int(session.get("detail_attempted") or 0) + 1
        session["details"] = session["detail_attempted"]
        session["unattempted"] = max(0, int(session.get("listed") or 0) - session["detail_attempted"])

    listed = next(
        (item for item in session.get("list_items") or [] if normalize_url(item["url"]) == stable_url),
        {},
    )
    job = {
        **listed,
        "url": stable_url,
        "title": listed.get("title") or payload.get("title"),
        "_observation_key": _observation_key(stable_url),
    }
    observed_at = _now()
    _emit(session["run_id"], "detail_attempt", job=job)
    if str(payload.get("description") or "").strip():
        session["detail_obtained"] = int(session.get("detail_obtained") or 0) + 1

    reason = _detail_rejection(job, payload)
    content_eligible = reason is None
    identity_status = "verified" if content_eligible else "unknown"
    evidence = {
        "strategy": "source_url",
        "platform": "boss",
        "job_url": stable_url,
        "detail_url": stable_url,
        "observed_at": observed_at,
    } if content_eligible else {}
    _emit(
        session["run_id"],
        "detail",
        job=job,
        detail=payload,
        rejection=reason,
        identity_status=identity_status,
        content_eligible=content_eligible,
        identity_evidence=evidence,
        observed_at=observed_at,
    )

    if reason:
        result = _reject(session, reason)
        _record_tail(session, "rejected", reason)
        return result

    session["content_eligible"] = int(session.get("content_eligible") or 0) + 1
    session["identity_verified"] = int(session.get("identity_verified") or 0) + 1
    session["complete"] = int(session.get("complete") or 0) + 1
    try:
        return _persist_detail(session, capture, job, payload, evidence)
    except Exception as exc:
        session["failed"] = int(session.get("failed") or 0) + 1
        session["last_error"] = str(exc)
        session["stop_reason"] = str(exc)
        _emit(session["run_id"], "failure", job=job, reason=str(exc))
        _record_tail(session, "failure", str(exc))
        return {"outcome": "failed", "reason": str(exc)}


def append_capture(run_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    capture = validate_capture(payload)
    normalized = capture.model_dump(mode="json")
    digest = _digest(normalized)
    with _LOCK:
        session = _load_session(run_id)
        if session.get("finished_at"):
            raise ValueError("桥接任务已结束")
        previous = (session.get("captures") or {}).get(digest)
        if previous:
            return {"duplicate": True, "result": previous, "session": session}
        if capture.kind == "list":
            result = _list_result(session, capture)
        else:
            result = _detail_result(session, capture)
        session["captures"][digest] = result
        session["status"] = "waiting_for_capture"
        session["updated_at"] = _now()
        _save_session(session)
        _sync_history(session)
        return {"duplicate": False, "result": result, "session": session}


def finish_session(run_id: str, reason: str | None = None) -> dict[str, Any]:
    with _LOCK:
        session = _load_session(run_id)
        if session.get("finished_at"):
            return session
        session["finished_at"] = _now()
        session["updated_at"] = session["finished_at"]
        session["stop_reason"] = reason
        session["status"] = "stopped" if reason else "completed"
        stats = {
            key: session.get(key)
            for key in (
                "listed", "details", "detail_attempted", "detail_obtained", "content_eligible",
                "identity_pending", "identity_verified", "complete", "inserted", "updated",
                "new", "skipped", "rejected", "failed", "unattempted", "rejection_reasons", "stop_reason",
            )
        }
        _emit(run_id, "finished", stats=stats)
        _record_tail(session, "finished", str(session["status"]))
        _save_session(session)
        _sync_history(session)
        return session

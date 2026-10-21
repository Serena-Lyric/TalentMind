"""Explicit normal-browser capture lifecycle and pairing API."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, Request

from app.collect import bridge
from app.collect.bridge_access import EXTENSION_ID, get_bridge_token, require_bridge_access, require_bridge_management
from app.response import BizError, ok

router = APIRouter()


def _biz_call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except (ValueError, RuntimeError) as exc:
        raise BizError(4001, str(exc)) from exc


@router.get("/collection/bridge/pairing")
def bridge_pairing(request: Request):
    require_bridge_management(request)
    extension = Path(__file__).resolve().parents[3] / "frontend" / "bridge-extension"
    return ok({
        "extension_id": EXTENSION_ID,
        "extension_path": str(extension),
        "token": get_bridge_token(),
        "sessions": bridge.list_sessions(),
    })


@router.post("/collection/bridge/sessions")
def bridge_session_create(request: Request, payload: dict[str, Any] = Body(...)):
    require_bridge_management(request)
    return ok(_biz_call(bridge.create_session, payload))


@router.get("/collection/bridge/sessions")
def bridge_session_list(request: Request):
    require_bridge_management(request)
    return ok({"items": bridge.list_sessions()})


@router.get("/collection/bridge/sessions/{session_id}")
def bridge_session_get(session_id: str, request: Request):
    require_bridge_management(request)
    return ok(_biz_call(bridge.get_session, session_id))


@router.post("/collection/bridge/sessions/{session_id}/captures")
def bridge_session_capture(session_id: str, request: Request, payload: dict[str, Any] = Body(...)):
    require_bridge_access(request)
    return ok(_biz_call(bridge.append_capture, session_id, payload))


@router.post("/collection/bridge/sessions/{session_id}/finish")
def bridge_session_finish(session_id: str, request: Request, payload: dict[str, Any] = Body(default={})):
    require_bridge_management(request)
    reason = str(payload.get("reason") or "").strip() or None
    return ok(_biz_call(bridge.finish_session, session_id, reason))

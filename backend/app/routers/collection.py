"""M1 采集模块管理 API。

API 只做任务生命周期与状态展示的薄封装，采集逻辑仍位于 app.collect。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Query

from app.collect import control
from app.response import BizError, ok

router = APIRouter()


def _biz_call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except (ValueError, RuntimeError) as exc:
        raise BizError(4001, str(exc)) from exc


@router.get("/collection/status")
def collection_status():
    return ok(control.get_status())


@router.get("/collection/progress")
def collection_progress():
    return ok(control.get_status())


@router.get("/collection/cdp-status")
def collection_cdp_status():
    config = control.get_config()
    return ok(control.get_cdp_status(config.get("cdp_endpoint"), config.get("user_data_dir")))


@router.post("/collection/prepare")
def collection_prepare(payload: dict[str, Any] = Body(default={} )):
    return ok(control.prepare_browser(auto_start=bool(payload.get("auto_start", False)), platform=payload.get("platform")))


@router.get("/collection/database-stats")
def collection_database_stats():
    return ok(control.get_database_stats())


@router.get("/collection/stats")
def collection_stats():
    return ok(control.get_database_stats())


@router.get("/collection/history")
def collection_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str = Query(""),
    mode: str = Query(""),
    platform: str = Query(""),
):
    return ok(control.get_history(page, page_size, status, mode, platform))


@router.get("/collection/config")
def collection_config():
    return ok(control.get_config())


@router.put("/collection/config")
def collection_config_update(payload: dict[str, Any] = Body(...)):
    return ok(_biz_call(control.update_config, payload))


@router.post("/collection/start")
def collection_start(payload: dict[str, Any] = Body(default={} )):
    return ok(_biz_call(control.start_task, payload))


@router.post("/collection/stop")
def collection_stop(payload: dict[str, Any] = Body(default={} )):
    return ok(_biz_call(control.stop_task, payload.get("run_id")))
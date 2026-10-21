"""M1 采集模块管理 API。

API 只做任务生命周期与状态展示的薄封装，采集逻辑仍位于 app.collect。
"""
from __future__ import annotations

from typing import Any
import os
from urllib.parse import urlsplit

from fastapi import APIRouter, Body, Query, Request, HTTPException

from app.collect import batch, control
from app.response import BizError, ok

router = APIRouter()


def _require_local_raw(request: Request) -> None:
    local = {'127.0.0.1', '::1', 'localhost'}
    host = urlsplit('http://' + request.headers.get('host', '')).hostname
    origin = request.headers.get('origin')
    origin_url = urlsplit(origin) if origin else None
    if (os.environ.get('TALENTMIND_LOCAL_RAW') != '1' or not request.client
            or request.client.host not in {'127.0.0.1', '::1'} or host not in local
            or (origin_url is not None and (origin_url.scheme not in {'http', 'https'} or origin_url.hostname not in local))
            or request.headers.get('sec-fetch-site') == 'cross-site'):
        raise HTTPException(status_code=403, detail='仅允许已启用的本地原文访问')


@router.get('/collection/platforms')
def collection_platforms():
    return ok(control.get_platforms())


@router.get('/collection/results')
def collection_results(request: Request, run_id: str = Query(...)):
    _require_local_raw(request)
    return ok(_biz_call(control.get_results, run_id))


@router.get('/collection/raw/{raw_id}')
def collection_raw(raw_id: int, request: Request):
    _require_local_raw(request)
    result = control.get_raw(raw_id)
    if result is None:
        raise HTTPException(status_code=404, detail='原始 JD 不存在')
    return ok(result)


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
    return ok(_biz_call(control.prepare_browser, auto_start=bool(payload.get("auto_start", False)),
                        platform=payload.get("platform"),
                        config_payload={key: value for key, value in payload.items() if key != 'auto_start'}))


@router.get("/collection/database-stats")
def collection_database_stats():
    return ok(control.get_database_stats())


@router.get("/collection/stats")
def collection_stats():
    return ok(control.get_database_stats())


@router.get("/collection/recent")
def collection_recent(limit: int = Query(10, ge=1, le=50)):
    return ok(control.get_recent_raw(limit))


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
    stopped = _biz_call(batch.stop_active)
    if stopped is not None:
        return ok(stopped)
    return ok(_biz_call(control.stop_task, payload.get("run_id")))


@router.post('/collection/batches')
def collection_batch_create(payload: dict[str, Any] = Body(...)):
    return ok(_biz_call(batch.create_batch, payload))


@router.get('/collection/batches')
def collection_batch_list():
    return ok(_biz_call(batch.list_batches))


@router.get('/collection/batches/{batch_id}')
def collection_batch_get(batch_id: str):
    return ok(_biz_call(batch.get_batch, batch_id))


@router.get('/collection/batches/{batch_id}/items/{item_id}/task')
def collection_batch_item_task(batch_id: str, item_id: str, request: Request):
    _require_local_raw(request)
    return ok(_biz_call(batch.get_item_task, batch_id, item_id))


@router.post('/collection/batches/{batch_id}/start')
def collection_batch_start(batch_id: str):
    return ok(_biz_call(batch.start_batch, batch_id))


@router.post('/collection/batches/{batch_id}/stop')
def collection_batch_stop(batch_id: str):
    return ok(_biz_call(batch.stop_batch, batch_id))

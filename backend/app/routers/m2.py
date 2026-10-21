"""Explicit localhost-only M2 tasks; demo login grants no backend access."""
from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from app.response import ok
from app.job_analysis.product import source
from app.job_analysis.product.workflow import Workflow
from .collection import _require_local_raw


def local_access(request: Request, response: Response):
    _require_local_raw(request)
    response.headers['Cache-Control'] = 'no-store'


router = APIRouter(prefix='/m2', dependencies=[Depends(local_access)])


@lru_cache
def get_workflow():
    return Workflow(source.ROOT / 'data/local/m2-product')


def call(fn, *args):
    try:
        return ok(fn(*args))
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from None
    except Exception:
        raise HTTPException(503, 'M2 本地数据服务不可用，请检查数据库连接或私有运行目录') from None


class Replay(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    revision: str = Field(default='v1', pattern=r'^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$')


@router.get('/sources')
def sources():
    return call(source.available_sources)


@router.post('/runs')
def create(payload: source.Selection):
    return call(get_workflow().create, payload)


@router.get('/runs')
def history():
    return call(get_workflow().list_runs)


@router.get('/runs/{run_id}')
def get_run(run_id: str):
    return call(get_workflow().get, run_id)


@router.get('/runs/{run_id}/items/{ordinal}')
def item(run_id: str, ordinal: int):
    return call(get_workflow().item, run_id, ordinal)


@router.post('/runs/{run_id}/start')
def start(run_id: str):
    return call(get_workflow().start, run_id)


@router.post('/runs/{run_id}/stop')
def stop(run_id: str):
    return call(get_workflow().stop, run_id)


@router.post('/runs/{run_id}/replay')
def replay(run_id: str, payload: Replay):
    return call(get_workflow().replay, run_id, payload.revision)


@router.get('/runs/{run_id}/report')
def report(run_id: str):
    return call(get_workflow().report, run_id)

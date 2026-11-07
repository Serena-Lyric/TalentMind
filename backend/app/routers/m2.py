"""Explicit localhost-only M2 tasks; demo login grants no backend access."""
from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from app.response import ok
from app.job_analysis.product import source
from app.job_analysis.product.workflow import History
from app.job_analysis.delivery.http_service import DeliveryService, available_inputs
from app.job_analysis.delivery.maintenance import Maintenance, WorkCommand, SkillCommand, CloseCommand
from .collection import _require_local_raw


def local_access(request: Request, response: Response):
    _require_local_raw(request)
    response.headers['Cache-Control'] = 'no-store'


router = APIRouter(prefix='/m2', dependencies=[Depends(local_access)])


@lru_cache
def get_workflow():
    return History(source.ROOT / 'data/local/m2-product')


def call(fn, *args):
    try:
        return ok(fn(*args))
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from None
    except Exception:
        raise HTTPException(503, 'M2 本地数据服务不可用，请检查数据库连接或私有运行目录') from None


@lru_cache
def get_delivery():
    private = source.ROOT / 'data/local'
    return DeliveryService(private / 'm2-delivery', history_roots=[
        private / 'm2-p5-p6-20261107' / name / 'state'
        for name in ('sequence-head-final', 'dev-head-final')])


class Selection(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    jd_ids: list[int] = Field(min_length=1, max_length=100)


@router.get('/delivery/candidates/work')
def work_candidates(revision: int | None = Query(None, ge=0)):
    return call(Maintenance(get_delivery()).work, revision)


@router.get('/delivery/candidates/pending')
def pending_maintenance():
    return call(Maintenance(get_delivery()).pending)


@router.post('/delivery/candidates/pending/{request_id}/resume')
def resume_maintenance(request_id: str):
    return call(Maintenance(get_delivery()).recover, request_id)


@router.post('/delivery/candidates/pending/{request_id}/close')
def close_maintenance(request_id: str, payload: CloseCommand):
    return call(Maintenance(get_delivery()).close, request_id, payload.reason)


@router.post('/delivery/candidates/work/batches')
def maintain_work(payload: WorkCommand):
    return call(Maintenance(get_delivery()).update_work, payload.model_dump())


@router.get('/delivery/candidates/skills')
def skill_candidates():
    return call(Maintenance(get_delivery()).skills)


@router.get('/delivery/candidates/skills/{candidate_id}')
def skill_candidate(candidate_id: str, version: int | None = Query(None, ge=1)):
    return call(Maintenance(get_delivery()).skill, candidate_id, version)


@router.post('/delivery/candidates/skills/{candidate_id}/actions')
def maintain_skill(candidate_id: str, payload: SkillCommand):
    return call(Maintenance(get_delivery()).update_skill, candidate_id, payload.model_dump())


@router.get('/delivery/inputs')
def inputs(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    return call(available_inputs, limit, offset)


@router.get('/delivery/compare')
def compare(before_run: str, after_run: str):
    from app.job_analysis.delivery.comparison import compare_runs
    def read_comparison():
        service = get_delivery()
        return compare_runs(service.get(before_run), service.get(after_run))
    return call(read_comparison)


@router.post('/delivery/runs')
def create(payload: Selection):
    return call(get_delivery().create, payload.jd_ids)


@router.get('/delivery/runs')
def delivery_history():
    return call(get_delivery().list_runs)


@router.get('/delivery/runs/{run_id}')
def delivery_run(run_id: str):
    return call(get_delivery().get, run_id)


@router.get('/delivery/runs/{run_id}/items/{index}')
def delivery_item(run_id: str, index: int):
    return call(get_delivery().item, run_id, index)


@router.post('/delivery/runs/{run_id}/start')
@router.post('/delivery/runs/{run_id}/resume')
def start(run_id: str):
    return call(get_delivery().start, run_id)


@router.post('/delivery/runs/{run_id}/stop')
def stop(run_id: str):
    return call(get_delivery().stop, run_id)


@router.post('/delivery/runs/{run_id}/abandon')
def abandon(run_id: str):
    return call(get_delivery().abandon, run_id)


@router.get('/delivery/runs/{run_id}/graph')
def delivery_graph(run_id: str):
    from app.graph.delivery_bundle import graph_info
    return call(graph_info, get_delivery(), run_id)


@router.get('/delivery/runs/{run_id}/graph/{name}')
def delivery_graph_artifact(run_id: str, name: str, snapshot: str = Query(..., pattern=r'^[a-f0-9]{64}$')):
    from app.graph.delivery_bundle import read_bundle
    result = call(read_bundle, get_delivery(), run_id, name, snapshot)
    return Response(result['data'], media_type='application/json', headers={'Cache-Control': 'no-store'})


@router.get('/runs')
def history():
    return call(get_workflow().list_runs)


@router.get('/runs/{run_id}')
def get_run(run_id: str):
    return call(get_workflow().get, run_id)


@router.get('/runs/{run_id}/items/{ordinal}')
def item(run_id: str, ordinal: int):
    return call(get_workflow().item, run_id, ordinal)


@router.get('/runs/{run_id}/reviews/export')
def review_export(run_id: str):
    return call(get_workflow().review_export, run_id)


@router.get('/runs/{run_id}/report')
def report(run_id: str):
    return call(get_workflow().report, run_id)


@router.get('/runs/{run_id}/graph')
def graph(run_id: str):
    from app.graph.product_bundle import graph_info
    return call(graph_info, get_workflow(), run_id)


@router.get('/runs/{run_id}/graph/{name}')
def graph_artifact(run_id: str, name: str):
    from app.graph.product_bundle import read_bundle
    from app.job_analysis.foundation.inputs import canonical
    result = call(read_bundle, get_workflow(), run_id, name)
    return Response(canonical(result['data']) + '\n', media_type='application/json', headers={'Cache-Control': 'no-store'})

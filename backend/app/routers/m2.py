"""Explicit localhost-only M2 tasks; demo login grants no backend access."""
from functools import lru_cache
from typing import Literal

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


class HumanScopeAnnotation(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    scope_status: Literal['in_scope', 'out_of_scope', 'needs_review', 'not_applicable']
    note: str = Field(default='', max_length=1000)


class HumanSkillStatementAnnotation(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    statement_id: str = Field(min_length=1, max_length=80)
    skill_ids: list[str] = Field(default_factory=list, max_length=20)
    human_state: Literal['required', 'preferred', 'mentioned', 'not_required', 'uncertain', 'not_skill']
    note: str = Field(default='', max_length=1000)


class HumanCategoryAnnotation(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    family_id: str = Field(min_length=1, max_length=80)
    human_decision: Literal['accepted', 'rejected', 'needs_followup']
    note: str = Field(default='', max_length=1000)


class HumanAnnotations(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    b1_scope: HumanScopeAnnotation | None = None
    b2_statements: list[HumanSkillStatementAnnotation] = Field(default_factory=list, max_length=200)
    b3_categories: list[HumanCategoryAnnotation] = Field(default_factory=list, max_length=50)


class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    decision: Literal['accepted', 'rejected', 'needs_followup']
    reviewer: str = Field(min_length=1, max_length=80)
    note: str = Field(default='', max_length=4000)
    machine_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    annotations: HumanAnnotations | None = None


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


@router.post('/runs/{run_id}/items/{ordinal}/review')
def review(run_id: str, ordinal: int, payload: ReviewRequest):
    def submit():
        workflow = get_workflow()
        workflow.review(run_id, ordinal, payload.model_dump())
        return workflow.item(run_id, ordinal)
    return call(submit)


@router.get('/runs/{run_id}/reviews/export')
def review_export(run_id: str):
    return call(get_workflow().review_export, run_id)


@router.post('/runs/{run_id}/replay')
def replay(run_id: str, payload: Replay):
    return call(get_workflow().replay, run_id, payload.revision)


@router.get('/runs/{run_id}/report')
def report(run_id: str):
    return call(get_workflow().report, run_id)


@router.post('/runs/{run_id}/graph')
def generate_graph(run_id: str):
    from app.graph.product_bundle import graph_info
    return call(graph_info, get_workflow(), run_id, True)


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

"""Local access gates are enforced before any JD read or task mutation."""
import importlib
import shutil

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def api(monkeypatch, tmp_path):
    assert importlib.util.find_spec('app.routers.m2'), 'M2 API missing'
    from app.routers import m2
    from app.job_analysis.product.workflow import Workflow
    engine = Workflow(tmp_path / 'api')
    monkeypatch.setattr(m2, 'get_workflow', lambda: engine)
    monkeypatch.setenv('TALENTMIND_LOCAL_RAW', '1')
    app = FastAPI()
    app.include_router(m2.router, prefix='/api')
    @app.middleware('http')
    async def fixture_peer(request, call_next):
        request.scope['client'] = ('127.0.0.1', 123)
        return await call_next(request)
    with TestClient(app, base_url='http://localhost') as client:
        yield client, m2, engine
    engine.join(10)
    assert not engine.busy
    shutil.rmtree(engine.root)
    assert not engine.root.exists()


@pytest.mark.parametrize('path,method,payload', [
    ('sources','GET',None), ('runs','GET',None), ('runs','POST',{}),
    ('runs/'+'a'*32,'GET',None), ('runs/'+'a'*32+'/items/1','GET',None),
    ('runs/'+'a'*32+'/items/1/review','POST',{}),
    ('runs/'+'a'*32+'/reviews/export','GET',None),
    ('runs/'+'a'*32+'/start','POST',{}), ('runs/'+'a'*32+'/stop','POST',{}),
    ('runs/'+'a'*32+'/replay','POST',{}), ('runs/'+'a'*32+'/report','GET',None),
    ('runs/'+'a'*32+'/graph','POST',{}), ('runs/'+'a'*32+'/graph','GET',None),
    ('runs/'+'a'*32+'/graph/facts.json','GET',None),
])
def test_all_m2_routes_gate_origin_before_io(api, monkeypatch, path, method, payload):
    client, m2, _ = api
    monkeypatch.setattr(m2, 'get_workflow', lambda: pytest.fail('unauthorized IO'))
    result = client.request(method, '/api/m2/' + path, json=payload, headers={'Origin':'https://evil.example'})
    assert result.status_code == 403


@pytest.mark.parametrize('headers,enabled', [({'Host':'evil.example'},'1'), ({'Sec-Fetch-Site':'cross-site'},'1'), ({},'0')])
def test_host_fetch_site_and_explicit_local_switch(api, monkeypatch, headers, enabled):
    client, _, _ = api
    monkeypatch.setenv('TALENTMIND_LOCAL_RAW', enabled)
    assert client.get('/api/m2/runs', headers=headers).status_code == 403


def test_api_create_does_not_start_and_validation_is_bounded(api, monkeypatch):
    client, m2, engine = api
    monkeypatch.setattr(m2.source, 'read_mysql', lambda _: ([dict(id=7, source='boss',job_title='后端工程师',raw_text='必须掌握 Python')], {'kind':'synthetic'}))
    response = client.post('/api/m2/runs', json={'limit':1})
    assert response.status_code == 200
    draft = response.json()['data']
    assert draft['status'] == 'queued' and not engine.busy
    assert response.headers['cache-control'] == 'no-store'
    assert client.post('/api/m2/runs', json={'limit':99999}).status_code == 422
    run_id = draft['run_id']
    assert client.get(f'/api/m2/runs/{run_id}/items/1').json()['data']['input']['id'] == 7
    assert client.post(f'/api/m2/runs/{run_id}/start', json={}).status_code == 200
    engine.join(10)
    report = client.get(f'/api/m2/runs/{run_id}/report').json()['data']
    assert report['summary']['input_total'] == 1
    assert report['summary']['stage_complete'] == 1


def test_review_api_binds_machine_result_and_exports_human_events(api, monkeypatch):
    client, m2, engine = api
    monkeypatch.setattr(m2.source, 'read_mysql', lambda _: ([dict(
        id=7,
        source='boss',
        job_title='后端工程师',
        raw_text='岗位职责：负责软件开发。\n任职要求：熟悉 Python。',
        duties=None,
        experience=None,
    )], {'kind':'synthetic'}))
    run_id = client.post('/api/m2/runs', json={'limit':1}).json()['data']['run_id']
    assert client.post(f'/api/m2/runs/{run_id}/items/1/review', json={
        'decision': 'accepted',
        'reviewer': 'human-reviewer',
        'note': '',
        'machine_sha256': '0' * 64,
    }).status_code == 400
    assert client.post(f'/api/m2/runs/{run_id}/start', json={}).status_code == 200
    engine.join(20)
    detail = client.get(f'/api/m2/runs/{run_id}/items/1').json()['data']
    response = client.post(f'/api/m2/runs/{run_id}/items/1/review', json={
        'decision': 'needs_followup',
        'reviewer': 'human-reviewer',
        'note': '需要人工核对组合要求',
        'machine_sha256': detail['machine_sha256'],
        'annotations': {
            'b1_scope': {'scope_status': 'in_scope', 'note': '人工核对范围'},
            'b2_statements': [{
                'statement_id': detail['stages']['b22']['result']['body']['skills'][0]['statement_ids'][0],
                'skill_ids': [detail['stages']['b22']['result']['body']['skills'][0]['id']],
                'human_state': 'uncertain',
                'note': '组合条件仍需确认',
            }],
            'b3_categories': [{
                'family_id': 'software_engineering',
                'human_decision': 'needs_followup',
                'note': '大类边界待定',
            }],
        },
    })
    assert response.status_code == 200
    reviewed = response.json()['data']
    assert reviewed['human_review']['reviewer'] == 'human-reviewer'
    assert reviewed['human_review']['human_annotations']['b1_scope']['scope_status'] == 'in_scope'
    assert reviewed['human_review']['human_annotations']['b2_statements'][0]['human_state'] == 'uncertain'
    assert reviewed['human_review']['human_annotations']['b3_categories'][0]['family_id'] == 'software_engineering'
    assert reviewed['stages'] == detail['stages']
    assert response.headers['cache-control'] == 'no-store'

    exported = client.get(f'/api/m2/runs/{run_id}/reviews/export')
    assert exported.status_code == 200
    payload = exported.json()['data']
    assert payload['schema_version'] == 'm2-human-review-export-1'
    assert payload['items'][0]['input']['id'] == 7
    assert payload['reviews'][0]['decision'] == 'needs_followup'
    assert exported.headers['cache-control'] == 'no-store'


def test_graph_artifacts_are_run_bound_and_local_only(api, monkeypatch):
    import hashlib
    client, m2, engine = api
    monkeypatch.setattr(m2.source, 'read_mysql', lambda _: ([dict(id=7, source='boss', job_title='后端工程师', raw_text='负责软件开发，必须掌握 Python')], {'kind':'synthetic'}))
    run_id = client.post('/api/m2/runs', json={'limit':1}).json()['data']['run_id']
    assert client.post(f'/api/m2/runs/{run_id}/graph').status_code == 400
    engine.start(run_id)
    engine.join(20)
    info = client.post(f'/api/m2/runs/{run_id}/graph').json()['data']
    assert info['manifest']['m2_product']['run_id'] == run_id
    response = client.get(f'/api/m2/runs/{run_id}/graph/manifest.json')
    assert response.status_code == 200
    assert hashlib.sha256(response.content).hexdigest() == info['manifest_sha256']
    assert response.headers['cache-control'] == 'no-store'
    assert client.get(f'/api/m2/runs/{run_id}/graph/facts.json').json()['nodes']
    assert client.get(f'/api/m2/runs/{run_id}/graph/workflow.sqlite3').status_code == 400
    assert client.get(f'/api/m2/runs/{run_id}/graph/facts.json', headers={'Origin':'https://evil.example'}).status_code == 403

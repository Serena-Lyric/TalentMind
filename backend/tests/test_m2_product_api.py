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
    ('runs/'+'a'*32+'/start','POST',{}), ('runs/'+'a'*32+'/stop','POST',{}),
    ('runs/'+'a'*32+'/replay','POST',{}), ('runs/'+'a'*32+'/report','GET',None),
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

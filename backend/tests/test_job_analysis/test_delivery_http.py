import asyncio
from copy import deepcopy

import pytest

from test_foundation_inputs import area
from test_understanding import ROW, draft
from test_understanding_pipeline import Fixture, response


def service(area, factory=None):
    from app.job_analysis.delivery.http_service import DeliveryService
    rows = [dict(ROW, id=1), dict(ROW, id=2)]
    value = draft()
    value['claims'][0]['core'] = True
    return DeliveryService(area / 'delivery', processor_factory=factory or (lambda: Fixture([response(value)])),
                           select_rows=lambda ids: [deepcopy(r) for r in rows if r['id'] in ids])


def test_http_service_freezes_selection_executes_delivery_and_reads_exact_history(area):
    engine = service(area)
    assert engine.list_runs() == []
    run = engine.create([2])
    assert run['status'] == 'prepared'
    assert [i['jd_id'] for i in run['items']] == ['2']
    assert run['items'][0]['input']['raw_text'] == ROW['raw_text']
    engine.start(run['run_id'])
    engine.join(10)
    result = engine.get(run['run_id'])
    assert result['status'] == 'completed'
    assert result['items'][0]['analysis']['jd_id'] == '2'
    assert result['items'][0]['analysis']['namespace'] == 'mysql-jd_pool'
    assert result['request_sha256'] == run['request_sha256']
    assert result['work']['candidates']
    assert engine.get(run['run_id']) == result
    assert engine.list_runs()[0]['run_id'] == run['run_id']


def test_selection_rejects_missing_duplicate_or_ineligible_inputs(area):
    engine = service(area)
    for ids in ([], [1, 1], [99]):
        with pytest.raises(ValueError): engine.create(ids)
    engine.select_rows = lambda ids: [dict(ROW, id=1, content_eligible=False)]
    with pytest.raises(ValueError, match='ineligible'): engine.create([1])


def test_stopped_run_resumes_exact_frozen_input_and_cannot_accept_changed_processor(area):
    engine = service(area)
    run = engine.create([1])
    stopped = engine.stop(run['run_id'])
    assert stopped['status'] == 'stopped'
    changed = Fixture([])
    changed.descriptor = dict(changed.descriptor, model_revision='changed')
    engine.processor_factory = lambda: changed
    with pytest.raises(ValueError, match='processor'): engine.start(run['run_id'])
    engine.processor_factory = lambda: Fixture([response(draft())])
    engine.start(run['run_id'])
    engine.join(10)
    assert engine.get(run['run_id'])['status'] == 'completed'


def test_http_start_reads_real_runner_partial_result_and_guards_origin(area, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.routers import m2
    value = draft()
    value['coverage']['duties'] = dict(status='partial', reason='ambiguous duty')
    engine = service(area, lambda: Fixture([response(value)]))
    monkeypatch.setattr(m2, 'get_delivery', lambda: engine)
    monkeypatch.setenv('TALENTMIND_LOCAL_RAW', '1')
    app = FastAPI()
    app.include_router(m2.router, prefix='/api')
    @app.middleware('http')
    async def peer(request, call_next):
        request.scope['client'] = ('127.0.0.1', 123)
        return await call_next(request)
    with TestClient(app, base_url='http://localhost') as client:
        created = client.post('/api/m2/delivery/runs', json={'jd_ids': [1]})
        assert created.status_code == 200
        run = created.json()['data']
        prefix = '/api/m2/delivery/runs/' + run['run_id']
        assert client.post(prefix + '/start').status_code == 200
        engine.join(10)
        result = client.get(prefix).json()['data']
        assert result['counts']['partial'] == 1
        assert result['items'][0]['analysis']['claims'][1]['requirement']['combination'] == 'any_of'
        for method, path in [('GET', '/api/m2/delivery/inputs'), ('GET', prefix), ('POST', prefix + '/resume'), ('POST', prefix + '/stop')]:
            assert client.request(method, path, headers={'Origin': 'https://evil.example'}).status_code == 403
        assert client.post('/api/m2/runs', json={}).status_code == 405


def test_stop_during_processor_keeps_committed_item_and_unrun_item(area):
    import threading
    entered, release = threading.Event(), threading.Event()
    class Blocking(Fixture):
        async def complete(self, messages):
            entered.set()
            await asyncio.to_thread(release.wait, 5)
            return await super().complete(messages)
    engine = service(area, lambda: Blocking([response(draft())]))
    run = engine.create([1, 2])
    try:
        engine.start(run['run_id'])
        assert entered.wait(5)
        assert engine.stop(run['run_id'])['stop_requested']
        release.set()
        engine.join(10)
        stopped = engine.get(run['run_id'])
        assert stopped['status'] == 'stopped'
        assert stopped['counts']['complete'] == stopped['counts']['not_run'] == 1
        engine.processor_factory = lambda: Fixture([response(draft())])
        engine.start(run['run_id'])
        engine.join(10)
        final = engine.get(run['run_id'])
        assert final['status'] == 'completed'
        assert final['items'][0]['analysis'] == stopped['items'][0]['analysis']
    finally:
        release.set()
        engine.join(10)


def test_research_candidate_commit_crash_retries_the_same_operations(area, monkeypatch):
    from app.job_analysis.delivery import runner
    engine = service(area)
    run = engine.create([1])
    def crash(stage):
        if stage == 'after_candidate_commit': raise RuntimeError('simulated process crash')
    monkeypatch.setattr(runner, 'checkpoint', crash)
    engine.start(run['run_id'])
    engine.join(10)
    assert engine.get(run['run_id'])['status'] == 'interrupted'
    monkeypatch.setattr(runner, 'checkpoint', lambda _: None)
    engine.start(run['run_id'])
    engine.join(10)
    assert engine.get(run['run_id'])['status'] == 'completed'


def test_existing_delivery_store_is_read_without_copy_or_reexecution(area):
    from app.job_analysis.delivery.http_service import DeliveryService
    origin = service(area)
    run = origin.create([1])
    origin.start(run['run_id'])
    origin.join(10)
    before = (origin.root / 'delivery.db').read_bytes()
    reader = DeliveryService(area / 'new-web', history_roots=[origin.root])
    loaded = reader.get(run['run_id'])
    assert loaded['run_id'] == run['run_id']
    assert loaded['request_sha256'] == run['request_sha256']
    assert loaded['execution_available'] is False
    assert reader.list_runs()[0]['run_id'] == run['run_id']
    assert not reader.root.exists()
    assert (origin.root / 'delivery.db').read_bytes() == before
    with pytest.raises(ValueError, match='history'): reader.start(run['run_id'])
    with pytest.raises(ValueError, match='history'): reader.stop(run['run_id'])


def test_pending_run_requires_resume_or_explicit_abandon_before_new_selection(area):
    engine = service(area)
    first = engine.create([1])
    with pytest.raises(RuntimeError, match='unfinished'): engine.create([2])
    abandoned = engine.abandon(first['run_id'])
    assert abandoned['status'] == 'abandoned'
    assert abandoned['items'] == first['items']
    assert abandoned['request_sha256'] == first['request_sha256']
    with pytest.raises(ValueError, match='abandoned'): engine.start(first['run_id'])
    with pytest.raises(ValueError, match='abandoned'): engine.stop(first['run_id'])
    second = engine.create([2])
    engine.start(second['run_id'])
    engine.join(10)
    assert engine.get(second['run_id'])['status'] == 'completed'


def test_start_reports_os_writer_conflict_before_success(area):
    from app.job_analysis.delivery import DeliveryStore
    engine = service(area)
    run = engine.create([1])
    try:
        with DeliveryStore(engine.root):
            with pytest.raises(RuntimeError, match='worker'):
                engine.start(run['run_id'])
    finally:
        engine.join(10)


def test_current_source_helpers_preserve_identity_without_retired_cohort_entrypoints():
    from app.job_analysis.product import source
    normalized = source.normalize_identity(dict(identity_status='pending', content_eligible=0,
                                               identity_evidence='{"kind":"synthetic"}'))
    assert normalized == dict(identity_status='pending', content_eligible=False,
                              identity_evidence={'kind': 'synthetic'})
    assert source.normalize_identity({})['identity_status'] == 'unknown'
    with pytest.raises(ValueError): source.normalize_identity({'identity_status': 'invented'})
    assert not hasattr(source, 'Selection')
    assert not hasattr(source, 'read_mysql')

"""Maintenance uses isolated persisted inputs, never a production database."""
import asyncio
from copy import deepcopy

import pytest

from app.job_analysis.delivery import DeliveryStore, execute
from app.job_analysis.delivery.http_service import DeliveryService
from app.job_analysis.foundation.inputs import digest
from test_delivery import request
from test_foundation_inputs import area
from test_knowledge_governance import unknown_case, shipped
from test_work_candidates import create
from test_work_evolution import duties


def setup(area, analysis=None, operations=None, name='current'):
    analysis = analysis or duties('a', ['开发订单交易接口。'])
    root = area / name
    with DeliveryStore(root, create=True) as store:
        result = asyncio.run(execute(store, name, request(store, [analysis], operations=[create(analysis)] if operations is None else operations), shipped()))
    return DeliveryService(root, knowledge=shipped().path), result


def test_work_maintenance_versions_retries_conflicts_and_frozen_runs(area):
    from app.job_analysis.delivery.maintenance import Maintenance
    engine, run = setup(area)
    api = Maintenance(engine)
    original = api.work()
    cid, candidate = next(iter(original['state']['candidates'].items()))
    command = dict(batch_id='edit-one', baseline=original['state']['binding'], analysis_sha256s=[],
                   operations=[dict(op='describe', candidate_id=cid, expected_version=candidate['version'],
                     description='人工研究说明', research_question='职责范围是否相同', unresolved=['独立真值不足'], reason='补充说明')])
    updated = api.update_work(command)
    assert updated['state']['candidates'][cid]['description'] == '人工研究说明'
    assert api.update_work(command) == updated
    assert api.work(original['state']['revision'])['state'] == original['state']
    assert engine.get('current')['work'] == run['work']
    stale = dict(command, batch_id='stale-edit')
    with pytest.raises(RuntimeError, match='stale'):
        api.update_work(stale)
    with DeliveryStore(engine.root) as store:
        asyncio.run(execute(store, 'frozen', request(store, [duties('b', ['开发订单交易接口。'])]), shipped(), stop=lambda: True))
    newer = dict(command, batch_id='blocked-edit', baseline=updated['state']['binding'])
    newer['operations'] = [dict(command['operations'][0], expected_version=updated['state']['candidates'][cid]['version'])]
    with pytest.raises(RuntimeError, match='unfinished'):
        api.update_work(newer)


def test_skill_revision_uses_new_historical_evidence_and_withdrawal_affects_next_run(area):
    from app.job_analysis.delivery.maintenance import Maintenance
    first, _ = unknown_case(raw_text='要求：使用 Flink SQL 开发实时数据任务。', jd_id='one', row_extra={'source_identity': 'a'})
    second, _ = unknown_case(raw_text='岗位需要具备 Flink SQL 实现流式任务的能力。', jd_id='two', row_extra={'source_identity': 'b'})
    engine, original = setup(area, first, [], 'current')
    history, _ = setup(area, second, [], 'history')
    engine.history_roots = (history.root,)
    api = Maintenance(engine)
    cid = api.skills()['items'][0]['candidate_id']
    before = api.skill(cid)
    assert [x['analysis_sha256'] for x in before['eligible_new_evidence']] == [digest(second)]
    command = dict(request_id='revise-one', expected_version=1, action='revise', reason='新来源支持说明',
                   description='有两份来源的候选说明', source_analysis_sha256=digest(second))
    revised = api.update_skill(cid, command)
    assert revised['candidate']['version'] == 2
    assert revised['candidate']['description'] == command['description']
    assert revised['eligible_new_evidence'] == []
    assert api.update_skill(cid, command) == revised
    assert api.skill(cid, 1)['candidate'] == before['candidate']
    with pytest.raises(RuntimeError, match='stale'):
        api.update_skill(cid, dict(command, request_id='stale'))
    with pytest.raises(ValueError, match='new evidence'):
        api.update_skill(cid, dict(command, request_id='reused', expected_version=2))
    withdrawn = api.update_skill(cid, dict(request_id='withdraw-one', expected_version=2, action='withdraw', reason='来源解释待核对'))
    assert withdrawn['candidate']['status'] == 'withdrawn'
    with DeliveryStore(engine.root) as store:
        newer = asyncio.run(execute(store, 'next', request(store, [second]), shipped()))
    assert newer['items'][0]['skill_candidates'][0]['status'] == 'withdrawn'
    assert newer['items'][0]['alignment']['requirements'][0]['alignments'][0]['state'] == 'unknown'
    assert engine.get('current')['items'] == [dict(original['items'][0], input=first['input_row'], input_version=first['input_version'])]


def test_browser_cannot_supply_review_or_forge_analysis(area):
    from app.job_analysis.delivery.maintenance import Maintenance
    engine, _ = setup(area)
    api = Maintenance(engine)
    value = api.work()
    rid = next(iter(value['state']['relations']))
    command = dict(batch_id='correct', baseline=value['state']['binding'], analysis_sha256s=[], operations=[
        dict(op='correct', relation_id=rid, expected_sha256=value['relation_sha256s'][rid], decision='corroborates', reason='有来源支持', verification={'reviewer':'browser'})])
    with pytest.raises(ValueError):
        api.update_work(command)
    command['operations'][0]['verification'] = None
    result = api.update_work(command)
    assert result['state']['relations'][rid]['human_confirmation'] == 'not_confirmed'
    assert result['state']['relations'][rid]['state'] == 'pending_review'


def test_skill_commit_interrupt_retry_and_new_run_guard(area, monkeypatch):
    from app.job_analysis.delivery import maintenance
    first, _ = unknown_case()
    engine, _ = setup(area, first, [])
    api = maintenance.Maintenance(engine)
    cid = api.skills()['items'][0]['candidate_id']
    command = dict(request_id='interrupted', expected_version=1, action='withdraw', reason='核对来源')
    def fail(stage):
        if stage == 'after_skill_commit':
            raise OSError('simulated exit after version commit')
    monkeypatch.setattr(maintenance, 'checkpoint', fail)
    with pytest.raises(OSError):
        api.update_skill(cid, command)
    assert api.skill(cid)['candidate']['version'] == 2
    pending = maintenance.Maintenance(engine).pending()['items']
    assert len(pending) == 1 and pending[0]['kind'] == 'skill'
    with DeliveryStore(engine.root) as store:
        with pytest.raises(RuntimeError, match='unfinished maintenance'):
            asyncio.run(execute(store, 'new-run', request(store, [first]), shipped()))
    monkeypatch.setattr(maintenance, 'checkpoint', lambda _: None)
    result = maintenance.Maintenance(engine).recover(pending[0]['id'])
    assert result['candidate']['version'] == 2
    assert api.update_skill(cid, command) == result
    assert api.pending()['items'] == []


def test_interrupted_knowledge_write_does_not_publish_partial_version(area, monkeypatch):
    from pathlib import Path
    from app.job_analysis.knowledge.storage import save_result, read_result
    path = area / 'version'
    real_open = Path.open
    def fail(target, *args, **kwargs):
        if target.name == 'manifest.json':
            raise OSError('interrupted manifest')
        return real_open(target, *args, **kwargs)
    monkeypatch.setattr(Path, 'open', fail)
    with pytest.raises(OSError):
        save_result(path, {'test': 'safe'})
    assert not path.exists()
    monkeypatch.setattr(Path, 'open', real_open)
    save_result(path, {'test': 'safe'})
    assert read_result(path) == {'test': 'safe'}


def test_http_maintenance_mutation_history_and_origin(area, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.routers import m2
    engine, _ = setup(area)
    monkeypatch.setattr(m2, 'get_delivery', lambda: engine)
    monkeypatch.setenv('TALENTMIND_LOCAL_RAW', '1')
    app = FastAPI()
    app.include_router(m2.router, prefix='/api')
    @app.middleware('http')
    async def peer(request, call_next):
        request.scope['client'] = ('127.0.0.1', 123)
        return await call_next(request)
    path = '/api/m2/delivery/candidates/work'
    with TestClient(app, base_url='http://localhost') as client:
        original = client.get(path).json()['data']
        rid = next(iter(original['state']['relations']))
        body = dict(batch_id='http-withdraw', baseline=original['state']['binding'], analysis_sha256s=[], operations=[
            dict(op='correct', relation_id=rid, expected_sha256=original['relation_sha256s'][rid],
                 decision='withdraw', reason='明确撤回关系', verification=None)])
        assert client.post(path+'/batches', json=body, headers={'Origin':'https://evil.example'}).status_code == 403
        response = client.post(path+'/batches', json=body)
        assert response.status_code == 200
        assert response.json()['data']['state']['relations'][rid]['state'] == 'withdrawn'
        assert client.post(path+'/batches', json=body).json() == response.json()
        assert client.get(path+'?revision=1').json()['data']['state'] == original['state']
        body['batch_id'] = 'http-stale'
        assert client.post(path+'/batches', json=body).status_code == 409


def test_work_commit_recovery_uses_original_batch_after_refresh(area, monkeypatch):
    from app.job_analysis.delivery import maintenance
    engine, _ = setup(area)
    api = maintenance.Maintenance(engine)
    before = api.work()
    rid = next(iter(before['state']['relations']))
    body = dict(batch_id='interrupted-work', baseline=before['state']['binding'], analysis_sha256s=[], operations=[
        dict(op='correct', relation_id=rid, expected_sha256=before['relation_sha256s'][rid], decision='withdraw', reason='撤回', verification=None)])
    def fail(stage):
        if stage == 'after_work_commit': raise OSError('lost response')
    monkeypatch.setattr(maintenance, 'checkpoint', fail)
    with pytest.raises(OSError): api.update_work(body)
    saved_revision = api.work()['state']['revision']
    monkeypatch.setattr(maintenance, 'checkpoint', lambda _: None)
    refreshed = maintenance.Maintenance(engine)
    result = refreshed.recover(refreshed.pending()['items'][0]['id'])
    assert result['state']['revision'] == saved_revision
    assert result['state']['relations'][rid]['state'] == 'withdrawn'
    assert refreshed.update_work(body) == result


def test_rejected_domain_operation_does_not_block_later_maintenance(area):
    from app.job_analysis.delivery.maintenance import Maintenance
    engine, _ = setup(area)
    api = Maintenance(engine)
    before = api.work()
    source = before['sources'][0]
    command = dict(batch_id='duplicate-link', baseline=before['state']['binding'], analysis_sha256s=[source['analysis_sha256']],
        operations=[dict(op='link', candidate_id='work-orders', analysis_sha256=source['analysis_sha256'], work_ids=['d1'], reason='重复关联')])
    with pytest.raises(ValueError, match='existing relation'): api.update_work(command)
    assert api.pending()['items'] == []
    assert api.work()['state'] == before['state']


def test_manual_link_does_not_add_unrequested_candidate_memberships(area):
    from app.job_analysis.delivery.maintenance import Maintenance
    seed = duties('seed', ['开发订单接口。'])
    engine, _ = setup(area, seed, [create(seed), create(seed, 'work-other')])
    incoming = duties('incoming', ['开发订单接口。'])
    history, _ = setup(area, incoming, [], 'history')
    engine.history_roots = (history.root,)
    api = Maintenance(engine)
    before = api.work()
    result = api.update_work(dict(batch_id='targeted-link', baseline=before['state']['binding'], analysis_sha256s=[digest(incoming)],
        operations=[dict(op='link', candidate_id='work-orders', analysis_sha256=digest(incoming), work_ids=['d1'], reason='只关联指定候选')]))
    assert [r['candidate_id'] for r in result['state']['relations'].values() if r['jd_id'] == 'incoming'] == ['work-orders']


def test_uncommitted_work_recovery_rejects_changed_algorithm(area, monkeypatch):
    from app.job_analysis.delivery import maintenance
    engine, _ = setup(area)
    api = maintenance.Maintenance(engine)
    before = api.work()
    candidate = before['state']['candidates']['work-orders']
    body = dict(batch_id='algorithm-bound', baseline=before['state']['binding'], analysis_sha256s=[], operations=[dict(
        op='describe', candidate_id='work-orders', expected_version=candidate['version'], description='说明',
        research_question='范围', unresolved=['未审核'], reason='维护')])
    def fail(stage):
        if stage == 'before_work_commit': raise OSError('pre-commit exit')
    monkeypatch.setattr(maintenance, 'checkpoint', fail)
    with pytest.raises(OSError): api.update_work(body)
    action_id = api.pending()['items'][0]['id']
    original_version = maintenance.algorithm_version
    monkeypatch.setattr(maintenance, 'checkpoint', lambda _: None)
    monkeypatch.setattr(maintenance, 'algorithm_version', lambda: {'revision':'changed'})
    with pytest.raises(RuntimeError, match='original algorithm'): api.recover(action_id)
    assert api.work()['state']['revision'] == before['state']['revision']
    monkeypatch.setattr(maintenance, 'algorithm_version', original_version)
    assert api.recover(action_id)['state']['revision'] == before['state']['revision'] + 1

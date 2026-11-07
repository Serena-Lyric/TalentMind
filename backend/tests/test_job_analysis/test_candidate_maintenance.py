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


def legacy_pending(area):
    """Create the old persisted protocol, without inventing a projection binding."""
    from app.job_analysis.delivery import maintenance
    first, _ = unknown_case()
    engine, _ = setup(area, first, [])
    api = maintenance.Maintenance(engine)
    cid = api.skills()['items'][0]['candidate_id']
    command = maintenance.SkillCommand(request_id='old-protocol', expected_version=1,
        action='mark_disputed', reason='旧版请求', competing_hypotheses=['其他解释'])
    updated = maintenance._PreviewRegistry(api._registry().root).mark_disputed(cid, command.reason, command.competing_hypotheses)
    payload = dict(candidate_id=cid, **command.model_dump())
    action_id = 'maintenance-skill-old-protocol'
    with DeliveryStore(engine.root) as store:
        store.append(action_id, 'maintenance_prepare', dict(request=payload, request_sha256=digest(payload),
            candidate=updated.model_dump(), kind='skill', algorithm=maintenance.algorithm_version()))
    api._registry()._write(updated)
    api._registry().project()
    return engine, api, cid, action_id


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


def test_published_skill_receipt_recovers_exactly_after_dependencies_change(area, monkeypatch):
    from app.job_analysis.delivery import maintenance
    from app.job_analysis.knowledge.candidates import CandidateRegistry
    first, _ = unknown_case()
    engine, _ = setup(area, first, [])
    api = maintenance.Maintenance(engine)
    cid = api.skills()['items'][0]['candidate_id']
    command = dict(request_id='receipt-failed', expected_version=1, action='mark_disputed',
                   reason='来源存在不同解释', competing_hypotheses=['可能是另一项能力'])
    captured = []
    append = DeliveryStore.append
    def fail_receipt(store, action_id, kind, value):
        if kind == 'maintenance_result':
            captured.append(deepcopy(value))
            raise OSError('receipt write interrupted')
        return append(store, action_id, kind, value)
    with monkeypatch.context() as patch:
        patch.setattr(DeliveryStore, 'append', fail_receipt)
        with pytest.raises(OSError, match='receipt write'):
            api.update_skill(cid, command)
    artifacts = {p.relative_to(engine.root): p.read_bytes() for p in (engine.root / 'skill-candidates').rglob('*') if p.is_file()}
    assert len(captured) == 1 and captured[0]['candidate']['version'] == 2
    assert len(api.pending()['items']) == 1
    with monkeypatch.context() as patch:
        patch.setattr(maintenance, 'algorithm_version', lambda: {'deployment': 'changed'})
        patch.setattr(CandidateRegistry, 'project', lambda *a, **k: pytest.fail('must not recompute old projection'))
        patch.setattr(maintenance.Maintenance, 'skill', lambda *a, **k: pytest.fail('must not rebuild old response'))
        patch.setattr(maintenance.Maintenance, '_sources', lambda *a, **k: pytest.fail('must not reinterpret current sources'))
        result = maintenance.Maintenance(engine).recover('maintenance-skill-receipt-failed')
        assert result == captured[0]
        assert api.update_skill(cid, command) == result
    assert api.pending()['items'] == []
    assert {p.relative_to(engine.root): p.read_bytes() for p in (engine.root / 'skill-candidates').rglob('*') if p.is_file()} == artifacts
    assert api._registry()._versions(cid) == [1, 2]
    with DeliveryStore(engine.root) as store:
        result = asyncio.run(execute(store, 'after-recovery', request(store, [first]), shipped()))
    assert result['status'] == 'completed'


@pytest.mark.parametrize('stage', ['before_skill_commit', 'after_skill_commit', 'after_skill_projection'])
def test_skill_recovery_distinguishes_published_and_unpublished_outputs(area, monkeypatch, stage):
    from app.job_analysis.delivery import maintenance
    first, _ = unknown_case()
    engine, _ = setup(area, first, [])
    api = maintenance.Maintenance(engine)
    cid = api.skills()['items'][0]['candidate_id']
    command = dict(request_id='boundary', expected_version=1, action='mark_disputed',
                   reason='核对边界', competing_hypotheses=['其他解释'])
    def interrupt(actual):
        if actual == stage:
            raise OSError('boundary interrupted')
    with monkeypatch.context() as patch:
        patch.setattr(maintenance, 'checkpoint', interrupt)
        with pytest.raises(OSError, match='boundary interrupted'):
            api.update_skill(cid, command)
    with monkeypatch.context() as patch:
        patch.setattr(maintenance, 'algorithm_version', lambda: {'deployment': 'changed'})
        if stage == 'after_skill_projection':
            result = api.recover('maintenance-skill-boundary')
            assert result['candidate']['version'] == 2
            assert api.pending()['items'] == []
        else:
            with pytest.raises(RuntimeError, match='original algorithm'):
                api.recover('maintenance-skill-boundary')
            assert len(api.pending()['items']) == 1
    assert api.recover('maintenance-skill-boundary')['candidate']['version'] == 2
    assert api._registry()._versions(cid) == [1, 2]


@pytest.mark.parametrize('artifact', ['candidate', 'projection'])
def test_skill_receipt_recovery_refuses_damaged_published_artifact(area, monkeypatch, artifact):
    from app.job_analysis.delivery import maintenance
    first, _ = unknown_case()
    engine, _ = setup(area, first, [])
    api = maintenance.Maintenance(engine)
    cid = api.skills()['items'][0]['candidate_id']
    command = dict(request_id='damaged', expected_version=1, action='mark_disputed',
                   reason='核对完整性', competing_hypotheses=['其他解释'])
    append = DeliveryStore.append
    saved = []
    def fail(store, action_id, kind, value):
        if kind == 'maintenance_result':
            saved.append(deepcopy(value))
            raise OSError('receipt interrupted')
        return append(store, action_id, kind, value)
    with monkeypatch.context() as patch:
        patch.setattr(DeliveryStore, 'append', fail)
        with pytest.raises(OSError):
            api.update_skill(cid, command)
    root = engine.root / 'skill-candidates'
    folder = root / 'candidates' / cid / 'versions' / '2' if artifact == 'candidate' else root / 'projections' / saved[0]['projection']['sha256']
    (folder / 'value.json').write_text('{}', encoding='utf-8')
    monkeypatch.setattr(maintenance, 'algorithm_version', lambda: {'deployment': 'changed'})
    with pytest.raises(ValueError):
        api.recover('maintenance-skill-damaged')
    assert (folder / 'value.json').read_text(encoding='utf-8') == '{}'
    assert len(api.pending()['items']) == 1


@pytest.mark.parametrize('committed', [False, True])
def test_legacy_skill_request_has_explicit_durable_incomplete_close(area, monkeypatch, committed):
    from app.job_analysis.delivery import maintenance
    first, _ = unknown_case()
    engine, _ = setup(area, first, [])
    api = maintenance.Maintenance(engine)
    cid = api.skills()['items'][0]['candidate_id']
    command = dict(request_id='legacy', expected_version=1, action='mark_disputed',
                   reason='旧维护', competing_hypotheses=['另一解释'])
    command = maintenance.SkillCommand.model_validate(command).model_dump()
    updated = maintenance._PreviewRegistry(api._registry().root).mark_disputed(cid, command['reason'], command['competing_hypotheses'])
    request_body = dict(candidate_id=cid, **command)
    with DeliveryStore(engine.root) as store:
        store.append('maintenance-skill-legacy', 'maintenance_prepare', dict(request=request_body,
                     request_sha256=digest(request_body), kind='skill', candidate=updated.model_dump(),
                     algorithm=maintenance.algorithm_version()))
    if committed:
        api._registry()._write(updated)
        api._registry().project()
    before = {p: p.read_bytes() for p in api._registry().root.rglob('*') if p.is_file()}
    with monkeypatch.context() as patch:
        patch.setattr(maintenance, 'algorithm_version', lambda: {'deployment': 'changed'})
        with pytest.raises(RuntimeError, match='original algorithm'):
            api.recover('maintenance-skill-legacy')
        assert api.pending()['items'][0]['can_close'] is True
        result = api.close('maintenance-skill-legacy', '停止旧版恢复，保留已写成果')
        assert result == dict(status='closed_incomplete', reason='停止旧版恢复，保留已写成果',
                              candidate_version_saved=committed, projection_binding='not_recorded')
        assert api.close('maintenance-skill-legacy', result['reason']) == result
        with pytest.raises(RuntimeError, match='closed'):
            api.recover('maintenance-skill-legacy')
        assert api.pending()['items'] == []
        assert api.pending()['closed'][0]['status'] == 'closed_incomplete'
    assert {p: p.read_bytes() for p in api._registry().root.rglob('*') if p.is_file()} == before
    with DeliveryStore(engine.root) as store:
        assert store.latest('maintenance-skill-legacy', 'maintenance_result') is None
        assert store.latest('maintenance-skill-legacy', 'maintenance_rejected') is None
        assert store.conn.execute("SELECT count(*) FROM events WHERE kind='maintenance_closed'").fetchone()[0] == 1
        result = asyncio.run(execute(store, 'after-close', request(store, [first]), shipped()))
    assert result['status'] == 'completed'


def test_new_bound_skill_request_cannot_use_legacy_close(area, monkeypatch):
    from app.job_analysis.delivery import maintenance
    first, _ = unknown_case()
    engine, _ = setup(area, first, [])
    api = maintenance.Maintenance(engine)
    cid = api.skills()['items'][0]['candidate_id']
    def interrupt(stage):
        if stage == 'after_skill_commit':
            raise OSError('exit')
    monkeypatch.setattr(maintenance, 'checkpoint', interrupt)
    with pytest.raises(OSError):
        api.update_skill(cid, dict(request_id='bound', expected_version=1, action='mark_disputed',
                         reason='原因', competing_hypotheses=['另一解释']))
    assert api.pending()['items'][0]['can_close'] is False
    with pytest.raises(ValueError, match='legacy'):
        api.close('maintenance-skill-bound', '不能跳过正常恢复')


def test_projection_publication_exit_can_finish_receipt_without_new_algorithm(area, monkeypatch):
    from app.job_analysis.delivery import maintenance
    first, _ = unknown_case()
    engine, _ = setup(area, first, [])
    api = maintenance.Maintenance(engine)
    cid = api.skills()['items'][0]['candidate_id']
    publish = maintenance.save_result
    def interrupt_after_publish(path, value):
        publish(path, value)
        raise OSError('exit after atomic projection publication')
    with monkeypatch.context() as patch:
        patch.setattr(maintenance, 'save_result', interrupt_after_publish)
        with pytest.raises(OSError, match='atomic projection'):
            api.update_skill(cid, dict(request_id='projection-boundary', expected_version=1,
                action='mark_disputed', reason='不同解释', competing_hypotheses=['其他解释']))
    with DeliveryStore(engine.root, readonly=True) as store:
        prepared = store.latest('maintenance-skill-projection-boundary', 'maintenance_prepare')
    monkeypatch.setattr(maintenance, 'algorithm_version', lambda: {'deployment': 'changed'})
    monkeypatch.setattr(maintenance, 'save_result', lambda *a, **k: pytest.fail('published outputs must not be rewritten'))
    result = api.recover('maintenance-skill-projection-boundary')
    assert result == prepared['response']
    assert api.pending()['items'] == []


@pytest.mark.parametrize('artifact', ['candidate', 'projection'])
def test_legacy_close_cannot_hide_damaged_artifacts(area, artifact):
    engine, api, cid, action_id = legacy_pending(area)
    root = api._registry().root
    path = root / 'candidates' / cid / 'versions' / '2' if artifact == 'candidate' else root / 'projections' / api._registry().project().sha256
    (path / 'value.json').write_text('{}', encoding='utf-8')
    with pytest.raises(ValueError, match='digest'):
        api.close(action_id, '不能将损坏伪装为成功')
    assert len(api.pending()['items']) == 1
    assert api.pending()['closed'] == []


@pytest.mark.parametrize('artifact', ['candidate', 'projection'])
def test_legacy_close_refuses_artifact_directory_replaced_by_file(area, artifact):
    engine, api, cid, action_id = legacy_pending(area)
    root = api._registry().root
    path = root / 'candidates' / cid / 'versions' / '2' if artifact == 'candidate' else root / 'projections' / api._registry().project().sha256
    assert path.resolve().is_relative_to(area.resolve())
    path.rename(path.with_name(path.name + '.fixture-backup'))
    path.write_bytes(b'partial')
    with pytest.raises(ValueError):
        api.close(action_id, '不能跳过错误类型的产物')
    assert path.read_bytes() == b'partial'
    assert len(api.pending()['items']) == 1


def test_legacy_close_http_is_explicit_validated_local_and_persisted(area, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.routers import m2
    from app.job_analysis.delivery import maintenance
    engine, api, cid, action_id = legacy_pending(area)
    monkeypatch.setattr(m2, 'get_delivery', lambda: engine)
    monkeypatch.setenv('TALENTMIND_LOCAL_RAW', '1')
    monkeypatch.setattr(maintenance, 'algorithm_version', lambda: {'deployment': 'changed'})
    app = FastAPI()
    app.include_router(m2.router, prefix='/api')
    @app.middleware('http')
    async def peer(request, call_next):
        request.scope['client'] = ('127.0.0.1', 123)
        return await call_next(request)
    base = '/api/m2/delivery/candidates/pending'
    with TestClient(app, base_url='http://localhost') as client:
        assert client.get(base).json()['data']['items'][0]['can_close'] is True
        path = f'{base}/{action_id}/close'
        assert client.post(path, json={'reason': ' '}).status_code == 422
        assert client.post(path, json={'reason': '保留成果', 'force': True}).status_code == 422
        assert client.post(path, json={'reason': '保留成果'}, headers={'Origin': 'https://evil.example'}).status_code == 403
        assert len(api.pending()['items']) == 1
        result = client.post(path, json={'reason': '明确结束旧恢复并保留已保存成果'})
        assert result.status_code == 200
        assert result.headers['cache-control'] == 'no-store'
        assert result.json()['data']['status'] == 'closed_incomplete'
        assert result.json()['data']['candidate_version_saved'] is True
        assert client.post(path, json={'reason': '不同原因'}).status_code == 409
        assert client.post(f'{base}/{action_id}/resume').status_code == 409
        refreshed = client.get(base).json()['data']
        assert refreshed['items'] == []
        assert refreshed['closed'][0]['candidate_id'] == cid
        assert refreshed['closed'][0]['reason'] == result.json()['data']['reason']


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

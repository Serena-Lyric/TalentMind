from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from app.job_analysis.foundation.inputs import digest
EXAMPLE = Path(__file__).parents[1] / 'app/job_analysis/baseline/examples/analysis.json'
@pytest.fixture(autouse=True)
def cleanup_graph_files(tmp_path, tmp_path_factory):
    import shutil
    target=tmp_path.resolve()
    base=tmp_path_factory.getbasetemp().resolve()
    assert target != base and target.is_relative_to(base)
    try:
        yield
    finally:
        if target.exists():
            shutil.rmtree(target)
        assert not target.exists()

def fixture(tmp_path):
    analysis=json.loads(EXAMPLE.read_text(encoding='utf-8'))
    result=dict(run_id='a'*32,request_sha256='b'*64,status='completed',knowledge={'sha256':'c'*64},items=[dict(index=0,namespace=analysis['namespace'],jd_id=analysis['jd_id'],analysis=analysis,analysis_sha256=digest(analysis),status='partial')],work=None)
    return SimpleNamespace(root=tmp_path,get=lambda _:deepcopy(result)),result

def test_graph_preserves_or_group_evidence_and_partial_results(tmp_path):
    from app.graph.delivery_bundle import graph_info,read_bundle
    service,result=fixture(tmp_path)
    info=graph_info(service,result['run_id'])
    assert 'm2DeliveryRun=' in info['url']
    manifest=json.loads(read_bundle(service,result['run_id'],'manifest.json'))
    facts=json.loads(read_bundle(service,result['run_id'],'facts.json'))
    sources=json.loads(read_bundle(service,result['run_id'],'sources.json'))
    assert manifest['delivery']['request_sha256']==result['request_sha256']
    assert sources['records'][0]['analysis']==result['items'][0]['analysis']
    java=next(e for e in facts['edges'] if e['member']=='Java')
    assert java['requirement']['combination']=='any_of'
    assert java['statement']['requirement']['members']==['Java','Python','其他语言']
    assert java['state']=='required'
    assert java['independent_requirement'] is False
    assert facts['nodes']
    assert json.loads(read_bundle(service,result['run_id'],'layout.json'))['derived_edges']==[]

def test_graph_rejects_corrupted_analysis_and_path_escape(tmp_path):
    from app.graph.delivery_bundle import graph_info,read_bundle
    service,result=fixture(tmp_path)
    result['items'][0]['analysis']['claims'][1]['evidence'][0]['quote']='fake'
    with pytest.raises(ValueError):graph_info(service,result['run_id'])
    with pytest.raises(ValueError):read_bundle(service,'../../outside','manifest.json')
    with pytest.raises(ValueError):read_bundle(service,'a'*32,'../../secret')

def test_active_partial_snapshot_remains_readable_after_resume_and_process_restart(tmp_path):
    from app.graph.delivery_bundle import graph_info,read_bundle,_bundle
    service,result=fixture(tmp_path)
    result['execution_active']=True
    result['status']='running'
    info=graph_info(service,result['run_id'])
    sha=info['manifest_sha256']
    original=read_bundle(service,result['run_id'],'sources.json',sha)
    result['status']='completed'
    result['execution_active']=False
    result['items']=[]
    second=graph_info(service,result['run_id'])
    assert second['manifest_sha256']!=sha
    _bundle.cache_clear()
    assert read_bundle(service,result['run_id'],'sources.json',sha)==original
    with pytest.raises(ValueError,match='unavailable'):
        read_bundle(service,result['run_id'],'manifest.json','f'*64)

def test_http_artifacts_require_digest_and_keep_old_snapshot_after_run_changes(tmp_path,monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.routers import m2
    service,result=fixture(tmp_path)
    monkeypatch.setattr(m2,'get_delivery',lambda:service)
    app=FastAPI()
    app.dependency_overrides[m2.local_access]=lambda:None
    app.include_router(m2.router,prefix='/api')
    with TestClient(app) as client:
        path=f"/api/m2/delivery/runs/{result['run_id']}/graph"
        response=client.get(path)
        assert response.status_code==200
        info=response.json()['data']
        sha=info['manifest_sha256']
        first=client.get(path+'/facts.json',params={'snapshot':sha})
        assert first.status_code==200
        result['items']=[]
        second=client.get(path+'/facts.json',params={'snapshot':sha})
        assert second.content==first.content
        assert client.get(path+'/facts.json').status_code==422
        assert client.get(path+'/facts.json',params={'snapshot':'f'*64}).status_code==400


def test_interrupted_artifact_write_is_unpublished_and_retryable(tmp_path, monkeypatch):
    from app.graph.delivery_bundle import graph_info, read_bundle, _bundle, _text, _sha
    service, result = fixture(tmp_path)
    sha = _sha(_bundle(_text(result))['manifest.json'])
    final = tmp_path / 'graphs' / result['run_id'] / sha
    original_open = Path.open

    class InterruptedWriter:
        def __init__(self, stream):
            self.stream = stream
        def __enter__(self):
            return self
        def __exit__(self, *args):
            self.stream.close()
        def write(self, content):
            self.stream.write(content[:len(content) // 2])
            self.stream.flush()
            raise OSError('simulated disk write interruption')

    def interrupt(path, mode='r', *args, **kwargs):
        stream = original_open(path, mode, *args, **kwargs)
        return InterruptedWriter(stream) if path.name == 'sources.json' and mode == 'x' else stream

    with monkeypatch.context() as patch:
        patch.setattr(Path, 'open', interrupt)
        with pytest.raises(OSError, match='simulated disk'):
            graph_info(service, result['run_id'])
    assert not final.exists(), 'No partial bytes may reach the published SHA directory'
    assert list(final.parent.iterdir()) == []
    info = graph_info(service, result['run_id'])
    assert info['manifest_sha256'] == sha
    assert json.loads(read_bundle(service, result['run_id'], 'sources.json', sha))['records'][0]['analysis'] == result['items'][0]['analysis']


@pytest.mark.parametrize('damage', ['truncate', 'delete'])
def test_published_snapshot_damage_is_never_repaired(tmp_path, damage):
    from app.graph.delivery_bundle import graph_info, read_bundle
    service, result = fixture(tmp_path)
    info = graph_info(service, result['run_id'])
    path = tmp_path / 'graphs' / result['run_id'] / info['manifest_sha256']
    target = path / 'sources.json'
    if damage == 'truncate':
        target.write_text('{"partial":', encoding='utf-8')
    else:
        target.unlink()
    before = {p.name: p.read_bytes() for p in path.iterdir()}
    with pytest.raises(ValueError):
        graph_info(service, result['run_id'])
    with pytest.raises(ValueError):
        read_bundle(service, result['run_id'], 'facts.json', info['manifest_sha256'])
    assert {p.name: p.read_bytes() for p in path.iterdir()} == before


def test_concurrent_publish_returns_one_complete_immutable_snapshot(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from app.graph.delivery_bundle import FILES, graph_info, read_bundle
    service, result = fixture(tmp_path)
    barrier = Barrier(6)
    def publish(_):
        barrier.wait(timeout=20)
        info = graph_info(service, result['run_id'])
        for name in FILES:
            json.loads(read_bundle(service, result['run_id'], name, info['manifest_sha256']))
        return info
    with ThreadPoolExecutor(max_workers=6) as executor:
        results = list(executor.map(publish, range(6)))
    assert all(info == results[0] for info in results)
    parent = tmp_path / 'graphs' / result['run_id']
    assert [p.name for p in parent.iterdir()] == [results[0]['manifest_sha256']]


def _publish_graph_process(root, result, barrier, output):
    from unittest.mock import patch
    from app.graph.delivery_bundle import FILES, graph_info, read_bundle
    service = SimpleNamespace(root=Path(root), get=lambda _: deepcopy(result))
    original_rename = Path.rename
    def simultaneous_publish(stage, target):
        barrier.wait(timeout=30)
        return original_rename(stage, target)
    try:
        with patch.object(Path, 'rename', simultaneous_publish):
            info = graph_info(service, result['run_id'])
        for name in FILES:
            json.loads(read_bundle(service, result['run_id'], name, info['manifest_sha256']))
        output.put(('ok', info['manifest_sha256']))
    except Exception as exc:
        output.put(('error', repr(exc)))


def test_processes_race_at_atomic_directory_publish(tmp_path):
    import multiprocessing
    service, result = fixture(tmp_path)
    context = multiprocessing.get_context('spawn')
    barrier, output = context.Barrier(3), context.Queue()
    processes = [context.Process(target=_publish_graph_process,
                                args=(str(service.root), result, barrier, output)) for _ in range(3)]
    try:
        for process in processes:
            process.start()
        results = [output.get(timeout=45) for _ in processes]
        for process in processes:
            process.join(timeout=5)
            assert process.exitcode == 0
        assert all(status == 'ok' for status, _ in results), results
        assert len({sha for _, sha in results}) == 1
        parent = tmp_path / 'graphs' / result['run_id']
        assert [p.name for p in parent.iterdir()] == [results[0][1]]
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)
        output.close()
        output.join_thread()


def test_ambiguous_legacy_partial_final_directory_is_preserved(tmp_path):
    from app.graph.delivery_bundle import graph_info, _bundle, _text, _sha
    service, result = fixture(tmp_path)
    contents = _bundle(_text(result))
    path = tmp_path / 'graphs' / result['run_id'] / _sha(contents['manifest.json'])
    path.mkdir(parents=True)
    (path / 'facts.json').write_text(contents['facts.json'][:12], encoding='utf-8')
    with pytest.raises(ValueError, match='unavailable'):
        graph_info(service, result['run_id'])
    assert {p.name: p.read_text(encoding='utf-8') for p in path.iterdir()} == {'facts.json': contents['facts.json'][:12]}


def test_research_snapshot_keeps_original_evidence_after_withdrawal(tmp_path):
    from app.graph.delivery_bundle import graph_info, read_bundle
    service, result = fixture(tmp_path)
    item = result['items'][0]
    relation = dict(id='r1', candidate_id='c1', state='research',
                    analysis_sha256=item['analysis_sha256'], work_ids=['d1'])
    result['work'] = dict(candidates={'c1': dict(description='合成任务恢复研究', members=['r1'])},
                          relations={'r1': relation})
    before = graph_info(service, result['run_id'])['manifest_sha256']
    original = read_bundle(service, result['run_id'], 'sources.json', before)
    old_facts = read_bundle(service, result['run_id'], 'facts.json', before)
    edge = next(e for e in json.loads(old_facts)['edges'] if e['type'] == 'RELATED_TO')
    source = json.loads(original)['records'][edge['source_record']]
    assert edge['research_relation']['analysis_sha256'] == source['analysis_sha256']
    assert edge['evidence'] == source['analysis']['claims'][0]['evidence'][0]
    relation['state'] = 'withdrawn'
    current = graph_info(service, result['run_id'])['manifest_sha256']
    assert current != before
    assert not any(e['type'] == 'RELATED_TO' for e in json.loads(read_bundle(service, result['run_id'], 'facts.json', current))['edges'])
    assert read_bundle(service, result['run_id'], 'facts.json', before) == old_facts
    assert read_bundle(service, result['run_id'], 'sources.json', before) == original

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

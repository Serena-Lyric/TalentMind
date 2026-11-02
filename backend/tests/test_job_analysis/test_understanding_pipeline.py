import asyncio
import json
from copy import deepcopy

from test_understanding import ROW,draft
from test_understanding_audit import prior,patch_for,relation


class Fixture:
    descriptor=dict(provider='synthetic',model='fixture',model_revision='pipeline-1')
    def __init__(self,responses):self.responses=iter(responses);self.requests=[]
    async def complete(self,messages):
        self.requests.append(deepcopy(messages))
        return next(self.responses)


def response(content=None,status='ok'):
    from app.job_analysis.understanding.processor import Completion
    return Completion(content=json.dumps(content) if content is not None else '',finish_reason='stop' if status=='ok' else None,
                      status=status,metadata={'usage':{'prompt_tokens':10,'completion_tokens':2,'total_tokens':12}} if status=='ok' else {})


def test_low_risk_jd_keeps_one_call_and_does_not_invent_an_audit():
    from app.job_analysis.understanding import understand
    p=Fixture([response(draft())]);stages=[]
    result=asyncio.run(understand('synthetic',ROW,'v1',p,on_stage=lambda name,value:stages.append(name)))
    assert len(p.requests)==1
    assert stages==['primary']
    assert result['pipeline']['processor_calls']==1
    assert result['pipeline']['usage_status']=='complete'


def test_default_public_entry_runs_one_scoped_audit_for_explicit_claims_and_preserves_both_stages():
    from app.job_analysis.understanding import analyze
    old=prior('使用 Redis 完成任务存储','任务存储')
    raw=json.loads(old['completion']);raw['relations']=[dict(duty_id='d1',requirement_id='r1',basis='explicit',
        evidence=[{'field':'raw_text','quote':'任务存储','occurrence':None}],reason='主理解提出用途，仍需源角色核对')]
    patch=patch_for(old);patch['relations']=[relation('instrumental_use','Redis','任务存储','使用')]
    p=Fixture([response(raw),response(patch)]);stages=[]
    result=asyncio.run(analyze('synthetic',old['analysis']['input_row'],'v1',p,on_stage=lambda name,value:stages.append(name)))
    assert stages==['primary','audit']
    assert len(p.requests)==2
    assert result['analysis']['relations'][0]['basis']=='explicit'
    assert result['primary_run']['analysis']['claims']
    assert result['pipeline']['processor_calls']==2
    assert result['pipeline']['total_usage']['total_tokens']==24
    assert result['request']==p.requests[1]
    assert result['primary_run']['request']==p.requests[0]


def test_audit_transport_failure_keeps_primary_facts_but_does_not_publish_unverified_explicit_edges():
    from app.job_analysis.understanding import understand
    old=prior('使用 Redis 完成任务存储','任务存储');raw=json.loads(old['completion'])
    raw['relations']=[dict(duty_id='d1',requirement_id='r1',basis='explicit',evidence=[{'field':'raw_text','quote':'任务存储','occurrence':None}],reason='主理解的待核验关系')]
    p=Fixture([response(raw),response(status='timeout')])
    result=asyncio.run(understand('synthetic',old['analysis']['input_row'],'v1',p))
    assert len(result['analysis']['claims'])==2
    assert result['analysis']['relations']==[]
    assert result['analysis']['coverage']['relations']['status']=='failed'
    assert result['execution']['status']=='partial'
    assert result['audit_attempt']['execution']['status']=='timeout'
    assert result['primary_run']['analysis']['relations'][0]['basis']=='explicit'
    assert result['pipeline']['usage_status']=='partial'
    assert result['pipeline']['total_usage']['total_tokens']==12

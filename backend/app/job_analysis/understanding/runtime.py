"""One full interpretation, at most one source-risk audit, with independently readable stages."""
from copy import deepcopy
import time

from ..baseline.contract import validate_analysis
from ..foundation.inputs import InputRecord,digest
from .core import analyze as extract,_outcome
from .audit import audit,_draft,_inside
from .policies import apply_constraints


def _risks(primary):
    analysis=primary['analysis']
    if not analysis['claims']:return []
    result=[]
    if any(r['basis']=='explicit' for r in analysis['relations']):result.append('explicit_relation_requires_role_check')
    if any(c['requirement'] and any(c['requirement'][k] is not None for k in ('degree','condition')) for c in analysis['claims']):
        result.append('qualification_requires_subject_binding')
    record=InputRecord.from_row(analysis['namespace'],analysis['input_row'])
    _,changes=apply_constraints(_draft(analysis,record)['claims'],record,_inside)
    if changes:result.append('source_constraint_conflict')
    if any(i.get('kind')=='claim_partially_preserved' for i in primary['execution']['issues']):
        result.append('structured_qualification_unresolved')
    return result


async def understand(namespace,row,input_version,processor,*,prior=None,on_stage=None):
    """Default entry. Synchronous on_stage can durably save each result before continuing."""
    started=time.monotonic()
    primary=await extract(namespace,row,input_version,processor,prior=prior)
    if on_stage:on_stage('primary',deepcopy(primary))
    risks=_risks(primary)
    stages=[primary]
    result=deepcopy(primary)
    selected='primary'
    if risks:
        checked=await audit(primary,processor)
        stages.append(checked)
        if on_stage:on_stage('audit',deepcopy(checked))
        if checked['analysis']['outcome'] in {'failed','not_run'}:
            # The primary facts remain accessible, but unverified explicit links
            # are not republished as an audit success or semantic "unknown".
            result['audit_attempt']=checked
            result['analysis']['relations']=[]
            result['analysis']['coverage']['relations']=dict(status='failed',reason='scoped_audit_execution_failed')
            if any(c['requirement'] for c in result['analysis']['claims']):
                result['analysis']['coverage']['requirements']=dict(status='partial',reason='primary_facts_retained_audit_failed')
            result['analysis']['outcome']=_outcome(result['analysis']['coverage'])
            result['analysis']=validate_analysis(result['analysis']).model_dump()
            result['execution']['status']='partial'
            selected='primary_partial_after_audit_failure'
        else:
            result=checked
            selected='scoped_audit'
        result['primary_run']=primary
    usages=[s['execution']['metadata'].get('usage',{}) for s in stages]
    totals={}
    for usage in usages:
        for key,value in usage.items():
            if type(value) is int and value>=0:totals[key]=totals.get(key,0)+value
    complete=all({'prompt_tokens','completion_tokens','total_tokens'}<=set(u) for u in usages)
    result['pipeline']=dict(id='p1-risk-scoped-audit-1',risks=risks,selected_stage=selected,
        processor_calls=len(stages),total_usage=totals,usage_status='complete' if complete else 'partial' if any(usages) else 'unknown',
        primary_analysis_sha256=digest(primary['analysis']),elapsed_seconds=round(time.monotonic()-started,3))
    return result

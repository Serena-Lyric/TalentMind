"""Evaluation never manufactures human truth from source-span matches."""
from copy import deepcopy

import pytest

from app.job_analysis.foundation.inputs import digest
from test_foundation_inputs import area
from test_work_evolution import duties


def materials():
    analysis = duties('a', ['开发订单交易接口。'])
    annotation = dict(input_sha256=analysis['input_sha256'], human_labels=[
        dict(unit_id='D01', dimension='duty', text='开发订单交易接口', state='not_applicable', logic=None,
             evidence=[dict(field='raw_text', start=0, end=9, quote='开发订单交易接口。', input_sha256=analysis['input_sha256'])])])
    case = dict(sample_id='DEV-SYN', input_sha256=analysis['input_sha256'], assertions=[dict(id='DEV-SYN-A01', **{'class':'A'})])
    return analysis, annotation, case


def test_no_adjudication_reports_coverage_hints_and_uncalculable_accuracy():
    from app.job_analysis.delivery.evaluation import evaluate
    analysis, annotation, case = materials()
    result = evaluate(analysis, annotation, case)
    assert result['units']['duty']['total'] == 1
    assert result['units']['duty']['unknown'] == 1
    assert result['conditions']['unassessed'] == 1
    assert result['conditions_by_class']['A']['unassessed'] == 1
    assert result['diagnostic_coverage']['unassessed_units'] == 1
    assert result['semantic_precision'] is None
    assert result['real_grouping']['denominator'] == 0
    assert result['real_grouping']['accuracy'] is None


def test_bound_agent_diagnostic_accounts_for_omissions_extras_and_conditions():
    from app.job_analysis.delivery.evaluation import evaluate
    analysis, annotation, case = materials()
    assessment = dict(analysis_sha256=digest(analysis), annotation_sha256=digest(annotation), case_sha256=digest(case),
                      kind='agent_diagnostic', units=[dict(unit_id='D01', prediction_ids=['d1'], verdict='partial', reason='boundary uncertain')],
                      conditions=[dict(id='DEV-SYN-A01', verdict='fail', reason='partial source scope')])
    result = evaluate(analysis, annotation, case, assessment)
    assert result['units']['duty']['partial'] == 1
    assert result['units']['duty']['matched'] == 0
    assert result['conditions']['fail'] == 1
    assert result['semantic_precision'] is None
    assert result['assessment_kind'] == 'agent_diagnostic'
    bad = deepcopy(assessment); bad['analysis_sha256'] = '0' * 64
    with pytest.raises(ValueError): evaluate(analysis, annotation, case, bad)
    bad = deepcopy(assessment); bad['units'][0]['prediction_ids'] = ['missing']
    with pytest.raises(ValueError): evaluate(analysis, annotation, case, bad)
    bad = deepcopy(assessment); bad['units'].append(bad['units'][0])
    with pytest.raises(ValueError): evaluate(analysis, annotation, case, bad)


@pytest.mark.parametrize('damage', [None, 'duplicate', 'annotation', 'approval', 'wrong_run'])
def test_evaluation_cli_binds_approved_release_annotation_and_actual_run(area, damage):
    import asyncio
    import json
    from pathlib import Path
    import subprocess
    import sys
    from test_approved_assertions import packet, create
    from test_understanding import claim
    from test_understanding_pipeline import Fixture, response
    from test_work_candidates_cli import KNOWLEDGE, BACKEND
    from app.job_analysis.delivery import DeliveryStore, execute
    from app.job_analysis.knowledge.catalog import load_snapshot
    tmp_path = area.resolve()
    args = packet(tmp_path)
    create(args)
    index, manifest, approval, target = args
    row = json.loads((manifest.parent / 'snapshots/DEV-01.json').read_text(encoding='utf-8'))
    draft = dict(coverage={k:dict(status='complete', reason='synthetic-only') for k in ('goals','objects','duties','requirements','relations')},
                 claims=[claim('d1','duty',row['raw_text'])], relations=[])
    with DeliveryStore(tmp_path / 'state', create=True) as store:
        request = dict(schema_version='m2-delivery-request-1', baseline=store.candidates.read()['binding'], operations=[],
                       items=[dict(namespace='synthetic', row=row, input_version='input-v1')])
        asyncio.run(execute(store,'one',request,load_snapshot(KNOWLEDGE),processor=Fixture([response(draft)])))
    case = dict(sample_id='DEV-01', annotation=str(manifest.parent/'annotations/DEV-01.json'), run_id='one')
    suite = dict(release=str(target/'release.json'), manifest=str(manifest), approval=str(approval), cases=[case])
    if damage == 'duplicate': suite['cases'].append(dict(case))
    if damage == 'annotation': Path(case['annotation']).write_text('{}', encoding='utf-8')
    if damage == 'approval': approval.write_text('{}', encoding='utf-8')
    if damage == 'wrong_run': case['run_id'] = 'unrelated'
    path = tmp_path/'suite.json'
    path.write_text(json.dumps(suite), encoding='utf-8')
    run = subprocess.run([sys.executable,'-m','app.job_analysis.delivery.evaluation','--state',str(tmp_path/'state'),
        '--suite',str(path),'--output',str(tmp_path/'evaluation')], cwd=BACKEND, capture_output=True, text=True, encoding='utf-8')
    assert run.returncode == (0 if damage is None else 1), run.stdout + run.stderr
    if damage is None:
        report = json.loads((tmp_path/'evaluation/evaluation.json').read_text(encoding='utf-8'))
        assert report['total_cases'] == 1
        assert report['cases'][0]['units']['duty']['total'] == 1
        assert report['cases'][0]['conditions_by_class']['A']['total'] == 1
        assert report['independent_market_accuracy'] is None

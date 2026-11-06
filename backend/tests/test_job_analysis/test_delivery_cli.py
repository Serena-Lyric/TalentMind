"""CLI consumers, real process exits, exact retries; no model/network calls."""
import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from app.job_analysis.foundation.inputs import digest
from test_foundation_inputs import area
from test_work_candidates_cli import KNOWLEDGE, BACKEND
from test_work_evolution import duties
from test_work_candidates import create
from test_delivery import request


def cli(*args, success=True):
    run = subprocess.run([sys.executable, '-m', 'app.job_analysis.delivery', *map(str, args)], cwd=BACKEND,
                         capture_output=True, text=True, encoding='utf-8')
    assert run.returncode == (0 if success else 1), run.stderr + run.stdout
    return json.loads(run.stdout)


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
    return path


@pytest.mark.parametrize('phase', ['before_item_commit', 'after_item_commit', 'before_candidate_commit', 'after_candidate_commit', 'after_result_commit'])
def test_process_exit_and_resume_commit_candidate_once(area, phase):
    from app.job_analysis.delivery import DeliveryStore
    root = area / 'delivery'
    cli('init', '--state', root)
    a = duties('a', ['开发订单交易接口。'])
    with DeliveryStore(root) as store:
        path = write(area / 'request.json', request(store, [a], operations=[create(a)]))
    script = '''
import asyncio,os,sys
from pathlib import Path
from app.job_analysis.foundation.inputs import parse_json
from app.job_analysis.knowledge.catalog import load_snapshot
from app.job_analysis.delivery import DeliveryStore,execute
from app.job_analysis.delivery import runner
runner.checkpoint=lambda stage: os._exit(73) if stage==sys.argv[4] else None
with DeliveryStore(sys.argv[1]) as store:
 asyncio.run(execute(store,'one',parse_json(Path(sys.argv[2]).read_text(encoding='utf-8')),load_snapshot(sys.argv[3])))
'''
    crashed = subprocess.run([sys.executable, '-c', script, str(root), str(path), str(KNOWLEDGE), phase], cwd=BACKEND)
    assert crashed.returncode == 73
    out = area / 'private'
    cli('resume', '--state', root, '--id', 'one', '--output', out)
    first = json.loads((out / 'one.json').read_text(encoding='utf-8'))
    assert first['work']['revision'] == 1
    cli('run', '--state', root, '--id', 'one', '--request', path, '--knowledge', KNOWLEDGE, '--output', out)
    with DeliveryStore(root) as store:
        assert store.read('one') == first
        assert store.candidates.read()['revision'] == 1
        assert store.conn.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        assert len(store.item_results('one')) == 1


def test_publication_failure_replays_saved_result_without_reanalysis(area):
    from app.job_analysis.delivery import DeliveryStore, execute, resume
    from app.job_analysis.knowledge.catalog import load_snapshot
    with DeliveryStore(area / 'delivery', create=True) as store:
        a = duties('a', ['开发订单交易接口。'])
        req = request(store, [a], operations=[create(a)])
        output = area / 'blocked'
        output.write_text('not a directory')
        with pytest.raises(OSError): asyncio.run(execute(store, 'one', req, load_snapshot(KNOWLEDGE), output=output))
        committed = store.read('one')
        assert committed['work']['revision'] == 1
        assert asyncio.run(resume(store, 'one', output=area / 'valid')) == committed
        assert store.candidates.read()['revision'] == 1


def test_read_is_bound_to_run_and_expected_request_after_later_run(area):
    from app.job_analysis.delivery import DeliveryStore, execute
    from app.job_analysis.knowledge.catalog import load_snapshot
    with DeliveryStore(area / 'delivery', create=True) as store:
        a = duties('a', ['开发订单交易接口。'])
        one = asyncio.run(execute(store, 'one', request(store, [a]), load_snapshot(KNOWLEDGE)))
        two = asyncio.run(execute(store, 'two', request(store, [a]), load_snapshot(KNOWLEDGE)))
    result = cli('read', '--state', area / 'delivery', '--id', 'one', '--expected-request', one['request_sha256'], '--output', area / 'read')
    assert result['run_id'] == 'one'
    assert result['candidate_revision'] == 1
    assert json.loads((area / 'read/one.json').read_text(encoding='utf-8')) == one
    rejected = cli('read', '--state', area / 'delivery', '--id', 'one', '--expected-request', two['request_sha256'], success=False)
    assert rejected['status'] == 'rejected'


def test_raw_jd_uses_request_bound_recorded_processor_and_no_network(area):
    from app.job_analysis.understanding.core import analyze
    from app.job_analysis.understanding.storage import save_run
    from test_understanding import ROW, draft
    from test_understanding_pipeline import Fixture, response
    source = asyncio.run(analyze('synthetic', ROW, 'v1', Fixture([response(draft())])))
    save_run(area / 'recorded', source)
    replay = write(area / 'replay.json', dict(schema_version='m2-recorded-processor-1', runs=[str(area / 'recorded')]))
    initial = cli('init', '--state', area / 'delivery')
    req = dict(schema_version='m2-delivery-request-1', baseline=initial['binding'],
               items=[dict(namespace='synthetic', row=ROW, input_version='v1')], operations=[])
    path = write(area / 'request.json', req)
    cli('run', '--state', area / 'delivery', '--id', 'one', '--request', path, '--knowledge', KNOWLEDGE, '--replay', replay, '--output', area / 'out')
    result = json.loads((area / 'out/one.json').read_text(encoding='utf-8'))
    assert result['items'][0]['p1']['execution']['metadata']['execution_mode'] == 'cached_recompile'
    assert result['items'][0]['p1']['pipeline']['processor_calls'] == 1
    assert result['items'][0]['alignment']['requirements']


def test_integrated_permanent_demo_consumes_new_work_and_preserves_history(area):
    from app.job_analysis.delivery.demo import run_demo
    summary = run_demo(area / 'demo', KNOWLEDGE)
    assert summary['batches'] >= 6
    assert summary['third_batch_used_new_work'] is True
    assert summary['counterevidence_narrowed_scope'] is True
    assert summary['exact_retry_kept_head'] is True
    assert summary['knowledge_changed_without_p1_change'] is True
    assert summary['stopped_then_resumed'] is True
    assert summary['historical_readback'] is True
    assert summary['real_human_grouping_denominator'] == 0


def test_historical_consumer_can_read_while_another_worker_owns_writer_lease(area):
    from app.job_analysis.delivery import DeliveryStore, execute
    from app.job_analysis.knowledge.catalog import load_snapshot
    with DeliveryStore(area / 'delivery', create=True) as writer:
        a = duties('a', ['开发订单交易接口。'])
        one = asyncio.run(execute(writer, 'one', request(writer, [a]), load_snapshot(KNOWLEDGE)))
        result = cli('read', '--state', area / 'delivery', '--id', 'one')
        assert result['request_sha256'] == one['request_sha256']


def test_recorded_final_p1_run_contains_both_primary_and_audit_requests(area):
    from app.job_analysis.delivery.recorded import RecordedProcessor
    from app.job_analysis.understanding.storage import save_run
    from app.job_analysis.understanding.runtime import understand
    from test_understanding_audit import prior, patch_for, relation
    from test_understanding_pipeline import Fixture, response
    old = prior('使用 Redis 完成任务存储', '任务存储')
    raw = json.loads(old['completion'])
    raw['relations'] = [dict(duty_id='d1', requirement_id='r1', basis='explicit',
        evidence=[dict(field='raw_text', quote='任务存储', occurrence=None)], reason='触发审计')]
    patch = patch_for(old)
    patch['relations'] = [relation('instrumental_use', 'Redis', '任务存储', '使用')]
    source = asyncio.run(understand('synthetic', old['analysis']['input_row'], 'v1', Fixture([response(raw), response(patch)])))
    save_run(area / 'source', source)
    replay = asyncio.run(understand('synthetic', old['analysis']['input_row'], 'v1', RecordedProcessor([area / 'source'])))
    assert replay['analysis']['claims'] == source['analysis']['claims']
    assert replay['analysis']['relations'] == source['analysis']['relations']
    assert replay['pipeline']['processor_calls'] == 2
    assert replay['primary_run']['execution']['metadata']['network_requests'] == 0

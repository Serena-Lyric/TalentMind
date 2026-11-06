"""Public synthetic inputs, real P1/P2/P3/P4 and isolated private SQLite."""
import asyncio
from copy import deepcopy

import pytest

from app.job_analysis.foundation.inputs import digest
from app.job_analysis.knowledge.catalog import load_snapshot
from test_foundation_inputs import area
from test_understanding import ROW, draft
from test_understanding_pipeline import Fixture, response
from test_work_evolution import duties
from test_work_candidates import create
from test_work_candidates_cli import KNOWLEDGE


def api():
    from app.job_analysis.delivery import DeliveryStore, execute, resume
    return DeliveryStore, execute, resume


def request(store, analyses=None, rows=None, operations=None):
    items = ([dict(namespace=a['namespace'], row=a['input_row'], input_version=a['input_version'], analysis=a)
              for a in analyses] if analyses is not None else
             [dict(namespace='synthetic', row=r, input_version='v1') for r in (rows or [ROW])])
    return dict(schema_version='m2-delivery-request-1', baseline=store.candidates.read()['binding'],
                items=items, operations=operations or [])


def test_entry_preserves_analysis_alignment_and_run_bound_candidate_history(area):
    Store, execute, _ = api()
    a = duties('a', ['开发订单交易接口。'])
    with Store(area / 'delivery', create=True) as store:
        result = asyncio.run(execute(store, 'one', request(store, [a], operations=[create(a)]), load_snapshot(KNOWLEDGE)))
        assert result['schema_version'] == 'm2-delivery-result-1'
        assert result['run_id'] == 'one'
        item = result['items'][0]
        assert item['analysis'] == a
        assert item['alignment']['source_analysis_sha256'] == digest(a)
        assert item['roles']['knowledge_sha256'] == result['knowledge']['sha256']
        assert item['role_assignment']['status'] == 'unavailable'
        assert item['role_assignment']['reason'] == 'p2_2_not_validated'
        assert result['work']['candidates']['work-orders']['research']['version'] == 1
        assert result['work']['formal_roles'] == []
        asyncio.run(execute(store, 'two', request(store, [a]), load_snapshot(KNOWLEDGE)))
        assert store.read('one') == result
        assert store.read('two')['work']['revision'] == 2


def test_processor_path_actually_runs_p1_and_preserves_observation_separately(area):
    Store, execute, _ = api()
    with Store(area / 'delivery', create=True) as store:
        processor = Fixture([response(draft())])
        one = asyncio.run(execute(store, 'one', request(store), load_snapshot(KNOWLEDGE), processor=processor))
        row = dict(ROW, crawled_at='2026-11-07T10:00:00+08:00')
        two = asyncio.run(execute(store, 'two', request(store, rows=[row]), load_snapshot(KNOWLEDGE), processor=Fixture([])))
        assert one['items'][0]['p1']['pipeline']['processor_calls'] == 1
        assert two['items'][0]['reuse']['from_run_id'] == 'one'
        assert two['items'][0]['observation'] == row['crawled_at']
        assert two['items'][0]['analysis'] == one['items'][0]['analysis']
        assert 'crawled_at' not in two['items'][0]['analysis']['input_row']


@pytest.mark.parametrize('change', ['content', 'model', 'knowledge', 'input_version'])
def test_dependency_changes_have_conservative_and_separate_reuse(area, change):
    Store, execute, _ = api()
    from app.job_analysis.knowledge.catalog import LoadedSnapshot
    from app.job_analysis.knowledge.models import validate_snapshot
    from app.job_analysis.foundation.inputs import canonical
    knowledge = load_snapshot(KNOWLEDGE)
    with Store(area / 'delivery', create=True) as store:
        one = asyncio.run(execute(store, 'one', request(store), knowledge, processor=Fixture([response(draft())])))
        req = request(store)
        processor = Fixture([response(draft())])
        if change == 'content':
            req['items'][0]['row'] = dict(ROW, raw_text=ROW['raw_text'] + '\n新职责待理解')
        if change == 'input_version': req['items'][0]['input_version'] = 'v2'
        if change == 'model': processor.descriptor = dict(processor.descriptor, model_revision='changed')
        if change == 'knowledge':
            import hashlib
            from pathlib import Path
            import json
            target = area / 'knowledge'
            target.mkdir()
            value = knowledge.snapshot.model_dump()
            value['revision'] = 'test-v2'
            raw = canonical(value).encode()
            (target / 'knowledge.json').write_bytes(raw)
            (target / 'manifest.json').write_text(json.dumps(dict(schema_version='m2-knowledge-manifest-1', sha256=hashlib.sha256(raw).hexdigest())))
            knowledge = load_snapshot(target)
        two = asyncio.run(execute(store, 'two', req, knowledge, processor=processor))
        assert two['items'][0]['reuse']['p1'] is (change == 'knowledge')
        if change == 'knowledge':
            assert two['items'][0]['analysis'] == one['items'][0]['analysis']
            assert two['items'][0]['alignment']['knowledge_sha256'] != one['items'][0]['alignment']['knowledge_sha256']
        assert store.read('one') == one


def test_stop_then_resume_keeps_committed_item_and_unknown_failures_separate(area):
    Store, execute, resume = api()
    with Store(area / 'delivery', create=True) as store:
        rows = [ROW, dict(ROW, id='two')]
        stopped = asyncio.run(execute(store, 'one', request(store, rows=rows), load_snapshot(KNOWLEDGE),
                                     processor=Fixture([response(draft())]), stop=lambda: bool(store.item_results('one'))))
        assert stopped['status'] == 'stopped'
        assert stopped['counts']['not_run'] == 1
        assert stopped['work'] is None
        finished = asyncio.run(resume(store, 'one', processor=Fixture([response(status='timeout')])))
        assert finished['counts']['failed'] == 1
        assert finished['counts']['complete'] == 1
        assert finished['items'][0]['analysis'] == stopped['items'][0]['analysis']
        assert finished['items'][1]['analysis']['outcome'] == 'failed'


def test_partial_is_preserved_but_never_reused_as_complete(area):
    Store, execute, _ = api()
    incomplete = draft()
    incomplete['coverage']['duties'] = dict(status='partial', reason='source_ambiguous')
    with Store(area / 'delivery', create=True) as store:
        one = asyncio.run(execute(store, 'one', request(store), load_snapshot(KNOWLEDGE), processor=Fixture([response(incomplete)])))
        assert one['counts']['partial'] == 1
        two = asyncio.run(execute(store, 'two', request(store), load_snapshot(KNOWLEDGE), processor=Fixture([response(draft())])))
        assert two['items'][0]['reuse']['p1'] is False
        assert two['counts']['complete'] == 1


def test_duplicate_request_stale_candidate_and_wrong_input_are_rejected(area):
    Store, execute, _ = api()
    a = duties('a', ['开发订单交易接口。'])
    with Store(area / 'delivery', create=True) as store:
        req = request(store, [a])
        one = asyncio.run(execute(store, 'one', req, load_snapshot(KNOWLEDGE)))
        assert asyncio.run(execute(store, 'one', req, load_snapshot(KNOWLEDGE))) == one
        with pytest.raises(ValueError):
            asyncio.run(execute(store, 'stale', req, load_snapshot(KNOWLEDGE)))
        bad = request(store, [a]); bad['items'][0]['row'] = dict(a['input_row'], raw_text='different')
        with pytest.raises(ValueError): asyncio.run(execute(store, 'bad', bad, load_snapshot(KNOWLEDGE)))
        with pytest.raises(ValueError): asyncio.run(execute(store, 'one', request(store, [a]), load_snapshot(KNOWLEDGE)))


def test_second_worker_cannot_steal_active_delivery(area):
    Store, _, _ = api()
    with Store(area / 'delivery', create=True):
        with pytest.raises((ValueError, RuntimeError)):
            Store(area / 'delivery')


def test_downstream_failure_keeps_p1_readable_and_retry_in_new_run(area, monkeypatch):
    Store, execute, _ = api()
    from app.job_analysis.delivery import runner
    real_align = runner.align_analysis
    with Store(area / 'delivery', create=True) as store:
        monkeypatch.setattr(runner, 'align_analysis', lambda *args: (_ for _ in ()).throw(ValueError('private failure')))
        one = asyncio.run(execute(store, 'one', request(store), load_snapshot(KNOWLEDGE), processor=Fixture([response(draft())])))
        assert one['items'][0]['analysis']['claims']
        assert one['items'][0]['interpretation_status'] == 'failed'
        assert one['counts']['partial'] == 1
        monkeypatch.setattr(runner, 'align_analysis', real_align)
        two = asyncio.run(execute(store, 'two', request(store), load_snapshot(KNOWLEDGE), processor=Fixture([])))
        assert two['items'][0]['reuse']['p1'] is True
        assert two['items'][0]['alignment']['requirements']


def test_failed_candidate_commit_exposes_completed_facts_to_reader(area, monkeypatch):
    Store, execute, resume = api()
    from app.job_analysis.delivery import runner
    original = runner.apply_batch
    with Store(area / 'delivery', create=True) as store:
        monkeypatch.setattr(runner, 'apply_batch', lambda *args: (_ for _ in ()).throw(ValueError('private failure')))
        with pytest.raises(ValueError):
            asyncio.run(execute(store, 'one', request(store), load_snapshot(KNOWLEDGE), processor=Fixture([response(draft())])))
        result = store.read('one')
        assert result['work'] is None
        assert result['status'] == 'candidate_failed'
        assert result['counts']['complete'] == 1
        monkeypatch.setattr(runner, 'apply_batch', original)
        assert asyncio.run(resume(store, 'one', processor=Fixture([])))['work']['revision'] == 1


def test_prompt_or_code_change_refuses_resume_but_historical_read_is_unchanged(area, monkeypatch):
    Store, execute, resume = api()
    from app.job_analysis.delivery import runner
    with Store(area / 'delivery', create=True) as store:
        original = asyncio.run(execute(store, 'one', request(store), load_snapshot(KNOWLEDGE), processor=Fixture([response(draft())])))
        asyncio.run(execute(store, 'stopped', request(store), load_snapshot(KNOWLEDGE), processor=Fixture([]), stop=lambda: True))
        monkeypatch.setattr(runner, 'LOADED', dict(runner.LOADED, prompt_sha256='0' * 64))
        monkeypatch.setattr(runner, 'dependencies', lambda: runner.LOADED)
        assert store.read('one') == original
        with pytest.raises(ValueError, match='original code'):
            asyncio.run(resume(store, 'stopped', processor=Fixture([])))
        later = asyncio.run(execute(store, 'later', request(store), load_snapshot(KNOWLEDGE), processor=Fixture([response(draft())])))
        assert later['items'][0]['reuse']['p1'] is False


def test_run_id_does_not_leak_into_candidate_identifier_limits(area):
    Store, execute, _ = api()
    with Store(area / 'delivery', create=True) as store:
        result = asyncio.run(execute(store, 'A' * 100, request(store), load_snapshot(KNOWLEDGE), processor=Fixture([response(draft())])))
        assert result['work']['revision'] == 1


@pytest.mark.parametrize('status', ['not_run', 'unrecognized'])
def test_not_executed_and_semantically_empty_are_distinct_from_failure(area, status):
    Store, execute, _ = api()
    value = draft()
    value['claims'] = []
    processor = Fixture([response(status='not_run') if status == 'not_run' else response(value)])
    with Store(area / 'delivery', create=True) as store:
        result = asyncio.run(execute(store, 'one', request(store), load_snapshot(KNOWLEDGE), processor=processor))
        expected = 'not_run' if status == 'not_run' else 'unknown'
        assert result['items'][0]['status'] == expected
        assert result['counts'][expected] == 1
        assert result['counts']['failed'] == 0
        assert result['items'][0]['p1_complete'] is False


def test_later_run_cannot_rebase_an_older_stopped_candidate_request(area):
    Store, execute, resume = api()
    with Store(area / 'delivery', create=True) as store:
        asyncio.run(execute(store, 'old', request(store), load_snapshot(KNOWLEDGE), processor=Fixture([]), stop=lambda: True))
        latest = asyncio.run(execute(store, 'new', request(store), load_snapshot(KNOWLEDGE), processor=Fixture([response(draft())])))
        with pytest.raises(ValueError, match='stale'):
            asyncio.run(resume(store, 'old', processor=Fixture([])))
        assert store.read('old')['status'] == 'candidate_failed'
        assert store.read('old')['items'][0]['analysis']['claims']
        assert store.candidates.read() == latest['work']


def test_primary_checkpoint_survives_cancellation_without_claiming_item_complete(area, monkeypatch):
    Store, execute, resume = api()
    from app.job_analysis.delivery import runner
    from app.job_analysis.understanding import core
    from test_understanding_audit import prior
    source = prior('使用 Redis 完成任务存储', '任务存储')
    import json
    value = json.loads(source['completion'])
    value['relations'] = [dict(duty_id='d1', requirement_id='r1', basis='explicit',
        evidence=[dict(field='raw_text', quote='任务存储', occurrence=None)], reason='触发定向审计')]
    class CancelAfterPrimary(Fixture):
        async def complete(self, messages):
            if self.requests: raise asyncio.CancelledError()
            return await super().complete(messages)
    with Store(area / 'delivery', create=True) as store:
        with pytest.raises(asyncio.CancelledError):
            asyncio.run(execute(store, 'one', request(store, rows=[source['analysis']['input_row']]), load_snapshot(KNOWLEDGE),
                                processor=CancelAfterPrimary([response(value)])))
        saved = store.read('one')
        assert saved['counts']['not_run'] == 1
        assert saved['work'] is None
        assert saved['stage_results'][0]['stage'] == 'primary'
        assert saved['stage_results'][0]['p1']['analysis']['claims']


def test_explicit_not_run_analysis_is_counted_as_not_executed(area):
    Store, execute, _ = api()
    analysis = duties('unexecuted', ['开发订单交易接口。'])
    analysis['claims'] = []
    analysis['outcome'] = 'not_run'
    for value in analysis['coverage'].values(): value.update(status='not_run', reason='explicitly_not_executed')
    with Store(area / 'delivery', create=True) as store:
        result = asyncio.run(execute(store, 'one', request(store, [analysis]), load_snapshot(KNOWLEDGE)))
        assert result['counts']['not_run'] == 1
        assert result['counts']['failed'] == 0


def test_live_prompt_change_cannot_reuse_or_relabel_loaded_dependencies(area, monkeypatch):
    Store, execute, resume = api()
    from app.job_analysis.delivery import runner
    with Store(area / 'delivery', create=True) as store:
        old = asyncio.run(execute(store, 'one', request(store), load_snapshot(KNOWLEDGE), processor=Fixture([response(draft())])))
        prompt = area / 'changed-prompt.txt'
        prompt.write_bytes(runner.PROMPT_PATH.read_bytes() + b'\nchanged')
        monkeypatch.setattr(runner, 'PROMPT_PATH', prompt)
        with pytest.raises(ValueError, match='loaded dependencies changed'):
            asyncio.run(execute(store, 'two', request(store), load_snapshot(KNOWLEDGE), processor=Fixture([])))
        assert store.read('one') == old


def test_truncated_processor_result_keeps_valid_facts_without_complete_reuse(area):
    Store, execute, _ = api()
    completion = response(draft())
    completion.finish_reason = 'length'
    with Store(area / 'delivery', create=True) as store:
        result = asyncio.run(execute(store, 'one', request(store), load_snapshot(KNOWLEDGE), processor=Fixture([completion])))
        item = result['items'][0]
        assert result['counts']['partial'] == 1
        assert item['p1']['execution']['status'] == 'truncated'
        assert len(item['analysis']['claims']) == 2
        assert item['p1_complete'] is False
        assert item['analysis']['coverage']['duties']['status'] == 'partial'

"""Product workflow with real native stages, synthetic JD and temporary SQLite only."""
import importlib
import json
import sqlite3
import threading
import shutil
from contextlib import closing

import pytest


@pytest.fixture
def product(tmp_path, monkeypatch):
    assert importlib.util.find_spec('app.job_analysis.product.workflow'), 'M2 product workflow missing'
    from app.job_analysis.product import source, workflow
    rows = [
        dict(id=1, source='boss', job_title='后端工程师', raw_text='岗位职责：负责软件开发。\n任职要求：必须掌握 Python。', duties=None, experience=None),
        dict(id=2, source='liepin', job_title='工程师', raw_text='公司使用 Python，具体岗位职责待确认。'),
        dict(id=3, source=None, job_title='历史缺来源', raw_text='熟悉 Python'),
        dict(id=4, source='boss', job_title='空正文', raw_text=None),
    ]
    monkeypatch.setattr(source, 'read_mysql', lambda selection: (rows, {'kind': 'synthetic_readonly_fixture'}))
    engine = workflow.Workflow(tmp_path / 'product')
    try:
        yield engine, source, workflow
    finally:
        engine.join(10)
        assert not engine.busy
        shutil.rmtree(engine.root)
        assert not engine.root.exists()


def finish(engine, run_id):
    engine.start(run_id)
    engine.join(15)
    assert not engine.busy
    return engine.get(run_id)


def test_full_denominator_native_stages_and_original_nulls(product):
    engine, source, _ = product
    draft = engine.create(source.Selection(limit=4))
    assert draft['status'] == 'queued' and draft['summary']['input_total'] == 4
    assert not engine.busy
    result = finish(engine, draft['run_id'])
    assert result['status'] == 'completed_with_issues'
    assert result['summary']['stage_complete'] == 2
    assert result['summary']['final_counts']['input_invalid'] == 2
    assert result['summary']['b1']['out_of_scope'] == 0
    assert result['summary']['b2']['failed'] == 0
    assert result['summary']['b22']['catalog_conflict_assessment'] == 'not_evaluated'
    assert len(result['items']) == 4
    detail = engine.item(draft['run_id'], 1)
    assert detail['input']['duties'] is None
    assert set(detail['stages']) == {'b1', 'b2', 'b22', 'b3'}
    assert all(detail['stages'][s]['status'] == 'saved' for s in ('b1', 'b2', 'b22', 'b3'))
    assert detail['stages']['b2']['result']['body']['statements']
    assert detail['formal_statistics_eligible'] is False
    assert engine.item(draft['run_id'], 3)['stages']['b1']['result']['execution_status'] == 'input_failed'
    assert '原始' not in json.dumps(result)  # summary endpoint does not return raw input
    assert '"raw_text":' not in json.dumps(result)
    with closing(sqlite3.connect(engine.root / 'analysis.sqlite3')) as conn:
        assert conn.execute('SELECT COUNT(*) FROM b22_reports').fetchone()[0] == 2
        assert conn.execute('SELECT COUNT(*) FROM b31_reports').fetchone()[0] == 2


def test_replay_frozen_input_no_mysql_reselect_and_no_members_leak(product, monkeypatch):
    engine, source, _ = product
    original = engine.create(source.Selection(limit=4))
    finish(engine, original['run_id'])
    monkeypatch.setattr(source, 'read_mysql', lambda _: pytest.fail('replay reread MySQL'))
    replay = engine.replay(original['run_id'], 'v2')
    result = finish(engine, replay['run_id'])
    assert result['input_sha256'] == original['input_sha256']
    assert result['parent_run_id'] == original['run_id']
    assert result['versions']['revision'] == 'v2'
    assert len(result['items']) == 4
    assert engine.report(original['run_id'])['summary']['input_total'] == 4
    for ordinal in (1, 2):
        for stage in ('b1', 'b2', 'b22', 'b3'):
            result = engine.item(replay['run_id'], ordinal)['stages'][stage]['result']
            assert result['jd_id'] == str(ordinal)
    with pytest.raises(ValueError): engine.item(original['run_id'], 999)
    with pytest.raises(ValueError): engine.get('../private')


def test_same_version_repeat_reuses_native_facts_without_overwriting_old_report(product):
    engine, source, _ = product
    first = engine.create(source.Selection(limit=4))
    finish(engine, first['run_id'])
    original = engine.report(first['run_id'])
    with closing(sqlite3.connect(engine.root / 'analysis.sqlite3')) as conn:
        before = conn.execute('SELECT COUNT(*) FROM b2_attempts').fetchone()[0]
    replay = engine.replay(first['run_id'], 'v1')
    result = finish(engine, replay['run_id'])
    with closing(sqlite3.connect(engine.root / 'analysis.sqlite3')) as conn:
        assert conn.execute('SELECT COUNT(*) FROM b2_attempts').fetchone()[0] == before
    assert original == engine.report(first['run_id'])
    assert result['summary'] == original['summary']
    assert engine.item(first['run_id'], 1)['stages']['b2']['result']['attempt_id'] == engine.item(replay['run_id'], 1)['stages']['b2']['result']['attempt_id']


def test_stop_stage_boundary_resume_keeps_committed_stage(product, monkeypatch):
    engine, source, _ = product
    entered, release = threading.Event(), threading.Event()
    original = engine._execute_stage
    def pause(stage, *args):
        value = original(stage, *args)
        if stage == 'b1':
            entered.set()
            assert release.wait(5)
        return value
    monkeypatch.setattr(engine, '_execute_stage', pause)
    draft = engine.create(source.Selection(limit=4))
    engine.start(draft['run_id'])
    assert entered.wait(5)
    try:
        stopped = engine.stop(draft['run_id'])
        assert stopped['status'] == 'stopping'
    finally:
        release.set()
    engine.join(10)
    assert engine.get(draft['run_id'])['status'] == 'stopped'
    assert engine.get(draft['run_id'])['summary']['final_counts']['stopped'] == 4
    first = engine.item(draft['run_id'], 1)['stages']['b1']['run_id']
    monkeypatch.setattr(engine, '_execute_stage', original)
    result = finish(engine, draft['run_id'])
    assert result['summary']['stage_complete'] == 2
    assert engine.item(draft['run_id'], 1)['stages']['b1']['run_id'] == first


def test_version_drift_rejects_resume_old_report_and_new_replay(product, monkeypatch):
    engine, source, workflow = product
    draft = engine.create(source.Selection(limit=4))
    original = workflow.versions
    monkeypatch.setattr(workflow, 'versions', lambda revision: {**original(revision), 'implementation': 'changed'})
    with pytest.raises(ValueError, match='version'): engine.start(draft['run_id'])
    replay = engine.replay(draft['run_id'], 'v2')
    assert replay['versions']['implementation'] == 'changed'


def test_failure_keeps_other_jds_and_safe_reason(product, monkeypatch):
    engine, source, _ = product
    original = engine._execute_stage
    def broken(stage, row, *args):
        if stage == 'b2' and row['id'] == 1: raise RuntimeError('password=DO_NOT_SAVE')
        return original(stage, row, *args)
    monkeypatch.setattr(engine, '_execute_stage', broken)
    draft = engine.create(source.Selection(limit=4))
    result = finish(engine, draft['run_id'])
    assert result['summary']['final_counts']['failed'] == 1
    assert result['summary']['stage_complete'] == 1
    report = engine.report(draft['run_id'])
    assert 'DO_NOT_SAVE' not in json.dumps(report)
    assert engine.item(draft['run_id'], 1)['stages']['b22']['status'] == 'blocked'


def test_input_hash_tamper_rejected(product):
    engine, source, _ = product
    draft = engine.create(source.Selection(limit=4))
    path = engine.root / 'runs' / draft['run_id'] / 'input.json'
    path.write_text('[]', encoding='utf-8')
    with pytest.raises(ValueError, match='integrity'): engine.start(draft['run_id'])


def test_changed_valid_jd_becomes_invalid_without_cached_member_leak(product, monkeypatch):
    engine, source, _ = product
    first = engine.create(source.Selection(limit=4))
    finish(engine, first['run_id'])
    monkeypatch.setattr(source, 'read_mysql', lambda _: ([dict(id=1, source=None, job_title='原岗位', raw_text='Python')], {'kind':'synthetic'}))
    second = engine.create(source.Selection(limit=1))
    result = finish(engine, second['run_id'])
    assert result['summary']['final_counts']['input_invalid'] == 1
    assert result['summary']['final_counts']['failed'] == 0
    assert engine.item(second['run_id'], 1)['stages']['b1']['result']['execution_status'] == 'input_failed'


def test_version_tracks_shared_dictionary_and_cleaner(tmp_path, monkeypatch):
    from app.job_analysis.product import workflow
    monkeypatch.setattr(workflow, 'APP', tmp_path)
    skills = tmp_path / 'skills'; skills.mkdir()
    collect = tmp_path / 'collect'; collect.mkdir()
    dictionary = skills / 'skill_dict_seed.json'
    cleaner = collect / 'cleaner.py'
    dictionary.write_text('[]', encoding='utf-8'); cleaner.write_text('v1', encoding='utf-8')
    first = workflow.versions('v1')
    dictionary.write_text('[{"canonical":"new"}]', encoding='utf-8')
    second = workflow.versions('v1')
    assert first != second
    cleaner.write_text('v2', encoding='utf-8')
    assert second != workflow.versions('v1')


def test_crash_after_report_commit_is_recoverable(product, monkeypatch):
    engine, source, workflow = product
    original = workflow.publish
    class Crash(BaseException): pass
    draft = engine.create(source.Selection(limit=4))
    # Model an actual process exit at the final durable boundary, not an ordinary failure.
    native = engine._execute_stage
    def no_native_publication(stage, *args): return native(stage, *args)
    monkeypatch.setattr(engine, '_execute_stage', no_native_publication)
    def crashed_publish(body, *args):
        if 'summary' in body: raise Crash()
        return original(body, *args)
    monkeypatch.setattr(workflow, 'publish', crashed_publish)
    # Call synchronously so pytest does not turn the simulated process exit into thread noise.
    lease = workflow.Lease(engine.root / 'worker.lock')
    with engine.db() as conn: conn.execute("UPDATE product_runs SET status='running' WHERE id=?", (draft['run_id'],))
    with pytest.raises(Crash): engine._work(draft['run_id'], lease)
    recovered = workflow.Workflow(engine.root)
    assert recovered.get(draft['run_id'])['status'] == 'interrupted'
    monkeypatch.setattr(workflow, 'publish', original)
    result = finish(recovered, draft['run_id'])
    assert result['summary']['finalized'] == 4
    assert (engine.root / 'reports' / (draft['run_id'] + '.json')).exists()


def test_selection_rejects_unbounded_or_injected_filter():
    assert importlib.util.find_spec('app.job_analysis.product.source'), 'M2 source missing'
    from app.job_analysis.product.source import Selection
    for payload in ({'limit': 0}, {'limit': 5001}, {'id_min': 5, 'id_max': 1}, {'sources': ['boss\x00']}, {'unexpected': 'value'}):
        with pytest.raises(ValueError): Selection(**payload)


def test_mysql_readonly_parameter_binding_and_finally_rollback(monkeypatch):
    assert importlib.util.find_spec('app.job_analysis.product.source'), 'M2 source missing'
    from app.job_analysis.product import source
    commands = []
    class Cursor:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def execute(self, sql, args=None): commands.append((sql, args))
        def fetchall(self): return [dict(id=9, source='odd source', job_title='role', raw_text='Python')]
    class Connection:
        def cursor(self): return Cursor()
        def rollback(self): commands.append(('ROLLBACK', None))
        def close(self): commands.append(('CLOSE', None))
    monkeypatch.setattr(source, 'connect', lambda: Connection())
    rows, provenance = source.read_mysql(source.Selection(sources=["x' OR 1=1 --"], id_min=2, id_max=20, limit=3))
    assert rows[0]['id'] == 9
    assert commands[0][0] == 'START TRANSACTION READ ONLY'
    select, args = commands[1]
    assert "x' OR" not in select and "x' OR 1=1 --" in args
    assert args[-1] == 3
    assert commands[-2:] == [('ROLLBACK', None), ('CLOSE', None)]
    assert provenance['transaction'] == 'READ ONLY; ROLLBACK'

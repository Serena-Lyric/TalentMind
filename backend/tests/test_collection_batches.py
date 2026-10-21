"""Synthetic batch orchestration; temporary files only, no browser or services."""
import importlib
import json
import os
import sys
import threading
import time
from io import StringIO

import pytest

from app.collect import control, worker_process


@pytest.fixture
def batch(tmp_path, monkeypatch):
    assert importlib.util.find_spec('app.collect.batch'), 'batch orchestration is missing'
    module = importlib.import_module('app.collect.batch')
    monkeypatch.setattr(module, '_STATE_DIR', tmp_path / 'batches')
    monkeypatch.setattr(module, '_ACTIVE_ID', None)
    monkeypatch.setattr(module, '_THREAD', None)
    monkeypatch.setattr(module, '_STOP', threading.Event())
    monkeypatch.setattr(control, '_STATE_DIR', tmp_path / 'single')
    monkeypatch.setattr(control, '_STATE_PATH', tmp_path / 'single' / 'state.json')
    monkeypatch.setattr(control, '_PROCESS', None)
    monkeypatch.setattr(control, '_STARTING_RUN', None)
    monkeypatch.setattr(control, '_RESERVATION', None)
    monkeypatch.setattr(control, '_DONE_EVENTS', {})
    monkeypatch.setattr(control, '_worker_environment', os.environ.copy)
    monkeypatch.setattr(control, '_ensure_browser', lambda endpoint, profile, platform, target: {
        'endpoint': endpoint, 'user_data_dir': profile,
        'platform_access': {platform: {'can_collect': True, 'access_state': 'public_accessible'}}})
    monkeypatch.setattr(control, 'get_database_stats', lambda: pytest.fail('batch must not query DB'))
    control.update_config({'switch_interval_min': 0, 'switch_interval_max': 0})
    yield module
    if module._ACTIVE_ID:
        module.stop_batch(module._ACTIVE_ID)
    if module._THREAD:
        module._THREAD.join(8)
        assert not module._THREAD.is_alive()
    for path in sorted(tmp_path.rglob('*'), reverse=True):
        if path.is_file():
            path.unlink()
    assert not list(tmp_path.rglob('*.json'))


def plan(**changes):
    return dict(platform='boss', keywords=[' Python ', 'Java', 'Python'],
                cities=[{'name': '北京', 'code': '101010100'},
                        {'name': '上海', 'code': '101020100'},
                        {'name': '北京', 'code': '101010100'}],
                pages=1, max_jobs=5, detail_limit=5, **changes)


def wait_for(batch, batch_id, statuses, timeout=5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = batch.get_batch(batch_id)
        if result['status'] in statuses:
            return result
        time.sleep(.01)
    pytest.fail(f'batch did not reach {statuses}: {result}')


def synthetic_workers(monkeypatch, outcomes=None):
    calls = []
    outcomes = iter(outcomes or [{}] * 10)
    class Worker:
        pid = 12345
        def __init__(self, stats):
            self.stdout = StringIO('TM_EVENT ' + json.dumps({'event': 'finished', 'stats': stats}) + '\n')
        def wait(self): return 0
        def poll(self): return 0
    def spawn(args, **kwargs):
        calls.append(args)
        stats = dict(listed=5, details=3, new=1, detail_attempted=3, detail_obtained=2,
                     complete=2, inserted=1, updated=1, skipped=0, rejected=0, failed=0, unattempted=2,
                     **next(outcomes))
        return Worker(stats)
    monkeypatch.setattr(control, '_spawn_process', spawn)
    return calls


def test_create_normalizes_cartesian_plan_without_start_or_private_config(batch, monkeypatch):
    monkeypatch.setattr(control, 'start_task', lambda *a, **kw: pytest.fail('create started task'))
    monkeypatch.setattr(control, '_ensure_browser', lambda *a: pytest.fail('create opened browser'))
    before = control._STATE_PATH.read_bytes()
    result = batch.create_batch(plan())
    assert result['status'] == 'queued'
    assert result['completed'] == 0 and result['total'] == 4
    assert [(x['keyword'], x['city']['name']) for x in result['items']] == [
        ('Python', '北京'), ('Python', '上海'), ('Java', '北京'), ('Java', '上海')]
    assert all(x['status'] == 'queued' and x['run_id'] is None and x['complete'] is None
               and x['listed'] is None for x in result['items'])
    assert control._STATE_PATH.read_bytes() == before
    assert 'cdp_endpoint' not in json.dumps(result)
    assert batch.get_batch(result['batch_id']) == result
    assert batch.list_batches() == {'items': [result], 'total': 1}


@pytest.mark.parametrize('changes', [
    {'platform': 'unknown'}, {'keywords': []}, {'keywords': [' ']}, {'keywords': 'Python'},
    {'keywords': ['a,b']}, {'keywords': ['x' * 101]}, {'keywords': [None]},
    {'keywords': [str(i) for i in range(11)]}, {'cities': []}, {'cities': [None]},
    {'cities': [{'name': '北京', 'code': '530'}]},
    {'cities': [{'name': '北京', 'code': '101010100', 'extra': True}]},
    {'pages': 2}, {'max_jobs': 6}, {'detail_limit': 0}, {'max_jobs': True},
    {'cdp_endpoint': 'http://127.0.0.1:1'}, {'owner': 'public-owner'}, {'platform': None},
])
def test_invalid_plan_has_no_files_or_side_effects(batch, changes):
    payload = plan()
    payload.update(changes)
    with pytest.raises(ValueError):
        batch.create_batch(payload)
    assert batch.list_batches() == {'items': [], 'total': 0}


def test_combinations_capped_at_fifty(batch, monkeypatch):
    cities = [{'name': str(i), 'code': str(i)} for i in range(6)]
    monkeypatch.setattr(control, 'get_platforms', lambda: [{'platform': 'boss', 'supported': True, 'cities': cities}])
    payload = plan()
    payload.update(keywords=[str(i) for i in range(10)], cities=cities[:6])
    with pytest.raises(ValueError): batch.create_batch(payload)
    payload['cities'] = cities[:5]
    assert batch.create_batch(payload)['total'] == 50


def test_sequential_runs_archive_counts_and_preserve_single_config(batch, monkeypatch):
    calls = synthetic_workers(monkeypatch)
    control.update_config({'search_url_template': 'https://www.zhipin.com/custom?key={keyword}'})
    before = control.get_config()
    draft = batch.create_batch(plan())
    batch.start_batch(draft['batch_id'])
    result = wait_for(batch, draft['batch_id'], {'completed'})
    assert result['completed'] == result['total'] == 4
    assert len(calls) == 4
    assert len({x['run_id'] for x in result['items']}) == 4
    assert all(x['status'] == 'completed' and x['complete'] == 2 and x['updated'] == 1 for x in result['items'])
    assert len(control._load_state()['history']) == 4
    assert control.get_config() == before
    with pytest.raises(RuntimeError): batch.start_batch(draft['batch_id'])


def test_batch_archives_content_and_identity_counters(batch, monkeypatch):
    extra = [{'content_eligible': 2, 'identity_pending': 1, 'identity_verified': 1}] * 4
    synthetic_workers(monkeypatch, extra)
    draft = batch.create_batch(plan())
    batch.start_batch(draft['batch_id'])
    result = wait_for(batch, draft['batch_id'], {'completed'})
    assert all(item['content_eligible'] == 2 for item in result['items'])
    assert all(item['identity_pending'] == 1 for item in result['items'])
    assert all(item['identity_verified'] == 1 for item in result['items'])


@pytest.mark.parametrize('gate', ['login_required', 'verification_required', 'content_limited'])
def test_browser_gate_stops_entire_batch_with_unknown_counts(batch, monkeypatch, gate):
    monkeypatch.setattr(control, '_ensure_browser', lambda endpoint, profile, platform, target: {
        'platform_access': {platform: {'can_collect': False, 'access_state': gate}}})
    draft = batch.create_batch(plan())
    batch.start_batch(draft['batch_id'])
    result = wait_for(batch, draft['batch_id'], {'blocked'})
    assert result['stop_reason'] == gate
    assert result['completed'] == 1
    assert result['items'][0]['status'] == 'blocked'
    assert result['items'][0]['complete'] is None
    assert [x['status'] for x in result['items'][1:]] == ['cancelled'] * 3
    assert all(x['run_id'] is None for x in result['items'][1:])


def test_worker_gate_stops_batch_but_ordinary_error_continues(batch, monkeypatch):
    synthetic_workers(monkeypatch, [{'stop_reason': 'ordinary_page_failure'},
                                  {'stop_reason': 'detail:content_limited'}])
    draft = batch.create_batch(plan())
    batch.start_batch(draft['batch_id'])
    result = wait_for(batch, draft['batch_id'], {'blocked'})
    assert result['completed'] == 2
    assert [x['status'] for x in result['items']] == ['error', 'blocked', 'cancelled', 'cancelled']


def test_waiting_batch_holds_shared_reservation_and_stop_interrupts_delay(batch, monkeypatch):
    synthetic_workers(monkeypatch)
    control.update_config({'switch_interval_min': 360, 'switch_interval_max': 720})
    draft = batch.create_batch(plan())
    another = batch.create_batch(plan())
    batch.start_batch(draft['batch_id'])
    waiting = wait_for(batch, draft['batch_id'], {'waiting_next_round'})
    assert waiting['next_run_at']
    with pytest.raises(RuntimeError): control.start_task({})
    with pytest.raises(RuntimeError): control.prepare_browser(config_payload={'keywords': ['different']})
    with pytest.raises(RuntimeError): batch.start_batch(another['batch_id'])
    stopped = batch.stop_batch(draft['batch_id'])
    assert stopped['status'] == 'stopped'
    assert stopped['next_run_at'] is None
    assert stopped['completed'] == 1
    assert [x['status'] for x in stopped['items']] == ['completed', 'cancelled', 'cancelled', 'cancelled']
    assert control._RESERVATION is None


def test_stop_preparing_blocks_next_item_and_waits_for_archive(batch, monkeypatch):
    entered, release = threading.Event(), threading.Event()
    def prepare(*args):
        entered.set()
        release.wait(15)
        return {'platform_access': {'boss': {'can_collect': True}}}
    monkeypatch.setattr(control, '_ensure_browser', prepare)
    monkeypatch.setattr(control, '_spawn_process', lambda *a, **kw: pytest.fail('stopped prepare spawned worker'))
    draft = batch.create_batch(plan())
    batch.start_batch(draft['batch_id'])
    assert entered.wait(2)
    try:
        stopping = batch.stop_batch(draft['batch_id'])
        assert stopping['status'] == 'stopping'
        assert [x['status'] for x in stopping['items'][1:]] == ['cancelled'] * 3
        assert stopping['finished_at'] is None
        with pytest.raises(RuntimeError): control.start_task({})
    finally:
        release.set()
    result = wait_for(batch, draft['batch_id'], {'stopped'})
    assert result['items'][0]['status'] == 'stopped'
    assert control._load_state()['history'][0]['status'] == 'stopped'


def test_single_preparing_task_prevents_batch_start(batch, monkeypatch):
    entered, release = threading.Event(), threading.Event()
    def prepare(*args):
        entered.set()
        release.wait(8)
        return {'platform_access': {'boss': {'can_collect': False, 'access_state': 'login_required'}}}
    monkeypatch.setattr(control, '_ensure_browser', prepare)
    run = control.start_task({})
    assert entered.wait(1)
    try:
        draft = batch.create_batch(plan())
        with pytest.raises(RuntimeError): batch.start_batch(draft['batch_id'])
        assert batch.get_batch(draft['batch_id'])['status'] == 'queued'
    finally:
        release.set()
        control._START_THREAD.join(3)


def test_unsupported_catalog_entry_cannot_create_batch(batch, monkeypatch):
    monkeypatch.setattr(control, 'get_platforms', lambda: [{'platform': 'boss', 'supported': False,
        'cities': [{'name': '北京', 'code': '101010100'}, {'name': '上海', 'code': '101020100'}]}])
    with pytest.raises(ValueError): batch.create_batch(plan())


def test_external_prepare_reserves_controller_until_browser_returns(batch, monkeypatch):
    entered, release = threading.Event(), threading.Event()
    def browser(*args):
        entered.set()
        release.wait(5)
        return {'platform_access': {'boss': {'can_collect': False, 'access_state': 'login_required'}}}
    monkeypatch.setattr(control, '_ensure_browser', browser)
    thread = threading.Thread(target=control.prepare_browser)
    thread.start()
    assert entered.wait(1)
    try:
        draft = batch.create_batch(plan())
        with pytest.raises(RuntimeError): batch.start_batch(draft['batch_id'])
        with pytest.raises(RuntimeError): control.start_task({})
    finally:
        release.set()
        thread.join(3)
    assert control._RESERVATION is None


@pytest.mark.parametrize('platform,city', [
    ('zhaopin', {'name': '上海', 'code': '538'}),
    ('liepin', {'name': '上海', 'code': '上海'}),
])
def test_each_platform_uses_catalog_city_and_limits_without_changing_single_settings(batch, monkeypatch, platform, city):
    calls = synthetic_workers(monkeypatch)
    control.update_config({'search_url_template': 'https://www.zhipin.com/custom?key={keyword}'})
    before = control.get_config()
    payload = plan()
    payload.update(platform=platform, keywords=['Java'], cities=[city], max_jobs=2, detail_limit=1)
    draft = batch.create_batch(payload)
    batch.start_batch(draft['batch_id'])
    result = wait_for(batch, draft['batch_id'], {'completed'})
    assert result['items'][0]['status'] == 'completed'
    args = calls[0]
    assert args[args.index('--platform') + 1] == platform
    assert args[args.index('--cities') + 1] == city['name'] + '=' + city['code']
    assert args[args.index('--detail-limit') + 1] == '1'
    assert args[args.index('--max-jobs') + 1] == '2'
    assert '--search-url-template' not in args
    assert control.get_config() == before


def test_stop_queued_cancels_without_reservation_or_child(batch, monkeypatch):
    monkeypatch.setattr(control, 'start_task', lambda *a, **kw: pytest.fail('stop queued started child'))
    draft = batch.create_batch(plan())
    stopped = batch.stop_batch(draft['batch_id'])
    assert stopped['status'] == 'stopped'
    assert stopped['completed'] == 0
    assert all(item['status'] == 'cancelled' and item['complete'] is None for item in stopped['items'])
    assert control._RESERVATION is None
    with pytest.raises(RuntimeError): batch.start_batch(draft['batch_id'])


@pytest.mark.parametrize('batch_id', ['../state', 'missing', 'batch-' + '0' * 32])
def test_unknown_or_unsafe_batch_id_rejected(batch, batch_id):
    with pytest.raises(ValueError): batch.get_batch(batch_id)


def test_batch_never_exposes_run_event_full_text(batch, monkeypatch):
    def spawn(args, **kwargs):
        class Worker:
            pid = 12345
            stdout = StringIO('TM_EVENT ' + json.dumps({'event': 'detail', 'platform': 'boss',
                'job': {'url': 'u', 'title': 'role'}, 'detail': {'description': 'PRIVATE_SENTINEL'}}) + '\n')
            def wait(self): return 0
            def poll(self): return 0
        return Worker()
    monkeypatch.setattr(control, '_spawn_process', spawn)
    payload = plan()
    payload.update(keywords=['Java'], cities=[{'name': '北京', 'code': '101010100'}])
    draft = batch.create_batch(payload)
    batch.start_batch(draft['batch_id'])
    result = wait_for(batch, draft['batch_id'], {'completed'})
    assert 'PRIVATE_SENTINEL' not in json.dumps(result)
    assert 'PRIVATE_SENTINEL' not in json.dumps(batch.list_batches())
    assert control.get_results(result['items'][0]['run_id'])[0]['raw_text'] == 'PRIVATE_SENTINEL'


def test_orchestration_error_stops_child_and_finishes_item_archive(batch, monkeypatch):
    entered, release = threading.Event(), threading.Event()
    def prepare(*args):
        entered.set()
        release.wait(3)
        return {'platform_access': {'boss': {'can_collect': False, 'access_state': 'login_required'}}}
    monkeypatch.setattr(control, '_ensure_browser', prepare)
    original = control._task_snapshot
    failures = []
    def snapshot(run_id):
        if not failures:
            failures.append(run_id)
            release.set()
            raise ValueError('synthetic orchestration fault')
        return original(run_id)
    monkeypatch.setattr(control, '_task_snapshot', snapshot)
    draft = batch.create_batch(plan())
    batch.start_batch(draft['batch_id'])
    assert entered.wait(1)
    result = wait_for(batch, draft['batch_id'], {'error'})
    batch._THREAD.join(3)
    result = batch.get_batch(draft['batch_id'])
    assert result['finished_at']
    assert result['items'][0]['status'] in {'blocked', 'stopped'}
    assert result['items'][0]['finished_at']
    assert result['completed'] == 1
    assert control._RESERVATION is None
    assert all(item['status'] == 'cancelled' for item in result['items'][1:])


def test_persistent_batch_save_failure_releases_only_after_child_archive(batch, monkeypatch):
    entered, release, save_failed = threading.Event(), threading.Event(), threading.Event()
    def prepare(*args):
        entered.set()
        release.wait(5)
        return {'platform_access': {'boss': {'can_collect': False, 'access_state': 'login_required'}}}
    monkeypatch.setattr(control, '_ensure_browser', prepare)
    draft = batch.create_batch(plan())
    batch.start_batch(draft['batch_id'])
    assert entered.wait(1)
    original = batch._save
    def full_disk(record):
        save_failed.set()
        raise OSError('synthetic full disk')
    monkeypatch.setattr(batch, '_save', full_disk)
    try:
        assert save_failed.wait(1)
        assert control._RESERVATION is not None
        assert batch._ACTIVE_ID == draft['batch_id']
        assert control._load_state()['history'] == []
        release.set()
        batch._THREAD.join(4)
        assert not batch._THREAD.is_alive()
        assert control._load_state()['history'][0]['finished_at']
        assert control._RESERVATION is None
        assert batch._ACTIVE_ID is None
    finally:
        release.set()
        monkeypatch.setattr(batch, '_save', original)
    assert batch.get_batch(draft['batch_id'])['status'] == 'interrupted'
    token = control._reserve_tasks()
    control._release_tasks(token)


def test_stop_at_next_item_boundary_does_not_assign_previous_run_to_pending_item(batch, monkeypatch):
    synthetic_workers(monkeypatch)
    original = batch._load
    def load(batch_id):
        record = original(batch_id)
        if record['batch']['status'] == 'waiting_next_round':
            batch._STOP.set()
        return record
    monkeypatch.setattr(batch, '_load', load)
    draft = batch.create_batch(plan())
    batch.start_batch(draft['batch_id'])
    batch._THREAD.join(3)
    result = batch.get_batch(draft['batch_id'])
    assert result['status'] == 'stopped'
    assert result['items'][0]['status'] == 'completed'
    assert all(item['run_id'] is None and item['status'] == 'cancelled' for item in result['items'][1:])


def test_item_task_reads_exact_log_after_run_falls_out_of_history(batch, monkeypatch):
    synthetic_workers(monkeypatch)
    draft = batch.create_batch(plan())
    batch.start_batch(draft['batch_id'])
    batch._THREAD.join(3)
    completed = batch.get_batch(draft['batch_id'])
    item = completed['items'][0]
    state = control._load_state()
    state['history'] = [{'run_id': f'newer-{i}', 'status': 'completed'} for i in range(100)]
    state['current_task'] = state['history'][0]
    control._save_state(state)
    path = control._STATE_DIR / (item['run_id'] + '.out.log')
    path.write_text('old line\n' + 'TM_EVENT ' + json.dumps({'description': 'PRIVATE_EVENT_BODY'}) + '\n'
                    + '\n'.join(f'line {i}' for i in range(35)) + '\n完成: {"complete": 999}\n', encoding='utf-8')
    task = batch.get_item_task(draft['batch_id'], item['item_id'])
    assert task['run_id'] == item['run_id']
    assert task['complete'] == 2 and task['detail_attempted'] == 3 and task['inserted'] == 1
    assert task['current_keyword'] == 'Python' and task['current_city'] == '北京'
    assert task['status'] == 'completed' and task['log_status'] == 'parsed'
    assert len(task['raw_log_tail']) == 30
    assert task['raw_log_tail'][-1] == '完成: {"complete": 999}'
    assert 'PRIVATE_EVENT_BODY' not in json.dumps(task)
    path.unlink()
    missing = batch.get_item_task(draft['batch_id'], item['item_id'])
    assert missing['log_status'] == 'missing' and missing['raw_log_tail'] == []
    assert missing['complete'] == 2


def test_item_task_rejects_pending_unknown_and_path_run_ids(batch, monkeypatch):
    draft = batch.create_batch(plan())
    with pytest.raises(ValueError): batch.get_item_task(draft['batch_id'], draft['items'][0]['item_id'])
    with pytest.raises(ValueError): batch.get_item_task(draft['batch_id'], '../control-state')
    path = batch._STATE_DIR / (draft['batch_id'] + '.json')
    record = json.loads(path.read_text(encoding='utf-8'))
    record['batch']['items'][0]['run_id'] = '../private'
    path.write_text(json.dumps(record), encoding='utf-8')
    with pytest.raises(ValueError): batch.get_item_task(draft['batch_id'], draft['items'][0]['item_id'])


@pytest.mark.parametrize('enabled,client,origin,allowed', [
    ('0', '127.0.0.1', None, False), ('1', '10.0.0.2', None, False),
    ('1', '127.0.0.1', 'https://evil.example', False),
    ('1', '127.0.0.1', 'http://localhost:18080', True),
])
def test_item_task_route_requires_local_raw_gate(batch, monkeypatch, enabled, client, origin, allowed):
    from app.routers import collection
    from fastapi import HTTPException
    from starlette.requests import Request
    monkeypatch.setenv('TALENTMIND_LOCAL_RAW', enabled)
    headers = [(b'host', b'localhost:18000')]
    if origin: headers.append((b'origin', origin.encode()))
    request = Request({'type': 'http', 'client': (client, 1), 'headers': headers})
    def task(*args):
        assert allowed, 'unauthorized request reached private logs'
        return {'raw_log_tail': ['private line']}
    monkeypatch.setattr(batch, 'get_item_task', task, raising=False)
    if allowed:
        result = collection.collection_batch_item_task('batch', 'item', request=request)
        assert result['data']['raw_log_tail'] == ['private line']
    else:
        with pytest.raises(HTTPException) as error:
            collection.collection_batch_item_task('batch', 'item', request=request)
        assert error.value.status_code == 403


def test_restarted_batch_is_interrupted_never_resumed(batch, monkeypatch):
    draft = batch.create_batch(plan())
    path = batch._STATE_DIR / (draft['batch_id'] + '.json')
    saved = json.loads(path.read_text(encoding='utf-8'))
    saved['batch'].update(status='running', current_item_id=draft['items'][0]['item_id'])
    saved['batch']['items'][0].update(status='running', run_id='old-run')
    path.write_text(json.dumps(saved), encoding='utf-8')
    monkeypatch.setattr(control, 'start_task', lambda *a, **kw: pytest.fail('restart resumed'))
    result = batch.get_batch(draft['batch_id'])
    assert result['status'] == 'interrupted'
    assert result['stop_reason'] == 'controller_restarted'
    assert result['items'][0]['status'] == 'interrupted'
    assert [x['status'] for x in result['items'][1:]] == ['cancelled'] * 3
    with pytest.raises(RuntimeError): batch.start_batch(draft['batch_id'])


def test_routes_create_draft_and_global_stop_stops_active_batch(batch, monkeypatch):
    from app.routers import collection
    monkeypatch.setattr(collection, 'batch', batch)
    synthetic_workers(monkeypatch)
    control.update_config({'switch_interval_min': 360, 'switch_interval_max': 360})
    draft = collection.collection_batch_create(plan())['data']
    assert draft['status'] == 'queued'
    collection.collection_batch_start(draft['batch_id'])
    wait_for(batch, draft['batch_id'], {'waiting_next_round'})
    result = collection.collection_stop({})['data']
    assert result['stopped'] is True
    assert result['batch_id'] == draft['batch_id']
    assert collection.collection_batch_get(draft['batch_id'])['data']['status'] == 'stopped'


@pytest.mark.skipif(os.name != 'nt', reason='Windows synthetic process tree')
def test_batch_stop_waits_for_real_synthetic_worker_tree_and_archive(batch, monkeypatch, tmp_path):
    workers = []
    pid_file = tmp_path / 'synthetic-ready'
    def spawn(args, **kwargs):
        script = ('import os,time; from pathlib import Path; '
                  f'Path({str(pid_file)!r}).write_text(str(os.getpid())); '
                  'print("synthetic worker",flush=True); time.sleep(60)')
        process = worker_process.spawn([sys.executable, '-u', '-c', script], **kwargs)
        workers.append(process)
        return process
    monkeypatch.setattr(control, '_spawn_process', spawn)
    draft = batch.create_batch(plan())
    try:
        batch.start_batch(draft['batch_id'])
        deadline = time.monotonic() + 5
        while not pid_file.exists() and time.monotonic() < deadline: time.sleep(.01)
        assert pid_file.exists()
        result = batch.stop_batch(draft['batch_id'])
        assert result['status'] == 'stopped'
        assert len(workers) == 1
        assert workers[0].poll() is not None
        assert workers[0]._collection_job.handle is None
        assert control._PROCESS is None
        assert control._load_state()['history'][0]['status'] == 'stopped'
        assert result['items'][0]['finished_at']
    finally:
        for process in workers:
            worker_process.close(process)
            process.wait(timeout=5)
        pid_file.unlink(missing_ok=True)

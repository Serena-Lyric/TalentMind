"""Product controller boundaries; no browser, network or production database."""
import json
import threading

import pytest

from app.collect import control


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(control, '_STATE_DIR', tmp_path)
    monkeypatch.setattr(control, '_STATE_PATH', tmp_path / 'state.json')
    monkeypatch.setattr(control, '_PROCESS', None)


def test_platform_switch_uses_own_city_codes():
    result = control.update_config({'platform': 'zhaopin'})
    assert result['cities'] == [{'name': '北京', 'code': '530'}]
    assert control.get_platforms()[1]['cities'][0]['code'] == '530'


@pytest.mark.parametrize('platform,city,url', [
    ('boss', {'name': '上海', 'code': '101020100'},
     'https://www.zhipin.com/web/geek/jobs?city=101020100&query=Java&page=1'),
    ('zhaopin', {'name': '上海', 'code': '538'},
     'https://www.zhaopin.com/jobs?jl=538&kw=Java&page=1'),
    ('liepin', {'name': '上海', 'code': '上海'},
     'https://www.liepin.com/zhaopin/?key=Java&dqs=%E4%B8%8A%E6%B5%B7&currentPage=1'),
])
def test_prepare_uses_unsaved_search_config_and_start_checks_same_target(monkeypatch, platform, city, url):
    urls = []
    config_before = control.get_config()
    def prepare(platform, endpoint, profile, **kwargs):
        urls.append(kwargs.get('url'))
        return dict(endpoint=endpoint, user_data_dir=profile, can_collect=False,
                    access_state='page_error', reason='no_access_evidence', target_url=kwargs.get('url'))
    monkeypatch.setattr(control.browser, 'prepare', prepare)
    monkeypatch.setattr(control, 'get_cdp_status', lambda *a: {'platform_access': {}})
    payload = dict(platform=platform, keywords=['Java'], cities=[city], pages=1, detail_limit=3, max_jobs=4)
    result = control.prepare_browser(config_payload=payload)
    assert result['can_collect'] is False
    assert result['target_url'] == url
    assert result['reason'] == 'no_access_evidence'
    assert '未检测到职位内容' in result['message']
    assert control.get_config() == config_before
    assert not control._STATE_PATH.exists()
    control.start_task(payload)
    control._START_THREAD.join(3)
    assert urls == [url, url]


def test_prepare_route_forwards_current_search_and_validation(monkeypatch):
    from app.routers import collection
    seen = []
    def prepare(**kwargs):
        seen.append(kwargs)
        return {'can_collect': False}
    monkeypatch.setattr(control, 'prepare_browser', prepare)
    payload = dict(auto_start=True, platform='zhaopin', keywords=['Java'],
                   cities=[{'name': '上海', 'code': '538'}], pages=1, detail_limit=3, max_jobs=4)
    collection.collection_prepare(payload)
    assert seen == [dict(auto_start=True, platform='zhaopin', config_payload={
        key: value for key, value in payload.items() if key != 'auto_start'})]


def test_prepare_rejects_invalid_temporary_config_before_browser(monkeypatch):
    def forbidden(*a, **kw): pytest.fail('invalid prepare config reached browser')
    monkeypatch.setattr(control.browser, 'prepare', forbidden)
    with pytest.raises(ValueError):
        control.prepare_browser(config_payload={'platform': 'boss', 'pages': 2})
    assert not control._STATE_PATH.exists()


@pytest.mark.parametrize('state,reason,can_collect,message', [
    ('login_required', 'manual_login_gate', False, '需人工登录'),
    ('verification_required', 'manual_verification_or_access_limit', False, '安全验证'),
    ('content_limited', 'guest_content_limited', False, '游客内容受限'),
    ('empty_results', 'explicit_empty_results', True, '暂无相关职位'),
    ('page_error', 'target_page_redirected', False, '目标搜索页已跳转'),
])
def test_prepare_message_explains_current_access_and_preserves_reason(monkeypatch, state, reason, can_collect, message):
    monkeypatch.setattr(control, '_ensure_browser', lambda *a: {'platform_access': {'boss': {
        'access_state': state, 'reason': reason, 'can_collect': can_collect}}})
    result = control.prepare_browser()
    assert result['can_collect'] is can_collect
    assert result['reason'] == reason
    assert message in result['message']


def test_automatic_security_redirect_is_not_reported_as_manual_verification(monkeypatch):
    monkeypatch.setattr(control, '_ensure_browser', lambda *a: {'platform_access': {'boss': {
        'access_state': 'verification_required', 'reason': 'security_check_redirect', 'can_collect': False}}})
    result = control.prepare_browser()
    assert '未发现可人工操作的验证内容' in result['message']
    assert '停止自动重试' in result['message']


def test_legacy_config_is_presented_with_current_bounds_without_rewriting_history():
    state = control._default_state()
    state['config'].update(max_jobs=12, detail_limit=8, keywords=['Python', 'Java'],
                           cities=[{'name': '北京', 'code': '101010100'}, {'name': '上海', 'code': '101020100'}])
    state['history'] = [{'run_id': 'legacy', 'max_jobs': 12}]
    control._save_state(state)
    config = control.get_config()
    assert config['max_jobs'] == config['detail_limit'] == 5
    assert config['keywords'] == ['Python']
    assert len(config['cities']) == 1
    assert control._load_state()['config']['max_jobs'] == 12
    assert control._load_state()['history'] == state['history']


@pytest.mark.parametrize('payload', [
    {'cities': [{'name': '北京', 'code': '530'}]}, {'pages': 2},
    {'max_jobs': 6}, {'detail_limit': 0}, {'max_jobs': True},
    {'keywords': []}, {'keywords': ['Python', 'Java']},
    {'mode': 'continuous'}, {'unexpected': 1}, {'settle_min': float('nan')},
    {'search_url_template': 'https://evil.example/{keyword}'},
])
def test_config_rejects_unsafe_or_invalid_input(payload):
    with pytest.raises(ValueError):
        control.update_config(payload)


def test_start_returns_before_browser_and_archives_block(monkeypatch):
    entered, release = threading.Event(), threading.Event()
    def browser(*args):
        entered.set()
        release.wait(3)
        return {'platform_access': {'boss': {'can_collect': False, 'access_state': 'verification_required'}}}
    monkeypatch.setattr(control, '_ensure_browser', browser)
    result = control.start_task({})
    assert entered.wait(1)
    task = control._load_state()['current_task']
    assert task['run_id'] == result['run_id']
    assert task['status'] == 'preparing'
    assert task['complete'] is None
    release.set()
    control._START_THREAD.join(3)
    history = control.get_history()['items']
    assert history[0]['status'] == 'waiting_for_browser'
    assert history[0]['stop_reason'] == 'verification_required'


def test_stop_during_browser_preparation_never_launches_worker(monkeypatch):
    entered, release = threading.Event(), threading.Event()
    def browser(*args):
        entered.set()
        release.wait(3)
        return {'platform_access': {'boss': {'can_collect': True}}}
    monkeypatch.setattr(control, '_ensure_browser', browser)
    def forbidden(*a, **kw):
        pytest.fail('stopped task must never spawn')
    monkeypatch.setattr(control, '_spawn_worker', forbidden)
    run = control.start_task({})
    assert entered.wait(1)
    control.stop_task(run['run_id'])
    release.set()
    control._START_THREAD.join(3)
    assert control.get_history()['items'][0]['stop_reason'] == 'user_stopped'


def test_slow_preparation_stop_reports_pending_until_thread_finishes(monkeypatch):
    entered, release = threading.Event(), threading.Event()
    def browser(*args):
        entered.set()
        release.wait(20)
        return {'platform_access': {'boss': {'can_collect': True}}}
    monkeypatch.setattr(control, '_ensure_browser', browser)
    run = control.start_task({})
    assert entered.wait(1)
    try:
        result = control.stop_task(run['run_id'])
        assert result == {'stopped': False, 'status': 'stopping', 'run_id': run['run_id']}
        assert control._load_state()['current_task']['finished_at'] is None
        with pytest.raises(RuntimeError):
            control.start_task({})
    finally:
        release.set()
        control._START_THREAD.join(3)
    assert control.get_history()['items'][0]['status'] == 'stopped'


def test_late_prepare_error_preserves_explicit_stop(monkeypatch):
    entered, release = threading.Event(), threading.Event()
    def browser(*args):
        entered.set()
        release.wait(3)
        raise OSError('synthetic late failure')
    monkeypatch.setattr(control, '_ensure_browser', browser)
    run = control.start_task({})
    assert entered.wait(1)
    control.stop_task(run['run_id'])
    release.set()
    control._START_THREAD.join(3)
    assert control.get_history()['items'][0]['status'] == 'stopped'


def test_stop_does_not_relabel_completed_task():
    state = control._default_state()
    task = control._empty_task('done', state['config'])
    task.update(status='completed', finished_at=control._now())
    state.update(current_task=task, history=[dict(task)])
    control._save_state(state)
    assert control.stop_task('done')['stopped'] is False
    assert control._load_state()['current_task']['status'] == 'completed'


def test_browser_exception_creates_error_history(monkeypatch):
    def broken(*a):
        raise OSError('synthetic browser failure')
    monkeypatch.setattr(control, '_ensure_browser', broken)
    run = control.start_task({})
    control._START_THREAD.join(3)
    task = control.get_history()['items'][0]
    assert task['run_id'] == run['run_id']
    assert task['status'] == 'error'
    assert task['stop_reason'] == 'OSError'


def test_restarted_controller_does_not_reuse_old_pid(monkeypatch):
    state = control._default_state()
    state['current_task'] = control._empty_task('old-run', state['config'])
    state['current_task'].update(status='running', pid=123)
    control._save_state(state)
    monkeypatch.setattr(control, 'get_database_stats', lambda: {'database_total': None, 'database_boss_total': None})
    result = control.get_status()
    assert result['status'] == 'error'
    assert result['pid'] is None
    assert result['stop_reason'] == 'controller_restarted'
    assert control.get_history()['items'][0]['run_id'] == 'old-run'


def test_stopped_watcher_drains_events_without_overwriting_stop():
    from io import StringIO
    state = control._default_state()
    state['current_task'] = control._empty_task('stopped', state['config'])
    state['current_task'].update(status='stopped', stop_reason='user_stopped')
    control._save_state(state)
    event = {'event': 'listed', 'platform': 'boss', 'jobs': [{'url': 'u', 'title': 'current'}]}
    class Worker:
        stdout = StringIO('TM_EVENT ' + json.dumps(event) + '\nBOSS 第 1 轮开始: 北京/Python;\n')
        def wait(self):
            return -1
    control._watch_process('stopped', Worker())
    task = control.get_history()['items'][0]
    assert task['status'] == 'stopped'
    assert task['stop_reason'] == 'user_stopped'
    assert task['listed'] == 1
    assert len(control.get_results('stopped')) == 1


def test_database_failure_is_unknown(monkeypatch):
    import app.db.mysql as mysql
    def unavailable():
        raise RuntimeError('synthetic unavailable')
    monkeypatch.setattr(mysql, 'SessionLocal', unavailable)
    result = control.get_database_stats()
    assert result['available'] is False
    assert result['database_total'] is None
    assert result['data_quality']['duties_nonempty'] is None


def test_unrecognized_legacy_log_has_unknown_counts(tmp_path):
    path = tmp_path / 'boss_collect_loop.out.log'
    path.write_text('unrecognized historical output\n', encoding='utf-8')
    result = control._summarize_log(path)
    assert result['listed'] is result['details'] is result['inserted'] is None


def test_results_only_include_run_events_and_preserve_current_detail():
    for run, event in [('one', {'event': 'listed', 'platform': 'boss', 'jobs': [{'url': 'u', 'title': '本轮'}]}),
                       ('two', {'event': 'listed', 'platform': 'boss', 'jobs': [{'url': 'old', 'title': '旧轮'}]}),
                       ('one', {'event': 'detail', 'platform': 'boss', 'job': {'url': 'u', 'title': '本轮'},
                                'detail': {'description': '负责 Python 开发'}, 'rejection': None}),
                       ('one', {'event': 'persisted', 'platform': 'boss', 'items': [
                           {'source_detail': 'u', 'outcome': 'skipped', 'jd_pool_id': 42} ]})]:
        control._parse_log_line(run, 'TM_EVENT ' + json.dumps(event, ensure_ascii=False))
    result = control.get_results('one')
    assert len(result) == 1
    assert result[0]['job_title'] == '本轮'
    assert result[0]['raw_text'] == '负责 Python 开发'
    assert result[0]['jd_pool_id'] == 42
    assert control.get_results('missing') == []
    with pytest.raises(ValueError):
        control.get_results('../state')


@pytest.mark.parametrize('enabled,client,host,origin,allowed', [
    ('0', '127.0.0.1', 'localhost:18000', None, False),
    ('1', '10.0.0.2', 'localhost:18000', None, False),
    ('1', '127.0.0.1', 'evil.example', None, False),
    ('1', '127.0.0.1', 'localhost:18000', 'https://evil.example', False),
    ('1', '127.0.0.1', 'localhost:18000', 'null', False),
    ('1', '127.0.0.1', 'localhost:18000', 'http://127.0.0.1:18080', True),
    ('1', '::1', '[::1]:18000', None, True),
])
def test_full_raw_requires_explicit_local_access(monkeypatch, enabled, client, host, origin, allowed):
    from fastapi import HTTPException
    from starlette.requests import Request
    from app.routers.collection import _require_local_raw
    monkeypatch.setenv('TALENTMIND_LOCAL_RAW', enabled)
    headers = [(b'host', host.encode())]
    if origin is not None:
        headers.append((b'origin', origin.encode()))
    request = Request({'type': 'http', 'client': (client, 1), 'headers': headers})
    if allowed:
        _require_local_raw(request)
    else:
        with pytest.raises(HTTPException) as error:
            _require_local_raw(request)
        assert error.value.status_code == 403


@pytest.mark.parametrize('enabled,client,origin,allowed', [
    ('0', '127.0.0.1', None, False), ('1', '10.0.0.2', None, False),
    ('1', '127.0.0.1', 'https://evil.example', False),
    ('1', '127.0.0.1', 'http://localhost:18080', True),
])
def test_results_route_applies_same_full_raw_gate(monkeypatch, enabled, client, origin, allowed):
    from fastapi import HTTPException
    from starlette.requests import Request
    from app.routers import collection
    monkeypatch.setenv('TALENTMIND_LOCAL_RAW', enabled)
    headers = [(b'host', b'localhost:18000')]
    if origin:
        headers.append((b'origin', origin.encode()))
    request = Request({'type': 'http', 'client': (client, 1), 'headers': headers})
    calls = []
    monkeypatch.setattr(control, 'get_results', lambda run: calls.append(run) or [{'raw_text': 'private body'}])
    if allowed:
        assert collection.collection_results(request=request, run_id='one')['data'][0]['raw_text'] == 'private body'
        assert calls == ['one']
    else:
        with pytest.raises(HTTPException) as error:
            collection.collection_results(request=request, run_id='one')
        assert error.value.status_code == 403
        assert calls == []


def test_private_json_events_never_enter_public_status_or_history_tail():
    state = control._default_state()
    state['current_task'] = control._empty_task('private', state['config'])
    control._save_state(state)
    event = {'event': 'detail', 'platform': 'boss', 'job': {'url': 'u', 'title': 'role'},
             'detail': {'description': 'PRIVATE_DETAIL_SENTINEL'}, 'rejection': None}
    control._parse_log_line('private', 'TM_EVENT ' + json.dumps(event))
    control._archive_task('private', status='completed')
    assert 'PRIVATE_DETAIL_SENTINEL' not in json.dumps(control._load_state())
    assert 'PRIVATE_DETAIL_SENTINEL' not in json.dumps(control.get_history())
    assert control.get_results('private')[0]['raw_text'] == 'PRIVATE_DETAIL_SENTINEL'


def test_private_json_events_never_enter_legacy_history_tail(tmp_path):
    path = tmp_path / 'boss_collect_loop.out.log'
    path.write_text('TM_EVENT ' + json.dumps({'event': 'detail', 'detail': {
        'description': 'PRIVATE_LEGACY_SENTINEL'}}) + '\n', encoding='utf-8')
    assert 'PRIVATE_LEGACY_SENTINEL' not in json.dumps(control._summarize_log(path))


def test_database_quality_and_latest_cover_all_platforms(tmp_path, monkeypatch):
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker
    import app.db.mysql as mysql
    path = tmp_path / 'synthetic-quality.sqlite'
    engine = create_engine('sqlite:///' + str(path))
    try:
        with engine.begin() as connection:
            connection.execute(text('CREATE TABLE jd_pool (source TEXT, source_detail TEXT, '
                'crawled_at TEXT, duties TEXT, status TEXT)'))
            connection.execute(text('INSERT INTO jd_pool VALUES (:source,:detail,:time,:duties,:status)'), [
                dict(source='boss', detail='shared', time='2026-01-01', duties='boss duty', status='cleaned'),
                dict(source='zhaopin', detail='shared', time='2026-02-01', duties='zhao duty', status='raw'),
                dict(source='zhaopin', detail='duplicate', time='2026-02-02', duties='', status='raw'),
                dict(source='zhaopin', detail='duplicate', time='2026-02-03', duties='', status='raw'),
                dict(source='liepin', detail=None, time='2026-03-01', duties='liepin duty', status='cleaned'),
                dict(source='hn', detail='https://example.com/placeholder', time='2026-04-01', duties='hn duty', status='raw'),
            ])
        monkeypatch.setattr(mysql, 'SessionLocal', sessionmaker(bind=engine))
        result = control.get_database_stats()
        assert result['available'] is True
        assert result['database_total'] == 6
        assert result['database_boss_total'] == 1
        assert result['latest_crawled_at'] == '2026-04-01'
        assert result['data_quality'] == dict(empty_source_detail=1, duplicate_source_detail=1,
            placeholder_empty_url=1, duties_nonempty=4,
            status_distribution=[{'status': 'cleaned', 'count': 2}, {'status': 'raw', 'count': 4}])
        assert {row['platform']: row['count'] for row in result['platform_counts']} == {
            'boss': 1, 'zhaopin': 3, 'liepin': 1, 'hn': 1}
    finally:
        with engine.begin() as connection:
            connection.execute(text('DELETE FROM jd_pool'))
            assert connection.execute(text('SELECT COUNT(*) FROM jd_pool')).scalar() == 0
        engine.dispose()
        path.unlink(missing_ok=True)
        assert not path.exists()


@pytest.mark.parametrize('raw,duties,requirements', [
    ('岗位职责：负责 Python 开发\n任职要求：熟悉 SQL\n福利待遇：五险', '负责 Python 开发', '熟悉 SQL'),
    ('工作职责:\n  1.开发接口\n  2.维护服务\n职位要求：掌握 Python；保留原标点\n公司介绍：略',
     '1.开发接口\n  2.维护服务', '掌握 Python；保留原标点'),
    ('Responsibilities: Build APIs. Requirements: Python\nBenefits: insurance', 'Build APIs.', 'Python'),
    ('任职要求\n熟悉 Python', None, '熟悉 Python'),
    ('负责开发接口，熟悉 Python 和 SQL', None, None),
])
def test_source_sections_preserve_explicit_original_text(raw, duties, requirements):
    from app.collect.cleaner import source_sections
    assert source_sections(raw) == {'duties': duties, 'requirements': requirements,
        'structure_source': '原文标题分段' if duties or requirements else None}


def test_results_include_explicit_requirements_and_original_body():
    body = '岗位职责：开发接口\n任职要求：Python\n福利待遇：五险'
    event = {'event': 'detail', 'platform': 'boss', 'job': {'url': 'u', 'title': 'role'},
             'detail': {'description': body}, 'rejection': None}
    control._parse_log_line('requirements', 'TM_EVENT ' + json.dumps(event))
    result = control.get_results('requirements')[0]
    assert result['raw_text'] == body
    assert result['duties'] == '开发接口'
    assert result['requirements'] == 'Python'
    assert result['structure_source'] == '原文标题分段'


def test_results_and_task_keep_pending_identity_separate_from_complete():
    state = control._default_state()
    state['current_task'] = control._empty_task('pending', state['config'])
    control._save_state(state)
    evidence = {'binding_policy': 'zhaopin-dom-panel-v1', 'stable_samples': 2}
    events = [
        {'event': 'listed', 'platform': 'zhaopin', 'jobs': [{
            'url': 'dom://zhaopin/provisional', 'title': 'Python 工程师',
            '_observation_key': 'zhaopin:card-0',
        }]},
        {'event': 'detail', 'platform': 'zhaopin',
         'job': {'url': 'dom://zhaopin/provisional', 'title': 'Python 工程师',
                 '_observation_key': 'zhaopin:card-0'},
         'detail': {'description': '负责 Python 开发'},
         'rejection': None, 'identity_status': 'pending', 'content_eligible': True,
         'identity_evidence': evidence},
        {'event': 'persisted', 'platform': 'zhaopin', 'items': [{
            'source_detail': 'dom://zhaopin/' + 'a' * 64,
            'observation_key': 'zhaopin:card-0', 'jd_pool_id': 9,
            'outcome': 'inserted', 'identity_status': 'pending',
            'content_eligible': True, 'identity_evidence': evidence,
        }]},
        {'event': 'finished', 'platform': 'zhaopin', 'stats': {
            'listed': 1, 'details': 1, 'detail_attempted': 1,
            'detail_obtained': 1, 'content_eligible': 1,
            'identity_pending': 1, 'identity_verified': 0,
            'complete': 0, 'inserted': 1, 'updated': 0, 'rejected': 0,
            'failed': 0, 'unattempted': 0, 'rejection_reasons': {}, 'stop_reason': None,
        }},
    ]
    for event in events:
        control._parse_log_line('pending', 'TM_EVENT ' + json.dumps(event, ensure_ascii=False))

    result = control.get_results('pending')[0]
    assert result['source_detail'] == 'dom://zhaopin/' + 'a' * 64
    assert result['identity_status'] == 'pending'
    assert result['content_eligible'] is True
    assert result['identity_evidence'] == evidence
    assert result['outcome'] == 'inserted'
    assert result['jd_pool_id'] == 9
    task = control._load_state()['current_task']
    assert task['content_eligible'] == 1
    assert task['identity_pending'] == 1
    assert task['identity_verified'] == 0
    assert task['complete'] == 0


def test_raw_adds_requirements_and_preserves_stored_duties(monkeypatch):
    import app.db.mysql as mysql
    body = '岗位职责：来源职责\n任职要求：Python\n福利待遇：五险'
    row = dict(id=1, source='boss', source_detail='u', job_title='role', crawled_at=None,
               raw_text=body, duties='既有职责字段', quality=.5)
    class Session:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def execute(self, *args): return self
        def mappings(self): return self
        def first(self): return row
    monkeypatch.setattr(mysql, 'SessionLocal', Session)
    result = control.get_raw(1)
    assert result['raw_text'] == body
    assert result['duties'] == '既有职责字段'
    assert result['requirements'] == 'Python'


def test_raw_reads_identity_metadata_from_migrated_schema(tmp_path, monkeypatch):
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker
    import app.db.mysql as mysql
    path = tmp_path / 'raw-identity.sqlite3'
    engine = create_engine('sqlite:///' + str(path))
    try:
        with engine.begin() as db:
            db.execute(text(
                'CREATE TABLE jd_pool (id INTEGER PRIMARY KEY, source TEXT, source_detail TEXT, '
                'job_title TEXT, crawled_at TEXT, raw_text TEXT, duties TEXT, quality FLOAT, '
                'identity_status TEXT, content_eligible BOOLEAN, identity_evidence TEXT)'
            ))
            db.execute(text(
                'INSERT INTO jd_pool VALUES (1, :source, :detail, :title, NULL, :raw, NULL, 0, '
                ':identity, 1, :evidence)'
            ), dict(source='zhaopin', detail='dom://zhaopin/' + 'a' * 64,
                    title='Python', raw='负责平台开发', identity='pending',
                    evidence='{"binding_policy":"zhaopin-dom-panel-v1"}'))
        monkeypatch.setattr(mysql, 'SessionLocal', sessionmaker(bind=engine))
        result = control.get_raw(1)
        assert result['identity_status'] == 'pending'
        assert result['content_eligible'] is True
        assert result['identity_evidence'] == {'binding_policy': 'zhaopin-dom-panel-v1'}
    finally:
        engine.dispose()
        path.unlink(missing_ok=True)


def test_status_poll_lets_owned_exited_worker_finish_watcher_archive(monkeypatch):
    from io import StringIO
    state = control._default_state()
    state['current_task'] = control._empty_task('owned-exit', state['config'])
    state['current_task'].update(status='running', pid=123)
    control._save_state(state)
    class Worker:
        stdout = StringIO('')
        def poll(self): return 0
        def wait(self): return 0
    worker = Worker()
    monkeypatch.setattr(control, '_PROCESS', worker)
    monkeypatch.setattr(control, 'get_database_stats', lambda: {'database_total': None, 'database_boss_total': None})
    assert control.get_status()['status'] == 'running'
    assert control._load_state()['current_task']['finished_at'] is None
    control._watch_process('owned-exit', worker)
    task = control.get_history()['items'][0]
    assert task['status'] == 'completed'
    assert task['stop_reason'] is None

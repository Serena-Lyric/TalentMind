"""Offline entry-point regressions; temporary ledger, fake browser, no real DB."""
import sys
import time
import types

import pytest

from app.collect import (batch, boss_collect_loop, browser, cn_collect_loop,
                         control, fetch_boss_jobs as boss, fetch_cn_jobs as cn,
                         frequency)
from app.collect.timing_validation import validate_collection_ranges


@pytest.fixture
def clock(tmp_path, monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(frequency, '_STATE_PATH', tmp_path / 'frequency.sqlite3')
    monkeypatch.setattr(frequency, '_clock', lambda: now[0])
    monkeypatch.setattr(time, 'sleep', lambda seconds: now.__setitem__(0, now[0] + seconds))
    # Reserve at the documented minima so exact assertions have no random flake.
    monkeypatch.setattr(frequency.random.SystemRandom, 'uniform', lambda _, low, high: low)
    return now


@pytest.mark.parametrize('bad', [0, 14.999, -1, float('nan'), float('inf'), -float('inf'), True])
@pytest.mark.parametrize('module', [boss, cn])
def test_direct_fetch_rejects_fast_or_invalid_before_browser(module, bad, monkeypatch):
    monkeypatch.setattr(browser, 'ensure_ready', lambda *a, **k: pytest.fail('browser touched'))
    args = (['Java'], [('北京', '530')])
    if module is cn:
        args = ('zhaopin', *args)
    with pytest.raises(ValueError):
        module.run_fetch(*args, cdp_endpoint='http://127.0.0.1:9333', delay=bad)


@pytest.mark.parametrize('module', [boss_collect_loop, cn_collect_loop])
@pytest.mark.parametrize('field,value', [('page_delay_min', 0), ('switch_interval_min', 359.99),
                                         ('settle_min', float('nan')), ('settle_min', 4.999), ('page_delay_max', float('inf'))])
def test_loop_rejects_before_fetch(module, field, value):
    args = ([module.QueryTarget('Java', '北京', '530')],)
    if module is cn_collect_loop:
        args = ('zhaopin', *args)
    with pytest.raises(ValueError):
        module.run_loop(*args, cdp_endpoint='http://127.0.0.1:9333', user_data_dir=None,
                        rounds=1, fetcher=lambda *a, **k: pytest.fail('fetch touched'), **{field: value})


@pytest.mark.parametrize('field,value', [('page_delay_min', 0), ('switch_interval_min', 0),
                                         ('switch_interval_max', float('nan'))])
def test_control_rejects_unsafe_persisted_settings(field, value):
    with pytest.raises(ValueError):
        control._validated_config({**control._DEFAULT_CONFIG, field: value}, {})


def test_slower_settings_remain_legal():
    validate_collection_ranges(60, 90, 5, 10, 900, 1200)
    with pytest.raises(ValueError):
        validate_collection_ranges(30, 15, 5, 10, 360, 720)


def fake_browser(monkeypatch, now, *, dom=False):
    actions = []
    current_url = ["https://www.zhaopin.com/jobs?kw=Java&jl=530"]
    class Client:
        def navigate(self, url, **kwargs):
            current_url[0] = url
            actions.append(('navigate', now[0], url))
        def evaluate(self, expression):
            if expression == 'location.href':
                return current_url[0]
            if expression == 'activate':
                actions.append(('activate', now[0], 'card'))
                return {'clicked': True}
            return {}
        def close(self):
            pass
    monkeypatch.setattr(browser, 'ensure_ready', lambda *a, **k: {'endpoint': 'http://127.0.0.1:9333'})
    monkeypatch.setattr(browser, 'wait_access', lambda *a, **k: {})
    monkeypatch.setattr(boss.CdpClient, 'connect_first_page', lambda *a, **k: Client())
    # A synthetic module prevents importing/creating the application's DB engine.
    db = types.ModuleType('app.db.mysql')
    db.get_db = lambda: iter([object()])
    def provider():
        yield object()
    db.get_db = provider
    monkeypatch.setitem(sys.modules, 'app.db.mysql', db)
    monkeypatch.setattr(boss, 'detail_rejection', lambda *a: 'empty_detail')
    monkeypatch.setattr(cn, 'content_rejection', lambda *a: 'empty_detail')
    monkeypatch.setattr(cn, 'build_panel_probe_js', lambda *a: 'probe')
    monkeypatch.setattr(cn, 'build_activate_card_js', lambda *a: 'activate')
    monkeypatch.setattr(cn, 'await_stable_panel', lambda *a, **k: {})
    return actions


def test_boss_max_jobs_break_still_delays_first_detail(clock, monkeypatch):
    actions = fake_browser(monkeypatch, clock)
    def search(client, url, settle):
        client.navigate(url)
        return [{'url': 'https://www.zhipin.com/job_detail/test1.html', 'title': 'Java'}]
    monkeypatch.setattr(boss, '_fetch_search_page', search)
    result = boss.run_fetch(['Java'], [('北京', '101010100')], pages=1,
                            max_jobs=1, detail_limit=1, delay=15, settle=5)
    assert result['detail_attempted'] == 1
    assert len(actions) == 2
    assert actions[1][1] - actions[0][1] >= 15


@pytest.mark.parametrize('dom', [False, True])
def test_cn_first_detail_navigation_or_dom_click_obeys_gate(clock, monkeypatch, dom):
    actions = fake_browser(monkeypatch, clock)
    job = {'url': 'https://www.zhaopin.com/job/CC000000000J00000000000.htm', 'title': 'Java'}
    if dom:
        job.update(_dom=True, _card_index=0)
    def search(client, spec, url, settle):
        client.navigate(url)
        return [job]
    monkeypatch.setattr(cn, 'fetch_search_page', search)
    result = cn.run_fetch('zhaopin', ['Java'], [('北京', '530')],
                          cdp_endpoint='http://127.0.0.1:9333', pages=1,
                          max_jobs=1, detail_limit=1, delay=15, settle=5)
    assert result['detail_attempted'] == 1
    assert [a[0] for a in actions] == ['navigate', 'activate' if dom else 'navigate']
    assert actions[1][1] - actions[0][1] >= 15


def test_cn_pages_one_multiple_combinations_waits(clock, monkeypatch):
    actions = fake_browser(monkeypatch, clock)
    def search(client, spec, url, settle):
        client.navigate(url)
        return []
    monkeypatch.setattr(cn, 'fetch_search_page', search)
    cn.run_fetch('zhaopin', ['Java', 'Python'], [('北京', '530')],
                 cdp_endpoint='http://127.0.0.1:9333', pages=1, detail_limit=0)
    assert len(actions) == 2
    assert actions[1][1] - actions[0][1] >= 360


def test_repeated_direct_fetch_shares_ledger(clock, monkeypatch):
    actions = fake_browser(monkeypatch, clock)
    def search(client, spec, url, settle):
        client.navigate(url)
        return []
    monkeypatch.setattr(cn, 'fetch_search_page', search)
    for keyword in ['Java', 'Java', 'Python']:
        cn.run_fetch('zhaopin', [keyword], [('北京', '530')],
                     cdp_endpoint='http://127.0.0.1:9333', detail_limit=0)
    assert actions[1][1] - actions[0][1] >= 15
    assert actions[2][1] - actions[1][1] >= 360


def test_cn_current_page_read_is_rate_limited(clock, monkeypatch):
    fake_browser(monkeypatch, clock)
    reads = []
    monkeypatch.setattr(cn, 'extract_current_page', lambda *a: reads.append(clock[0]) or [])
    for _ in range(2):
        cn.run_fetch('zhaopin', ['Java'], [('北京', '530')],
                     cdp_endpoint='http://127.0.0.1:9333', current_page_only=True)
    assert reads[1] - reads[0] >= 15


@pytest.mark.parametrize('module', [boss_collect_loop, cn_collect_loop])
def test_state_failure_stops_loop_without_retry(module):
    def fetch(*a, **k):
        raise frequency.FrequencyStateError('broken ledger')
    args = ([module.QueryTarget('Java', '北京', '530')],)
    if module is cn_collect_loop:
        args = ('zhaopin', *args)
    result = module.run_loop(*args, cdp_endpoint='http://127.0.0.1:9333', user_data_dir=None,
                             rounds=2, fetcher=fetch,
                             sleeper=lambda _: pytest.fail('must not retry state failure'))
    assert result == 2


def test_prepare_loads_use_gate_and_claim_actual_default_query(clock, monkeypatch, tmp_path):
    profile = tmp_path / 'browser'
    actions = []
    sessions = []
    monkeypatch.setattr(browser, '_profile', lambda _: profile)
    monkeypatch.setattr(browser, '_edge_sessions', lambda: sessions)
    def launch(*args):
        actions.append(clock[0])
        sessions.append({'profile': str(profile)})
    monkeypatch.setattr(browser, '_launch_edge', launch)
    monkeypatch.setattr(browser, '_owned_endpoint', lambda *a: 'http://127.0.0.1:9333')
    monkeypatch.setattr(browser, '_page_targets', lambda *a: [])
    monkeypatch.setattr(browser, '_create_page', lambda *a: actions.append(clock[0]) or {'id': 'new'})
    monkeypatch.setattr(browser, '_inspect_targets', lambda *a: {'can_collect': True})
    browser.prepare('boss', user_data_dir=str(profile))
    assert actions == [1000, 1015]
    # Default preparation really loaded Python; Java is a new combination.
    frequency.wait_for_action('boss', 'Java', '101010100', sleeper=time.sleep)
    assert clock[0] - actions[-1] >= 360


def test_batch_revalidates_before_thread_or_browser(monkeypatch):
    record = {'batch': {'status': 'queued'}}
    marker = object()
    released = []
    monkeypatch.setattr(batch, '_ACTIVE_ID', None)
    monkeypatch.setattr(batch, '_load', lambda _: record)
    monkeypatch.setattr(control, '_reserve_tasks', lambda: marker)
    monkeypatch.setattr(control, '_release_tasks', lambda value: released.append(value))
    monkeypatch.setattr(control, 'get_config', lambda: {**control._DEFAULT_CONFIG, 'switch_interval_min': 0})
    monkeypatch.setattr(batch, '_save', lambda _: pytest.fail('unsafe batch started'))
    with pytest.raises(ValueError):
        batch.start_batch('batch-test')
    assert released == [marker]


@pytest.mark.parametrize('module', [boss, cn])
def test_cli_rejects_zero_delay_before_prepare(module, monkeypatch):
    argv = ['collect', '--keywords', 'Java', '--cities', '北京=530', '--delay', '0']
    if module is cn:
        argv += ['--platform', 'zhaopin']
    monkeypatch.setattr(sys, 'argv', argv)
    monkeypatch.setattr(browser, 'ensure_ready', lambda *a, **k: pytest.fail('browser touched'))
    with pytest.raises((ValueError, SystemExit)):
        module.main()


def test_boss_failed_detail_cannot_accelerate_next_detail(clock, monkeypatch):
    actions = fake_browser(monkeypatch, clock)
    def search(client, url, settle):
        client.navigate(url)
        return [{'url': f'https://www.zhipin.com/job_detail/test{i}.html', 'title': 'Java'}
                for i in range(2)]
    monkeypatch.setattr(boss, '_fetch_search_page', search)
    original = boss.CdpClient.connect_first_page
    connections = [0]
    def connect(*a, **k):
        client = original(*a, **k)
        connections[0] += 1
        if connections[0] == 2:
            def fail(expression):
                raise ValueError('synthetic detail failure')
            client.evaluate = fail
        return client
    monkeypatch.setattr(boss.CdpClient, 'connect_first_page', connect)
    with pytest.raises(ValueError, match='synthetic detail failure'):
        boss.run_fetch(['Java'], [('北京', '101010100')], pages=1,
                       max_jobs=2, detail_limit=2, delay=15, settle=5)
    assert len(actions) == 2  # A failed browser callback never opens the next item.
    assert actions[1][1] - actions[0][1] >= 15


def test_cn_details_keep_original_combination_scope(clock, monkeypatch):
    actions = fake_browser(monkeypatch, clock)
    def search(client, spec, url, settle):
        client.navigate(url)
        name = 'java' if 'Java' in url else 'python'
        return [{'url': f'https://www.zhaopin.com/job/{name}', 'title': name}]
    monkeypatch.setattr(cn, 'fetch_search_page', search)
    cn.run_fetch('zhaopin', ['Java', 'Python'], [('北京', '530')],
                 cdp_endpoint='http://127.0.0.1:9333', pages=1, max_jobs=0, detail_limit=2)
    assert len(actions) == 4
    assert all(b[1] - a[1] >= 360 for a, b in zip(actions, actions[1:]))


@pytest.mark.parametrize('module', [boss_collect_loop, cn_collect_loop])
def test_once_skips_switch_sleep_but_two_rounds_wait(module):
    args = ([module.QueryTarget('Java', '北京', '530')],)
    if module is cn_collect_loop:
        args = ('zhaopin', *args)
    waits = []
    assert module.run_loop(*args, cdp_endpoint='http://127.0.0.1:9333', user_data_dir=None,
                           rounds=1, fetcher=lambda *a, **k: {}, sleeper=waits.append) == 0
    assert waits == []
    assert module.run_loop(*args, cdp_endpoint='http://127.0.0.1:9333', user_data_dir=None,
                           rounds=2, fetcher=lambda *a, **k: {}, sleeper=waits.append) == 0
    assert len(waits) == 1 and 360 <= waits[0] <= 720


@pytest.mark.parametrize('platform,first,second', [
    ('boss', 'https://www.zhipin.com/web/geek/jobs?query=Java&city=101010100',
     'https://www.zhipin.com/web/geek/jobs?query=Python&city=101010100'),
    ('zhaopin', 'https://www.zhaopin.com/jobs?kw=Java&jl=530',
     'https://www.zhaopin.com/jobs?kw=Java&jl=538'),
    ('liepin', 'https://www.liepin.com/zhaopin/?key=Java&dqs=010',
     'https://www.liepin.com/zhaopin/?key=Python&dqs=010'),
])
def test_explicit_prepare_switch_uses_combination_gate(clock, platform, first, second):
    browser.run_search_navigation(platform, first, lambda: None)
    previous = clock[0]
    browser.run_search_navigation(platform, second, lambda: None)
    assert clock[0] - previous >= 360


@pytest.mark.parametrize('query', ['', '?query=Java', '?query=Java&query=Python&city=1',
                                    '?query=&city=1', '?query=Java&city=1&city=2'])
def test_prepare_unknown_or_ambiguous_scope_fails_before_reservation(clock, monkeypatch, query):
    monkeypatch.setattr(frequency, 'run_action', lambda *a, **k: pytest.fail('invalid scope reserved'))
    with pytest.raises(ValueError):
        browser.run_search_navigation('boss', 'https://www.zhipin.com/web/geek/jobs' + query, lambda: None)


@pytest.mark.parametrize('template', [
    'https://www.zhaopin.com/jobs?kw=Python&jl={city}',
    'https://www.zhaopin.com/jobs?kw={keyword}&jl=538',
    'https://www.zhaopin.com/jobs?kw={keyword}&kw=Python&jl={city}',
    'https://www.zhaopin.com/jobs?custom_keyword={keyword}&jl={city}',
    'https://other.example/jobs?kw={keyword}&jl={city}',
])
def test_cn_template_cannot_disguise_real_search_scope(clock, monkeypatch, template):
    actions = fake_browser(monkeypatch, clock)
    monkeypatch.setattr(browser, 'ensure_ready', lambda *a, **k: pytest.fail('invalid template prepared browser'))
    with pytest.raises(ValueError):
        cn.run_fetch('zhaopin', ['Java'], [('北京', '530')],
                     cdp_endpoint='http://127.0.0.1:9333', search_url_template=template)
    assert actions == []


def test_current_page_must_match_declared_scope(clock, monkeypatch):
    actions = fake_browser(monkeypatch, clock)
    monkeypatch.setattr(cn, 'extract_current_page', lambda *a: pytest.fail('wrong page extracted'))
    with pytest.raises(cn.CdpError, match='collection_search_target_mismatch'):
        cn.run_fetch('zhaopin', ['Python'], [('北京', '530')],
                     cdp_endpoint='http://127.0.0.1:9333', current_page_only=True)
    assert actions == []


def test_browser_callback_runtime_does_not_eat_next_page_delay(clock, monkeypatch):
    actions = fake_browser(monkeypatch, clock)
    def search(client, spec, url, settle):
        client.navigate(url)
        clock[0] += 100  # A delayed browser operation must remain exclusive.
        return []
    monkeypatch.setattr(cn, 'fetch_search_page', search)
    cn.run_fetch('zhaopin', ['Java'], [('北京', '530')],
                 cdp_endpoint='http://127.0.0.1:9333', pages=2, detail_limit=0)
    assert len(actions) == 2
    assert actions[1][1] - (actions[0][1] + 100) >= 15


@pytest.mark.parametrize('module', [boss, cn])
def test_slower_delay_survives_early_list_break(clock, monkeypatch, module):
    actions = fake_browser(monkeypatch, clock)
    if module is boss:
        def search(client, url, settle):
            client.navigate(url)
            return [{'url': 'https://www.zhipin.com/job_detail/slower.html', 'title': 'Java'}]
        monkeypatch.setattr(module, '_fetch_search_page', search)
        module.run_fetch(['Java'], [('北京', '101010100')], pages=1, max_jobs=1,
                         detail_limit=1, delay=90, settle=5)
    else:
        def search(client, spec, url, settle):
            client.navigate(url)
            return [{'url': 'https://www.zhaopin.com/job/slower', 'title': 'Java'}]
        monkeypatch.setattr(module, 'fetch_search_page', search)
        module.run_fetch('zhaopin', ['Java'], [('北京', '530')],
                         cdp_endpoint='http://127.0.0.1:9333', pages=1, max_jobs=1,
                         detail_limit=1, delay=90, settle=5)
    assert len(actions) == 2
    assert actions[1][1] - actions[0][1] >= 90


def test_cn_prevalidates_later_combinations_before_browser(clock, monkeypatch):
    monkeypatch.setattr(browser, 'ensure_ready', lambda *a, **k: pytest.fail('partial plan prepared browser'))
    # Java is valid, but the fixed template disagrees with the second combination.
    with pytest.raises(ValueError, match='collection_search_target_mismatch'):
        cn.run_fetch('zhaopin', ['Java', 'Python'], [('北京', '530')],
                     cdp_endpoint='http://127.0.0.1:9333',
                     search_url_template='https://www.zhaopin.com/jobs?kw=Java&jl={city}&page={page}')


def test_cn_prevalidates_later_pages_before_browser(clock, monkeypatch):
    monkeypatch.setattr(browser, 'ensure_ready', lambda *a, **k: pytest.fail('partial plan prepared browser'))
    # Page one happens to match keyword "1", while the second page does not.
    with pytest.raises(ValueError, match='collection_search_target_mismatch'):
        cn.run_fetch('zhaopin', ['1'], [('北京', '530')], pages=2,
                     cdp_endpoint='http://127.0.0.1:9333',
                     search_url_template='https://www.zhaopin.com/jobs?kw={page}&jl={city}')

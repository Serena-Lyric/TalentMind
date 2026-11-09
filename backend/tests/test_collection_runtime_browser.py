"""Unified CDP engine tests; runners are synthetic, no browser or database."""
import pytest

from app.collect import browser
from app.collect.fetchers.cdp import CdpError
from app.collect.runtime.browser import CdpEngine
from app.collect.runtime.platforms import PLATFORMS, RuntimeConfig


def test_cdp_engine_dispatches_three_platforms_to_fixed_isolated_profiles():
    calls = []

    def boss_runner(*args, **kwargs):
        calls.append(('boss', args, kwargs))
        return {'listed': 1, 'detail_attempted': 1, 'inserted': 1, 'stop_reason': None}

    def cn_runner(*args, **kwargs):
        calls.append((args[0], args, kwargs))
        return {'listed': 1, 'detail_attempted': 1, 'inserted': 1, 'stop_reason': None}

    provider = lambda: None
    engine = CdpEngine(boss_runner=boss_runner, cn_runner=cn_runner)
    config = RuntimeConfig()
    results = [
        engine.fetch_once(platform, 'Python', PLATFORMS[platform].cities[0], 1, provider, config=config)
        for platform in ('boss', 'zhaopin', 'liepin')
    ]

    assert [result['status'] for result in results] == ['success', 'success', 'success']
    profiles = {kwargs['user_data_dir'] for _, _, kwargs in calls}
    assert len(profiles) == 3
    assert all(path.endswith(('boss', 'zhaopin', 'liepin')) for path in profiles)
    for _, _, kwargs in calls:
        assert kwargs['pages'] == 1
        assert kwargs['detail_limit'] == 1
        assert kwargs['max_jobs'] == 1
        assert kwargs['login_timeout'] == 0
        assert kwargs['db_provider'] is provider


def test_cdp_engine_maps_block_and_login_without_retry():
    attempts = []

    def blocked(*args, **kwargs):
        attempts.append('blocked')
        raise browser.AccessBlocked('verification_required')

    engine = CdpEngine(boss_runner=blocked, cn_runner=blocked)
    result = engine.fetch_once('boss', 'Python', PLATFORMS['boss'].cities[0], 1, lambda: None)
    assert result['status'] == 'blocked'
    assert attempts == ['blocked']

    def login(*args, **kwargs):
        attempts.append('login')
        raise CdpError('login_required')

    engine = CdpEngine(boss_runner=login, cn_runner=login)
    result = engine.fetch_once('zhaopin', 'Python', PLATFORMS['zhaopin'].cities[0], 1, lambda: None)
    assert result['status'] == 'needs_login'
    assert attempts == ['blocked', 'login']

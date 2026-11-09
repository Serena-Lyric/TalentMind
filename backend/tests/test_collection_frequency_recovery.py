"""Recovery uses synthetic actions and a private temporary SQLite ledger only."""
import os
import sqlite3
import subprocess
import sys
from contextlib import closing
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.collect import frequency


@pytest.fixture
def ledger(tmp_path, monkeypatch):
    clock = [1800000000.0]
    monkeypatch.setattr(frequency, '_STATE_PATH', tmp_path / 'frequency.sqlite3')
    monkeypatch.setattr(frequency, '_clock', lambda: clock[0])
    try:
        yield clock
    finally:
        for path in tmp_path.iterdir():
            if path.is_file():
                path.unlink()
        assert not any(tmp_path.iterdir())


def interrupted_action():
    raise RuntimeError('synthetic browser failure')


def test_exception_is_explicitly_recoverable_without_refunding_cooldown(ledger):
    with pytest.raises(RuntimeError, match='synthetic'):
        frequency.run_action('zhaopin', 'Python', '530', interrupted_action)
    ledger[0] += 1000
    with pytest.raises(frequency.FrequencyStateError, match='unfinished'):
        frequency.reserve_action('zhaopin', 'Python', '530')
    from app.collect import frequency_recovery
    status = frequency_recovery.get_status('zhaopin')
    assert status['state'] == 'unfinished'
    assert status['interruption'] == 'exception'
    assert status['can_recover'] is True
    recovered = frequency_recovery.recover('zhaopin', status['recovery_token'])
    assert recovered['recovered'] is True
    assert recovered['next_action_at'] == ledger[0] + 30
    assert recovered['next_combination_at'] == ledger[0] + 720
    with pytest.raises(frequency.FrequencyLimitError):
        frequency.reserve_action('zhaopin', 'Python', '530')
    ledger[0] += 30
    with pytest.raises(frequency.FrequencyLimitError):
        frequency.reserve_action('zhaopin', 'Java', '530')
    frequency.reserve_action('zhaopin', 'Python', '530')


def test_legacy_marker_recovery_is_exact_idempotent_and_audited(ledger):
    frequency._reserve_action('zhaopin', 'Python', '530', kind='page', flight='legacy-owner')
    from app.collect import frequency_recovery
    status = frequency_recovery.get_status('zhaopin')
    assert status['interruption'] == 'unknown'
    with pytest.raises(frequency.FrequencyStateError, match='changed'):
        frequency_recovery.recover('zhaopin', 'stale-owner')
    first = frequency_recovery.recover('zhaopin', 'legacy-owner')
    ledger[0] += 1
    second = frequency_recovery.recover('zhaopin', 'legacy-owner')
    assert second['next_action_at'] == first['next_action_at']
    assert second['recovered'] is True
    with closing(sqlite3.connect(frequency._STATE_PATH)) as connection:
        assert connection.execute('SELECT COUNT(*) FROM collection_action_recoveries').fetchone() == (1,)
        assert connection.execute('SELECT COUNT(*) FROM collection_action_flights').fetchone() == (0,)


def test_active_writer_cannot_be_recovered(ledger):
    frequency._reserve_action('zhaopin', 'Python', '530', kind='page', flight='active')
    from app.collect import frequency_recovery
    with closing(sqlite3.connect(frequency._STATE_PATH)) as writer:
        writer.execute('BEGIN IMMEDIATE')
        try:
            assert frequency_recovery.get_status('zhaopin')['state'] == 'busy'
            with pytest.raises(frequency.FrequencyStateError, match='busy'):
                frequency_recovery.recover('zhaopin', 'active')
            assert writer.execute('SELECT owner FROM collection_action_flights').fetchone() == ('active',)
        finally:
            writer.rollback()


def test_recovery_fences_reserved_callback_before_execution(ledger, monkeypatch):
    from app.collect import frequency_recovery
    original = frequency._reserve_action
    def reserve_then_recover(*args, **kwargs):
        result = original(*args, **kwargs)
        frequency_recovery.recover('zhaopin', kwargs['flight'])
        return result
    monkeypatch.setattr(frequency, '_reserve_action', reserve_then_recover)
    called = []
    with pytest.raises(frequency.FrequencyStateError, match='reservation_lost'):
        frequency.run_action('zhaopin', 'Python', '530', lambda: called.append(True))
    assert called == []


def test_concurrent_recovery_has_one_receipt_and_one_cooldown(ledger):
    frequency._reserve_action('zhaopin', 'Python', '530', kind='page', flight='legacy')
    from app.collect import frequency_recovery
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: frequency_recovery.recover('zhaopin', 'legacy'), range(2)))
    assert all(result['recovered'] for result in results)
    assert results[0]['next_action_at'] == results[1]['next_action_at']


def test_process_crash_marker_is_recoverable(ledger):
    code = '''
import os, sys
from pathlib import Path
from app.collect import frequency
frequency._STATE_PATH = Path(sys.argv[1])
frequency._clock = lambda: float(sys.argv[2])
frequency.run_action('zhaopin', 'Python', '530', lambda: os._exit(7))
'''
    process = subprocess.run([sys.executable, '-c', code, str(frequency._STATE_PATH), str(ledger[0])],
                             capture_output=True, env=os.environ.copy(), timeout=20)
    assert process.returncode == 7
    from app.collect import frequency_recovery
    status = frequency_recovery.get_status('zhaopin')
    assert status['state'] == 'unfinished'
    assert status['interruption'] == 'unknown'
    assert frequency_recovery.recover('zhaopin', status['recovery_token'])['recovered']


def _hold_browser_action(path, now, started, finish):
    from pathlib import Path
    from app.collect import frequency
    frequency._STATE_PATH = Path(path)
    frequency._clock = lambda: now
    def callback():
        started.set()
        if not finish.wait(15):
            raise RuntimeError('synthetic callback timed out')
    frequency.run_action('zhaopin', 'Python', '530', callback)


def test_live_callback_in_other_process_keeps_its_flight(ledger):
    import multiprocessing
    from app.collect import frequency_recovery
    context = multiprocessing.get_context('spawn')
    started, finish = context.Event(), context.Event()
    process = context.Process(target=_hold_browser_action, args=(str(frequency._STATE_PATH), ledger[0], started, finish))
    try:
        process.start()
        assert started.wait(10)
        with closing(sqlite3.connect(frequency._STATE_PATH)) as connection:
            token = connection.execute('SELECT owner FROM collection_action_flights').fetchone()[0]
        assert frequency_recovery.get_status('zhaopin')['state'] == 'busy'
        with pytest.raises(frequency.FrequencyStateError, match='busy'):
            frequency_recovery.recover('zhaopin', token)
        finish.set()
        process.join(10)
        assert process.exitcode == 0
        assert frequency_recovery.get_status('zhaopin')['state'] == 'clear'
    finally:
        finish.set()
        if process.is_alive():
            process.terminate()
            process.join()


def test_old_recovery_receipt_never_clears_new_action(ledger):
    from app.collect import frequency_recovery
    frequency._reserve_action('zhaopin', 'Python', '530', kind='page', flight='old')
    frequency_recovery.recover('zhaopin', 'old')
    ledger[0] += 30
    frequency._reserve_action('zhaopin', 'Python', '530', kind='page', flight='new')
    with pytest.raises(frequency.FrequencyStateError, match='changed'):
        frequency_recovery.recover('zhaopin', 'old')
    assert frequency_recovery.get_status('zhaopin')['recovery_token'] == 'new'


def test_recovery_retains_longer_switch_budget_and_other_platform(ledger):
    from app.collect import frequency_recovery
    frequency._reserve_action('zhaopin', 'Python', '530', kind='page', flight='owner')
    other = frequency.reserve_action('liepin', 'Java', '北京')
    with closing(sqlite3.connect(frequency._STATE_PATH)) as connection, connection:
        connection.execute('UPDATE collection_frequency SET next_switch=? WHERE platform=?', (ledger[0] + 900, 'zhaopin'))
    result = frequency_recovery.recover('zhaopin', 'owner')
    assert result['next_combination_at'] == ledger[0] + 900
    assert frequency_recovery.get_status('liepin')['next_action_at'] == other['next_action_at']


def test_recovery_transaction_rolls_back_if_receipt_write_fails(ledger):
    from app.collect import frequency_recovery
    frequency._reserve_action('zhaopin', 'Python', '530', kind='page', flight='owner')
    with closing(sqlite3.connect(frequency._STATE_PATH)) as connection, connection:
        connection.execute('CREATE TABLE collection_action_recoveries (wrong_column TEXT)')
    with pytest.raises(frequency.FrequencyStateError, match='unavailable'):
        frequency_recovery.recover('zhaopin', 'owner')
    assert frequency_recovery.get_status('zhaopin')['recovery_token'] == 'owner'


@pytest.mark.parametrize('damage', ['empty', 'invalid_interval', 'clock_rollback'])
def test_recovery_never_repairs_invalid_ledger(ledger, damage):
    if damage == 'empty':
        frequency._STATE_PATH.touch()
    else:
        frequency._reserve_action('zhaopin', 'Python', '530', kind='page', flight='owner')
        if damage == 'clock_rollback':
            ledger[0] -= 1
        else:
            with closing(sqlite3.connect(frequency._STATE_PATH)) as connection, connection:
                connection.execute('UPDATE collection_frequency SET next_page=last_reserved+1')
    from app.collect import frequency_recovery
    assert frequency_recovery.get_status('zhaopin')['state'] == 'unavailable'
    with pytest.raises(frequency.FrequencyStateError):
        frequency_recovery.recover('zhaopin', 'owner')


def test_status_of_missing_ledger_does_not_create_it(ledger):
    from app.collect import frequency_recovery
    assert frequency_recovery.get_status('zhaopin')['state'] == 'clear'
    assert not frequency._STATE_PATH.exists()


@pytest.fixture
def controller(ledger, monkeypatch, tmp_path):
    from app.collect import control
    monkeypatch.setattr(control, '_STATE_DIR', tmp_path)
    monkeypatch.setattr(control, '_STATE_PATH', tmp_path / 'control.json')
    monkeypatch.setattr(control, '_PROCESS', None)
    monkeypatch.setattr(control, '_STARTING_RUN', None)
    monkeypatch.setattr(control, '_RESERVATION', None)
    return control


@pytest.mark.parametrize('activity', ['_RESERVATION', '_PROCESS', '_STARTING_RUN'])
def test_controller_activity_blocks_diagnosis_and_recovery(controller, monkeypatch, activity):
    frequency._reserve_action('zhaopin', 'Python', '530', kind='page', flight='owner')
    monkeypatch.setattr(controller, activity, object())
    result = controller.get_frequency_status('zhaopin')
    assert result['state'] == 'busy'
    assert not result['can_recover']
    with pytest.raises(RuntimeError, match='正在运行'):
        controller.recover_frequency('zhaopin', 'owner')


def test_controller_recovery_releases_its_own_reservation(controller):
    frequency._reserve_action('zhaopin', 'Python', '530', kind='page', flight='owner')
    with pytest.raises(frequency.FrequencyStateError, match='changed'):
        controller.recover_frequency('zhaopin', 'stale')
    assert controller._RESERVATION is None
    assert controller.recover_frequency('zhaopin', 'owner')['recovered']
    assert controller._RESERVATION is None


@pytest.mark.parametrize('enabled,host,origin,allowed', [
    ('1', '127.0.0.1', 'http://localhost:5173', True),
    ('0', '127.0.0.1', 'http://localhost:5173', False),
    ('1', '192.0.2.10', 'http://localhost:5173', False),
    ('1', '127.0.0.1', 'https://untrusted.example', False),
])
def test_frequency_routes_require_local_boundary(controller, monkeypatch, enabled, host, origin, allowed):
    from fastapi import HTTPException
    from starlette.requests import Request
    from app.routers import collection
    monkeypatch.setenv('TALENTMIND_LOCAL_RAW', enabled)
    request = Request({'type': 'http', 'client': (host, 1234),
                       'headers': [(b'host', b'localhost:8000'), (b'origin', origin.encode())]})
    frequency._reserve_action('zhaopin', 'Python', '530', kind='page', flight='owner')
    if allowed:
        assert collection.collection_frequency('zhaopin', request)['data']['state'] == 'unfinished'
        assert collection.collection_frequency_recover('zhaopin', request, {'recovery_token': 'owner'})['data']['recovered']
    else:
        with pytest.raises(HTTPException) as error:
            collection.collection_frequency('zhaopin', request)
        assert error.value.status_code == 403
        with pytest.raises(HTTPException) as error:
            collection.collection_frequency_recover('zhaopin', request, {'recovery_token': 'owner'})
        assert error.value.status_code == 403


@pytest.fixture
def split_ledger(tmp_path, monkeypatch):
    clock = [1800000000.0]
    legacy = tmp_path / 'frequency.sqlite3'
    monkeypatch.setattr(frequency, '_STATE_PATH', frequency._DEFAULT_STATE_PATH)
    monkeypatch.setattr(frequency, '_LEDGER_ROOT', tmp_path / 'runtime')
    monkeypatch.setattr(frequency, '_clock', lambda: clock[0])
    return legacy, clock


def test_legacy_flight_migration_preserves_unfinished_and_cooldown(split_ledger, monkeypatch):
    legacy, clock = split_ledger
    from app.collect import frequency_recovery

    monkeypatch.setattr(frequency, '_STATE_PATH', legacy)
    frequency._reserve_action('zhaopin', 'Python', '530', kind='page', flight='legacy-owner')
    monkeypatch.setattr(frequency, '_STATE_PATH', frequency._DEFAULT_STATE_PATH)

    assert frequency.legacy_migration_required('zhaopin') is True
    migrated = frequency_recovery.migrate_legacy_platform('zhaopin', legacy)
    assert migrated['migrated'] is True
    assert legacy.exists()
    assert frequency.ledger_path('zhaopin').exists()

    status = frequency_recovery.get_status('zhaopin')
    assert status['state'] == 'unfinished'
    assert status['recovery_token'] == 'legacy-owner'

    clock[0] += 1000
    recovered = frequency_recovery.recover('zhaopin', 'legacy-owner')
    assert recovered['next_action_at'] == clock[0] + 30
    with pytest.raises(frequency.FrequencyLimitError):
        frequency.reserve_action('zhaopin', 'Python', '530')

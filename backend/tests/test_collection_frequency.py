import sqlite3
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
        for path in tmp_path.rglob('*'):
            if path.is_file():
                path.unlink()
        assert not any(path.is_file() for path in tmp_path.rglob('*'))


def test_initial_page_then_hard_page_boundary(ledger):
    result = frequency.reserve_action('boss', 'Java', '101')
    assert 15 <= result['next_action_at'] - ledger[0] <= 30
    ledger[0] = result['next_action_at'] - .001
    with pytest.raises(frequency.FrequencyLimitError):
        frequency.reserve_action('boss', 'Java', '101')
    ledger[0] = result['next_action_at']
    frequency.reserve_action('boss', 'Java', '101')


def test_new_combination_waits_shared_switch_cooldown(ledger):
    result = frequency.reserve_action('boss', 'Java', '101')
    assert 360 <= result['next_combination_at'] - ledger[0] <= 720
    ledger[0] = result['next_action_at']
    with pytest.raises(frequency.FrequencyLimitError):
        frequency.reserve_action('boss', 'Python', '101')
    ledger[0] = result['next_combination_at']
    frequency.reserve_action('boss', 'Python', '101')


def test_prepare_preserves_target_and_platforms_are_independent(ledger):
    prepared = frequency.reserve_action('boss', '', '', kind='prepare')
    ledger[0] = prepared['next_action_at']
    first = frequency.reserve_action('boss', 'Java', '101')
    frequency.reserve_action('liepin', 'Java', '101')
    ledger[0] = first['next_action_at']
    preparation = frequency.reserve_action('boss', '', '', kind='prepare')
    ledger[0] = preparation['next_action_at']
    with pytest.raises(frequency.FrequencyLimitError):
        frequency.reserve_action('boss', 'Python', '101')


def test_capture_permit_uses_30_second_design_bound(ledger):
    assert frequency.reserve_action('boss', 'Java', '101', kind='capture')['next_action_at'] == ledger[0] + 30


def test_failed_caller_and_new_connection_do_not_reset_reservation(ledger):
    frequency.reserve_action('boss', 'Java', '101')
    # Every call uses a new connection; an exception after reserving cannot refund it.
    with pytest.raises(frequency.FrequencyLimitError):
        frequency.reserve_action('boss', 'Java', '101')


def test_atomic_competing_reservations_allow_only_one(ledger):
    frequency.reserve_action('liepin', 'Java', '101')
    def reserve(_):
        try:
            frequency.reserve_action('boss', 'Java', '101')
            return 'ok'
        except frequency.FrequencyLimitError:
            return 'limited'
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(reserve, range(6)))
    assert results.count('ok') == 1
    assert results.count('limited') == 5


def test_clock_rollback_corrupt_state_and_unrelated_sources_fail_closed(ledger):
    frequency.reserve_action('boss', 'Java', '101')
    ledger[0] -= 1
    with pytest.raises(frequency.FrequencyStateError, match='rollback'):
        frequency.reserve_action('boss', 'Java', '101')
    with pytest.raises(ValueError):
        frequency.reserve_action('hn', 'Java', '101')
    frequency._STATE_PATH.write_bytes(b'not a database')
    with pytest.raises(frequency.FrequencyStateError, match='unavailable'):
        frequency.reserve_action('boss', 'Java', '101')


def test_wait_rechecks_gate_after_sleep(ledger):
    first = frequency.reserve_action('boss', 'Java', '101')
    sleeps = []
    def sleep(seconds):
        sleeps.append(seconds)
        ledger[0] += seconds
    frequency.wait_for_action('boss', 'Java', '101', sleeper=sleep)
    assert len(sleeps) == 1
    assert ledger[0] == first['next_action_at']


def test_separate_interpreter_keeps_existing_cooldown(ledger):
    import os
    import subprocess
    import sys
    result = frequency.reserve_action('boss', 'Java', '101')
    code = '''
import sys
from pathlib import Path
from app.collect import frequency
frequency._STATE_PATH = Path(sys.argv[1])
frequency._clock = lambda: float(sys.argv[2])
try:
    frequency.reserve_action('boss', 'Java', '101')
except frequency.FrequencyLimitError:
    print('limited-after-restart')
else:
    raise AssertionError('restart reset the ledger')
'''
    process = subprocess.run([sys.executable, '-c', code, str(frequency._STATE_PATH), str(ledger[0])], capture_output=True, text=True, env=os.environ.copy(), check=True)
    assert process.stdout.strip() == 'limited-after-restart'


@pytest.mark.parametrize('damage', ['empty', 'short_interval', 'bad_target'])
def test_invalid_persisted_ledger_is_not_silently_reset(ledger, damage):
    if damage == 'empty':
        frequency._STATE_PATH.touch()
    else:
        frequency.reserve_action('boss', 'Java', '101')
        with closing(sqlite3.connect(frequency._STATE_PATH)) as connection, connection:
            statement = "UPDATE collection_frequency SET next_page=last_reserved+1" if damage == 'short_interval' else "UPDATE collection_frequency SET keyword=''"
            connection.execute(statement)
    with pytest.raises(frequency.FrequencyStateError):
        frequency.reserve_action('boss', 'Java', '101')


def test_run_action_counts_from_completion_not_early_reservation(ledger):
    observed = []
    def action():
        ledger[0] += 120
        observed.append(ledger[0])
        return 'result'
    assert frequency.run_action('boss', 'Java', '101', action) == 'result'
    with pytest.raises(frequency.FrequencyLimitError) as error:
        frequency.reserve_action('boss', 'Java', '101')
    assert 15 <= error.value.retry_after <= 30


def test_failed_action_remains_blocked_after_cooldown(ledger):
    def failed():
        raise RuntimeError('uncertain browser navigation')
    with pytest.raises(RuntimeError, match='uncertain'):
        frequency.run_action('boss', 'Java', '101', failed)
    ledger[0] += 10000
    with pytest.raises(frequency.FrequencyStateError, match='unfinished'):
        frequency.reserve_action('boss', 'Java', '101')


def _claim_permit(path, token, now, barrier, queue):
    from pathlib import Path
    from app.collect import frequency
    frequency._STATE_PATH = Path(path)
    barrier.wait()
    try:
        frequency.consume_capture_permit('run', 'list', token, now)
        queue.put('accepted')
    except ValueError:
        queue.put('rejected')


def test_capture_permit_is_consumed_once_across_processes(ledger):
    import multiprocessing
    reservation = frequency.reserve_action('boss', 'Java', '101', kind='capture')
    permit = frequency.issue_capture_permit('run', 'list', reservation)
    context = multiprocessing.get_context('spawn')
    barrier, queue = context.Barrier(2), context.Queue()
    processes = [context.Process(target=_claim_permit, args=(str(frequency._STATE_PATH), permit['token'], ledger[0], barrier, queue)) for _ in range(2)]
    try:
        for process in processes:
            process.start()
        results = [queue.get(timeout=15), queue.get(timeout=15)]
        assert sorted(results) == ['accepted', 'rejected']
        for process in processes:
            process.join(timeout=15)
            assert process.exitcode == 0
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join()
        queue.close()


def test_late_capture_permit_cannot_shorten_combination_interval(ledger, monkeypatch):
    class MinimumRandom:
        def uniform(self, lower, upper):
            return lower
    monkeypatch.setattr(frequency.random, 'SystemRandom', MinimumRandom)
    start = ledger[0]
    reservation = frequency.reserve_action('boss', 'Java', '101', kind='capture')
    permit = frequency.issue_capture_permit('run', 'list', reservation)
    ledger[0] += 14.9
    frequency.consume_capture_permit('run', 'list', permit['token'], ledger[0])
    actual_read = ledger[0]
    ledger[0] = start + 360
    with pytest.raises(frequency.FrequencyLimitError):
        frequency.reserve_action('boss', 'Python', '101', kind='capture')
    ledger[0] = reservation['next_combination_at']
    assert ledger[0] - actual_read >= 360
    frequency.reserve_action('boss', 'Python', '101', kind='capture')


def test_clock_rollback_before_callback_blocks_the_actual_action(ledger, monkeypatch):
    values = iter([ledger[0], ledger[0] - 1])
    monkeypatch.setattr(frequency, '_clock', lambda: next(values))
    called = []
    with pytest.raises(frequency.FrequencyStateError, match='rollback'):
        frequency.run_action('boss', 'Java', '101', lambda: called.append(True))
    assert called == []

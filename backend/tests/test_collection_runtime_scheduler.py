"""Scheduler tests use fake processes and isolated runtime state."""
import pytest

from app.collect import frequency
from app.collect.runtime import scheduler, state
from app.collect.runtime.platforms import RuntimeConfig


class FakeProcess:
    next_pid = 4000

    def __init__(self):
        type(self).next_pid += 1
        self.pid = type(self).next_pid
        self.returncode = None
        self.terminated = False
        self.killed = False

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        return self.returncode

    def terminate(self):
        self.terminated = True
        self.returncode = 0

    def kill(self):
        self.killed = True
        self.returncode = -9


@pytest.fixture
def isolated_scheduler(tmp_path, monkeypatch):
    monkeypatch.setattr(scheduler, '_STATE_ROOT', tmp_path / 'runtime')
    monkeypatch.setattr(scheduler, '_SCHEDULER_PATH', tmp_path / 'runtime' / 'scheduler.json')
    monkeypatch.setattr(scheduler, '_PROCESSES', {})
    monkeypatch.setattr(scheduler, '_PROCESS_META', {})
    monkeypatch.setattr(scheduler, '_clock', lambda: 1000.0)
    monkeypatch.setattr(scheduler.readiness, 'require_database_ready', lambda: None)
    monkeypatch.setattr(frequency, 'legacy_migration_required', lambda platform: False)
    spawned = []

    def spawn(platform, config):
        process = FakeProcess()
        spawned.append((platform, process))
        return process

    monkeypatch.setattr(scheduler, '_spawn_worker', spawn)
    return spawned


def test_start_spawns_three_workers_and_aggregates_status(isolated_scheduler):
    result = scheduler.start(RuntimeConfig())

    assert sorted(platform for platform, _ in isolated_scheduler) == ['boss', 'liepin', 'zhaopin']
    assert result['status'] in {'running', 'waiting'}
    assert set(result['platforms']) == {'boss', 'zhaopin', 'liepin'}
    assert all(item['status'] in {'running', 'waiting'} for item in result['platforms'].values())
    assert scheduler._SCHEDULER_PATH.exists()


def test_one_blocked_platform_does_not_hide_other_platforms(isolated_scheduler):
    scheduler.start(RuntimeConfig())
    boss = state.load_state('boss', root=scheduler._STATE_ROOT)
    boss.status = 'blocked'
    boss.stop_reason = 'verification_required'
    state.save_state(boss, root=scheduler._STATE_ROOT)

    result = scheduler.status()
    assert result['platforms']['boss']['status'] == 'blocked'
    assert result['platforms']['zhaopin']['status'] in {'running', 'waiting'}
    assert result['platforms']['liepin']['status'] in {'running', 'waiting'}


def test_stop_marks_all_platforms_stopped(isolated_scheduler):
    scheduler.start(RuntimeConfig())
    result = scheduler.stop()

    assert all(item['status'] == 'stopped' for item in result['platforms'].values())
    assert all(state.stop_requested(platform, root=scheduler._STATE_ROOT)
               for platform in ('boss', 'zhaopin', 'liepin'))
    assert all(process.terminated for _, process in isolated_scheduler)


def test_resume_blocked_requires_confirmation_and_applies_safety_delay(isolated_scheduler):
    scheduler.start(RuntimeConfig())
    boss = state.load_state('boss', root=scheduler._STATE_ROOT)
    boss.status = 'blocked'
    boss.stop_reason = 'verification_required'
    state.save_state(boss, root=scheduler._STATE_ROOT)

    with pytest.raises(ValueError, match='confirm'):
        scheduler.resume('boss', confirmed=False)
    result = scheduler.resume('boss', confirmed=True)
    assert result['platforms']['boss']['status'] in {'running', 'waiting'}
    assert result['platforms']['boss']['next_run_at'] >= 1030
    assert sum(platform == 'boss' for platform, _ in isolated_scheduler) == 2


def test_start_fails_closed_when_legacy_migration_is_required(isolated_scheduler, monkeypatch):
    monkeypatch.setattr(frequency, 'legacy_migration_required', lambda platform: platform == 'zhaopin')
    with pytest.raises(RuntimeError, match='legacy_migration_required'):
        scheduler.start(RuntimeConfig())
    assert isolated_scheduler == []


def test_status_restores_persisted_worker_pid_and_creation_time(isolated_scheduler, monkeypatch):
    process = FakeProcess()
    process.created_at = 123456
    scheduler._SCHEDULER_PATH.parent.mkdir(parents=True, exist_ok=True)
    scheduler._SCHEDULER_PATH.write_text(
        '{"started_at": 1000, "config": {}, "pids": {"boss": {"pid": %d, "created_at": 123456}}}' % process.pid,
        encoding='utf-8',
    )
    value = state.RuntimeState(platform='boss', status='waiting', next_run_at=1000, updated_at=1000)
    state.save_state(value, root=scheduler._STATE_ROOT)
    monkeypatch.setattr(scheduler, '_pid_process', lambda platform, pid, created_at: process
                        if platform == 'boss' and pid == process.pid and created_at == 123456 else None)

    result = scheduler.status()
    assert scheduler._PROCESSES['boss'] is process
    assert result['platforms']['boss']['status'] == 'waiting'

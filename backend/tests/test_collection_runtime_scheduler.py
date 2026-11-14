"""Scheduler tests use fake processes and isolated runtime state."""
import pytest

from app.collect import frequency
from app.collect.runtime import lease, scheduler, state
from app.collect.runtime.platforms import RuntimeConfig


class FakeProcess:
    next_pid = 4000

    def __init__(self):
        type(self).next_pid += 1
        self.pid = type(self).next_pid
        self.returncode = None
        self.terminated = False
        self.killed = False
        self._collection_job = FakeJob(f'Local\\TalentMind.Collection.{self.pid:032x}')

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


class FakeJob:
    def __init__(self, name):
        self.name = name
        self.handle = None


@pytest.fixture
def isolated_scheduler(tmp_path, monkeypatch):
    monkeypatch.setattr(scheduler, '_STATE_ROOT', tmp_path / 'runtime')
    monkeypatch.setattr(scheduler, '_SCHEDULER_PATH', tmp_path / 'runtime' / 'scheduler.json')
    monkeypatch.setattr(scheduler, '_PROCESSES', {})
    monkeypatch.setattr(scheduler, '_PROCESS_META', {})
    monkeypatch.setattr(scheduler, '_LEASES', {})
    monkeypatch.setattr(scheduler, '_clock', lambda: 1000.0)
    monkeypatch.setattr(scheduler.readiness, 'require_database_ready', lambda: None)
    monkeypatch.setattr(frequency, 'legacy_migration_required', lambda platform: False)
    monkeypatch.setattr(lease.worker_process, 'job_has_processes', lambda name: False)
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
    monkeypatch.setattr(scheduler, '_pid_process', lambda platform, pid, created_at, job_name=None: process
                        if platform == 'boss' and pid == process.pid and created_at == 123456 else None)

    result = scheduler.status()
    assert scheduler._PROCESSES['boss'] is process
    assert result['platforms']['boss']['status'] == 'waiting'


def test_start_preserves_existing_checkpoint_and_pending_next_due(isolated_scheduler):
    existing = state.RuntimeState(
        platform='boss', status='stopped', keyword_index=1, city_index=2, page=3,
        next_run_at=1234.0, last_saved_identity='boss://saved', last_success_at=1200.0,
        stats={'inserted': 2}, updated_at=1200.0,
    )
    state.save_state(existing, root=scheduler._STATE_ROOT)
    scheduler._write_scheduler({'config': scheduler._config_dict(RuntimeConfig()), 'pids': {}})

    scheduler.start(RuntimeConfig())
    loaded = state.load_state('boss', root=scheduler._STATE_ROOT)
    assert (loaded.keyword_index, loaded.city_index, loaded.page) == (1, 2, 3)
    assert loaded.next_run_at == 1234.0
    assert loaded.last_saved_identity == 'boss://saved'
    assert loaded.last_success_at == 1200.0
    assert loaded.stats == {'inserted': 2}
    assert loaded.status == 'waiting'


@pytest.mark.parametrize('status', ['blocked', 'needs_login', 'failed'])
def test_start_skips_platform_that_needs_manual_recovery(isolated_scheduler, status):
    existing = state.RuntimeState(platform='boss', status=status, stop_reason='review_required', updated_at=1000)
    state.save_state(existing, root=scheduler._STATE_ROOT)
    state.request_stop('boss', root=scheduler._STATE_ROOT)
    active_boss = FakeProcess()
    scheduler._PROCESSES['boss'] = active_boss

    result = scheduler.start(RuntimeConfig())

    assert sorted(platform for platform, _ in isolated_scheduler) == ['liepin', 'zhaopin']
    assert result['platforms']['boss']['status'] == status
    assert state.load_state('boss', root=scheduler._STATE_ROOT).stop_reason == 'review_required'
    assert state.stop_requested('boss', root=scheduler._STATE_ROOT)
    assert scheduler._PROCESSES['boss'] is active_boss


@pytest.mark.parametrize('scheduler_contents', ['{"stopped_at": 900}', '{"config": null}'])
def test_start_requires_checkpoint_reset_when_saved_plan_is_missing(
    isolated_scheduler, scheduler_contents,
):
    existing = state.RuntimeState(
        platform='boss', status='stopped', keyword_index=1, city_index=2, page=3,
        last_saved_identity='boss://saved', stats={'inserted': 1}, updated_at=900,
    )
    state.save_state(existing, root=scheduler._STATE_ROOT)
    scheduler._SCHEDULER_PATH.parent.mkdir(parents=True, exist_ok=True)
    scheduler._SCHEDULER_PATH.write_text(scheduler_contents, encoding='utf-8')

    with pytest.raises(RuntimeError, match='plan_unavailable'):
        scheduler.start({})

    assert isolated_scheduler == []
    loaded = state.load_state('boss', root=scheduler._STATE_ROOT)
    assert (loaded.keyword_index, loaded.city_index, loaded.page) == (1, 2, 3)
    assert loaded.last_saved_identity == 'boss://saved'


def test_start_requires_checkpoint_reset_when_scheduler_json_is_corrupt(isolated_scheduler):
    existing = state.RuntimeState(
        platform='boss', status='stopped', keyword_index=1, page=2,
        last_saved_identity='boss://saved', stats={'inserted': 1}, updated_at=900,
    )
    state.save_state(existing, root=scheduler._STATE_ROOT)
    scheduler._SCHEDULER_PATH.parent.mkdir(parents=True, exist_ok=True)
    scheduler._SCHEDULER_PATH.write_text('{"config":', encoding='utf-8')

    with pytest.raises(RuntimeError, match='plan_unavailable'):
        scheduler.start({})

    assert isolated_scheduler == []
    assert state.load_state('boss', root=scheduler._STATE_ROOT).page == 2


def test_explicit_checkpoint_reset_allows_default_plan_when_config_is_unavailable(isolated_scheduler):
    state.save_state(state.RuntimeState(
        platform='boss', status='stopped', keyword_index=2, page=3,
        last_saved_identity='boss://saved', stats={'inserted': 1}, updated_at=900,
    ), root=scheduler._STATE_ROOT)
    scheduler._SCHEDULER_PATH.parent.mkdir(parents=True, exist_ok=True)
    scheduler._SCHEDULER_PATH.write_text('{"stopped_at": 900}', encoding='utf-8')

    scheduler.start({'reset_checkpoint': True})

    assert isolated_scheduler == []
    loaded = state.load_state('boss', root=scheduler._STATE_ROOT)
    assert (loaded.keyword_index, loaded.city_index, loaded.page) == (0, 0, 1)
    assert loaded.last_saved_identity is None
    assert loaded.stats == {}
    assert scheduler._stored_runtime_config(scheduler._read_scheduler()).keywords == ('Python',)
    scheduler.start({})
    assert sorted(platform for platform, _ in isolated_scheduler) == ['boss', 'liepin', 'zhaopin']
    scheduler.stop()


def test_resume_failed_requires_confirmation_and_keeps_safety_delay(isolated_scheduler):
    failed = state.RuntimeState(platform='boss', status='failed', stop_reason='db_error', updated_at=1000)
    state.save_state(failed, root=scheduler._STATE_ROOT)
    with pytest.raises(ValueError, match='confirmation'):
        scheduler.resume('boss', confirmed=False)
    result = scheduler.resume('boss', confirmed=True)
    assert result['platforms']['boss']['status'] in {'running', 'waiting'}
    assert result['platforms']['boss']['next_run_at'] >= 1030


def test_resume_keeps_manual_gate_when_worker_lease_has_no_restorable_process(tmp_path, monkeypatch):
    state_root = tmp_path / 'runtime'
    monkeypatch.setattr(scheduler, '_STATE_ROOT', state_root)
    monkeypatch.setattr(scheduler, '_SCHEDULER_PATH', state_root / 'scheduler.json')
    monkeypatch.setattr(scheduler, '_PROCESSES', {})
    monkeypatch.setattr(scheduler, '_PROCESS_META', {})
    monkeypatch.setattr(scheduler, '_LEASES', {})
    monkeypatch.setattr(scheduler, '_pid_alive', lambda pid, created_at: True)
    monkeypatch.setattr(lease, '_pid_alive', lambda pid, created_at: True)
    state.save_state(state.RuntimeState(
        platform='boss', status='blocked', stop_reason='verification_required', updated_at=900,
    ), root=state_root)
    state.request_stop('boss', root=state_root)
    scheduler._write_scheduler({'config': scheduler._config_dict(RuntimeConfig()), 'pids': {}})
    held = lease.acquire('boss', 'scheduler:test', 'runtime', root=state_root, pid=900, created_at=1)
    lease.rebind(held, 901, 2, owner='worker:901:test')

    with pytest.raises(lease.WriterBusy):
        scheduler.resume('boss', confirmed=True)

    value = state.load_state('boss', root=state_root)
    assert value.status == 'blocked'
    assert value.stop_reason == 'verification_required'
    assert state.stop_requested('boss', root=state_root)
    assert lease.status('boss', root=state_root) is not None


def test_scheduler_blocks_old_writer_and_stop_releases_its_lease(isolated_scheduler, monkeypatch):
    monkeypatch.setattr(lease, '_pid_alive', lambda pid, created_at: pid == 900 or any(
        process.pid == pid and process.poll() is None for _, process in isolated_scheduler
    ))
    old = lease.acquire('boss', 'old-single', 'single', root=scheduler._STATE_ROOT, pid=900, created_at=1)
    with pytest.raises(lease.WriterBusy, match='collection_writer_busy:boss:single'):
        scheduler.start(RuntimeConfig())
    assert isolated_scheduler == []
    old.release()

    scheduler.start(RuntimeConfig())
    assert lease.status('boss', root=scheduler._STATE_ROOT)['kind'] == 'runtime'
    scheduler.stop()
    assert lease.status('boss', root=scheduler._STATE_ROOT) is None


@pytest.mark.parametrize('status', ['blocked', 'needs_login', 'failed'])
def test_stop_preserves_manual_gate_and_start_skips_restricted_platform(isolated_scheduler, status):
    value = state.RuntimeState(platform='boss', status=status, stop_reason='review_required', updated_at=1000)
    state.save_state(value, root=scheduler._STATE_ROOT)
    scheduler.stop()
    assert state.load_state('boss', root=scheduler._STATE_ROOT).status == status
    assert state.stop_requested('boss', root=scheduler._STATE_ROOT)

    result = scheduler.start(RuntimeConfig())

    assert sorted(platform for platform, _ in isolated_scheduler) == ['liepin', 'zhaopin']
    assert result['platforms']['boss']['status'] == status
    assert state.stop_requested('boss', root=scheduler._STATE_ROOT)
    assert state.load_state('boss', root=scheduler._STATE_ROOT).stop_reason == 'review_required'


def test_custom_config_stop_start_empty_reuses_stored_plan(tmp_path, monkeypatch):
    monkeypatch.setattr(scheduler, '_STATE_ROOT', tmp_path / 'runtime')
    monkeypatch.setattr(scheduler, '_SCHEDULER_PATH', tmp_path / 'runtime' / 'scheduler.json')
    monkeypatch.setattr(scheduler, '_PROCESSES', {})
    monkeypatch.setattr(scheduler, '_PROCESS_META', {})
    monkeypatch.setattr(scheduler, '_LEASES', {})
    monkeypatch.setattr(scheduler.readiness, 'require_database_ready', lambda: None)
    monkeypatch.setattr(scheduler.frequency, 'legacy_migration_required', lambda platform: False)
    configs = []
    processes = []
    def spawn(platform, config):
        configs.append(config)
        process = FakeProcess()
        processes.append(process)
        return process
    monkeypatch.setattr(lease, '_pid_alive', lambda pid, created_at: any(
        process.pid == pid and process.poll() is None for process in processes
    ))
    monkeypatch.setattr(scheduler, '_spawn_worker', spawn)
    custom = RuntimeConfig(
        keywords=('CustomRole',),
        cities={'boss': (('深圳', '101280600'),), 'zhaopin': (('深圳', '765'),), 'liepin': (('深圳', '深圳'),)},
    )
    scheduler.start(custom)
    scheduler.stop()
    configs.clear()
    scheduler.start({})
    assert configs[0].keywords == ('CustomRole',)
    assert configs[0].cities['boss'] == (('深圳', '101280600'),)


def test_scheduler_binds_runtime_lease_to_spawned_worker_pid(isolated_scheduler, monkeypatch):
    monkeypatch.setattr(lease, '_pid_alive', lambda pid, created_at: True)
    scheduler.start(RuntimeConfig())
    record = lease.status('boss', root=scheduler._STATE_ROOT)
    assert record['pid'] == isolated_scheduler[0][1].pid
    assert record['owner'].startswith('worker:')


def test_stop_fails_closed_when_worker_termination_is_unconfirmed(tmp_path, monkeypatch):
    class StuckProcess:
        pid = 9001
        def poll(self): return None
        def wait(self, timeout=None): return None
        def terminate(self): pass
        def kill(self): pass

    monkeypatch.setattr(scheduler, '_STATE_ROOT', tmp_path / 'runtime')
    monkeypatch.setattr(scheduler, '_SCHEDULER_PATH', tmp_path / 'runtime' / 'scheduler.json')
    monkeypatch.setattr(scheduler, '_PROCESSES', {})
    monkeypatch.setattr(scheduler, '_PROCESS_META', {})
    monkeypatch.setattr(scheduler, '_LEASES', {})
    monkeypatch.setattr(lease, '_pid_alive', lambda pid, created_at: True)
    monkeypatch.setattr(scheduler.readiness, 'require_database_ready', lambda: None)
    monkeypatch.setattr(scheduler.frequency, 'legacy_migration_required', lambda platform: False)
    monkeypatch.setattr(scheduler, '_spawn_worker', lambda platform, config: StuckProcess())
    tick = [0.0]
    monkeypatch.setattr(scheduler.time, 'monotonic', lambda: tick[0])
    monkeypatch.setattr(scheduler.time, 'sleep', lambda seconds: tick.__setitem__(0, tick[0] + seconds))
    scheduler.start(RuntimeConfig())
    with pytest.raises(RuntimeError, match='termination_unknown'):
        scheduler.stop()
    assert lease.status('boss', root=scheduler._STATE_ROOT) is not None


def test_stop_keeps_runtime_lease_when_scheduler_cannot_restore_worker(tmp_path, monkeypatch):
    state_root = tmp_path / 'runtime'
    monkeypatch.setattr(scheduler, '_STATE_ROOT', state_root)
    monkeypatch.setattr(scheduler, '_SCHEDULER_PATH', state_root / 'scheduler.json')
    monkeypatch.setattr(scheduler, '_PROCESSES', {})
    monkeypatch.setattr(scheduler, '_PROCESS_META', {})
    monkeypatch.setattr(scheduler, '_LEASES', {})
    monkeypatch.setattr(scheduler, '_pid_alive', lambda pid, created_at: True)
    monkeypatch.setattr(lease, '_pid_alive', lambda pid, created_at: True)
    held = lease.acquire('boss', 'scheduler:test', 'runtime', root=state_root, pid=900, created_at=1)
    lease.rebind(held, 901, 2, owner='worker:901:test')
    scheduler._LEASES['boss'] = held
    state.save_state(state.RuntimeState(platform='boss', status='waiting'), root=state_root)
    scheduler._write_scheduler({'started_at': 1000, 'config': {}, 'pids': {}})

    scheduler.stop()

    assert lease.status('boss', root=state_root) is not None
    assert state.load_state('boss', root=state_root).status == 'failed'
    assert 'boss' in scheduler._read_scheduler()['pids']


def test_new_backend_can_stop_restored_worker_and_release_worker_owned_lease(isolated_scheduler, monkeypatch):
    scheduler.start(RuntimeConfig())
    by_pid = {process.pid: process for _, process in isolated_scheduler}
    alive = set(by_pid)
    monkeypatch.setattr(lease.worker_process, 'job_has_processes', lambda name: False)
    for platform, process in isolated_scheduler:
        job_name = f'Local\\TalentMind.Collection.{process.pid:032x}'
        process._collection_job = FakeJob(job_name)
        held = scheduler._LEASES[platform]
        lease.rebind(held, process.pid, None, owner=f'worker:{process.pid}:test', job_name=job_name)
    scheduler._write_scheduler({
        'started_at': 1000,
        'config': scheduler._config_dict(RuntimeConfig()),
        'pids': scheduler._process_payload(),
    })
    monkeypatch.setattr(scheduler, '_pid_process', lambda platform, pid, created_at, job_name=None: by_pid.get(pid))
    monkeypatch.setattr(scheduler, '_pid_alive', lambda pid, created_at: pid in alive)
    monkeypatch.setattr(lease, '_pid_alive', lambda pid, created_at: pid in alive)
    for process in by_pid.values():
        original = process.terminate
        def terminate(process=process, original=original):
            alive.discard(process.pid)
            original()
        process.terminate = terminate
    scheduler._PROCESSES.clear()
    scheduler._LEASES.clear()

    result = scheduler.stop()
    assert all(item['status'] == 'stopped' for item in result['platforms'].values())
    assert lease.status('boss', root=scheduler._STATE_ROOT) is None

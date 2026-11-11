"""Runtime API is a thin wrapper over the isolated scheduler."""
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app.collect import frequency, readiness
from app.collect.runtime import scheduler, state
from app.routers import collection


def test_runtime_status_start_stop_and_resume_forward_to_scheduler(monkeypatch):
    seen = []
    status_value = {'status': 'waiting', 'platforms': {}}
    monkeypatch.setattr(scheduler, 'status', lambda: status_value)
    monkeypatch.setattr(scheduler, 'start', lambda payload: seen.append(('start', payload)) or status_value)
    monkeypatch.setattr(scheduler, 'stop', lambda: seen.append(('stop',)) or {'status': 'stopped', 'platforms': {}})
    monkeypatch.setattr(scheduler, 'resume', lambda platform, confirmed=False: seen.append(('resume', platform, confirmed)) or status_value)

    assert collection.collection_runtime_status()['data'] == status_value
    assert collection.collection_runtime_start({'keywords': ['Python']})['data'] == status_value
    assert collection.collection_runtime_stop()['data']['status'] == 'stopped'
    assert collection.collection_runtime_resume('boss', {'confirmed': True})['data'] == status_value
    assert seen == [
        ('start', {'keywords': ['Python']}),
        ('stop',),
        ('resume', 'boss', True),
    ]


def test_old_single_start_route_remains_compatible(monkeypatch):
    from app.collect import control
    monkeypatch.setattr(control, 'start_task', lambda payload: {'run_id': 'legacy', 'status': 'preparing'})
    result = collection.collection_start({'platform': 'boss'})
    assert result['data']['run_id'] == 'legacy'


def test_asgi_empty_start_payload_reaches_real_scheduler_default_validation(monkeypatch, tmp_path):
    class Process:
        pid = 43210
        returncode = None

        def poll(self):
            return self.returncode

        def wait(self, timeout=None):
            return self.returncode

        def terminate(self):
            self.returncode = 0

    monkeypatch.setattr(scheduler, '_STATE_ROOT', tmp_path / 'runtime')
    monkeypatch.setattr(scheduler, '_SCHEDULER_PATH', tmp_path / 'runtime' / 'scheduler.json')
    monkeypatch.setattr(scheduler, '_PROCESSES', {})
    monkeypatch.setattr(scheduler, '_PROCESS_META', {})
    monkeypatch.setattr(scheduler, '_LEASES', {})
    monkeypatch.setattr(scheduler, '_spawn_worker', lambda platform, config: Process())
    monkeypatch.setattr(readiness, 'require_database_ready', lambda: None)
    monkeypatch.setattr(frequency, 'legacy_migration_required', lambda platform: False)

    app = FastAPI()
    app.include_router(collection.router)
    response = TestClient(app).post('/collection/runtime/start', json={})
    assert response.status_code == 200
    assert response.json()['code'] == 0
    assert set(response.json()['data']['platforms']) == {'boss', 'zhaopin', 'liepin'}
    scheduler.stop()


def _all_restricted_runtime(tmp_path, monkeypatch, scheduler_data):
    state_root = tmp_path / 'runtime'
    monkeypatch.setattr(scheduler, '_STATE_ROOT', state_root)
    monkeypatch.setattr(scheduler, '_SCHEDULER_PATH', state_root / 'scheduler.json')
    monkeypatch.setattr(scheduler, '_PROCESSES', {})
    monkeypatch.setattr(scheduler, '_PROCESS_META', {})
    monkeypatch.setattr(scheduler, '_LEASES', {})
    statuses = {'boss': 'blocked', 'zhaopin': 'needs_login', 'liepin': 'failed'}
    for platform, status in statuses.items():
        state.save_state(state.RuntimeState(
            platform=platform, status=status, keyword_index=1, city_index=2, page=3,
            last_saved_identity=f'{platform}://saved', stats={'inserted': 2},
            stop_reason=f'{platform}_manual', updated_at=1000,
        ), root=state_root)
        state.request_stop(platform, root=state_root)
    scheduler._SCHEDULER_PATH.parent.mkdir(parents=True, exist_ok=True)
    scheduler._SCHEDULER_PATH.write_text(scheduler_data, encoding='utf-8')
    return statuses


@pytest.mark.parametrize('scheduler_data', ['{"stopped_at": 900}', '{"config":'])
def test_asgi_reset_all_restricted_checkpoint_is_local_then_resume_is_reachable(
    tmp_path, monkeypatch, scheduler_data,
):
    statuses = _all_restricted_runtime(tmp_path, monkeypatch, scheduler_data)
    spawned = []
    preflight = []

    class Process:
        pid = 54321
        returncode = None
        def poll(self): return self.returncode
        def wait(self, timeout=None): return self.returncode
        def terminate(self): self.returncode = 0

    monkeypatch.setattr(scheduler, '_spawn_worker', lambda platform, config: spawned.append(platform) or Process())
    monkeypatch.setattr(scheduler.readiness, 'require_database_ready', lambda: preflight.append('database'))
    monkeypatch.setattr(frequency, 'legacy_migration_required', lambda platform: False)
    app = FastAPI()
    from app.middleware import register_exception_handlers
    register_exception_handlers(app)
    app.include_router(collection.router)

    with TestClient(app) as client:
        reset = client.post('/collection/runtime/start', json={'reset_checkpoint': True})
        assert reset.status_code == 200
        assert reset.json()['code'] == 0
        assert spawned == []
        assert preflight == []
        for platform, status in statuses.items():
            value = state.load_state(platform, root=scheduler._STATE_ROOT)
            assert value.status == status
            assert value.stop_reason == f'{platform}_manual'
            assert (value.keyword_index, value.city_index, value.page) == (0, 0, 1)
            assert value.last_saved_identity is None
            assert value.stats == {}
            assert state.stop_requested(platform, root=scheduler._STATE_ROOT)

        restored = client.post('/collection/runtime/resume/boss', json={'confirmed': True})

    assert restored.status_code == 200
    assert restored.json()['code'] == 0
    assert spawned == ['boss']
    assert state.load_state('boss', root=scheduler._STATE_ROOT).status == 'waiting'
    assert not state.stop_requested('boss', root=scheduler._STATE_ROOT)
    assert state.stop_requested('zhaopin', root=scheduler._STATE_ROOT)
    assert state.stop_requested('liepin', root=scheduler._STATE_ROOT)


@pytest.mark.parametrize('scheduler_data', ['{"stopped_at": 900}', '{"config":'])
def test_asgi_all_restricted_still_requires_explicit_reset_before_resume(
    tmp_path, monkeypatch, scheduler_data,
):
    statuses = _all_restricted_runtime(tmp_path, monkeypatch, scheduler_data)
    spawned = []
    monkeypatch.setattr(scheduler, '_spawn_worker', lambda platform, config: spawned.append(platform))
    monkeypatch.setattr(frequency, 'legacy_migration_required', lambda platform: False)
    app = FastAPI()
    from app.middleware import register_exception_handlers
    register_exception_handlers(app)
    app.include_router(collection.router)

    with TestClient(app) as client:
        start = client.post('/collection/runtime/start', json={})
        resume = client.post('/collection/runtime/resume/boss', json={'confirmed': True})

    assert start.status_code == 200 and start.json()['code'] != 0
    assert resume.status_code == 200 and resume.json()['code'] != 0
    assert spawned == []
    for platform, status in statuses.items():
        value = state.load_state(platform, root=scheduler._STATE_ROOT)
        assert value.status == status
        assert value.stop_reason == f'{platform}_manual'
        assert (value.keyword_index, value.city_index, value.page) == (1, 2, 3)
        assert state.stop_requested(platform, root=scheduler._STATE_ROOT)


def test_asgi_local_reset_refuses_a_live_runtime_lease_without_changing_gates(tmp_path, monkeypatch):
    statuses = _all_restricted_runtime(tmp_path, monkeypatch, '{"stopped_at": 900}')
    spawned = []
    from app.collect.runtime import lease
    monkeypatch.setattr(lease, '_pid_alive', lambda pid, created_at: True)
    held = lease.acquire('boss', 'scheduler:test', 'runtime', root=scheduler._STATE_ROOT, pid=900, created_at=1)
    lease.rebind(held, 901, 2, owner='worker:901:test')
    monkeypatch.setattr(scheduler, '_spawn_worker', lambda platform, config: spawned.append(platform))
    app = FastAPI()
    from app.middleware import register_exception_handlers
    register_exception_handlers(app)
    app.include_router(collection.router)

    response = TestClient(app).post('/collection/runtime/start', json={'reset_checkpoint': True})

    assert response.status_code == 200 and response.json()['code'] != 0
    assert spawned == []
    for platform, status in statuses.items():
        value = state.load_state(platform, root=scheduler._STATE_ROOT)
        assert value.status == status
        assert (value.keyword_index, value.city_index, value.page) == (1, 2, 3)
        assert state.stop_requested(platform, root=scheduler._STATE_ROOT)
    assert lease.status('boss', root=scheduler._STATE_ROOT) is not None

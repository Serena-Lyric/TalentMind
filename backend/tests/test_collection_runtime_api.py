"""Runtime API is a thin wrapper over the isolated scheduler."""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.collect import frequency, readiness
from app.collect.runtime import scheduler
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

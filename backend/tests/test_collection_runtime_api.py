"""Runtime API is a thin wrapper over the isolated scheduler."""
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

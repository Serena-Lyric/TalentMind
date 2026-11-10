"""Cross-process writer lease tests; only temporary files."""
import json
import multiprocessing
import os

import pytest

from app.collect.runtime import lease


def test_second_owner_is_blocked_and_release_allows_reacquire(tmp_path, monkeypatch):
    monkeypatch.setattr(lease, '_pid_alive', lambda pid, created_at: True)
    first = lease.acquire('boss', 'scheduler:test', 'runtime', root=tmp_path, pid=100, created_at=123)
    with pytest.raises(lease.WriterBusy, match='collection_writer_busy:boss:runtime'):
        lease.acquire('boss', 'control:test', 'single', root=tmp_path, pid=101, created_at=124)
    first.release()
    second = lease.acquire('boss', 'control:test', 'single', root=tmp_path, pid=101, created_at=124)
    second.release()


def test_different_platforms_do_not_block_each_other(tmp_path, monkeypatch):
    monkeypatch.setattr(lease, '_pid_alive', lambda pid, created_at: True)
    boss = lease.acquire('boss', 'boss-owner', 'runtime', root=tmp_path, pid=100, created_at=1)
    zhaopin = lease.acquire('zhaopin', 'zhaopin-owner', 'runtime', root=tmp_path, pid=101, created_at=2)
    assert lease.status('boss', root=tmp_path)['owner'] == 'boss-owner'
    assert lease.status('zhaopin', root=tmp_path)['owner'] == 'zhaopin-owner'
    boss.release(); zhaopin.release()


def test_stale_lock_is_reclaimed(tmp_path, monkeypatch):
    path = lease.lock_path('boss', root=tmp_path)
    path.mkdir(parents=True)
    (path / 'owner.json').write_text(json.dumps({'platform': 'boss', 'owner': 'dead', 'kind': 'runtime', 'pid': 999999, 'created_at': 1}), encoding='utf-8')
    monkeypatch.setattr(lease, '_pid_alive', lambda pid, created_at: pid == 100)
    acquired = lease.acquire('boss', 'new-owner', 'runtime', root=tmp_path, pid=100, created_at=2)
    assert acquired.owner == 'new-owner'
    assert lease.status('boss', root=tmp_path)['owner'] == 'new-owner'
    acquired.release()


def test_incomplete_lock_record_fails_closed_and_is_not_deleted(tmp_path):
    path = lease.lock_path('boss', root=tmp_path)
    path.mkdir(parents=True)
    with pytest.raises(lease.WriterStateError, match='state_unknown'):
        lease.acquire('boss', 'new-owner', 'runtime', root=tmp_path, pid=100, created_at=2)
    assert path.exists()
    assert not (path / 'owner.json').exists()


def test_rebind_moves_owner_to_worker_pid(tmp_path, monkeypatch):
    monkeypatch.setattr(lease, '_pid_alive', lambda pid, created_at: True)
    held = lease.acquire('boss', 'launcher', 'runtime', root=tmp_path, pid=100, created_at=1)
    lease.rebind(held, 200, 2, owner='worker:200')
    record = lease.status('boss', root=tmp_path)
    assert record['owner'] == 'worker:200'
    assert record['pid'] == 200
    held.release()
    assert lease.status('boss', root=tmp_path) is None


def _race_worker(root, start, finish, results):
    from app.collect.runtime import lease
    held = None
    start.wait(timeout=15)
    try:
        try:
            held = lease.acquire('boss', f'process:{os.getpid()}', 'runtime', root=root)
            results.put('ok')
        except (lease.WriterBusy, lease.WriterStateError):
            results.put('blocked')
        finish.wait(timeout=15)
    finally:
        if held is not None:
            held.release()


def test_two_processes_cannot_both_publish_writer_lock(tmp_path):
    context = multiprocessing.get_context('spawn')
    start = context.Barrier(2)
    finish = context.Barrier(2)
    results = context.Queue()
    processes = [context.Process(target=_race_worker, args=(tmp_path, start, finish, results)) for _ in range(2)]
    for process in processes:
        process.start()
    outcomes = [results.get(timeout=20) for _ in processes]
    for process in processes:
        process.join(timeout=20)
    assert outcomes.count('ok') == 1
    assert outcomes.count('blocked') == 1
    assert all(process.exitcode == 0 for process in processes)
    assert lease.status('boss', root=tmp_path) is None

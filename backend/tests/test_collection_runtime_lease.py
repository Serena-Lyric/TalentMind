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


def test_stale_release_cannot_remove_a_new_owner(tmp_path, monkeypatch):
    path = lease.lock_path('boss', root=tmp_path)
    path.mkdir(parents=True)
    (path / 'owner.json').write_text(json.dumps({
        'platform': 'boss', 'owner': 'dead', 'kind': 'runtime', 'pid': 999999, 'created_at': 1,
    }), encoding='utf-8')
    monkeypatch.setattr(lease, '_pid_alive', lambda pid, created_at: pid == 100)

    stale = lease.Lease('boss', 'dead', 'runtime', path, 999999, 1)
    assert lease.release_if_dead('boss', root=tmp_path) is True
    current = lease.acquire('boss', 'current', 'runtime', root=tmp_path, pid=100, created_at=2)

    stale.release()

    assert lease.release_if_dead('boss', root=tmp_path) is False
    assert lease.status('boss', root=tmp_path)['owner'] == 'current'
    current.release()


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


def _stale_race_worker(root, owner, started, stale_read, allow_stale_read, finish, results):
    from app.collect.runtime import lease
    original_read = lease._read_owner
    paused = False

    def read_owner(lock_dir):
        nonlocal paused
        value = original_read(lock_dir)
        if not paused and value and value.get('owner') == 'dead':
            paused = True
            stale_read.set()
            allow_stale_read.wait(timeout=20)
        return value

    lease._read_owner = read_owner
    held = None
    started.set()
    try:
        held = lease.acquire('boss', owner, 'runtime', root=root)
        results.put((owner, 'acquired'))
        finish.wait(timeout=20)
    except (lease.WriterBusy, lease.WriterStateError):
        results.put((owner, 'blocked'))
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


def test_two_processes_cannot_reclaim_the_same_stale_writer_lock(tmp_path):
    context = multiprocessing.get_context('spawn')
    path = lease.lock_path('boss', root=tmp_path)
    path.mkdir(parents=True)
    (path / 'owner.json').write_text(json.dumps({
        'platform': 'boss', 'owner': 'dead', 'kind': 'runtime', 'pid': 999999, 'created_at': 1,
    }), encoding='utf-8')
    started_a, started_b = context.Event(), context.Event()
    stale_read_a, stale_read_b = context.Event(), context.Event()
    allow_a, allow_b, finish = context.Event(), context.Event(), context.Event()
    results = context.Queue()
    first = context.Process(target=_stale_race_worker, args=(
        tmp_path, 'process-a', started_a, stale_read_a, allow_a, finish, results,
    ))
    first.start()
    second = None
    try:
        assert stale_read_a.wait(timeout=15)
        second = context.Process(target=_stale_race_worker, args=(
            tmp_path, 'process-b', started_b, stale_read_b, allow_b, finish, results,
        ))
        second.start()
        assert started_b.wait(timeout=15)
        saw_old_owner_before_a_reclaimed = stale_read_b.wait(timeout=2)

        allow_a.set()
        outcomes = [results.get(timeout=20)]
        allow_b.set()
        outcomes.append(results.get(timeout=20))
        finish.set()
        first.join(timeout=20)
        second.join(timeout=20)

        assert not saw_old_owner_before_a_reclaimed
        assert dict(outcomes) == {'process-a': 'acquired', 'process-b': 'blocked'}
        assert first.exitcode == 0
        assert second.exitcode == 0
    finally:
        allow_a.set()
        allow_b.set()
        finish.set()
        for process in (first, second):
            if process is not None and process.is_alive():
                process.terminate()
            if process is not None:
                process.join(timeout=5)

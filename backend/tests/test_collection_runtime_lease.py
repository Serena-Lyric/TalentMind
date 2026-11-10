"""Cross-process writer lease tests; only temporary files."""
import json

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
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({'platform': 'boss', 'owner': 'dead', 'kind': 'runtime', 'pid': 999999, 'created_at': 1}), encoding='utf-8')
    monkeypatch.setattr(lease, '_pid_alive', lambda pid, created_at: pid == 100)
    acquired = lease.acquire('boss', 'new-owner', 'runtime', root=tmp_path, pid=100, created_at=2)
    assert acquired.owner == 'new-owner'
    assert lease.status('boss', root=tmp_path)['owner'] == 'new-owner'
    acquired.release()

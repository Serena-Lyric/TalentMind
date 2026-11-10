"""Cross-process, per-platform writer leases for collection entrypoints."""
from __future__ import annotations

import json
import os
import shutil
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.collect.runtime import state

_KINDS = frozenset({'runtime', 'single', 'batch', 'bridge'})
_now = time.time


class WriterBusy(RuntimeError):
    def __init__(self, platform: str, owner: dict[str, Any] | None = None):
        self.platform = platform
        self.owner = owner or {}
        super().__init__(f'collection_writer_busy:{platform}:{self.owner.get("kind") or "unknown"}')


class WriterStateError(RuntimeError):
    """The lock exists but its owner record is incomplete or unverifiable."""


@dataclass
class Lease:
    platform: str
    owner: str
    kind: str
    path: Path
    pid: int
    created_at: int | None

    def release(self) -> None:
        release(self)


def lock_path(platform: str, root: Path | str | None = None) -> Path:
    return state.stop_path(platform, root=root).parent / 'writer.lock'


def _owner_path(lock_dir: Path) -> Path:
    return lock_dir / 'owner.json'


def _pid_alive(pid: int, created_at: int | None) -> bool:
    from app.collect.runtime import scheduler
    return scheduler._pid_alive(pid, created_at)


def _created_at(pid: int) -> int | None:
    from app.collect.runtime import scheduler
    return scheduler._process_creation_time(pid)


def _read_owner(lock_dir: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(_owner_path(lock_dir).read_text(encoding='utf-8'))
        return value if isinstance(value, dict) else None
    except (OSError, ValueError, json.JSONDecodeError):
        return None


def _write_owner(lock_dir: Path, payload: dict[str, Any]) -> None:
    temporary = lock_dir / f'owner.{uuid.uuid4().hex}.tmp'
    try:
        with temporary.open('wb') as stream:
            stream.write(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode('utf-8'))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, _owner_path(lock_dir))
    finally:
        temporary.unlink(missing_ok=True)


def _payload(platform: str, owner: str, kind: str, pid: int, created_at: int | None) -> dict[str, Any]:
    return {
        'platform': platform,
        'owner': owner,
        'kind': kind,
        'pid': pid,
        'created_at': created_at,
        'acquired_at': _now(),
    }


def status(platform: str, root: Path | str | None = None) -> dict[str, Any] | None:
    lock_dir = lock_path(platform, root=root)
    value = _read_owner(lock_dir)
    if value is None:
        return None
    pid = value.get('pid')
    created_at = value.get('created_at')
    if type(pid) is not int or not _pid_alive(pid, created_at):
        return None
    return value


def _reclaim_stale(lock_dir: Path) -> None:
    stale = lock_dir.with_name(f'writer.lock.stale-{uuid.uuid4().hex}')
    try:
        os.replace(lock_dir, stale)
    except FileNotFoundError:
        return
    except OSError:
        # Another process may have reclaimed it first; retry acquisition.
        return
    shutil.rmtree(stale, ignore_errors=True)


def acquire(
    platform: str,
    owner: str,
    kind: str,
    *,
    root: Path | str | None = None,
    pid: int | None = None,
    created_at: int | None = None,
) -> Lease:
    state.stop_path(platform, root=root)  # validate platform/root
    if kind not in _KINDS:
        raise ValueError('unsupported collection writer kind')
    if not isinstance(owner, str) or not owner.strip():
        raise ValueError('collection writer owner required')
    lock_dir = lock_path(platform, root=root)
    lock_dir.parent.mkdir(parents=True, exist_ok=True)
    pid = os.getpid() if pid is None else int(pid)
    created_at = _created_at(pid) if created_at is None else created_at
    payload = _payload(platform, owner, kind, pid, created_at)
    for _ in range(4):
        try:
            os.mkdir(lock_dir)
        except FileExistsError:
            existing = _read_owner(lock_dir)
            if existing is None:
                # An owner file can be absent while another process is publishing
                # the lock. Never interpret that as stale; a damaged record needs
                # explicit investigation.
                raise WriterStateError(f'collection_writer_state_unknown:{platform}')
            existing_pid = existing.get('pid')
            existing_created = existing.get('created_at')
            if type(existing_pid) is int and _pid_alive(existing_pid, existing_created):
                raise WriterBusy(platform, existing)
            _reclaim_stale(lock_dir)
            continue
        try:
            _write_owner(lock_dir, payload)
        except BaseException:
            shutil.rmtree(lock_dir, ignore_errors=True)
            raise
        return Lease(platform, owner, kind, lock_dir, pid, created_at)
    raise WriterBusy(platform, _read_owner(lock_dir))


def rebind(lease: Lease, pid: int, created_at: int | None, *, owner: str | None = None) -> Lease:
    """Atomically move ownership from the launcher to the actual worker."""
    current = _read_owner(lease.path)
    if current is None or current.get('owner') != lease.owner:
        raise WriterStateError(f'collection_writer_owner_changed:{lease.platform}')
    new_owner = owner or f'worker:{pid}:{uuid.uuid4().hex}'
    payload = _payload(lease.platform, new_owner, lease.kind, int(pid), created_at)
    _write_owner(lease.path, payload)
    lease.owner = new_owner
    lease.pid = int(pid)
    lease.created_at = created_at
    return lease


def release(lease: Lease) -> None:
    current = _read_owner(lease.path)
    if current is None or current.get('owner') != lease.owner:
        return
    _reclaim_stale(lease.path)


def release_if_dead(platform: str, root: Path | str | None = None) -> bool:
    lock_dir = lock_path(platform, root=root)
    current = _read_owner(lock_dir)
    if current is None:
        return False
    pid = current.get('pid')
    if type(pid) is int and _pid_alive(pid, current.get('created_at')):
        return False
    _reclaim_stale(lock_dir)
    return True

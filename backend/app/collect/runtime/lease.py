"""Cross-process, per-platform writer leases for collection entrypoints."""
from __future__ import annotations

import errno
import json
import os
import shutil
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.collect import worker_process
from app.collect.runtime import state

_KINDS = frozenset({'runtime', 'single', 'batch', 'bridge'})
_OPERATION_MUTEX = threading.Lock()
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
    job_name: str | None = None

    def release(self) -> None:
        release(self)


def lock_path(platform: str, root: Path | str | None = None) -> Path:
    return state.stop_path(platform, root=root).parent / 'writer.lock'


def _owner_path(lock_dir: Path) -> Path:
    return lock_dir / 'owner.json'


@contextmanager
def _operation_lock(lock_dir: Path):
    """Serialize every lease mutation using an OS-owned lock on a stable sibling file."""
    with _OPERATION_MUTEX:
        guard_path = lock_dir.with_name(f'{lock_dir.name}.guard')
        guard_path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(guard_path, os.O_CREAT | os.O_RDWR, 0o600)
        locked = False
        try:
            if os.name == 'nt':
                import msvcrt
                if os.fstat(fd).st_size == 0:
                    os.write(fd, b'\0')
                deadline = time.monotonic() + 10
                while not locked:
                    try:
                        os.lseek(fd, 0, os.SEEK_SET)
                        msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                        locked = True
                    except OSError as exc:
                        lock_conflict = exc.errno in {
                            errno.EACCES, errno.EAGAIN, errno.EWOULDBLOCK,
                            getattr(errno, 'EDEADLK', -1),
                        } or getattr(exc, 'winerror', None) == 33
                        if not lock_conflict:
                            raise WriterStateError('collection_writer_guard_unavailable') from exc
                        if time.monotonic() >= deadline:
                            raise WriterStateError('collection_writer_guard_timeout') from exc
                        time.sleep(.01)
            else:
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_EX)
                locked = True
            yield
        finally:
            if locked:
                if os.name == 'nt':
                    import msvcrt
                    os.lseek(fd, 0, os.SEEK_SET)
                    msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)


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


def _payload(
    platform: str,
    owner: str,
    kind: str,
    pid: int,
    created_at: int | None,
    job_name: str | None = None,
) -> dict[str, Any]:
    value = {
        'platform': platform,
        'owner': owner,
        'kind': kind,
        'pid': pid,
        'created_at': created_at,
        'acquired_at': _now(),
    }
    if job_name:
        value['job_name'] = job_name
    return value


def _is_worker_owner(value: dict[str, Any]) -> bool:
    return str(value.get('owner') or '').startswith('worker:')


def _owner_tree_alive(value: dict[str, Any]) -> bool | None:
    pid = value.get('pid')
    if type(pid) is not int or pid <= 0:
        return None
    if _pid_alive(pid, value.get('created_at')):
        return True
    if os.name != 'nt' or not _is_worker_owner(value):
        return False
    job_name = value.get('job_name')
    if not isinstance(job_name, str) or not job_name:
        return None
    try:
        return worker_process.job_has_processes(job_name)
    except (OSError, ValueError):
        return None


def status(platform: str, root: Path | str | None = None) -> dict[str, Any] | None:
    lock_dir = lock_path(platform, root=root)
    value = _read_owner(lock_dir)
    if value is None:
        return None
    return value if _owner_tree_alive(value) is not False else None


def _reclaim_stale(lock_dir: Path, expected_owner: str) -> bool:
    current = _read_owner(lock_dir)
    if current is None or current.get('owner') != expected_owner:
        return False
    stale = lock_dir.with_name(f'writer.lock.stale-{uuid.uuid4().hex}')
    try:
        os.replace(lock_dir, stale)
    except FileNotFoundError:
        return False
    except OSError:
        # Another process may have reclaimed it first; retry acquisition.
        return False
    shutil.rmtree(stale, ignore_errors=True)
    return True


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
    with _operation_lock(lock_dir):
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
                existing_owner = existing.get('owner')
                if not isinstance(existing_owner, str) or not existing_owner:
                    raise WriterStateError(f'collection_writer_state_unknown:{platform}')
                existing_alive = _owner_tree_alive(existing)
                if existing_alive is True:
                    raise WriterBusy(platform, existing)
                if existing_alive is None:
                    raise WriterStateError(f'collection_writer_tree_unknown:{platform}')
                _reclaim_stale(lock_dir, existing_owner)
                continue
            try:
                _write_owner(lock_dir, payload)
            except BaseException:
                shutil.rmtree(lock_dir, ignore_errors=True)
                raise
            return Lease(platform, owner, kind, lock_dir, pid, created_at)
    raise WriterBusy(platform, _read_owner(lock_dir))


def rebind(
    lease: Lease,
    pid: int,
    created_at: int | None,
    *,
    owner: str | None = None,
    job_name: str | None = None,
) -> Lease:
    """Atomically move ownership from the launcher to the actual worker."""
    with _operation_lock(lease.path):
        current = _read_owner(lease.path)
        if current is None or current.get('owner') != lease.owner:
            raise WriterStateError(f'collection_writer_owner_changed:{lease.platform}')
        new_owner = owner or f'worker:{pid}:{uuid.uuid4().hex}'
        payload = _payload(lease.platform, new_owner, lease.kind, int(pid), created_at, job_name)
        _write_owner(lease.path, payload)
        lease.owner = new_owner
        lease.pid = int(pid)
        lease.created_at = created_at
        lease.job_name = job_name
        return lease


def release(lease: Lease) -> None:
    with _operation_lock(lease.path):
        current = _read_owner(lease.path)
        if current is None or current.get('owner') != lease.owner:
            return
        _reclaim_stale(lease.path, lease.owner)


def release_if_dead(platform: str, root: Path | str | None = None) -> bool:
    lock_dir = lock_path(platform, root=root)
    with _operation_lock(lock_dir):
        current = _read_owner(lock_dir)
        if current is None:
            return False
        if _owner_tree_alive(current) is not False:
            return False
        owner = current.get('owner')
        if not isinstance(owner, str) or not owner:
            return False
        return _reclaim_stale(lock_dir, owner)

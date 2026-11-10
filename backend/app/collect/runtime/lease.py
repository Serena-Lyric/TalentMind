"""Cross-process, per-platform writer leases for collection entrypoints."""
from __future__ import annotations

import json
import os
import time
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


def _pid_alive(pid: int, created_at: int | None) -> bool:
    from app.collect.runtime import scheduler
    return scheduler._pid_alive(pid, created_at)


def _created_at(pid: int) -> int | None:
    from app.collect.runtime import scheduler
    return scheduler._process_creation_time(pid)


def _read(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
        return value if isinstance(value, dict) else None
    except (OSError, ValueError, json.JSONDecodeError):
        return None


def status(platform: str, root: Path | str | None = None) -> dict[str, Any] | None:
    path = lock_path(platform, root=root)
    value = _read(path)
    if value is None:
        return None
    pid = value.get('pid')
    created_at = value.get('created_at')
    if type(pid) is not int or not _pid_alive(pid, created_at):
        return None
    return value


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
    path = lock_path(platform, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    pid = os.getpid() if pid is None else int(pid)
    created_at = _created_at(pid) if created_at is None else created_at
    payload = {
        'platform': platform,
        'owner': owner,
        'kind': kind,
        'pid': pid,
        'created_at': created_at,
        'acquired_at': _now(),
    }
    for _ in range(4):
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            existing = _read(path)
            if existing is None:
                path.unlink(missing_ok=True)
                continue
            existing_pid = existing.get('pid')
            existing_created = existing.get('created_at')
            if type(existing_pid) is int and _pid_alive(existing_pid, existing_created):
                raise WriterBusy(platform, existing)
            path.unlink(missing_ok=True)
            continue
        try:
            os.write(descriptor, json.dumps(payload, ensure_ascii=False, sort_keys=True).encode('utf-8'))
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        return Lease(platform, owner, kind, path, pid, created_at)
    raise WriterBusy(platform, _read(path))


def release(lease: Lease) -> None:
    path = lease.path
    existing = _read(path)
    if existing is None:
        return
    if existing.get('owner') == lease.owner:
        path.unlink(missing_ok=True)

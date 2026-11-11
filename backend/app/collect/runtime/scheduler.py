"""Start, stop and resume the three isolated platform worker processes."""
from __future__ import annotations

import ctypes
import json
import os
import signal
import subprocess
import sys
import threading
import time
import uuid
from ctypes import wintypes
from dataclasses import asdict
from pathlib import Path
from typing import Any

from app.collect import frequency, readiness, worker_process
from app.collect.runtime import lease, state
from app.collect.runtime.platforms import RuntimeConfig, config_from_payload, default_runtime_config, get_platform

_REPO_ROOT = Path(__file__).resolve().parents[4]
_BACKEND_ROOT = Path(__file__).resolve().parents[3]
_STATE_ROOT = _REPO_ROOT / 'data/local/collection/runtime'
_SCHEDULER_PATH = _STATE_ROOT / 'scheduler.json'
_PROCESSES: dict[str, subprocess.Popen] = {}
_PROCESS_META: dict[str, dict[str, int | str | None]] = {}
_LEASES: dict[str, lease.Lease] = {}
_LOCK = threading.RLock()
_clock = time.time
_MANUAL_RECOVERY_STATUSES = frozenset({'blocked', 'needs_login', 'failed'})
_KERNEL32 = ctypes.windll.kernel32 if os.name == 'nt' else None
if _KERNEL32 is not None:
    _KERNEL32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    _KERNEL32.OpenProcess.restype = wintypes.HANDLE
    _KERNEL32.GetProcessTimes.argtypes = [
        wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
    ]
    _KERNEL32.GetProcessTimes.restype = wintypes.BOOL
    _KERNEL32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    _KERNEL32.GetExitCodeProcess.restype = wintypes.BOOL
    _KERNEL32.CloseHandle.argtypes = [wintypes.HANDLE]
    _KERNEL32.CloseHandle.restype = wintypes.BOOL


def _config_dict(config: RuntimeConfig) -> dict[str, Any]:
    return asdict(config)


_CONFIG_KEYS = frozenset(_config_dict(default_runtime_config()))


def _stored_runtime_config(scheduler_data: dict[str, Any]) -> RuntimeConfig | None:
    value = scheduler_data.get('config')
    if not isinstance(value, dict) or frozenset(value) != _CONFIG_KEYS:
        return None
    try:
        config = config_from_payload(value)
        config.validate()
    except (TypeError, ValueError):
        return None
    return config


def _has_checkpoint(value: state.RuntimeState) -> bool:
    return bool(value.keyword_index or value.city_index or value.page != 1
                or value.last_saved_identity or value.stats)


class _FileTime(ctypes.Structure):
    _fields_ = [('dwLowDateTime', wintypes.DWORD), ('dwHighDateTime', wintypes.DWORD)]


def _process_creation_time(pid: int) -> int | None:
    if os.name != 'nt':
        return None
    handle = _KERNEL32.OpenProcess(0x1000, False, int(pid))
    if not handle:
        return None
    try:
        created = _FileTime()
        exited = _FileTime()
        kernel = _FileTime()
        user = _FileTime()
        if not _KERNEL32.GetProcessTimes(
            handle, ctypes.byref(created), ctypes.byref(exited), ctypes.byref(kernel), ctypes.byref(user),
        ):
            return None
        return (int(created.dwHighDateTime) << 32) | int(created.dwLowDateTime)
    finally:
        _KERNEL32.CloseHandle(handle)


def _pid_alive(pid: int, created_at: int | None = None) -> bool:
    if os.name != 'nt':
        try:
            os.kill(int(pid), 0)
            return True
        except OSError:
            return False
    handle = _KERNEL32.OpenProcess(0x1000, False, int(pid))
    if not handle:
        return False
    try:
        code = wintypes.DWORD()
        if not _KERNEL32.GetExitCodeProcess(handle, ctypes.byref(code)):
            return False
        if code.value != 259:
            return False
        return created_at is None or _process_creation_time(int(pid)) == created_at
    finally:
        _KERNEL32.CloseHandle(handle)


class _PidProcess:
    def __init__(self, pid: int, created_at: int | None, job=None):
        self.pid = pid
        self.created_at = created_at
        self._collection_job = job

    def poll(self):
        if _pid_alive(self.pid, self.created_at):
            return None
        job = self._collection_job
        if job is not None and job.handle and job.active_processes():
            return None
        return 0

    def wait(self, timeout=None):
        deadline = time.monotonic() + (timeout if timeout is not None else 0)
        while self.poll() is None:
            if timeout is not None and time.monotonic() >= deadline:
                raise subprocess.TimeoutExpired(str(self.pid), timeout)
            time.sleep(.1)
        return 0

    def terminate(self):
        if os.name == 'nt':
            worker_process.stop(self, timeout=5)
            return
        os.kill(self.pid, signal.SIGTERM)

    def kill(self):
        if os.name == 'nt':
            worker_process.stop(self, timeout=5)
            return
        os.kill(self.pid, signal.SIGTERM)


def _pid_process(platform: str, pid: int, created_at: int | None, job_name: str | None = None):
    job = None
    if os.name == 'nt' and job_name:
        try:
            job = worker_process.open_job(job_name)
        except (OSError, ValueError) as exc:
            if not isinstance(exc, OSError) or getattr(exc, 'winerror', None) != 2:
                raise RuntimeError('collection_worker_tree_unverifiable') from exc
        if job is not None:
            process = _PidProcess(pid, created_at, job)
            if process.poll() is None:
                return process
            worker_process.close(process)
    if _pid_alive(pid, created_at):
        return _PidProcess(pid, created_at)
    return None


def _restore_processes() -> None:
    data = _read_scheduler()
    for platform, value in (data.get('pids') or {}).items():
        if platform in _PROCESSES:
            continue
        if isinstance(value, dict):
            pid = value.get('pid')
            created_at = value.get('created_at')
            job_name = value.get('job_name')
        else:
            pid, created_at = value, None
            job_name = None
        if type(pid) is not int or pid <= 0:
            continue
        process = (_pid_process(platform, pid, created_at, job_name) if job_name
                   else _pid_process(platform, pid, created_at))
        if process is not None:
            _PROCESSES[platform] = process
            _PROCESS_META[platform] = {'pid': pid, 'created_at': created_at, 'job_name': job_name}


def _process_payload() -> dict[str, dict[str, int | str | None]]:
    result = {}
    for platform, process in _PROCESSES.items():
        meta = _PROCESS_META.get(platform) or {}
        job_name = getattr(getattr(process, '_collection_job', None), 'name', meta.get('job_name'))
        result[platform] = {
            'pid': int(process.pid),
            'created_at': meta.get('created_at', _process_creation_time(int(process.pid))),
        }
        if job_name:
            result[platform]['job_name'] = job_name
    return result




def _write_scheduler(payload: dict[str, Any]) -> None:
    _SCHEDULER_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp = _SCHEDULER_PATH.with_suffix('.tmp')
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(_SCHEDULER_PATH)


def _spawn_worker(platform: str, config: RuntimeConfig) -> subprocess.Popen:
    log_path = _STATE_ROOT / platform / 'worker.log'
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open('a', encoding='utf-8') as log_file:
        return worker_process.spawn(
            [sys.executable, '-m', 'app.collect.runtime.worker', '--platform', platform,
             '--config-json', json.dumps(_config_dict(config), ensure_ascii=False)],
            cwd=str(_BACKEND_ROOT), stdout=log_file, stderr=subprocess.STDOUT, text=True,
        )


def _bind_worker_lease(platform: str, process, held: lease.Lease) -> None:
    created_at = _process_creation_time(int(process.pid))
    job_name = getattr(getattr(process, '_collection_job', None), 'name', None)
    lease.rebind(
        held, int(process.pid), created_at,
        owner=f'worker:{process.pid}:{uuid.uuid4().hex}', job_name=job_name,
    )
    _PROCESS_META[platform] = {'pid': int(process.pid), 'created_at': created_at, 'job_name': job_name}


def _alive(process) -> bool:
    return process is not None and process.poll() is None


def _stop_process(process) -> None:
    if process is None:
        return
    job = getattr(process, '_collection_job', None)
    if (job is not None and hasattr(job, 'member_handles')
            or os.name == 'nt' and isinstance(process, _PidProcess)):
        try:
            worker_process.stop(process, timeout=5)
        except BaseException as exc:
            raise RuntimeError('collection_worker_termination_unknown') from exc
        if process.poll() is None:
            raise RuntimeError('collection_worker_termination_unknown')
        worker_process.close(process)
        return
    try:
        process.wait(timeout=3)
    except (subprocess.TimeoutExpired, AttributeError):
        pass
    if process.poll() is None:
        try:
            process.terminate()
            process.wait(timeout=2)
        except (subprocess.TimeoutExpired, OSError, AttributeError):
            try:
                process.kill()
            except (OSError, AttributeError):
                pass
    deadline = time.monotonic() + 3
    while process.poll() is None and time.monotonic() < deadline:
        time.sleep(.05)
    if process.poll() is None:
        raise RuntimeError('collection_worker_termination_unknown')


def _state_for(platform: str) -> state.RuntimeState:
    value = state.load_state(platform, root=_STATE_ROOT)
    process = _PROCESSES.get(platform)
    if process is not None and process.poll() is not None and value.status in {'running', 'waiting'}:
        value.status = 'failed'
        value.stop_reason = 'worker_exited'
        value.next_run_at = None
        value.updated_at = _clock()
        state.save_state(value, root=_STATE_ROOT)
        _PROCESSES.pop(platform, None)
        lease.release_if_dead(platform, root=_STATE_ROOT)
    return value


def status() -> dict[str, Any]:
    with _LOCK:
        _restore_processes()
        platforms = {platform: _state_for(platform).to_dict() for platform in ('boss', 'zhaopin', 'liepin')}
        running = any(item['status'] in {'running', 'waiting'} for item in platforms.values())
        attention = any(item['status'] in {'needs_login', 'blocked', 'failed'} for item in platforms.values())
        top = 'running' if running else 'attention' if attention else 'stopped'
        return {'status': top, 'platforms': platforms, 'scheduler_path': str(_SCHEDULER_PATH),
                'writers': {platform: lease.status(platform, root=_STATE_ROOT) for platform in ('boss', 'zhaopin', 'liepin')}}


def start(payload: RuntimeConfig | dict[str, Any] | None = None) -> dict[str, Any]:
    raw_payload = dict(payload) if isinstance(payload, dict) else payload
    reset_checkpoint = bool(raw_payload.get('reset_checkpoint')) if isinstance(raw_payload, dict) else False
    if isinstance(raw_payload, dict):
        raw_payload.pop('reset_checkpoint', None)
    scheduler_data = _read_scheduler()
    stored_config = _stored_runtime_config(scheduler_data)
    empty_payload = raw_payload is None or raw_payload == {}
    config = stored_config if empty_payload and stored_config is not None else config_from_payload(raw_payload)
    config.validate()
    with _LOCK:
        existing = {platform: state.load_state(platform, root=_STATE_ROOT) for platform in ('boss', 'zhaopin', 'liepin')}
        platforms = ('boss', 'zhaopin', 'liepin')
        restricted = [platform for platform, value in existing.items()
                      if value.status in _MANUAL_RECOVERY_STATUSES]
        available = [platform for platform in platforms if platform not in restricted]
        for platform in restricted:
            state.request_stop(platform, root=_STATE_ROOT)
        _restore_processes()
        if reset_checkpoint:
            active_processes = [platform for platform, process in _PROCESSES.items() if _alive(process)]
            active_states = [platform for platform, value in existing.items()
                             if value.status in {'running', 'waiting'}]
            if active_processes or active_states:
                active = ','.join(dict.fromkeys(active_processes + active_states))
                raise RuntimeError('collection_runtime_reset_requires_stopped_workers:' + active)
            for platform, process in list(_PROCESSES.items()):
                _PROCESSES.pop(platform, None)
                _PROCESS_META.pop(platform, None)

            reset_leases: list[lease.Lease] = []
            try:
                for platform in platforms:
                    reset_leases.append(lease.acquire(
                        platform, f'checkpoint-reset:{os.getpid()}:{platform}', 'runtime', root=_STATE_ROOT,
                    ))
                now = _clock()
                for platform, value in existing.items():
                    value.keyword_index = 0
                    value.city_index = 0
                    value.page = 1
                    value.next_run_at = None
                    value.last_saved_identity = None
                    value.last_success_at = None
                    value.stats = {}
                    value.updated_at = now
                    state.save_state(value, root=_STATE_ROOT)
                    _LEASES.pop(platform, None)
                scheduler_data = _read_scheduler()
                scheduler_data['config'] = _config_dict(config)
                scheduler_data['pids'] = {}
                scheduler_data['checkpoint_reset_at'] = now
                _write_scheduler(scheduler_data)
            finally:
                for held in reset_leases:
                    held.release()
            return status()
        if not available:
            raise RuntimeError('collection_runtime_manual_recovery_required:' + ','.join(restricted))
        active = [platform for platform, process in _PROCESSES.items() if _alive(process)]
        if any(platform not in restricted for platform in active):
            raise RuntimeError('collection_runtime_already_running')
        for platform in available:
            if frequency.legacy_migration_required(platform):
                raise RuntimeError(f'collection_legacy_migration_required:{platform}')
        has_checkpoint = any(_has_checkpoint(value) for value in existing.values())
        if has_checkpoint and stored_config is None and not reset_checkpoint:
            raise RuntimeError('collection_runtime_plan_unavailable: explicit reset required')
        if stored_config is not None and config != stored_config and has_checkpoint and not reset_checkpoint:
            raise RuntimeError('collection_runtime_config_mismatch: explicit reset required')
        for platform, process in list(_PROCESSES.items()):
            if not _alive(process):
                _PROCESSES.pop(platform, None)
                _PROCESS_META.pop(platform, None)
        acquired: dict[str, lease.Lease] = {}
        spawned: dict[str, Any] = {}
        try:
            for platform in available:
                acquired[platform] = lease.acquire(
                    platform, f'scheduler:{os.getpid()}:{platform}', 'runtime', root=_STATE_ROOT,
                )
            readiness.require_database_ready()
            now = _clock()
            for platform in available:
                state.clear_stop(platform, root=_STATE_ROOT)
                value = existing[platform]
                value.status = 'waiting'
                value.stop_reason = None
                value.next_run_at = value.next_run_at if value.next_run_at is not None else now
                value.updated_at = now
                state.save_state(value, root=_STATE_ROOT)
                process = _spawn_worker(platform, config)
                spawned[platform] = process
                _bind_worker_lease(platform, process, acquired[platform])
            _LEASES.update(acquired)
            _PROCESSES.update(spawned)
            _write_scheduler({
                'started_at': now,
                'config': _config_dict(config),
                'pids': _process_payload(),
            })
            return status()
        except Exception:
            for process in spawned.values():
                _stop_process(process)
            for platform, item in acquired.items():
                item.release()
                _LEASES.pop(platform, None)
            for platform in available:
                _PROCESS_META.pop(platform, None)
            for platform in spawned:
                _PROCESSES.pop(platform, None)
            raise


def _unresolved_runtime_writer(platform: str, released: bool) -> dict[str, Any] | None:
    writer = lease.status(platform, root=_STATE_ROOT)
    if writer is not None:
        kind = writer.get('kind')
        return writer if kind == 'runtime' or kind not in {'single', 'batch', 'bridge'} else None
    if not released and lease.lock_path(platform, root=_STATE_ROOT).exists():
        return {}
    return None


def stop() -> dict[str, Any]:
    with _LOCK:
        for platform in ('boss', 'zhaopin', 'liepin'):
            state.request_stop(platform, root=_STATE_ROOT)
        _restore_processes()
        processes = dict(_PROCESSES)
        unresolved: dict[str, dict[str, Any]] = {}
        for platform, process in processes.items():
            _stop_process(process)
            if not _alive(process):
                _PROCESSES.pop(platform, None)
                _PROCESS_META.pop(platform, None)
            released = lease.release_if_dead(platform, root=_STATE_ROOT)
            writer = _unresolved_runtime_writer(platform, released)
            value = state.load_state(platform, root=_STATE_ROOT)
            if writer is not None:
                unresolved[platform] = writer
                if value.status not in _MANUAL_RECOVERY_STATUSES:
                    value.status = 'failed'
                    value.stop_reason = 'worker_termination_unconfirmed'
                    value.next_run_at = None
            elif value.status not in _MANUAL_RECOVERY_STATUSES:
                value.status = 'stopped'
                value.stop_reason = 'user_stopped'
            value.updated_at = _clock()
            state.save_state(value, root=_STATE_ROOT)
        for platform in ('boss', 'zhaopin', 'liepin'):
            if platform not in processes:
                released = lease.release_if_dead(platform, root=_STATE_ROOT)
                writer = _unresolved_runtime_writer(platform, released)
                value = state.load_state(platform, root=_STATE_ROOT)
                if writer is not None:
                    unresolved[platform] = writer
                    if value.status not in _MANUAL_RECOVERY_STATUSES:
                        value.status = 'failed'
                        value.stop_reason = 'worker_termination_unconfirmed'
                        value.next_run_at = None
                elif value.status not in _MANUAL_RECOVERY_STATUSES:
                    value.status = 'stopped'
                    value.stop_reason = 'user_stopped'
                value.updated_at = _clock()
                state.save_state(value, root=_STATE_ROOT)
        for platform in list(_LEASES):
            released = lease.release_if_dead(platform, root=_STATE_ROOT)
            writer = _unresolved_runtime_writer(platform, released)
            if writer is None:
                _LEASES.pop(platform, None)
            else:
                unresolved[platform] = writer
        _PROCESSES.clear()
        remaining_meta = {platform: meta for platform, meta in _PROCESS_META.items()
                          if platform in unresolved}
        _PROCESS_META.clear()
        _PROCESS_META.update(remaining_meta)
        scheduler_data = _read_scheduler()
        scheduler_data['stopped_at'] = _clock()
        old_pids = scheduler_data.get('pids') if isinstance(scheduler_data.get('pids'), dict) else {}
        pids = {platform: old_pids[platform] for platform in unresolved if platform in old_pids}
        for platform, writer in unresolved.items():
            owner = writer.get('owner')
            pid = writer.get('pid')
            if not isinstance(owner, str) or not owner.startswith('worker:') or type(pid) is not int:
                continue
            process = {'pid': pid, 'created_at': writer.get('created_at')}
            if writer.get('job_name'):
                process['job_name'] = writer['job_name']
            pids[platform] = process
        pids.update(_process_payload())
        scheduler_data['pids'] = pids
        _write_scheduler(scheduler_data)
        return status()


def resume(platform: str, confirmed: bool = False) -> dict[str, Any]:
    get_platform(platform)
    with _LOCK:
        value = state.load_state(platform, root=_STATE_ROOT)
        if value.status not in {'blocked', 'needs_login', 'failed'}:
            raise ValueError('collection_runtime_platform_not_waiting_for_manual_action')
        if value.status in {'blocked', 'failed'} and not confirmed:
            raise ValueError('manual_recovery_confirmation_required')
        state.request_stop(platform, root=_STATE_ROOT)
        _restore_processes()
        value = state.load_state(platform, root=_STATE_ROOT)
        scheduler_data = _read_scheduler()
        config = _stored_runtime_config(scheduler_data)
        has_checkpoint = any(
            _has_checkpoint(state.load_state(item, root=_STATE_ROOT))
            for item in ('boss', 'zhaopin', 'liepin')
        )
        if config is None and has_checkpoint:
            raise RuntimeError('collection_runtime_plan_unavailable: explicit reset required')
        if config is None:
            config = default_runtime_config()
        if frequency.legacy_migration_required(platform):
            raise RuntimeError(f'collection_legacy_migration_required:{platform}')
        process = _PROCESSES.get(platform)
        if process is not None:
            _stop_process(process)
            _PROCESSES.pop(platform, None)
            _PROCESS_META.pop(platform, None)
            held = _LEASES.pop(platform, None)
            if held is not None:
                held.release()
            else:
                lease.release_if_dead(platform, root=_STATE_ROOT)
            process = None
        acquired = lease.acquire(platform, f'scheduler:{os.getpid()}:{platform}', 'runtime', root=_STATE_ROOT)
        state.clear_stop(platform, root=_STATE_ROOT)
        delay = 15.0 if value.status == 'needs_login' else 30.0
        now = _clock()
        value.status = 'waiting'
        value.stop_reason = None
        value.next_run_at = now + delay
        value.updated_at = now
        state.save_state(value, root=_STATE_ROOT)
        try:
            process = _spawn_worker(platform, config)
            _bind_worker_lease(platform, process, acquired)
        except Exception:
            if process is not None:
                _stop_process(process)
            acquired.release()
            raise
        _LEASES[platform] = acquired
        _PROCESSES[platform] = process
        _PROCESS_META[platform] = {
            'pid': process.pid,
            'created_at': _process_creation_time(process.pid),
            'job_name': getattr(getattr(process, '_collection_job', None), 'name', None),
        }
        scheduler_data['config'] = _config_dict(config)
        scheduler_data['pids'] = _process_payload()
        _write_scheduler(scheduler_data)
        return status()


def _read_scheduler() -> dict[str, Any]:
    try:
        value = json.loads(_SCHEDULER_PATH.read_text(encoding='utf-8'))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError, json.JSONDecodeError):
        return {}

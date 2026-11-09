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
from ctypes import wintypes
from dataclasses import asdict
from pathlib import Path
from typing import Any

from app.collect import frequency, readiness
from app.collect.runtime import state
from app.collect.runtime.platforms import RuntimeConfig, config_from_payload, get_platform

_REPO_ROOT = Path(__file__).resolve().parents[4]
_BACKEND_ROOT = Path(__file__).resolve().parents[3]
_STATE_ROOT = _REPO_ROOT / 'data/local/collection/runtime'
_SCHEDULER_PATH = _STATE_ROOT / 'scheduler.json'
_PROCESSES: dict[str, subprocess.Popen] = {}
_PROCESS_META: dict[str, dict[str, int | None]] = {}
_LOCK = threading.RLock()
_clock = time.time


def _config_dict(config: RuntimeConfig) -> dict[str, Any]:
    return asdict(config)


class _FileTime(ctypes.Structure):
    _fields_ = [('dwLowDateTime', wintypes.DWORD), ('dwHighDateTime', wintypes.DWORD)]


def _process_creation_time(pid: int) -> int | None:
    if os.name != 'nt':
        return None
    handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, int(pid))
    if not handle:
        return None
    try:
        created = _FileTime()
        exited = _FileTime()
        kernel = _FileTime()
        user = _FileTime()
        if not ctypes.windll.kernel32.GetProcessTimes(
            handle, ctypes.byref(created), ctypes.byref(exited), ctypes.byref(kernel), ctypes.byref(user),
        ):
            return None
        return (int(created.dwHighDateTime) << 32) | int(created.dwLowDateTime)
    finally:
        ctypes.windll.kernel32.CloseHandle(handle)


def _pid_alive(pid: int, created_at: int | None = None) -> bool:
    if os.name != 'nt':
        try:
            os.kill(int(pid), 0)
            return True
        except OSError:
            return False
    handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, int(pid))
    if not handle:
        return False
    try:
        code = wintypes.DWORD()
        if not ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
            return False
        if code.value != 259:
            return False
        return created_at is None or _process_creation_time(int(pid)) == created_at
    finally:
        ctypes.windll.kernel32.CloseHandle(handle)


class _PidProcess:
    def __init__(self, pid: int, created_at: int | None):
        self.pid = pid
        self.created_at = created_at

    def poll(self):
        return None if _pid_alive(self.pid, self.created_at) else 0

    def wait(self, timeout=None):
        deadline = time.monotonic() + (timeout if timeout is not None else 0)
        while self.poll() is None:
            if timeout is not None and time.monotonic() >= deadline:
                raise subprocess.TimeoutExpired(str(self.pid), timeout)
            time.sleep(.1)
        return 0

    def terminate(self):
        os.kill(self.pid, signal.SIGTERM)

    def kill(self):
        os.kill(self.pid, signal.SIGTERM)


def _pid_process(platform: str, pid: int, created_at: int | None):
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
        else:
            pid, created_at = value, None
        if type(pid) is not int or pid <= 0:
            continue
        process = _pid_process(platform, pid, created_at)
        if process is not None:
            _PROCESSES[platform] = process
            _PROCESS_META[platform] = {'pid': pid, 'created_at': created_at}


def _process_payload() -> dict[str, dict[str, int | None]]:
    result = {}
    for platform, process in _PROCESSES.items():
        meta = _PROCESS_META.get(platform) or {}
        result[platform] = {
            'pid': int(process.pid),
            'created_at': meta.get('created_at', _process_creation_time(int(process.pid))),
        }
    return result




def _write_scheduler(payload: dict[str, Any]) -> None:
    _SCHEDULER_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp = _SCHEDULER_PATH.with_suffix('.tmp')
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(_SCHEDULER_PATH)


def _spawn_worker(platform: str, config: RuntimeConfig) -> subprocess.Popen:
    log_path = _STATE_ROOT / platform / 'worker.log'
    log_path.parent.mkdir(parents=True, exist_ok=True)
    kwargs: dict[str, Any] = {
        'cwd': str(_BACKEND_ROOT),
        'stdout': log_path.open('a', encoding='utf-8'),
        'stderr': subprocess.STDOUT,
        'text': True,
    }
    if os.name == 'nt':
        kwargs['creationflags'] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs['start_new_session'] = True
    return subprocess.Popen(
        [sys.executable, '-m', 'app.collect.runtime.worker', '--platform', platform,
         '--config-json', json.dumps(_config_dict(config), ensure_ascii=False)],
        **kwargs,
    )


def _alive(process) -> bool:
    return process is not None and process.poll() is None


def _stop_process(process) -> None:
    if process is None:
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
    return value


def status() -> dict[str, Any]:
    with _LOCK:
        _restore_processes()
        platforms = {platform: _state_for(platform).to_dict() for platform in ('boss', 'zhaopin', 'liepin')}
        running = any(item['status'] in {'running', 'waiting'} for item in platforms.values())
        attention = any(item['status'] in {'needs_login', 'blocked', 'failed'} for item in platforms.values())
        top = 'running' if running else 'attention' if attention else 'stopped'
        return {'status': top, 'platforms': platforms, 'scheduler_path': str(_SCHEDULER_PATH)}


def start(payload: RuntimeConfig | dict[str, Any] | None = None) -> dict[str, Any]:
    config = config_from_payload(payload)
    config.validate()
    with _LOCK:
        _restore_processes()
        if any(_alive(process) for process in _PROCESSES.values()):
            raise RuntimeError('collection_runtime_already_running')
        for platform in ('boss', 'zhaopin', 'liepin'):
            if frequency.legacy_migration_required(platform):
                raise RuntimeError(f'collection_legacy_migration_required:{platform}')
        readiness.require_database_ready()
        now = _clock()
        spawned: dict[str, Any] = {}
        try:
            for platform in ('boss', 'zhaopin', 'liepin'):
                state.clear_stop(platform, root=_STATE_ROOT)
                state.save_state(
                    state.RuntimeState(platform=platform, status='waiting', next_run_at=now, updated_at=now),
                    root=_STATE_ROOT,
                )
                spawned[platform] = _spawn_worker(platform, config)
            _PROCESSES.update(spawned)
            _PROCESS_META.clear()
            for platform, process in spawned.items():
                _PROCESS_META[platform] = {'pid': process.pid, 'created_at': _process_creation_time(process.pid)}
            _write_scheduler({
                'started_at': now,
                'config': _config_dict(config),
                'pids': _process_payload(),
            })
            return status()
        except Exception:
            for process in spawned.values():
                _stop_process(process)
            _PROCESSES.clear()
            raise


def stop() -> dict[str, Any]:
    with _LOCK:
        _restore_processes()
        processes = dict(_PROCESSES)
        for platform in ('boss', 'zhaopin', 'liepin'):
            state.request_stop(platform, root=_STATE_ROOT)
        for platform, process in processes.items():
            _stop_process(process)
            value = state.load_state(platform, root=_STATE_ROOT)
            value.status = 'stopped'
            value.stop_reason = 'user_stopped'
            value.next_run_at = None
            value.updated_at = _clock()
            state.save_state(value, root=_STATE_ROOT)
        for platform in ('boss', 'zhaopin', 'liepin'):
            if platform not in processes:
                value = state.load_state(platform, root=_STATE_ROOT)
                value.status = 'stopped'
                value.next_run_at = None
                value.updated_at = _clock()
                state.save_state(value, root=_STATE_ROOT)
        _PROCESSES.clear()
        _PROCESS_META.clear()
        _write_scheduler({'stopped_at': _clock()})
        return status()


def resume(platform: str, confirmed: bool = False) -> dict[str, Any]:
    get_platform(platform)
    with _LOCK:
        _restore_processes()
        value = state.load_state(platform, root=_STATE_ROOT)
        if value.status not in {'blocked', 'needs_login'}:
            raise ValueError('collection_runtime_platform_not_waiting_for_manual_action')
        if value.status == 'blocked' and not confirmed:
            raise ValueError('blocked_resume_confirmation_required')
        if frequency.legacy_migration_required(platform):
            raise RuntimeError(f'collection_legacy_migration_required:{platform}')
        process = _PROCESSES.pop(platform, None)
        if process is not None:
            state.request_stop(platform, root=_STATE_ROOT)
            _stop_process(process)
        state.clear_stop(platform, root=_STATE_ROOT)
        delay = 30.0 if value.status == 'blocked' else 15.0
        now = _clock()
        value.status = 'waiting'
        value.stop_reason = None
        value.next_run_at = now + delay
        value.updated_at = now
        state.save_state(value, root=_STATE_ROOT)
        config = config_from_payload(
            (_read_scheduler().get('config') if _SCHEDULER_PATH.exists() else None)
        )
        process = _spawn_worker(platform, config)
        _PROCESSES[platform] = process
        _PROCESS_META[platform] = {'pid': process.pid, 'created_at': _process_creation_time(process.pid)}
        scheduler_data = _read_scheduler()
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

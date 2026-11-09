"""Start, stop and resume the three isolated platform worker processes."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
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
_LOCK = threading.RLock()
_clock = time.time


def _config_dict(config: RuntimeConfig) -> dict[str, Any]:
    return asdict(config)




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
        platforms = {platform: _state_for(platform).to_dict() for platform in ('boss', 'zhaopin', 'liepin')}
        running = any(item['status'] in {'running', 'waiting'} for item in platforms.values())
        attention = any(item['status'] in {'needs_login', 'blocked', 'failed'} for item in platforms.values())
        top = 'running' if running else 'attention' if attention else 'stopped'
        return {'status': top, 'platforms': platforms, 'scheduler_path': str(_SCHEDULER_PATH)}


def start(payload: RuntimeConfig | dict[str, Any] | None = None) -> dict[str, Any]:
    config = config_from_payload(payload)
    config.validate()
    with _LOCK:
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
            _write_scheduler({
                'started_at': now,
                'config': _config_dict(config),
                'pids': {platform: process.pid for platform, process in spawned.items()},
            })
            return status()
        except Exception:
            for process in spawned.values():
                _stop_process(process)
            _PROCESSES.clear()
            raise


def stop() -> dict[str, Any]:
    with _LOCK:
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
        _write_scheduler({'stopped_at': _clock()})
        return status()


def resume(platform: str, confirmed: bool = False) -> dict[str, Any]:
    get_platform(platform)
    with _LOCK:
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
        _PROCESSES[platform] = _spawn_worker(platform, config)
        return status()


def _read_scheduler() -> dict[str, Any]:
    try:
        value = json.loads(_SCHEDULER_PATH.read_text(encoding='utf-8'))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError, json.JSONDecodeError):
        return {}

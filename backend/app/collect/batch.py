"""Bounded serial plans over the existing single-run controller.

Only an explicit start reserves the controller and prepares a browser. Runtime
plans stay under data/local; restart archives interruptions without resuming.
"""
from __future__ import annotations

import json
import logging
import random
import re
import threading
import uuid
from datetime import datetime, timedelta, timezone
from collections import deque
from pathlib import Path
from typing import Any

from app.collect import control

_STATE_DIR = Path(__file__).resolve().parents[3] / 'data' / 'local' / 'collection' / 'batches'
_LOCK = threading.RLock()
_ACTIVE_ID: str | None = None
_THREAD: threading.Thread | None = None
_STOP = threading.Event()
_ACTIVE = {'running', 'waiting_next_round', 'stopping'}
_COUNTERS = ('listed', 'detail_attempted', 'detail_obtained', 'complete', 'inserted',
             'updated', 'skipped', 'rejected', 'failed')
_GATES = ('login_required', 'verification_required', 'content_limited')


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds')


def _path(batch_id: str) -> Path:
    if not isinstance(batch_id, str) or not re.fullmatch(r'batch-[a-f0-9]{32}', batch_id):
        raise ValueError('无效 batch_id')
    return _STATE_DIR / (batch_id + '.json')


def _save(record: dict) -> None:
    path = _path(record['batch']['batch_id'])
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)


def _cancel_pending(value: dict, reason: str) -> None:
    for item in value['items']:
        if item['status'] == 'queued':
            item.update(status='cancelled', stop_reason=reason, finished_at=_now())


def _load(batch_id: str) -> dict:
    path = _path(batch_id)
    if not path.exists():
        raise ValueError('批次不存在')
    record = json.loads(path.read_text(encoding='utf-8'))
    value = record['batch']
    if value['status'] in _ACTIVE and batch_id != _ACTIVE_ID:
        value.update(status='interrupted', stop_reason='controller_restarted',
                     finished_at=_now(), next_run_at=None, current_item_id=None)
        for item in value['items']:
            if item['status'] in {'preparing', 'running'}:
                item.update(status='interrupted', stop_reason='controller_restarted', finished_at=_now())
        _cancel_pending(value, 'controller_restarted')
        _save(record)
    return record


def _copy(value: dict) -> dict:
    return json.loads(json.dumps(value))


def create_batch(payload: dict[str, Any]) -> dict:
    allowed = {'platform', 'keywords', 'cities', 'pages', 'max_jobs', 'detail_limit'}
    if not isinstance(payload, dict) or set(payload) - allowed:
        raise ValueError('未知批次字段')
    platform = payload.get('platform')
    spec = next((p for p in control.get_platforms() if p['platform'] == platform), None)
    if spec is None or not spec.get('supported'):
        raise ValueError('不支持的平台')
    keywords = payload.get('keywords')
    if not isinstance(keywords, list) or any(not isinstance(k, str) or not k.strip()
            or len(k.strip()) > 100 or ',' in k for k in keywords):
        raise ValueError('关键词必须是非空字符串列表，每项不超过100字符且不含逗号')
    keywords = list(dict.fromkeys(k.strip() for k in keywords))
    if not 1 <= len(keywords) <= 10:
        raise ValueError('关键词去重后须为1..10项')
    cities = payload.get('cities')
    if not isinstance(cities, list) or not cities or any(city not in spec['cities'] for city in cities):
        raise ValueError('城市及代码必须属于当前平台目录')
    cities = [dict(city) for i, city in enumerate(cities) if city not in cities[:i]]
    if len(keywords) * len(cities) > 50:
        raise ValueError('批次最多50个关键词和城市组合')
    limits = {key: payload.get(key, default) for key, default in
              (('pages', 1), ('max_jobs', 5), ('detail_limit', 5))}
    for key, upper in (('pages', 1), ('max_jobs', 5), ('detail_limit', 5)):
        if type(limits[key]) is not int or not 1 <= limits[key] <= upper:
            raise ValueError(f'{key} 必须为1..{upper}整数')
    batch_id = 'batch-' + uuid.uuid4().hex
    items = [dict(item_id=f'{batch_id}-{i + 1}', keyword=keyword, city=city,
                  status='queued', run_id=None, started_at=None, finished_at=None,
                  stop_reason=None, **dict.fromkeys(_COUNTERS))
             for i, (keyword, city) in enumerate((k, c) for k in keywords for c in cities)]
    value = dict(batch_id=batch_id, platform=platform, status='queued', created_at=_now(),
                 started_at=None, finished_at=None, stop_reason=None, total=len(items), completed=0,
                 current_item_id=None, next_run_at=None, items=items)
    with _LOCK:
        _save({'batch': value, 'limits': limits})
    return _copy(value)


def get_batch(batch_id: str) -> dict:
    with _LOCK:
        return _copy(_load(batch_id)['batch'])


def get_item_task(batch_id: str, item_id: str) -> dict:
    value = get_batch(batch_id)
    item = next((item for item in value['items'] if item['item_id'] == item_id), None)
    if item is None:
        raise ValueError('批次条目不存在')
    run_id = item['run_id']
    if not run_id:
        raise ValueError('条目尚未执行，没有任务日志')
    if not re.fullmatch(re.escape(value['platform']) + r'-[a-f0-9]{32}', run_id):
        raise ValueError('无效条目 run_id')
    directory = control._STATE_DIR.resolve()
    path = directory / (run_id + '.out.log')
    if path.resolve().parent != directory:
        raise ValueError('日志路径不属于采集运行目录')
    task = dict(run_id=run_id, platform=value['platform'], status=item['status'], mode='once',
                started_at=item['started_at'], finished_at=item['finished_at'],
                current_keyword=item['keyword'], current_city=item['city']['name'],
                stop_reason=item['stop_reason'], last_error=item['stop_reason'],
                details=item['detail_attempted'], new=item['inserted'],
                log_status='missing', raw_log_tail=[], **{key: item[key] for key in _COUNTERS})
    try:
        if path.exists():
            with path.open(encoding='utf-8', errors='replace') as stream:
                task['raw_log_tail'] = list(deque((line.rstrip('\r\n') for line in stream
                    if not line.strip().startswith('TM_EVENT ')), maxlen=30))
            task['log_status'] = 'parsed' if task['raw_log_tail'] else 'empty'
    except OSError:
        task['log_status'] = 'unavailable'
    return task


def list_batches() -> dict:
    with _LOCK:
        paths = sorted(_STATE_DIR.glob('batch-*.json'), key=lambda p: p.stat().st_mtime_ns, reverse=True)
        items = [_copy(_load(path.stem)['batch']) for path in paths]
        items.sort(key=lambda value: value['created_at'], reverse=True)
        return {'items': items, 'total': len(items)}


def start_batch(batch_id: str) -> dict:
    global _ACTIVE_ID, _THREAD, _STOP
    with _LOCK:
        record = _load(batch_id)
        value = record['batch']
        if value['status'] != 'queued' or _ACTIVE_ID is not None:
            raise RuntimeError('批次已启动或已有其他批次正在运行')
        reservation = control._reserve_tasks()
        try:
            config = control.get_config()
            _STOP = threading.Event()
            _ACTIVE_ID = batch_id
            value.update(status='running', started_at=_now())
            _save(record)
            _THREAD = threading.Thread(target=_run, args=(batch_id, reservation, config), daemon=True)
            _THREAD.start()
        except BaseException:
            _ACTIVE_ID = None
            control._release_tasks(reservation)
            raise
        return _copy(value)


def _update_item(item: dict, task: dict, *, finished: bool = False) -> None:
    item.update({key: task.get(key) for key in _COUNTERS})
    item['stop_reason'] = task.get('stop_reason')
    if not finished:
        item['status'] = 'running' if task.get('status') == 'running' else 'preparing'
        return
    gate = next((gate for gate in _GATES if any(gate in str(task.get(key) or '')
                for key in ('stop_reason', 'browser_page_status'))), None)
    item.update(status='blocked' if gate else 'stopped' if task.get('status') == 'stopped'
                else 'completed' if task.get('status') == 'completed' else 'error',
                finished_at=task.get('finished_at') or _now())


def _run(batch_id: str, reservation: object, config: dict) -> None:
    global _ACTIVE_ID
    run_id = None
    run_item_index = None
    error_reason = None
    try:
        with _LOCK:
            total = _load(batch_id)['batch']['total']
        for index in range(total):
            with _LOCK:
                record = _load(batch_id)
                value = record['batch']
                if _STOP.is_set():
                    break
                run_id = None
                run_item_index = index
                item = value['items'][index]
                value.update(status='running', current_item_id=item['item_id'], next_run_at=None)
                item.update(status='preparing', started_at=_now())
                _save(record)
                payload = dict(platform=value['platform'], keywords=[item['keyword']], cities=[item['city']],
                               mode='once', rounds=0, **record['limits'])
                try:
                    run_id = item['run_id'] = control.start_task(payload, _reservation=reservation)['run_id']
                except Exception as exc:
                    run_id = None
                    item.update(status='error', stop_reason=type(exc).__name__, finished_at=_now())
                _save(record)
            if run_id:
                while True:
                    done = control._wait_task_done(run_id, .2)
                    task = control._task_snapshot(run_id)
                    with _LOCK:
                        record = _load(batch_id)
                        item = record['batch']['items'][index]
                        _update_item(item, task, finished=done)
                        _save(record)
                    if done:
                        break
            with _LOCK:
                record = _load(batch_id)
                value = record['batch']
                item = value['items'][index]
                value['completed'] += 1
                value['current_item_id'] = None
                if item['status'] == 'blocked':
                    value.update(status='blocked', stop_reason=item['stop_reason'])
                    _cancel_pending(value, item['stop_reason'] or 'browser_blocked')
                    _save(record)
                    break
                if _STOP.is_set():
                    _save(record)
                    break
                if index + 1 < total:
                    delay = random.uniform(config['switch_interval_min'], config['switch_interval_max'])
                    value.update(status='waiting_next_round', next_run_at=(
                        datetime.now(timezone.utc).astimezone() + timedelta(seconds=delay)).isoformat(timespec='seconds'))
                else:
                    delay = 0
                    value['status'] = 'completed'
                _save(record)
            if _STOP.wait(delay):
                break
    except Exception as exc:
        error_reason = type(exc).__name__
    finally:
        # A failed file write must never release a still-running child to another task.
        archived = run_id is None
        try:
            if run_id:
                if not control._wait_task_done(run_id, 0):
                    try:
                        control.stop_task(run_id)
                    except RuntimeError:
                        pass
                    while not control._wait_task_done(run_id, .2):
                        pass
                archived = True
            with _LOCK:
                record = _load(batch_id)
                value = record['batch']
                if run_id:
                    item = value['items'][run_item_index]
                    item['run_id'] = run_id
                    if item['status'] in {'preparing', 'running'}:
                        _update_item(item, control._task_snapshot(run_id), finished=True)
                value['completed'] = sum(item['status'] in {'completed', 'error', 'blocked', 'stopped'}
                                         for item in value['items'])
                if error_reason:
                    value.update(status='error', stop_reason=error_reason)
                    _cancel_pending(value, error_reason)
                if _STOP.is_set():
                    value.update(status='stopped', stop_reason='user_stopped')
                    _cancel_pending(value, 'user_stopped')
                value.update(finished_at=_now(), next_run_at=None, current_item_id=None)
                _save(record)
        except Exception:
            logging.getLogger(__name__).exception('批次归档失败: %s', batch_id)
        finally:
            if archived:
                with _LOCK:
                    control._release_tasks(reservation)
                    _ACTIVE_ID = None


def stop_batch(batch_id: str) -> dict:
    with _LOCK:
        record = _load(batch_id)
        value = record['batch']
        if value['finished_at']:
            return _copy(value)
        if value['status'] == 'queued':
            _cancel_pending(value, 'user_stopped')
            value.update(status='stopped', stop_reason='user_stopped', finished_at=_now())
            _save(record)
            return _copy(value)
        if batch_id != _ACTIVE_ID:
            raise RuntimeError('没有可停止的活动批次')
        _STOP.set()
        value.update(status='stopping', stop_reason='user_stopped', next_run_at=None)
        _cancel_pending(value, 'user_stopped')
        run_id = next((item['run_id'] for item in value['items'] if item['item_id'] == value['current_item_id']), None)
        _save(record)
        thread = _THREAD
    if run_id and not control._wait_task_done(run_id, 0):
        control.stop_task(run_id)
    if thread:
        thread.join(timeout=1)
    return get_batch(batch_id)


def stop_active() -> dict | None:
    with _LOCK:
        batch_id = _ACTIVE_ID
    if batch_id is None:
        return None
    value = stop_batch(batch_id)
    return {'batch_id': batch_id, 'stopped': value['status'] == 'stopped', 'status': value['status']}

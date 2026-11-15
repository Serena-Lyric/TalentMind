"""Atomic per-platform runtime checkpoints and stop markers."""
from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

_PLATFORMS = frozenset({'boss', 'zhaopin', 'liepin'})
_STATUSES = frozenset({'idle', 'running', 'waiting', 'needs_login', 'blocked', 'failed', 'stopped'})
_REPO_ROOT = Path(__file__).resolve().parents[4]
_DEFAULT_ROOT = _REPO_ROOT / 'data/local/collection/runtime'


def _check_platform(platform: str) -> str:
    value = str(platform or '').strip()
    if value not in _PLATFORMS:
        raise ValueError('unsupported collection runtime platform')
    return value


def _root(root: Path | str | None) -> Path:
    return Path(root) if root is not None else _DEFAULT_ROOT


def state_path(platform: str, root: Path | str | None = None) -> Path:
    return _root(root) / _check_platform(platform) / 'state.sqlite3'


def stop_path(platform: str, root: Path | str | None = None) -> Path:
    return _root(root) / _check_platform(platform) / 'STOP'


@dataclass
class RuntimeState:
    platform: str
    status: str = 'idle'
    keyword_index: int = 0
    city_index: int = 0
    page: int = 1
    next_run_at: float | None = None
    last_saved_identity: str | None = None
    last_success_at: float | None = None
    stop_reason: str | None = None
    stats: dict[str, Any] = field(default_factory=dict)
    updated_at: float = field(default_factory=time.time)

    def validate(self) -> None:
        _check_platform(self.platform)
        if self.status not in _STATUSES:
            raise ValueError('invalid collection runtime status')
        if type(self.keyword_index) is not int or self.keyword_index < 0:
            raise ValueError('keyword_index must be a non-negative integer')
        if type(self.city_index) is not int or self.city_index < 0:
            raise ValueError('city_index must be a non-negative integer')
        if type(self.page) is not int or self.page < 1:
            raise ValueError('page must be a positive integer')
        for value, name in ((self.next_run_at, 'next_run_at'), (self.last_success_at, 'last_success_at'), (self.updated_at, 'updated_at')):
            if value is not None and (not isinstance(value, (int, float)) or value < 0):
                raise ValueError(f'{name} must be a non-negative number')
        if not isinstance(self.stats, dict):
            raise ValueError('stats must be an object')

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(path), timeout=5, isolation_level=None)
    connection.execute('PRAGMA synchronous=FULL')
    return connection


def _ensure_schema(connection: sqlite3.Connection) -> None:
    connection.execute('''CREATE TABLE IF NOT EXISTS runtime_state (
        platform TEXT PRIMARY KEY,
        status TEXT NOT NULL,
        keyword_index INTEGER NOT NULL,
        city_index INTEGER NOT NULL,
        page INTEGER NOT NULL,
        next_run_at REAL,
        last_saved_identity TEXT,
        last_success_at REAL,
        stop_reason TEXT,
        stats_json TEXT NOT NULL,
        updated_at REAL NOT NULL)''')


def load_state(platform: str, root: Path | str | None = None) -> RuntimeState:
    platform = _check_platform(platform)
    path = state_path(platform, root)
    if not path.exists():
        return RuntimeState(platform=platform)
    connection = None
    try:
        connection = _connect(path)
        _ensure_schema(connection)
        row = connection.execute(
            '''SELECT platform,status,keyword_index,city_index,page,next_run_at,
                      last_saved_identity,last_success_at,stop_reason,stats_json,updated_at
               FROM runtime_state WHERE platform=?''',
            (platform,),
        ).fetchone()
        if row is None:
            return RuntimeState(platform=platform)
        return RuntimeState(
            platform=row[0], status=row[1], keyword_index=row[2], city_index=row[3], page=row[4],
            next_run_at=row[5], last_saved_identity=row[6], last_success_at=row[7],
            stop_reason=row[8], stats=json.loads(row[9] or '{}'), updated_at=row[10],
        )
    except (sqlite3.Error, ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError('collection_runtime_state_unavailable') from exc
    finally:
        if connection is not None:
            connection.close()


def save_state(value: RuntimeState, root: Path | str | None = None) -> None:
    value.validate()
    path = state_path(value.platform, root)
    connection = None
    try:
        connection = _connect(path)
        connection.execute('BEGIN IMMEDIATE')
        _ensure_schema(connection)
        connection.execute(
            '''INSERT INTO runtime_state
               (platform,status,keyword_index,city_index,page,next_run_at,last_saved_identity,
                last_success_at,stop_reason,stats_json,updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(platform) DO UPDATE SET
                 status=excluded.status, keyword_index=excluded.keyword_index,
                 city_index=excluded.city_index, page=excluded.page,
                 next_run_at=excluded.next_run_at, last_saved_identity=excluded.last_saved_identity,
                 last_success_at=excluded.last_success_at, stop_reason=excluded.stop_reason,
                 stats_json=excluded.stats_json, updated_at=excluded.updated_at''',
            (
                value.platform, value.status, value.keyword_index, value.city_index, value.page,
                value.next_run_at, value.last_saved_identity, value.last_success_at,
                value.stop_reason, json.dumps(value.stats, ensure_ascii=False, sort_keys=True),
                value.updated_at,
            ),
        )
        connection.commit()
    except sqlite3.Error as exc:
        if connection is not None and connection.in_transaction:
            connection.rollback()
        raise RuntimeError('collection_runtime_state_unavailable') from exc
    finally:
        if connection is not None:
            connection.close()


def request_stop(platform: str, root: Path | str | None = None) -> None:
    path = stop_path(platform, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text('stop\n', encoding='ascii')
    temp.replace(path)


def stop_requested(platform: str, root: Path | str | None = None) -> bool:
    return stop_path(platform, root).exists()


def clear_stop(platform: str, root: Path | str | None = None) -> None:
    stop_path(platform, root).unlink(missing_ok=True)

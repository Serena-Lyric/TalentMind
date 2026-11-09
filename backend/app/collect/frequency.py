"""Non-optional, cross-entry timing limits for Chinese recruitment collection.

Reservations are committed before browser activity. The private SQLite ledger is
shared across processes/restarts; caller delays may slow collection, never relax it.
"""
from __future__ import annotations

import math
import random
import sqlite3
import secrets
import time
from contextlib import closing
from pathlib import Path

PAGE_DELAY_MIN = 15.0
PAGE_DELAY_MAX = 30.0
SWITCH_INTERVAL_MIN = 360.0
SWITCH_INTERVAL_MAX = 720.0
_PLATFORMS = frozenset({'boss', 'zhaopin', 'liepin'})
_STATE_PATH = Path(__file__).resolve().parents[3] / 'data/local/collection/frequency.sqlite3'
_clock = time.time


class FrequencyStateError(RuntimeError):
    """State cannot be trusted; do not perform browser activity."""


class FrequencyLimitError(RuntimeError):
    def __init__(self, retry_after: float):
        self.retry_after = retry_after
        super().__init__(f'collection_frequency_limited: wait at least {math.ceil(retry_after)} seconds')


def _validate_state(row: tuple, now: float) -> None:
    """Apply the same persisted-state checks to reservations and recovery."""
    if not math.isfinite(now) or now < 0:
        raise FrequencyStateError('collection_frequency_clock_invalid')
    last, next_page, old_keyword, old_city, next_switch = row
    if (any(not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0
            for value in (last, next_page, next_switch))
            or not PAGE_DELAY_MIN - .000001 <= next_page - last <= PAGE_DELAY_MAX + .000001
            or (old_keyword is None) != (old_city is None)
            or (old_keyword is not None and (not isinstance(old_keyword, str)
                or not old_keyword.strip() or not isinstance(old_city, str)
                or not old_city.strip() or next_switch <= 0))):
        raise FrequencyStateError('collection_frequency_state_invalid')
    if now < last:
        raise FrequencyStateError('collection_frequency_clock_rollback')


def reserve_action(platform: str, keyword: str, city: str, *, kind: str = 'page') -> dict:
    return _reserve_action(platform, keyword, city, kind=kind)


def _reserve_action(platform: str, keyword: str, city: str, *, kind: str, flight: str | None = None) -> dict:
    if platform not in _PLATFORMS or kind not in {'page', 'prepare', 'capture'}:
        raise ValueError('unsupported collection frequency scope')
    keyword, city = str(keyword).strip(), str(city).strip()
    if kind != 'prepare' and (not keyword or not city):
        raise ValueError('collection frequency requires keyword and city code')
    # A preparation action has no proven query target and must not replace it.
    target = None if kind == 'prepare' else (keyword, city)
    connection = None
    try:
        _STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        existed = _STATE_PATH.exists()
        connection = sqlite3.connect(str(_STATE_PATH), timeout=5, isolation_level=None)
        connection.execute('PRAGMA synchronous=FULL')
        connection.execute('BEGIN IMMEDIATE')
        now = _clock()
        if not math.isfinite(now) or now < 0:
            raise FrequencyStateError('collection_frequency_clock_invalid')
        version = connection.execute('PRAGMA user_version').fetchone()[0]
        if version != 1 and (existed or version != 0):
            raise FrequencyStateError('collection_frequency_schema_invalid')
        if version == 1 and not connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='collection_frequency'").fetchone():
            raise FrequencyStateError('collection_frequency_schema_invalid')
        connection.execute('''CREATE TABLE IF NOT EXISTS collection_frequency (
            platform TEXT PRIMARY KEY, last_reserved REAL NOT NULL,
            next_page REAL NOT NULL, keyword TEXT, city TEXT,
            next_switch REAL NOT NULL)''')
        connection.execute('PRAGMA user_version=1')
        connection.execute('CREATE TABLE IF NOT EXISTS collection_action_flights (platform TEXT PRIMARY KEY, owner TEXT NOT NULL)')
        if connection.execute('SELECT 1 FROM collection_action_flights WHERE platform=?', (platform,)).fetchone():
            raise FrequencyStateError('collection_action_unfinished: previous action must be investigated before collection resumes')
        row = connection.execute(
            'SELECT last_reserved,next_page,keyword,city,next_switch FROM collection_frequency WHERE platform=?',
            (platform,),
        ).fetchone()
        if row:
            last, next_page, old_keyword, old_city, next_switch = row
            _validate_state(row, now)
            due = next_page
            if target and old_keyword is not None and target != (old_keyword, old_city):
                due = max(due, next_switch)
            if now < due:
                raise FrequencyLimitError(due - now)
        else:
            old_keyword, old_city, next_switch = None, None, 0.0
        # A browser permit may be used for up to 15 seconds. Reserving the
        # upper design bound keeps even late uses at least 15 seconds apart.
        page_delay = PAGE_DELAY_MAX if kind == 'capture' else random.SystemRandom().uniform(PAGE_DELAY_MIN, PAGE_DELAY_MAX)
        next_page = now + page_delay
        if target:
            old_keyword, old_city = target
            switch_minimum = SWITCH_INTERVAL_MIN + 15.0 if kind == 'capture' else SWITCH_INTERVAL_MIN
            next_switch = now + random.SystemRandom().uniform(switch_minimum, SWITCH_INTERVAL_MAX)
        connection.execute('''INSERT INTO collection_frequency VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(platform) DO UPDATE SET last_reserved=excluded.last_reserved,
            next_page=excluded.next_page, keyword=excluded.keyword, city=excluded.city,
            next_switch=excluded.next_switch''',
            (platform, now, next_page, old_keyword, old_city, next_switch))
        if flight is not None:
            connection.execute('INSERT INTO collection_action_flights VALUES (?, ?)', (platform, flight))
        connection.commit()
        return {'reserved_at': now, 'next_action_at': next_page, 'next_combination_at': next_switch}
    except (FrequencyLimitError, FrequencyStateError):
        raise
    except (OSError, sqlite3.Error) as exc:
        if isinstance(exc, sqlite3.Error) and (getattr(exc, 'sqlite_errorcode', 0) & 255) in {sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED}:
            raise FrequencyStateError('collection_frequency_busy: another module action holds the ledger lock') from exc
        raise FrequencyStateError('collection_frequency_state_unavailable') from exc
    finally:
        if connection is not None:
            if connection.in_transaction:
                connection.rollback()
            connection.close()


def wait_for_action(platform: str, keyword: str, city: str, *, kind: str = 'page', sleeper=time.sleep) -> dict:
    """Wait only on a valid cooldown, then atomically compete for a new slot."""
    while True:
        try:
            return reserve_action(platform, keyword, city, kind=kind)
        except FrequencyLimitError as exc:
            sleeper(exc.retry_after)


def run_action(platform: str, keyword: str, city: str, action, *, kind: str = 'page', sleeper=time.sleep):
    """Serialize the browser action and time the next slot from its completion.

    An unfinished marker survives process loss or an uncertain browser exception.
    Investigate that action before recovery; it is never silently refunded.
    """
    owner = secrets.token_hex(16)
    while True:
        try:
            reservation = _reserve_action(platform, keyword, city, kind=kind, flight=owner)
            break
        except FrequencyLimitError as exc:
            sleeper(exc.retry_after)
    connection = None
    try:
        connection = sqlite3.connect(str(_STATE_PATH), timeout=5, isolation_level=None)
        connection.execute('PRAGMA synchronous=FULL')
        connection.execute('BEGIN IMMEDIATE')
        row = connection.execute('SELECT owner FROM collection_action_flights WHERE platform=?', (platform,)).fetchone()
        if row != (owner,):
            raise FrequencyStateError('collection_action_reservation_lost')
        before_action = _clock()
        if not math.isfinite(before_action) or before_action < reservation['reserved_at']:
            raise FrequencyStateError('collection_frequency_clock_rollback')
        try:
            result = action()
        except BaseException:
            # The callback has unwound, but browser completion remains uncertain.
            # Preserve the flight and reservation for explicit, fenced recovery.
            connection.execute('''CREATE TABLE IF NOT EXISTS collection_action_failures (
                owner TEXT PRIMARY KEY, platform TEXT NOT NULL)''')
            connection.execute('INSERT INTO collection_action_failures VALUES (?, ?)', (owner, platform))
            connection.commit()
            raise
        finished = _clock()
        if not math.isfinite(finished) or finished < reservation['reserved_at']:
            raise FrequencyStateError('collection_frequency_clock_rollback')
        page_due = finished + random.SystemRandom().uniform(PAGE_DELAY_MIN, PAGE_DELAY_MAX)
        if kind == 'prepare':
            connection.execute('UPDATE collection_frequency SET last_reserved=?,next_page=? WHERE platform=?', (finished, page_due, platform))
        else:
            switch_due = finished + random.SystemRandom().uniform(SWITCH_INTERVAL_MIN, SWITCH_INTERVAL_MAX)
            connection.execute('UPDATE collection_frequency SET last_reserved=?,next_page=?,next_switch=? WHERE platform=?', (finished, page_due, switch_due, platform))
        connection.execute('DELETE FROM collection_action_flights WHERE platform=? AND owner=?', (platform, owner))
        connection.commit()
        return result
    except (OSError, sqlite3.Error) as exc:
        if isinstance(exc, sqlite3.Error) and (getattr(exc, 'sqlite_errorcode', 0) & 255) in {sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED}:
            raise FrequencyStateError('collection_frequency_busy: another module action holds the ledger lock') from exc
        raise FrequencyStateError('collection_frequency_state_unavailable') from exc
    finally:
        if connection is not None:
            if connection.in_transaction:
                connection.rollback()
            connection.close()


def issue_capture_permit(run_id: str, kind: str, reservation: dict) -> dict:
    permit = {'token': secrets.token_urlsafe(24), 'kind': kind,
              'issued_at': reservation['reserved_at'], 'expires_at': reservation['reserved_at'] + 15.0}
    try:
        with closing(sqlite3.connect(str(_STATE_PATH), timeout=5)) as connection, connection:
            connection.execute('PRAGMA synchronous=FULL')
            connection.execute('CREATE TABLE IF NOT EXISTS collection_capture_permits (token TEXT PRIMARY KEY, run_id TEXT NOT NULL, kind TEXT NOT NULL, issued REAL NOT NULL, expires REAL NOT NULL, used INTEGER NOT NULL)')
            connection.execute('INSERT INTO collection_capture_permits VALUES (?, ?, ?, ?, ?, 0)',
                               (permit['token'], run_id, kind, permit['issued_at'], permit['expires_at']))
        return permit
    except (OSError, sqlite3.Error) as exc:
        raise FrequencyStateError('collection_capture_permit_state_unavailable') from exc


def consume_capture_permit(run_id: str, kind: str, permit: str | None, now: float) -> None:
    if not permit or not math.isfinite(now):
        raise ValueError('capture_permit_required_or_expired')
    try:
        with closing(sqlite3.connect(str(_STATE_PATH), timeout=5)) as connection, connection:
            connection.execute('PRAGMA synchronous=FULL')
            connection.execute('BEGIN IMMEDIATE')
            changed = connection.execute('''UPDATE collection_capture_permits SET used=1
                WHERE token=? AND run_id=? AND kind=? AND used=0 AND issued<=? AND expires>?''',
                (permit, run_id, kind, now, now)).rowcount
            if changed != 1:
                raise ValueError('capture_permit_required_or_expired')
    except (OSError, sqlite3.Error) as exc:
        raise FrequencyStateError('collection_capture_permit_state_unavailable') from exc

"""Explicit, fenced recovery of interrupted browser actions in the private ledger."""
from contextlib import contextmanager
import sqlite3

from app.collect import frequency


def _check_platform(platform: str) -> None:
    if platform not in frequency._PLATFORMS:
        raise ValueError('unsupported collection frequency scope')


@contextmanager
def _locked_ledger():
    connection = None
    try:
        # mode=rw prevents a missing ledger from being silently created here.
        uri = frequency._STATE_PATH.resolve().as_uri() + '?mode=rw'
        connection = sqlite3.connect(uri, uri=True, timeout=.2, isolation_level=None)
        connection.execute('PRAGMA synchronous=FULL')
        connection.execute('BEGIN IMMEDIATE')
        if connection.execute('PRAGMA user_version').fetchone() != (1,):
            raise frequency.FrequencyStateError('collection_frequency_schema_invalid')
        yield connection
    except (OSError, sqlite3.Error) as exc:
        if isinstance(exc, sqlite3.Error) and (getattr(exc, 'sqlite_errorcode', 0) & 255) in {sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED}:
            raise frequency.FrequencyStateError('collection_frequency_busy') from exc
        raise frequency.FrequencyStateError('collection_frequency_state_unavailable') from exc
    finally:
        if connection is not None:
            if connection.in_transaction:
                connection.rollback()
            connection.close()


def _has_table(connection, name: str) -> bool:
    return connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None


def _read_state(connection, platform: str) -> tuple:
    now = frequency._clock()
    row = connection.execute(
        'SELECT last_reserved,next_page,keyword,city,next_switch FROM collection_frequency WHERE platform=?',
        (platform,),
    ).fetchone()
    if row:
        frequency._validate_state(row, now)
    flight = None
    if _has_table(connection, 'collection_action_flights'):
        flight = connection.execute('SELECT owner FROM collection_action_flights WHERE platform=?', (platform,)).fetchone()
    if flight and (not row or not isinstance(flight[0], str) or not flight[0]):
        raise frequency.FrequencyStateError('collection_frequency_state_invalid')
    return row, flight, now


def _status(platform: str, row=None, flight=None, interruption=None) -> dict:
    return {
        'platform': platform, 'state': 'unfinished' if flight else 'clear',
        'can_recover': bool(flight), 'recovery_token': flight[0] if flight else None,
        'reason': 'collection_action_unfinished' if flight else None,
        'next_action_at': row[1] if row else None,
        'next_combination_at': row[4] if row else None,
        'interruption': interruption,
        'message': ('上次页面动作未完成确认。可显式恢复并重新等待冷却，随后重新准备浏览器。'
                    if flight else '频率账本正常，后续页面动作仍须遵守冷却。'),
    }


def get_status(platform: str) -> dict:
    """Probe the writer lock without changing rows or creating a missing ledger."""
    _check_platform(platform)
    if not frequency._STATE_PATH.exists():
        return _status(platform)
    try:
        with _locked_ledger() as connection:
            row, flight, _ = _read_state(connection, platform)
            interruption = None
            if flight:
                failed = (_has_table(connection, 'collection_action_failures') and connection.execute(
                    'SELECT 1 FROM collection_action_failures WHERE owner=? AND platform=?', (flight[0], platform),
                ).fetchone())
                interruption = 'exception' if failed else 'unknown'
            return _status(platform, row, flight, interruption)
    except frequency.FrequencyStateError as exc:
        busy = str(exc) == 'collection_frequency_busy'
        return {**_status(platform), 'state': 'busy' if busy else 'unavailable',
                'reason': str(exc), 'message': '页面动作正在占用账本，请等待结束。' if busy else '频率账本无法核验，请检查本地状态。'}


def recover(platform: str, recovery_token: str) -> dict:
    """Fence an exact flight and retain its frequency budget and audit receipt.

    run_action holds this writer lock during the callback and verifies ownership
    after obtaining it. Removing an owner here therefore also fences callbacks
    waiting between their committed reservation and their action transaction.
    """
    _check_platform(platform)
    if not isinstance(recovery_token, str) or not recovery_token or len(recovery_token) > 128:
        raise ValueError('collection_recovery_token_required')
    with _locked_ledger() as connection:
        row, flight, now = _read_state(connection, platform)
        if flight != (recovery_token,):
            receipt = (_has_table(connection, 'collection_action_recoveries') and connection.execute(
                'SELECT 1 FROM collection_action_recoveries WHERE owner=? AND platform=?', (recovery_token, platform),
            ).fetchone())
            if not flight and receipt:
                return {**_status(platform, row), 'recovered': True}
            raise frequency.FrequencyStateError('collection_action_changed: refresh before recovery')
        # An interrupted action's completion time is unknown. Start a full upper
        # bound from recovery, retaining any longer existing combination budget.
        page_due = now + frequency.PAGE_DELAY_MAX
        switch_due = max(row[4], now + frequency.SWITCH_INTERVAL_MAX) if row[2] is not None else row[4]
        connection.execute('''CREATE TABLE IF NOT EXISTS collection_action_recoveries (
            owner TEXT PRIMARY KEY, platform TEXT NOT NULL, recovered_at REAL NOT NULL,
            previous_reserved REAL NOT NULL, previous_page REAL NOT NULL, previous_switch REAL NOT NULL)''')
        connection.execute('INSERT INTO collection_action_recoveries VALUES (?, ?, ?, ?, ?, ?)',
                           (recovery_token, platform, now, row[0], row[1], row[4]))
        connection.execute('UPDATE collection_frequency SET last_reserved=?,next_page=?,next_switch=? WHERE platform=?',
                           (now, page_due, switch_due, platform))
        connection.execute('DELETE FROM collection_action_flights WHERE platform=? AND owner=?', (platform, recovery_token))
        connection.commit()
        updated = (now, page_due, row[2], row[3], switch_due)
        return {**_status(platform, updated), 'recovered': True}

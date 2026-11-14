"""Explicit, fenced recovery of interrupted browser actions in the private ledger."""
from contextlib import contextmanager
from pathlib import Path
import sqlite3

from app.collect import frequency


def _check_platform(platform: str) -> None:
    if platform not in frequency._PLATFORMS:
        raise ValueError('unsupported collection frequency scope')


@contextmanager
def _locked_ledger(platform: str):
    connection = None
    try:
        # mode=rw prevents a missing ledger from being silently created here.
        uri = frequency.ledger_path(platform).resolve().as_uri() + '?mode=rw'
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
    if frequency.legacy_migration_required(platform):
        return {
            **_status(platform), 'state': 'legacy_migration_required',
            'can_recover': False, 'reason': 'collection_legacy_migration_required',
            'message': '检测到旧共享频率账本；必须先显式迁移，不能从空账本重置冷却。',
        }
    if not frequency.ledger_path(platform).exists():
        return _status(platform)
    try:
        with _locked_ledger(platform) as connection:
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
    if frequency.legacy_migration_required(platform):
        raise frequency.FrequencyStateError('collection_legacy_migration_required')
    with _locked_ledger(platform) as connection:
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

def migrate_legacy_platform(platform: str, source_path: Path | None = None) -> dict:
    """Copy one platform's legacy row/flight without deleting or resetting it.

    The source file remains untouched. A conflicting target is rejected rather
    than overwritten. Repeated migration of identical state is idempotent.
    """
    _check_platform(platform)
    source = Path(source_path or frequency._DEFAULT_STATE_PATH)
    if not source.exists():
        raise frequency.FrequencyStateError('collection_legacy_ledger_missing')
    target = frequency.ledger_path(platform)
    try:
        source_uri = source.resolve().as_uri() + '?mode=ro'
        with sqlite3.connect(source_uri, uri=True, timeout=.2) as source_db:
            if source_db.execute('PRAGMA user_version').fetchone() != (1,):
                raise frequency.FrequencyStateError('collection_legacy_schema_invalid')
            if not _has_table(source_db, 'collection_frequency'):
                raise frequency.FrequencyStateError('collection_legacy_schema_invalid')
            row = source_db.execute(
                'SELECT last_reserved,next_page,keyword,city,next_switch FROM collection_frequency WHERE platform=?',
                (platform,),
            ).fetchone()
            flight = None
            if _has_table(source_db, 'collection_action_flights'):
                flight = source_db.execute(
                    'SELECT owner FROM collection_action_flights WHERE platform=?', (platform,),
                ).fetchone()
            failure = None
            if flight and _has_table(source_db, 'collection_action_failures'):
                failure = source_db.execute(
                    'SELECT 1 FROM collection_action_failures WHERE owner=? AND platform=?',
                    (flight[0], platform),
                ).fetchone()
        if row is None and flight is None:
            return {'migrated': False, 'already_migrated': False, 'reason': 'legacy_platform_missing'}
        if row is not None:
            frequency._validate_state(row, frequency._clock())
        if flight and (row is None or not isinstance(flight[0], str) or not flight[0]):
            raise frequency.FrequencyStateError('collection_legacy_schema_invalid')

        target.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(target, timeout=5, isolation_level=None) as connection:
            connection.execute('PRAGMA synchronous=FULL')
            connection.execute('BEGIN IMMEDIATE')
            version = connection.execute('PRAGMA user_version').fetchone()[0]
            if version not in (0, 1):
                raise frequency.FrequencyStateError('collection_frequency_schema_invalid')
            connection.execute('''CREATE TABLE IF NOT EXISTS collection_frequency (
                platform TEXT PRIMARY KEY, last_reserved REAL NOT NULL,
                next_page REAL NOT NULL, keyword TEXT, city TEXT,
                next_switch REAL NOT NULL)''')
            connection.execute('CREATE TABLE IF NOT EXISTS collection_action_flights (platform TEXT PRIMARY KEY, owner TEXT NOT NULL)')
            connection.execute('CREATE TABLE IF NOT EXISTS collection_action_failures (owner TEXT PRIMARY KEY, platform TEXT NOT NULL)')
            connection.execute('''CREATE TABLE IF NOT EXISTS collection_legacy_migrations (
                platform TEXT PRIMARY KEY, source_path TEXT NOT NULL, migrated_at REAL NOT NULL,
                owner TEXT, previous_reserved REAL, previous_page REAL, previous_switch REAL)''')
            connection.execute('PRAGMA user_version=1')
            existing_row = connection.execute(
                'SELECT last_reserved,next_page,keyword,city,next_switch FROM collection_frequency WHERE platform=?',
                (platform,),
            ).fetchone()
            existing_flight = connection.execute(
                'SELECT owner FROM collection_action_flights WHERE platform=?', (platform,),
            ).fetchone()
            if existing_row is not None or existing_flight is not None:
                if existing_row == row and existing_flight == flight:
                    connection.rollback()
                    return {'migrated': False, 'already_migrated': True, 'platform': platform}
                raise frequency.FrequencyStateError('collection_legacy_migration_conflict')
            if row is not None:
                connection.execute(
                    'INSERT INTO collection_frequency VALUES (?, ?, ?, ?, ?, ?)', (platform, *row),
                )
            if flight is not None:
                connection.execute(
                    'INSERT INTO collection_action_flights VALUES (?, ?)', (platform, flight[0]),
                )
                if failure:
                    connection.execute(
                        'INSERT OR REPLACE INTO collection_action_failures VALUES (?, ?)', (flight[0], platform),
                    )
            connection.execute(
                'INSERT OR REPLACE INTO collection_legacy_migrations VALUES (?, ?, ?, ?, ?, ?, ?)',
                (platform, str(source), frequency._clock(), flight[0] if flight else None,
                 row[0] if row else None, row[1] if row else None, row[4] if row else None),
            )
            connection.commit()
        return {'migrated': True, 'already_migrated': False, 'platform': platform,
                'source': str(source), 'target': str(target), 'flight': flight[0] if flight else None}
    except frequency.FrequencyStateError:
        raise
    except (OSError, sqlite3.Error) as exc:
        raise frequency.FrequencyStateError('collection_legacy_migration_failed') from exc

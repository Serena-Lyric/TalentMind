"""Private immutable requests, checkpoints and consumer results; one OS-owned writer."""
from pathlib import Path
import re
import sqlite3

from ..foundation.inputs import canonical, check_public, digest, parse_json
from ..foundation.store import safe_destination
from ..product.workflow import Lease
from ..work_candidates.storage import CandidateStore

APP_ID = 0x4D324435


class DeliveryStore:
    def __init__(self, root, *, create=False, readonly=False):
        self.root = safe_destination(root)
        path = self.root / 'delivery.db'
        exists = path.exists()
        if path.resolve() != path:
            raise ValueError('redirected delivery database prohibited')
        if not exists and not create:
            raise ValueError('delivery store not initialized')
        self.root.mkdir(parents=True, exist_ok=True)
        if exists and path.stat().st_nlink != 1:
            raise ValueError('hardlinked delivery store prohibited')
        if readonly:
            self.lease = None
            self.candidates = None
            self.conn = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)
            if (self.conn.execute('PRAGMA application_id').fetchone()[0] != APP_ID or
                    self.conn.execute('PRAGMA user_version').fetchone()[0] != 1):
                self.conn.close()
                raise ValueError('not a delivery store')
            return
        self.lease = Lease(self.root / 'delivery.lock')
        try:
            self.conn = sqlite3.connect(path)
            app = self.conn.execute('PRAGMA application_id').fetchone()[0]
            version = self.conn.execute('PRAGMA user_version').fetchone()[0]
            if exists and (app != APP_ID or version != 1):
                raise ValueError('not a delivery store; no automatic migration')
            self.conn.execute('PRAGMA recursive_triggers=ON')
            self.conn.execute('PRAGMA synchronous=FULL')
            if not exists:
                self.conn.execute(f'PRAGMA application_id={APP_ID}')
                self.conn.execute('PRAGMA user_version=1')
                self.conn.execute('CREATE TABLE requests(run_id TEXT PRIMARY KEY, body TEXT NOT NULL, sha TEXT NOT NULL)')
                self.conn.execute('CREATE TABLE events(seq INTEGER PRIMARY KEY, run_id TEXT NOT NULL, kind TEXT NOT NULL, body TEXT NOT NULL, sha TEXT NOT NULL)')
                for table in ('requests', 'events'):
                    for op in ('UPDATE', 'DELETE'):
                        self.conn.execute(f"CREATE TRIGGER {table}_{op} BEFORE {op} ON {table} BEGIN SELECT RAISE(ABORT,'immutable delivery history'); END")
                self.conn.commit()
            missing_candidates = not (self.root / 'candidates.db').exists()
            if missing_candidates and self.conn.execute('SELECT count(*) FROM requests').fetchone()[0]:
                raise ValueError('candidate history missing; do not recreate')
            self.candidates = CandidateStore(self.root / 'candidates.db', create=missing_candidates)
        except BaseException:
            if hasattr(self, 'conn'): self.conn.close()
            self.lease.close()
            raise

    def __enter__(self): return self

    def __exit__(self, *exc):
        if self.candidates is not None: self.candidates.__exit__(*exc)
        self.conn.close()
        if self.lease is not None: self.lease.close()

    def request(self, run_id):
        row = self.conn.execute('SELECT body,sha FROM requests WHERE run_id=?', (run_id,)).fetchone()
        if row is None: raise ValueError('unknown delivery run')
        return self._checked(row)

    @staticmethod
    def _checked(row):
        value = parse_json(row[0])
        if digest(value) != row[1]: raise ValueError('delivery digest mismatch')
        return value

    def prepare(self, run_id, value):
        if not isinstance(run_id, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,100}', run_id):
            raise ValueError('invalid run ID')
        check_public(value)
        row = self.conn.execute('SELECT body,sha FROM requests WHERE run_id=?', (run_id,)).fetchone()
        if row:
            if self._checked(row) != value: raise ValueError('run ID already bound to different request')
            return
        if value['request']['baseline'] != self.candidates.read()['binding']:
            raise ValueError('stale candidate baseline')
        with self.conn:
            self.conn.execute('INSERT INTO requests VALUES(?,?,?)', (run_id, canonical(value), digest(value)))

    def append(self, run_id, kind, value):
        check_public(value)
        with self.conn:
            self.conn.execute('INSERT INTO events(run_id,kind,body,sha) VALUES(?,?,?,?)',
                              (run_id, kind, canonical(value), digest(value)))

    def latest(self, run_id, kind):
        row = self.conn.execute('SELECT body,sha FROM events WHERE run_id=? AND kind=? ORDER BY seq DESC LIMIT 1',
                                (run_id, kind)).fetchone()
        return self._checked(row) if row else None

    def item_results(self, run_id):
        return {value['index']: value for value in
                (self._checked(row) for row in self.conn.execute('SELECT body,sha FROM events WHERE run_id=? AND kind=? ORDER BY seq',
                                                               (run_id, 'item')))}

    def stages(self, run_id):
        return [self._checked(row) for row in self.conn.execute(
            'SELECT body,sha FROM events WHERE run_id=? AND kind=? ORDER BY seq', (run_id, 'p1_stage'))]

    def cached(self, key):
        for run_id, body, sha in self.conn.execute("SELECT run_id,body,sha FROM events WHERE kind='item' ORDER BY seq DESC"):
            item = self._checked((body, sha))
            if item['p1_key'] == key and item['p1_complete']:
                return run_id, item
        return None

    def read(self, run_id):
        self.request(run_id)
        value = self.latest(run_id, 'result') or self.latest(run_id, 'progress')
        if value is None: raise ValueError('run has no readable result yet')
        return value

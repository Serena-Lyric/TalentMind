"""Additive immutable catalogue objects; upstream running tasks stay untouched."""
from ..foundation.inputs import canonical, digest
from ..foundation.store import AnalysisStore


class CatalogStore(AnalysisStore):
    def __init__(self, path):
        super().__init__(path, recover=False)
        try:
            self.conn.executescript('''
                CREATE TABLE IF NOT EXISTS c35_revisions (revision TEXT PRIMARY KEY, catalog_sha256 TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS c35_artifacts (
                    id TEXT PRIMARY KEY, kind TEXT NOT NULL, snapshot_id TEXT,
                    candidate_id TEXT, body TEXT NOT NULL, sha256 TEXT NOT NULL);
            ''')
            for table in ('c35_revisions', 'c35_artifacts'):
                for operation in ('UPDATE', 'DELETE'):
                    self.conn.execute(f"CREATE TRIGGER IF NOT EXISTS {table}_{operation} BEFORE {operation} ON {table} "
                                      "BEGIN SELECT RAISE(ABORT,'immutable B3-5 history'); END")
            self.conn.commit()
        except BaseException:
            self.__exit__()
            raise

    def save(self, kind, body, snapshot_id=None, candidate_id=None):
        result = dict(body, run_id=kind + '-' + digest(body)[:48])
        existing = self.conn.execute('SELECT body FROM c35_artifacts WHERE id=?', (result['run_id'],)).fetchone()
        if existing is not None:
            if existing['body'] != canonical(result):
                raise ValueError('catalogue artifact identity collision')
        else:
            self.conn.execute('INSERT INTO c35_artifacts VALUES (?,?,?,?,?,?)',
                (result['run_id'], kind, snapshot_id, candidate_id, canonical(result), digest(result)))
        return result

"""Additive B2 state: only snapshots are shared with A/B1, histories stay separate."""
from uuid import uuid4

from ..foundation.inputs import canonical, digest
from ..foundation.store import AnalysisStore, now


class SemanticStore(AnalysisStore):
    def __init__(self, path):
        super().__init__(path)
        try:
            self.conn.executescript("""
                CREATE TABLE IF NOT EXISTS b2_versions (id TEXT PRIMARY KEY, manifest TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS b2_runs (
                    id TEXT PRIMARY KEY, namespace TEXT NOT NULL, input_path TEXT NOT NULL,
                    input_sha256 TEXT NOT NULL, input_bytes BLOB NOT NULL,
                    version_id TEXT NOT NULL REFERENCES b2_versions(id), status TEXT NOT NULL,
                    started_at TEXT NOT NULL, finished_at TEXT, error TEXT);
                CREATE TABLE IF NOT EXISTS b2_heads (
                    namespace TEXT NOT NULL, jd_id TEXT NOT NULL,
                    snapshot_id INTEGER NOT NULL REFERENCES snapshots(id), PRIMARY KEY(namespace,jd_id));
                CREATE TABLE IF NOT EXISTS b2_observations (
                    run_id TEXT NOT NULL REFERENCES b2_runs(id), snapshot_id INTEGER NOT NULL REFERENCES snapshots(id),
                    crawled_at TEXT, PRIMARY KEY(run_id,snapshot_id));
                CREATE TABLE IF NOT EXISTS b2_members (
                    run_id TEXT NOT NULL REFERENCES b2_runs(id), snapshot_id INTEGER NOT NULL REFERENCES snapshots(id),
                    attempt_id INTEGER REFERENCES b2_attempts(id), reused INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY(run_id,snapshot_id));
                CREATE TABLE IF NOT EXISTS b2_attempts (
                    id INTEGER PRIMARY KEY, run_id TEXT NOT NULL REFERENCES b2_runs(id),
                    snapshot_id INTEGER NOT NULL REFERENCES snapshots(id),
                    version_id TEXT NOT NULL REFERENCES b2_versions(id), status TEXT NOT NULL,
                    started_at TEXT NOT NULL, finished_at TEXT, body TEXT, error TEXT);
                CREATE INDEX IF NOT EXISTS b2_lookup ON b2_attempts(snapshot_id,version_id,id);
                CREATE TABLE IF NOT EXISTS b2_reports (
                    run_id TEXT PRIMARY KEY REFERENCES b2_runs(id), body TEXT NOT NULL, sha256 TEXT NOT NULL);
                CREATE TRIGGER IF NOT EXISTS b2_terminal BEFORE UPDATE ON b2_attempts
                    WHEN OLD.status != 'running' BEGIN SELECT RAISE(ABORT,'immutable B2 attempt'); END;
                CREATE TRIGGER IF NOT EXISTS b2_identity BEFORE UPDATE OF run_id,snapshot_id,version_id,started_at ON b2_attempts
                    BEGIN SELECT RAISE(ABORT,'immutable B2 attempt identity'); END;
                CREATE TRIGGER IF NOT EXISTS b2_delete BEFORE DELETE ON b2_attempts
                    BEGIN SELECT RAISE(ABORT,'immutable B2 attempt'); END;
            """)
            for table in ("b2_versions", "b2_reports", "b2_observations"):
                for operation in ("UPDATE", "DELETE"):
                    self.conn.execute(f"CREATE TRIGGER IF NOT EXISTS {table}_{operation} BEFORE {operation} ON {table} "
                                      "BEGIN SELECT RAISE(ABORT,'immutable B2 history'); END")
            self.conn.execute("UPDATE b2_attempts SET status='retryable',error='process_interrupted',finished_at=? WHERE status='running'", (now(),))
            self.conn.execute("UPDATE b2_runs SET status='interrupted',error='process_interrupted' WHERE status='running'")
            self.conn.commit()
        except BaseException:
            self.__exit__()
            raise

    def prepare(self, batch, manifest):
        identity, version = uuid4().hex, digest(manifest)
        with self.conn:
            self.conn.execute("INSERT OR IGNORE INTO b2_versions VALUES (?,?)", (version, canonical(manifest)))
            self.conn.execute("INSERT INTO b2_runs VALUES (?,?,?,?,?,?,'pending',?,NULL,NULL)",
                (identity, batch.namespace, str(batch.path), batch.digest, batch.raw_bytes, version, now()))
            for record in batch.records:
                self.conn.execute("INSERT OR IGNORE INTO snapshots(namespace,jd_id,fingerprint,payload) VALUES (?,?,?,?)",
                    (record.namespace, record.jd_id, record.fingerprint, record.payload_json))
                snapshot = self.conn.execute("SELECT id FROM snapshots WHERE namespace=? AND jd_id=? AND fingerprint=?",
                    (record.namespace, record.jd_id, record.fingerprint)).fetchone()[0]
                self.conn.execute("INSERT INTO b2_heads VALUES (?,?,?) ON CONFLICT(namespace,jd_id) DO UPDATE SET snapshot_id=excluded.snapshot_id",
                    (record.namespace, record.jd_id, snapshot))
                self.conn.execute("INSERT INTO b2_observations VALUES (?,?,?)", (identity, snapshot, record.observation))
            # Freeze B2's explicit dataset, never infer membership from A or B1 heads.
            self.conn.execute("INSERT INTO b2_members(run_id,snapshot_id) SELECT ?,snapshot_id FROM b2_heads WHERE namespace=?",
                (identity, batch.namespace))
        return identity

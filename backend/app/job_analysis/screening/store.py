"""Optional additive B1 tables. A's schema version and analysis tables are unchanged."""
from uuid import uuid4

from ..foundation.inputs import canonical, digest
from ..foundation.store import AnalysisStore, now


class ScreeningStore(AnalysisStore):
    def __init__(self, path):
        super().__init__(path)
        try:
            self.conn.executescript("""
                CREATE TABLE IF NOT EXISTS b1_versions (
                    id TEXT PRIMARY KEY, manifest TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS b1_runs (
                    id TEXT PRIMARY KEY, namespace TEXT NOT NULL, input_path TEXT NOT NULL,
                    input_sha256 TEXT NOT NULL, input_bytes BLOB, input_total INTEGER NOT NULL,
                    version_id TEXT NOT NULL REFERENCES b1_versions(id), status TEXT NOT NULL,
                    started_at TEXT NOT NULL, finished_at TEXT, error TEXT);
                CREATE TABLE IF NOT EXISTS b1_heads (
                    namespace TEXT NOT NULL, jd_id TEXT NOT NULL,
                    snapshot_id INTEGER NOT NULL REFERENCES snapshots(id), PRIMARY KEY(namespace,jd_id));
                CREATE TABLE IF NOT EXISTS b1_observations (
                    run_id TEXT NOT NULL REFERENCES b1_runs(id), snapshot_id INTEGER NOT NULL REFERENCES snapshots(id),
                    crawled_at TEXT, PRIMARY KEY(run_id,snapshot_id));
                CREATE TABLE IF NOT EXISTS b1_members (
                    run_id TEXT NOT NULL REFERENCES b1_runs(id), ordinal INTEGER NOT NULL,
                    snapshot_id INTEGER REFERENCES snapshots(id), jd_id TEXT, input_position INTEGER,
                    input_error TEXT, source_run_id TEXT REFERENCES b1_runs(id), source_position INTEGER,
                    decision_id INTEGER REFERENCES b1_decisions(id), reused INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY(run_id,ordinal));
                CREATE TABLE IF NOT EXISTS b1_decisions (
                    id INTEGER PRIMARY KEY, run_id TEXT NOT NULL REFERENCES b1_runs(id),
                    snapshot_id INTEGER NOT NULL REFERENCES snapshots(id),
                    version_id TEXT NOT NULL REFERENCES b1_versions(id), status TEXT NOT NULL,
                    started_at TEXT NOT NULL, finished_at TEXT, body TEXT, error TEXT);
                CREATE INDEX IF NOT EXISTS b1_lookup ON b1_decisions(snapshot_id,version_id,id);
                CREATE TABLE IF NOT EXISTS b1_reports (
                    run_id TEXT PRIMARY KEY REFERENCES b1_runs(id), body TEXT NOT NULL, sha256 TEXT NOT NULL);
                CREATE TRIGGER IF NOT EXISTS b1_terminal BEFORE UPDATE ON b1_decisions
                    WHEN OLD.status != 'running' BEGIN SELECT RAISE(ABORT,'immutable B1 decision'); END;
                CREATE TRIGGER IF NOT EXISTS b1_identity BEFORE UPDATE OF run_id,snapshot_id,version_id,started_at ON b1_decisions
                    BEGIN SELECT RAISE(ABORT,'immutable B1 decision identity'); END;
                CREATE TRIGGER IF NOT EXISTS b1_delete BEFORE DELETE ON b1_decisions
                    BEGIN SELECT RAISE(ABORT,'immutable B1 decision'); END;
            """)
            for table in ("b1_versions", "b1_reports", "b1_observations"):
                for operation in ("UPDATE", "DELETE"):
                    self.conn.execute(f"CREATE TRIGGER IF NOT EXISTS {table}_{operation} BEFORE {operation} ON {table} "
                                      "BEGIN SELECT RAISE(ABORT,'immutable B1 history'); END")
            self.conn.execute("UPDATE b1_decisions SET status='retryable',error='process_interrupted',finished_at=? WHERE status='running'", (now(),))
            self.conn.execute("UPDATE b1_runs SET status='interrupted',error='process_interrupted' WHERE status='running'")
            self.conn.commit()
        except BaseException:
            self.__exit__()
            raise

    def prepare(self, batch, version):
        identity = uuid4().hex
        version_id = digest(version)
        with self.conn:
            self.conn.execute("INSERT OR IGNORE INTO b1_versions VALUES (?,?)", (version_id, canonical(version)))
            self.conn.execute("INSERT INTO b1_runs VALUES (?,?,?,?,?,?,?,'pending',?,NULL,NULL)",
                (identity, batch.namespace, str(batch.path), batch.sha256, batch.raw_bytes, len(batch.units), version_id, now()))
            positions = {}
            for unit in batch.units:
                record = unit.record
                if record is None:
                    continue
                self.conn.execute("INSERT OR IGNORE INTO snapshots(namespace,jd_id,fingerprint,payload) VALUES (?,?,?,?)",
                    (record.namespace, record.jd_id, record.fingerprint, record.payload_json))
                snapshot = self.conn.execute("SELECT id FROM snapshots WHERE namespace=? AND jd_id=? AND fingerprint=?",
                    (record.namespace, record.jd_id, record.fingerprint)).fetchone()[0]
                self.conn.execute("INSERT INTO b1_heads VALUES (?,?,?) ON CONFLICT(namespace,jd_id) DO UPDATE SET snapshot_id=excluded.snapshot_id",
                    (record.namespace, record.jd_id, snapshot))
                self.conn.execute("INSERT INTO b1_observations VALUES (?,?,?)", (identity, snapshot, record.observation))
                positions[snapshot] = unit.position
            ordinal = 0
            for row in self.conn.execute("SELECT jd_id,snapshot_id FROM b1_heads WHERE namespace=? ORDER BY jd_id", (batch.namespace,)).fetchall():
                ordinal += 1
                position = positions.get(row["snapshot_id"])
                origin = (identity, position) if position is not None else tuple(self.conn.execute(
                    "SELECT run_id,input_position FROM b1_members WHERE snapshot_id=? AND input_position IS NOT NULL ORDER BY rowid DESC LIMIT 1",
                    (row["snapshot_id"],)).fetchone())
                self.conn.execute("INSERT INTO b1_members(run_id,ordinal,snapshot_id,jd_id,input_position,source_run_id,source_position) VALUES (?,?,?,?,?,?,?)",
                    (identity, ordinal, row["snapshot_id"], row["jd_id"], position, *origin))
            for unit in batch.units:
                if unit.error:
                    ordinal += 1
                    self.conn.execute("INSERT INTO b1_members(run_id,ordinal,jd_id,input_position,input_error) VALUES (?,?,?,?,?)",
                        (identity, ordinal, unit.jd_id, unit.position, unit.error))
        return identity

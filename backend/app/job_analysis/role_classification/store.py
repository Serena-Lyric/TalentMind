"""Append-only B3 tables; reuse A locks/snapshots without recovering A runs."""
from ..foundation.store import AnalysisStore


class RoleStore(AnalysisStore):
    def __init__(self, path):
        super().__init__(path, recover=False)
        try:
            self.conn.executescript("""
                CREATE TABLE IF NOT EXISTS b30_versions (id TEXT PRIMARY KEY, manifest TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS b30_inputs (
                    run_id TEXT PRIMARY KEY, path TEXT NOT NULL, sha256 TEXT NOT NULL, raw_bytes BLOB NOT NULL);
                CREATE TABLE IF NOT EXISTS b30_results (
                    id TEXT PRIMARY KEY, snapshot_id INTEGER NOT NULL REFERENCES snapshots(id),
                    annotation_sha256 TEXT NOT NULL, version_id TEXT NOT NULL REFERENCES b30_versions(id),
                    body TEXT NOT NULL, sha256 TEXT NOT NULL, created_at TEXT NOT NULL,
                    UNIQUE(snapshot_id,annotation_sha256,version_id));
                CREATE TABLE IF NOT EXISTS b30_reports (
                    run_id TEXT PRIMARY KEY REFERENCES b30_inputs(run_id), body TEXT NOT NULL, sha256 TEXT NOT NULL);
            """)
            for table in ("b30_versions", "b30_inputs", "b30_results", "b30_reports"):
                for operation in ("UPDATE", "DELETE"):
                    self.conn.execute(f"CREATE TRIGGER IF NOT EXISTS {table}_{operation} BEFORE {operation} ON {table} "
                                      "BEGIN SELECT RAISE(ABORT,'immutable B3 history'); END")
            self.conn.commit()
        except BaseException:
            self.__exit__()
            raise

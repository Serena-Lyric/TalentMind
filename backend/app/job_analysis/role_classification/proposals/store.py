"""Independent append-only suggestion history; no recovery of previous A runs."""
from ...foundation.store import AnalysisStore


class ProposalStore(AnalysisStore):
    def __init__(self, path):
        super().__init__(path, recover=False)
        try:
            self.conn.executescript("""
                CREATE TABLE IF NOT EXISTS b31_versions (id TEXT PRIMARY KEY, manifest TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS b31_inputs (
                    run_id TEXT PRIMARY KEY, path TEXT NOT NULL, sha256 TEXT NOT NULL, raw_bytes BLOB NOT NULL);
                CREATE TABLE IF NOT EXISTS b31_results (
                    id TEXT PRIMARY KEY, snapshot_id INTEGER NOT NULL REFERENCES snapshots(id),
                    version_id TEXT NOT NULL REFERENCES b31_versions(id),
                    body TEXT NOT NULL, sha256 TEXT NOT NULL, created_at TEXT NOT NULL,
                    UNIQUE(snapshot_id,version_id));
                CREATE TABLE IF NOT EXISTS b31_reports (
                    run_id TEXT PRIMARY KEY REFERENCES b31_inputs(run_id), body TEXT NOT NULL, sha256 TEXT NOT NULL);
            """)
            for table in ("b31_versions", "b31_inputs", "b31_results", "b31_reports"):
                for operation in ("UPDATE", "DELETE"):
                    self.conn.execute(f"CREATE TRIGGER IF NOT EXISTS {table}_{operation} BEFORE {operation} ON {table} "
                                      "BEGIN SELECT RAISE(ABORT,'immutable B3-1 history'); END")
            self.conn.commit()
        except BaseException:
            self.__exit__()
            raise

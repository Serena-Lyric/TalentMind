"""Governance adds immutable tables only; opening it never opens/revises B2 attempts."""
from uuid import uuid4

from ..foundation.inputs import canonical, digest
from ..foundation.store import AnalysisStore
from .candidates import Review


class GovernanceStore(AnalysisStore):
    def __init__(self, path):
        super().__init__(path)
        try:
            self.conn.executescript("""
                CREATE TABLE IF NOT EXISTS b22_versions (id TEXT PRIMARY KEY, manifest TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS b22_results (
                    id TEXT PRIMARY KEY, source_attempt INTEGER NOT NULL, source_snapshot INTEGER NOT NULL REFERENCES snapshots(id),
                    source_sha256 TEXT NOT NULL, version_id TEXT NOT NULL REFERENCES b22_versions(id),
                    body TEXT NOT NULL, sha256 TEXT NOT NULL, created_at TEXT NOT NULL,
                    UNIQUE(source_attempt,source_snapshot,source_sha256,version_id));
                CREATE TABLE IF NOT EXISTS b22_reports (
                    run_id TEXT PRIMARY KEY, body TEXT NOT NULL, sha256 TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS b22_reviews (
                    id TEXT PRIMARY KEY, result_id TEXT NOT NULL REFERENCES b22_results(id),
                    candidate_id TEXT NOT NULL, body TEXT NOT NULL, sha256 TEXT NOT NULL);
            """)
            for table in ("b22_versions", "b22_results", "b22_reports", "b22_reviews"):
                for operation in ("UPDATE", "DELETE"):
                    self.conn.execute(f"CREATE TRIGGER IF NOT EXISTS {table}_{operation} BEFORE {operation} ON {table} "
                        "BEGIN SELECT RAISE(ABORT,'immutable B22 history'); END")
            self.conn.commit()
        except BaseException:
            self.__exit__()
            raise

    def record_review(self, result_id, event):
        from ..foundation.inputs import parse_json
        event = Review.model_validate(event).model_dump()
        row = self.conn.execute("SELECT body FROM b22_results WHERE id=?", (result_id,)).fetchone()
        if row is None:
            raise ValueError("governance result not found")
        candidates = parse_json(row[0])["candidates"]
        if not any(c["id"] == event["candidate_id"] and c["version"] == event["candidate_version"] for c in candidates):
            raise ValueError("review candidate/version mismatch")
        identity = uuid4().hex
        with self.conn:
            self.conn.execute("INSERT INTO b22_reviews VALUES (?,?,?,?,?)",
                (identity, result_id, event["candidate_id"], canonical(event), digest(event)))
        return identity

    def reviews(self, result_id):
        from ..foundation.inputs import parse_json
        result = []
        for row in self.conn.execute("SELECT body,sha256 FROM b22_reviews WHERE result_id=? ORDER BY rowid", (result_id,)):
            body = parse_json(row[0])
            if digest(body) != row[1]:
                raise ValueError("review integrity mismatch")
            result.append(body)
        return result

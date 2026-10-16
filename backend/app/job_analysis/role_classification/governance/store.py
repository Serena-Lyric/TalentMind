"""Additive B3-2 history; never recover or alter upstream execution states."""
from uuid import uuid4

from ...foundation.inputs import InputRecord, canonical, check_public, digest, parse_json
from ...foundation.store import AnalysisStore, now
from ..validation import validate_evidence
from .models import Review


def result_version(version_id, claims_sha256, body_sha256):
    return digest(dict(version_id=version_id, claims_sha256=claims_sha256, body_sha256=body_sha256))


class CanonicalStore(AnalysisStore):
    def __init__(self, path):
        super().__init__(path, recover=False)
        try:
            self.conn.executescript("""
                CREATE TABLE IF NOT EXISTS b32_versions (id TEXT PRIMARY KEY, manifest TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS b32_inputs (
                    run_id TEXT PRIMARY KEY, path TEXT NOT NULL, sha256 TEXT NOT NULL, raw_bytes BLOB NOT NULL);
                CREATE TABLE IF NOT EXISTS b32_results (
                    id TEXT PRIMARY KEY, snapshot_id INTEGER NOT NULL REFERENCES snapshots(id),
                    claims_sha256 TEXT NOT NULL, version_id TEXT NOT NULL REFERENCES b32_versions(id),
                    body TEXT NOT NULL, sha256 TEXT NOT NULL, created_at TEXT NOT NULL,
                    UNIQUE(snapshot_id,claims_sha256,version_id));
                CREATE TABLE IF NOT EXISTS b32_reports (
                    run_id TEXT PRIMARY KEY REFERENCES b32_inputs(run_id), body TEXT NOT NULL, sha256 TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS b32_reviews (
                    id TEXT PRIMARY KEY, result_id TEXT NOT NULL REFERENCES b32_results(id),
                    body TEXT NOT NULL, sha256 TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS b32_exports (
                    id TEXT PRIMARY KEY, source_run_id TEXT NOT NULL REFERENCES b32_reports(run_id),
                    body TEXT NOT NULL, sha256 TEXT NOT NULL);
            """)
            for table in ("b32_versions", "b32_inputs", "b32_results", "b32_reports", "b32_reviews", "b32_exports"):
                for operation in ("UPDATE", "DELETE"):
                    self.conn.execute(f"CREATE TRIGGER IF NOT EXISTS {table}_{operation} BEFORE {operation} ON {table} "
                                      "BEGIN SELECT RAISE(ABORT,'immutable B3-2 history'); END")
            self.conn.commit()
        except BaseException:
            self.__exit__()
            raise

    def record_review(self, result_id, event):
        check_public(event)
        item = Review.model_validate(event)
        row = self.conn.execute("SELECT * FROM b32_results WHERE id=?", (result_id,)).fetchone()
        if row is None:
            raise ValueError("candidate result not found")
        body = parse_json(row["body"])
        if digest(body) != row["sha256"]:
            raise ValueError("candidate result integrity mismatch")
        targets = body["candidates"] if item.target_kind == "candidate" else body["relations"]
        if item.result_version != result_version(row["version_id"], row["claims_sha256"], row["sha256"]) or item.target_id not in {t["id"] for t in targets}:
            raise ValueError("review target or version mismatch")
        snapshot = self.conn.execute("SELECT * FROM snapshots WHERE id=?", (row["snapshot_id"],)).fetchone()
        record = InputRecord(snapshot["namespace"], snapshot["jd_id"], snapshot["payload"], None)
        if record.fingerprint != snapshot["fingerprint"] or record.payload != body["source_payload"]:
            raise ValueError("review snapshot integrity mismatch")
        for ref in item.evidence_refs:
            validate_evidence(record, ref.model_dump())
        if item.supersedes:
            earlier = next((r["event"] for r in self.reviews(result_id) if r["id"] == item.supersedes), None)
            if earlier is None or (earlier["target_kind"], earlier["target_id"], earlier["result_version"]) != (item.target_kind, item.target_id, item.result_version):
                raise ValueError("superseded event must have same target and version")
        identity = "review-" + uuid4().hex
        saved = dict(event=item.model_dump(), created_at=now())
        with self.conn:
            self.conn.execute("INSERT INTO b32_reviews VALUES (?,?,?,?)", (identity, result_id, canonical(saved), digest(saved)))
        return identity

    def reviews(self, result_id):
        result = []
        for row in self.conn.execute("SELECT * FROM b32_reviews WHERE result_id=? ORDER BY rowid", (result_id,)):
            body = parse_json(row["body"])
            if digest(body) != row["sha256"]:
                raise ValueError("review integrity mismatch")
            result.append(dict(id=row["id"], result_id=row["result_id"], **body))
        return result

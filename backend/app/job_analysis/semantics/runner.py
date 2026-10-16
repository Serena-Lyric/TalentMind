"""B2 per-JD transactions, exact dependency reuse, immutable replay and atomic output."""
from collections import Counter
from pathlib import Path

from ..foundation.inputs import InputRecord, canonical, digest, parse_json
from ..foundation.runner import publish, _output_path as output_path
from ..foundation.store import now
from .rules import SkillSemanticAnalyzer
from .validation import validate


def checkpoint(stage):
    """Durable lifecycle boundary for local interruption instrumentation."""


def execute(store, batch, *, analyzer=None, rules_revision="v1", output=None):
    analyzer = analyzer or SkillSemanticAnalyzer()
    if batch.path == store.path:
        raise ValueError("input must be separate from state")
    if output is not None:
        output_path(store, output, batch.path)
    identity = store.prepare(batch, analyzer.manifest(rules_revision))
    checkpoint("after_prepare")
    return resume(store, identity, analyzer=analyzer, output=output)


def resume(store, identity, *, analyzer=None, output=None):
    analyzer = analyzer or SkillSemanticAnalyzer()
    run = store.conn.execute("SELECT * FROM b2_runs WHERE id=?", (identity,)).fetchone()
    if run is None:
        raise ValueError("B2 run not found")
    saved = parse_json(store.conn.execute("SELECT manifest FROM b2_versions WHERE id=?", (run["version_id"],)).fetchone()[0])
    if analyzer.manifest(saved["revision"]) != saved:
        raise ValueError("resume requires original B2 dependencies")
    destination = output_path(store, output, Path(run["input_path"])) if output is not None else None
    with store.conn:
        store.conn.execute("UPDATE b2_runs SET status='running',error=NULL WHERE id=?", (identity,))
    if not store.conn.execute("SELECT 1 FROM b2_reports WHERE run_id=?", (identity,)).fetchone():
        rows = store.conn.execute("""SELECT s.*,m.attempt_id FROM b2_members m JOIN snapshots s ON s.id=m.snapshot_id
            WHERE m.run_id=? ORDER BY s.namespace,s.jd_id""", (identity,)).fetchall()
        for row in rows:
            assigned = store.conn.execute("SELECT status FROM b2_attempts WHERE id=?", (row["attempt_id"],)).fetchone()
            if assigned and assigned["status"] in ("completed", "partial", "failed"):
                continue
            latest = store.conn.execute("SELECT id,status FROM b2_attempts WHERE snapshot_id=? AND version_id=? ORDER BY id DESC LIMIT 1",
                (row["id"], run["version_id"])).fetchone()
            # A partial deterministic result is also exactly reusable; it stays partial.
            if latest and latest["status"] in ("completed", "partial"):
                with store.conn:
                    store.conn.execute("UPDATE b2_members SET attempt_id=?,reused=1 WHERE run_id=? AND snapshot_id=?",
                        (latest["id"], identity, row["id"]))
                continue
            with store.conn:
                cursor = store.conn.execute("INSERT INTO b2_attempts(run_id,snapshot_id,version_id,status,started_at) VALUES (?,?,?,'running',?)",
                    (identity, row["id"], run["version_id"], now()))
                attempt = cursor.lastrowid
                store.conn.execute("UPDATE b2_members SET attempt_id=?,reused=0 WHERE run_id=? AND snapshot_id=?",
                    (attempt, identity, row["id"]))
            checkpoint("after_start")
            record = InputRecord(row["namespace"], row["jd_id"], row["payload"], None)
            try:
                raw = analyzer.analyze(record)
            except Exception:
                body, error = None, "semantic_execution_failed"
            else:
                checkpoint("after_analyze")
                try:
                    body, error = validate(raw, record, analyzer), None
                except (ValueError, TypeError, KeyError):
                    body, error = None, "semantic_result_invalid"
            status = "failed" if error else "completed" if body["coverage"] == "complete" else "partial"
            with store.conn:
                store.conn.execute("UPDATE b2_attempts SET status=?,body=?,error=?,finished_at=? WHERE id=?",
                    (status, canonical(body) if body else None, error, now(), attempt))
                checkpoint("before_commit")
            checkpoint("after_commit")
        build_report(store, identity)
        checkpoint("after_report")
    result = replay(store, identity)
    if destination is not None:
        try:
            publish(result, destination, identity)
        except (OSError, ValueError):
            with store.conn:
                store.conn.execute("UPDATE b2_runs SET status='publication_failed',error='artifact_publish_failed' WHERE id=?", (identity,))
            raise
        checkpoint("after_output")
    with store.conn:
        store.conn.execute("UPDATE b2_runs SET status=?,finished_at=? WHERE id=?",
            ("completed_with_failures" if result["audit"]["failed"] else "completed", now(), identity))
    return result


def build_report(store, identity):
    run = store.conn.execute("SELECT * FROM b2_runs WHERE id=?", (identity,)).fetchone()
    manifest = parse_json(store.conn.execute("SELECT manifest FROM b2_versions WHERE id=?", (run["version_id"],)).fetchone()[0])
    members = []
    for row in store.conn.execute("""SELECT s.*,m.attempt_id,m.reused,a.status,a.body,a.error,a.finished_at
        FROM b2_members m JOIN snapshots s ON s.id=m.snapshot_id JOIN b2_attempts a ON a.id=m.attempt_id
        WHERE m.run_id=? ORDER BY s.namespace,s.jd_id""", (identity,)):
        if row["status"] not in ("completed", "partial", "failed"):
            raise ValueError("B2 members unfinished")
        payload = parse_json(row["payload"])
        members.append(dict(namespace=row["namespace"], jd_id=row["jd_id"], fingerprint=row["fingerprint"], snapshot_id=row["id"],
            attempt_id=row["attempt_id"], status=row["status"], error=row["error"], decided_at=row["finished_at"],
            source=payload["source"], source_detail=payload.get("source_detail"),
            semantic_eligibility="supported_scope_complete" if row["status"] == "completed" else "incomplete_or_failed",
            body=parse_json(row["body"]) if row["body"] else None))
    total = store.conn.execute("SELECT count(*) FROM b2_members WHERE run_id=?", (identity,)).fetchone()[0]
    if len(members) != total:
        raise ValueError("B2 members unfinished")
    statuses = Counter(m["status"] for m in members)
    result = dict(run_id=identity, mode="offline_skill_semantics_audit", input_path=run["input_path"],
        input_sha256=run["input_sha256"], version_id=run["version_id"], manifest=manifest,
        members=members, audit=dict(jd_records=len(members), completed=statuses["completed"],
            partial=statuses["partial"], failed=statuses["failed"],
            no_recognized_skills=sum(bool(m["body"]) and m["body"]["outcome"] == "no_recognized_skills" for m in members)),
        formal_statistics_eligible=False, created_at=now())
    with store.conn:
        store.conn.execute("INSERT INTO b2_reports VALUES (?,?,?)", (identity, canonical(result), digest(result)))


def replay(store, identity):
    row = store.conn.execute("SELECT * FROM b2_reports WHERE run_id=?", (identity,)).fetchone()
    if row is None:
        raise ValueError("B2 report not found")
    result = parse_json(row["body"])
    if digest(result) != row["sha256"]:
        raise ValueError("B2 report integrity mismatch")
    return result

"""Serial B1 execution, append-only decisions, frozen membership and atomic audit output."""
from collections import Counter
from pathlib import Path

from ..foundation.inputs import InputRecord, canonical, digest, parse_json
from ..foundation.runner import publish
from ..foundation.store import now, safe_destination
from .inputs import read_batch
from .rules import Decision, RULESET, manifest, screen


def checkpoint(stage):
    """Durable lifecycle boundary for local progress/crash instrumentation."""


def output_path(store, output, input_path):
    path = safe_destination(output)
    # State may live inside output: publish writes only <run_id>.json, never the SQLite filename.
    if path == store.path or path.is_relative_to(store.path) or input_path == path or input_path.is_relative_to(path):
        raise ValueError("output must be separate from input and state")
    return path


def execute(store, input_path, namespace, *, scope, rules_revision="v1", output=None):
    version = manifest(scope, rules_revision)
    batch = read_batch(input_path, namespace)
    if batch.path == store.path:
        raise ValueError("input must be separate from state")
    if output is not None:
        output_path(store, output, batch.path)
    identity = store.prepare(batch, version)
    checkpoint("after_prepare")
    return resume(store, identity, output=output)


def resume(store, identity, *, output=None):
    run = store.conn.execute("SELECT * FROM b1_runs WHERE id=?", (identity,)).fetchone()
    if run is None:
        raise ValueError("B1 run not found")
    version = parse_json(store.conn.execute("SELECT manifest FROM b1_versions WHERE id=?", (run["version_id"],)).fetchone()[0])
    if manifest(version["scope"], version["rules"]["revision"]) != version:
        raise ValueError("resume requires original B1 rule implementation")
    destination = output_path(store, output, Path(run["input_path"])) if output is not None else None
    report = store.conn.execute("SELECT 1 FROM b1_reports WHERE run_id=?", (identity,)).fetchone()
    with store.conn:
        store.conn.execute("UPDATE b1_runs SET status='running',error=NULL WHERE id=?", (identity,))
    if report is None:
        members = store.conn.execute("SELECT * FROM b1_members WHERE run_id=? ORDER BY ordinal", (identity,)).fetchall()
        for member in members:
            if member["input_error"]:
                continue
            assigned = store.conn.execute("SELECT * FROM b1_decisions WHERE id=?", (member["decision_id"],)).fetchone()
            if assigned and assigned["status"] in ("completed", "failed"):
                continue
            latest = store.conn.execute("SELECT * FROM b1_decisions WHERE snapshot_id=? AND version_id=? ORDER BY id DESC LIMIT 1",
                (member["snapshot_id"], run["version_id"])).fetchone()
            if latest and latest["status"] == "completed":
                with store.conn:
                    store.conn.execute("UPDATE b1_members SET decision_id=?,reused=1 WHERE run_id=? AND ordinal=?",
                        (latest["id"], identity, member["ordinal"]))
                continue
            with store.conn:
                cursor = store.conn.execute("INSERT INTO b1_decisions(run_id,snapshot_id,version_id,status,started_at) VALUES (?,?,?,'running',?)",
                    (identity, member["snapshot_id"], run["version_id"], now()))
                decision_id = cursor.lastrowid
                store.conn.execute("UPDATE b1_members SET decision_id=?,reused=0 WHERE run_id=? AND ordinal=?",
                    (decision_id, identity, member["ordinal"]))
            checkpoint("after_start")
            row = store.conn.execute("SELECT * FROM snapshots WHERE id=?", (member["snapshot_id"],)).fetchone()
            record = InputRecord(row["namespace"], row["jd_id"], row["payload"], None)
            try:
                body = screen(record, version["scope"])
            except Exception:
                body, error = None, "screening_execution_failed"
            else:
                checkpoint("after_screen")
                try:
                    body = Decision.model_validate(body).model_dump()
                    for evidence in body["evidence"]:
                        text = record.payload.get(evidence["field"], "")
                        if text[evidence["start"]:evidence["end"]] != evidence["quote"]:
                            raise ValueError("evidence mismatch")
                    error = None
                except (ValueError, TypeError, KeyError):
                    body, error = None, "screening_result_invalid"
            with store.conn:
                store.conn.execute("UPDATE b1_decisions SET status=?,body=?,error=?,finished_at=? WHERE id=?",
                    ("failed" if error else "completed", canonical(body) if body else None, error, now(), decision_id))
                checkpoint("before_commit")
            checkpoint("after_commit")
        result = build_report(store, identity)
        checkpoint("after_report")
    else:
        result = replay(store, identity)
    if destination is not None:
        try:
            publish(result, destination, identity)
        except (OSError, ValueError):
            with store.conn:
                store.conn.execute("UPDATE b1_runs SET status='publication_failed',error='artifact_publish_failed' WHERE id=?", (identity,))
            raise
        checkpoint("after_output")
    with store.conn:
        store.conn.execute("UPDATE b1_runs SET status=?,finished_at=? WHERE id=?",
            ("completed_with_failures" if result["audit"]["input_failed"] + result["audit"]["screening_failed"] else "completed", now(), identity))
    return result


def counts(members):
    validity = Counter(m["validity"] for m in members)
    scope = Counter(m["scope_status"] or "not_applicable" for m in members)
    reasons = Counter(code for m in members for code in m["reason_codes"])
    return {
        "member_total": len(members),
        "validity_counts": {k: validity[k] for k in ("valid", "invalid", "undetermined", "not_evaluated")},
        "scope_counts": {k: scope[k] for k in ("in_scope", "out_of_scope", "needs_review", "not_applicable")},
        "input_failed": sum(m["execution_status"] == "input_failed" for m in members),
        "screening_failed": sum(m["execution_status"] == "failed" for m in members),
        "reason_counts": dict(sorted(reasons.items())),
    }


def build_report(store, identity):
    run = store.conn.execute("SELECT * FROM b1_runs WHERE id=?", (identity,)).fetchone()
    version = parse_json(store.conn.execute("SELECT manifest FROM b1_versions WHERE id=?", (run["version_id"],)).fetchone()[0])
    members = []
    rows = store.conn.execute("""SELECT m.*,s.fingerprint,s.payload,d.status,d.body,d.error,d.finished_at
        FROM b1_members m LEFT JOIN snapshots s ON s.id=m.snapshot_id
        LEFT JOIN b1_decisions d ON d.id=m.decision_id WHERE m.run_id=? ORDER BY m.ordinal""", (identity,)).fetchall()
    for row in rows:
        if not row["input_error"] and row["status"] not in ("completed", "failed"):
            raise ValueError("B1 members unfinished")
        payload = parse_json(row["payload"]) if row["payload"] else {}
        body = parse_json(row["body"]) if row["body"] else dict(validity="not_evaluated", scope_status=None,
            reason_codes=[row["input_error"] or row["error"]], explanation="输入无法解析或筛选执行失败，未作岗位判断。",
            evidence=[], review_reasons=[])
        members.append(dict(namespace=run["namespace"], jd_id=row["jd_id"], snapshot_id=row["snapshot_id"],
            fingerprint=row["fingerprint"], input_position=row["input_position"],
            input_snapshot=dict(run_id=row["source_run_id"] or identity,
                sha256=store.conn.execute("SELECT input_sha256 FROM b1_runs WHERE id=?",
                    (row["source_run_id"] or identity,)).fetchone()[0],
                position=row["source_position"] if row["source_run_id"] else row["input_position"]),
            source=payload.get("source"), source_detail=payload.get("source_detail"),
            decision_id=row["decision_id"], version_id=run["version_id"],
            rules_version=version["rules"]["revision"], rules_implementation=RULESET,
            scope_version=version["scope"]["version"],
            execution_status="input_failed" if row["input_error"] else row["status"],
            execution_error=row["input_error"] or row["error"], decided_at=row["finished_at"], **body))
    audit = counts(members) | {
        "counting_unit": "JD identities in frozen B1 dataset plus current input errors; not independent positions",
        "input_total": run["input_total"],
        "input_unit_kind": "array elements or nonblank JSONL lines; unreadable container is one failed unit at position 0",
        "current_input": counts([m for m in members if m["input_position"] is not None]),
        "reused": sum(row["reused"] for row in rows),
    }
    result = dict(run_id=identity, mode="offline_scope_audit", input_sha256=run["input_sha256"],
        input_path=run["input_path"], raw_input_retained=run["input_bytes"] is not None,
        screening_version=run["version_id"], rules=version["rules"],
        scope_definition=version["scope"], scope_sha256=digest(version["scope"]),
        members=members, audit=audit, formal_statistics_eligible=False,
        analysis_status="not_executed_by_b1", created_at=now())
    with store.conn:
        store.conn.execute("INSERT INTO b1_reports VALUES (?,?,?)", (identity, canonical(result), digest(result)))
    return result


def replay(store, identity):
    row = store.conn.execute("SELECT * FROM b1_reports WHERE run_id=?", (identity,)).fetchone()
    if row is None:
        raise ValueError("B1 report not found")
    result = parse_json(row["body"])
    if digest(result) != row["sha256"]:
        raise ValueError("B1 report integrity mismatch")
    return result

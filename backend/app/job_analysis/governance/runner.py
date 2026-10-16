"""Recompute the overlay from saved B2/snapshot inputs; commit whole reports atomically."""
from pathlib import Path
from uuid import uuid4

from pydantic import TypeAdapter

from ..foundation.inputs import InputRecord, canonical, digest, parse_json
from ..foundation.models import VersionName
from ..foundation.runner import publish, _output_path as output_path
from ..foundation.store import now
from ..semantics.runner import replay as replay_b2
from .catalog import Catalog
from .extract import analyze


def execute(store, b2_run, *, catalog=None, revision="v1", output=None):
    catalog = catalog or Catalog()
    TypeAdapter(VersionName).validate_python(revision)
    source = replay_b2(store, b2_run)
    destination = output_path(store, output, Path(source["input_path"])) if output is not None else None
    manifest = dict(revision=revision, **catalog.manifest())
    version, identity = digest(manifest), uuid4().hex
    members = []
    # No running state: interruption before commit leaves zero new rows; replay handles publish retry.
    with store.conn:
        store.conn.execute("INSERT OR IGNORE INTO b22_versions VALUES (?,?)", (version, canonical(manifest)))
        for member in source["members"]:
            snapshot = store.conn.execute("SELECT * FROM snapshots WHERE id=?", (member["snapshot_id"],)).fetchone()
            attempt = store.conn.execute("SELECT * FROM b2_attempts WHERE id=?", (member["attempt_id"],)).fetchone()
            if snapshot is None or attempt is None or attempt["snapshot_id"] != snapshot["id"]:
                raise ValueError("B2 source relationship mismatch")
            record = InputRecord(snapshot["namespace"], snapshot["jd_id"], snapshot["payload"], None)
            if (member["namespace"], member["jd_id"], member["fingerprint"]) != (record.namespace, record.jd_id, record.fingerprint):
                raise ValueError("B2 snapshot identity mismatch")
            original = parse_json(attempt["body"]) if attempt["body"] else None
            if original != member["body"] or attempt["status"] != member["status"]:
                raise ValueError("B2 source body mismatch")
            source_digest = digest(original)
            saved = store.conn.execute("SELECT * FROM b22_results WHERE source_attempt=? AND source_snapshot=? AND source_sha256=? AND version_id=?",
                (attempt["id"], snapshot["id"], source_digest, version)).fetchone()
            if saved:
                body, result_id = parse_json(saved["body"]), saved["id"]
                if digest(body) != saved["sha256"]:
                    raise ValueError("governance result integrity mismatch")
            else:
                result_id = uuid4().hex
                body = analyze(record, original, catalog) if original is not None else None
                store.conn.execute("INSERT INTO b22_results VALUES (?,?,?,?,?,?,?,?)", (result_id, attempt["id"], snapshot["id"],
                    source_digest, version, canonical(body), digest(body), now()))
            members.append(dict(namespace=record.namespace, jd_id=record.jd_id, fingerprint=record.fingerprint,
                snapshot_id=snapshot["id"], source_attempt=attempt["id"], source_status=attempt["status"],
                result_id=result_id, status="overlay_saved" if body is not None else "upstream_failed", body=body))
        result = dict(run_id=identity, schema_version="b22-report-1", mode="offline_skill_governance",
            source_b2_run=b2_run, source_report_sha256=digest(source), input_path=source["input_path"],
            version_id=version, manifest=manifest, alias_audit=catalog.audit, members=members,
            audit=dict(jd_records=len(members), overlays=sum(m["body"] is not None for m in members),
                       upstream_failed=sum(m["body"] is None for m in members),
                       candidates=sum(len(m["body"]["candidates"]) for m in members if m["body"])),
            formal_statistics_eligible=False, created_at=now())
        store.conn.execute("INSERT INTO b22_reports VALUES (?,?,?)", (identity, canonical(result), digest(result)))
    if destination is not None:
        publish(result, destination, identity)
    return result


def replay(store, identity):
    row = store.conn.execute("SELECT body,sha256 FROM b22_reports WHERE run_id=?", (identity,)).fetchone()
    if row is None:
        raise ValueError("governance report not found")
    body = parse_json(row[0])
    if digest(body) != row[1]:
        raise ValueError("governance report integrity mismatch")
    return body

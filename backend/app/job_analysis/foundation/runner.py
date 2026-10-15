"""Serial incremental execution with durable per-JD commit and resumable publication."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

from ...skills.normalizer import build_alias_map
from .aggregate import build
from .inputs import InputRecord, canonical, parse_json
from .models import analysis_version
from .store import now, safe_destination
from .validation import validate_response


def checkpoint(stage):
    """Lifecycle event boundary; callers may attach local progress instrumentation."""


def dictionary():
    path = Path(__file__).resolve().parents[2] / "skills" / "skill_dict_seed.json"
    return parse_json(path.read_text(encoding="utf-8"))


def execute(store, batch, analyzer, *, analysis_revision="v1", aggregate_revision="v1", force=False, output=None):
    if output is not None:
        _output_path(store, output, batch.path)
    version = analysis_version(analysis_revision, analyzer.spec, dictionary())
    run_id = store.ingest(batch, version, force, aggregate_revision)
    checkpoint("after_prepare")
    return resume(store, run_id, analyzer, output=output)


def _output_path(store, output, input_path=None):
    path = safe_destination(output)
    if path == store.path or path.is_relative_to(store.path) or (input_path and (path == input_path or input_path.is_relative_to(path))):
        raise ValueError("output must be separate from input and state")
    return path


def resume(store, run_id, analyzer, *, output=None):
    run = store.run(run_id)
    if run is None or run["version_id"] is None:
        raise ValueError("versioned run not found")
    saved = store.conn.execute("SELECT manifest FROM versions WHERE id=?", (run["version_id"],)).fetchone()[0]
    revision = parse_json(saved)["revision"]
    seed = dictionary()
    version = analysis_version(revision, analyzer.spec, seed)
    if version.key != run["version_id"]:
        raise ValueError("resume requires the original analysis dependencies")
    destination = _output_path(store, output, Path(run["input_path"])) if output is not None else None
    aliases = build_alias_map(seed)
    with store.conn:
        store.conn.execute("UPDATE runs SET status='running',error=NULL WHERE id=?", (run_id,))
    tasks = store.conn.execute("""SELECT s.*,t.attempt_id FROM tasks t JOIN snapshots s ON s.id=t.snapshot_id
                                  WHERE t.run_id=? ORDER BY s.namespace,s.jd_id""", (run_id,)).fetchall()
    for row in tasks:
        assigned = store.attempt(row["attempt_id"])
        if assigned and assigned["status"] in ("completed", "partial", "failed"):
            continue
        latest = store.conn.execute("SELECT id,status FROM attempts WHERE snapshot_id=? AND version_id=? ORDER BY id DESC LIMIT 1",
                                    (row["id"], version.key)).fetchone()
        if not run["force"] and latest and latest["status"] == "completed":
            with store.conn:
                store.conn.execute("UPDATE tasks SET attempt_id=?,reused=1 WHERE run_id=? AND snapshot_id=?", (latest["id"], run_id, row["id"]))
            continue
        with store.conn:
            cursor = store.conn.execute("INSERT INTO attempts(run_id,snapshot_id,version_id,status,started_at) VALUES (?,?,?,'running',?)",
                                        (run_id, row["id"], version.key, now()))
            attempt_id = cursor.lastrowid
            store.conn.execute("UPDATE tasks SET attempt_id=? WHERE run_id=? AND snapshot_id=?", (attempt_id, run_id, row["id"]))
        checkpoint("after_start")
        record = InputRecord(row["namespace"], row["jd_id"], row["payload"], None)
        try:
            raw = analyzer.analyze(record)
        except Exception:
            # Exception text can contain provider credentials; persist a safe failure category only.
            result = {"status": "failed", "error": "analyzer_call_failed", "coverage": None, "facts": []}
        else:
            checkpoint("after_analyze")
            result = validate_response(raw, record, aliases)
        with store.conn:
            for index, fact in enumerate(result["facts"]):
                store.conn.execute("INSERT INTO facts(attempt_id,ordinal,body) VALUES (?,?,?)", (attempt_id, index, canonical(fact)))
            store.conn.execute("UPDATE attempts SET status=?,error=?,coverage=?,finished_at=? WHERE id=?",
                               (result["status"], result["error"], result["coverage"], now(), attempt_id))
            checkpoint("before_commit")
        checkpoint("after_commit")
    result = build(store, run_id, run["aggregate_revision"])
    checkpoint("after_aggregate")
    if destination:
        try:
            publish(result, destination, run_id)
        except (OSError, ValueError):
            with store.conn:
                store.conn.execute("UPDATE runs SET status='publication_failed',error='artifact_publish_failed' WHERE id=?", (run_id,))
            raise
        checkpoint("after_output")
    with store.conn:
        store.conn.execute("UPDATE runs SET status=?,finished_at=? WHERE id=?",
            ("completed_with_failures" if result["business"]["failed_records"] else "completed", now(), run_id))
    return result


def publish(result, destination, identity):
    destination = safe_destination(destination)
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / (identity + ".json")
    content = canonical(result) + "\n"
    if target.exists():
        if target.read_text(encoding="utf-8") != content:
            raise ValueError("refusing to overwrite a different existing artifact")
        return target
    # Only abandoned staging files owned by this immutable artifact are removed.
    for abandoned in destination.glob(f".m2-{identity}-*.tmp"):
        abandoned.unlink()
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=destination,
                                         prefix=f".m2-{identity}-", suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        checkpoint("after_stage_output")
        os.replace(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return target

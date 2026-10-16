"""Explicit claims, full dependency versions, one transaction, immutable replay."""
import hashlib
from collections import defaultdict
from pathlib import Path
from uuid import uuid4

from pydantic import TypeAdapter

from ...foundation.inputs import canonical, digest, parse_json
from ...foundation.models import VersionName
from ...foundation.runner import publish, _output_path as output_path
from ...foundation.store import now
from .models import Catalog, Submission
from .store import result_version
from .validation import validate_submission


def checkpoint(stage):
    """Lifecycle boundary for interruption instrumentation."""


def version_manifest(catalog, revision):
    TypeAdapter(VersionName).validate_python(revision)
    root = Path(__file__).resolve().parents[2]
    paths = sorted(Path(__file__).resolve().parent.glob("*.py")) + [
        root / "role_classification" / name for name in ("models.py", "validation.py", "proposals/models.py")
    ] + [root / "foundation" / name for name in ("inputs.py", "models.py", "store.py", "runner.py")
    ] + [root / "semantics/models.py"]
    return dict(schema_version="b32-manifest-1", revision=revision, catalog=catalog,
        source_sha256={p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
        evidence_policy="exact-source-character-spans-v1", interpretation="explicit_pending_claims_only",
        formal_admission="disabled")


def execute(store, batch, submission, catalog, *, revision="v1", output=None, input_paths=()):
    bodies = validate_submission(batch, submission, catalog)
    config = Catalog.model_validate(catalog).model_dump()
    marks = Submission.model_validate(submission).model_dump()
    manifest = version_manifest(config, revision)
    version, run_id = digest(manifest), uuid4().hex
    protected = [str(Path(p).resolve()) for p in (batch.path, *input_paths)]
    destination = output_path(store, output, batch.path) if output is not None else None
    if destination is not None:
        for path in protected:
            output_path(store, destination, Path(path))
    members = []
    # Full submission hash conservatively invalidates results after any claim/catalogue ambiguity change.
    claims_hash = digest(marks)
    with store.conn:
        store.conn.execute("INSERT OR IGNORE INTO b32_versions VALUES (?,?)", (version, canonical(manifest)))
        store.conn.execute("INSERT INTO b32_inputs VALUES (?,?,?,?)", (run_id, str(batch.path), batch.digest, batch.raw_bytes))
        for position, (record, body) in enumerate(zip(batch.records, bodies, strict=True), 1):
            store.conn.execute("INSERT OR IGNORE INTO snapshots(namespace,jd_id,fingerprint,payload) VALUES (?,?,?,?)",
                (record.namespace, record.jd_id, record.fingerprint, record.payload_json))
            snapshot = store.conn.execute("SELECT id,payload FROM snapshots WHERE namespace=? AND jd_id=? AND fingerprint=?",
                (record.namespace, record.jd_id, record.fingerprint)).fetchone()
            if snapshot["payload"] != record.payload_json:
                raise ValueError("snapshot integrity mismatch")
            saved = store.conn.execute("SELECT * FROM b32_results WHERE snapshot_id=? AND claims_sha256=? AND version_id=?",
                (snapshot["id"], claims_hash, version)).fetchone()
            if saved:
                if digest(parse_json(saved["body"])) != saved["sha256"] or parse_json(saved["body"]) != body:
                    raise ValueError("candidate result integrity mismatch")
                identity = saved["id"]
            else:
                identity = uuid4().hex
                store.conn.execute("INSERT INTO b32_results VALUES (?,?,?,?,?,?,?)",
                    (identity, snapshot["id"], claims_hash, version, canonical(body), digest(body), now()))
            members.append(dict(namespace=record.namespace, jd_id=record.jd_id, fingerprint=record.fingerprint,
                input_position=position, observation=record.observation, snapshot_id=snapshot["id"],
                result_id=identity, result_version=result_version(version, claims_hash, digest(body)), reused=saved is not None, body=body))
            checkpoint("after_result")
        names = defaultdict(set)
        for body in bodies:
            for claim in body["candidates"]:
                for name in (claim["raw_name"], claim["proposed_name"]):
                    if name:
                        names[name.strip().casefold()].add(claim["id"])
        catalog_audit = [dict(reason="name_has_multiple_candidates", name=name, candidate_ids=sorted(ids))
                         for name, ids in sorted(names.items()) if len(ids) > 1]
        result = dict(run_id=run_id, schema_version="b32-report-1", mode="offline_explicit_candidate_governance",
            input_path=str(batch.path), input_paths=protected, input_sha256=batch.digest, dataset=batch.namespace,
            submission=marks, submission_sha256=claims_hash, manifest=manifest, version_id=version, members=members,
            catalog_audit=catalog_audit,
            audit=dict(jd_records=len(members), candidate_claims=sum(len(b["candidates"]) for b in bodies),
                relation_claims=sum(len(b["relations"]) for b in bodies)), formal_jobs=[], formal_admitted=False,
            classification_complete=False, formal_statistics_eligible=False, semantic_validation="not_performed", created_at=now())
        store.conn.execute("INSERT INTO b32_reports VALUES (?,?,?)", (run_id, canonical(result), digest(result)))
        checkpoint("before_commit")
    checkpoint("after_commit")
    if destination is not None:
        publish(result, destination, run_id)
        checkpoint("after_output")
    return result


def replay(store, run_id):
    row = store.conn.execute("SELECT body,sha256 FROM b32_reports WHERE run_id=?", (run_id,)).fetchone()
    export = False
    if row is None:
        row = store.conn.execute("SELECT body,sha256 FROM b32_exports WHERE id=?", (run_id,)).fetchone()
        export = True
    if row is None:
        raise ValueError("candidate report/export not found")
    result = parse_json(row["body"])
    if digest(result) != row["sha256"]:
        raise ValueError("candidate report integrity mismatch")
    source_run = result["source_run_id"] if export else run_id
    source = store.conn.execute("SELECT raw_bytes,sha256 FROM b32_inputs WHERE run_id=?", (source_run,)).fetchone()
    if source is None or hashlib.sha256(source["raw_bytes"]).hexdigest() != source["sha256"] or source["sha256"] != result["input_sha256"]:
        raise ValueError("candidate input integrity mismatch")
    return result


def review_export(store, run_id):
    report = replay(store, run_id)
    if report["schema_version"] != "b32-report-1":
        raise ValueError("review export requires an original candidate run")
    identity = "reviews-" + uuid4().hex
    result = dict(run_id=identity, export_id=identity, source_run_id=run_id, schema_version="b32-review-export-1",
        version_id=report["version_id"], input_paths=report["input_paths"], input_sha256=report["input_sha256"],
        members=[dict(result_id=m["result_id"], body=m["body"], reviews=store.reviews(m["result_id"])) for m in report["members"]],
        formal_jobs=[], formal_admitted=False, formal_statistics_eligible=False, created_at=now())
    with store.conn:
        store.conn.execute("INSERT INTO b32_exports VALUES (?,?,?,?)", (identity, run_id, canonical(result), digest(result)))
    return result

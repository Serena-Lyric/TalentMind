"""Explicit assertions only; whole-run transaction then immutable publication."""
import hashlib
from pathlib import Path
from uuid import uuid4

from pydantic import TypeAdapter

from ..foundation.inputs import InputRecord, canonical, check_public, digest, parse_json
from ..foundation.models import VersionName
from ..foundation.runner import publish, _output_path as output_path
from ..foundation.store import now
from .models import AnnotationBatch, Taxonomy
from .validation import validate_annotation


def checkpoint(stage):
    """Lifecycle boundary for local interruption instrumentation."""


def version_manifest(taxonomy, revision):
    TypeAdapter(VersionName).validate_python(revision)
    root = Path(__file__).resolve().parent
    paths = sorted(root.glob("*.py")) + [root.parent / "foundation" / name for name in
        ("inputs.py", "models.py", "store.py", "runner.py")] + [root.parent / "semantics" / "models.py"]
    sources = {p.relative_to(root.parent).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    return dict(schema_version="b30-1", revision=revision, taxonomy=taxonomy,
                source_sha256=sources, evidence_policy="exact-source-character-spans-v1")


def execute(store, batch, annotations, taxonomy, *, revision="v1", output=None, input_paths=()):
    check_public(taxonomy)
    config = Taxonomy.model_validate(taxonomy).model_dump()
    check_public(annotations)
    marks = AnnotationBatch.model_validate(dict(schema_version="b30-annotations-1", annotations=annotations)).annotations
    text = batch.raw_bytes.decode("utf-8-sig")
    rows = (parse_json(text) if batch.path.suffix.lower() == ".json" else
            [parse_json(line) for line in text.splitlines() if line.strip()] if batch.path.suffix.lower() == ".jsonl" else None)
    if not isinstance(rows, list) or tuple(InputRecord.from_row(batch.namespace, row) for row in rows) != batch.records:
        raise ValueError("source bytes do not match input records")
    records = {}
    for record in batch.records:
        # Public Python callers receive the same validation as JSON callers.
        restored = InputRecord.from_row(batch.namespace, dict(record.payload, id=record.jd_id, crawled_at=record.observation))
        if record.namespace != batch.namespace or restored != record or record.jd_id in records:
            raise ValueError("invalid or duplicate source identity")
        records[record.jd_id] = record
    if not records:
        raise ValueError("explicit nonempty input required")
    validated = {}
    supplied = {}
    for mark in marks:
        if mark.jd_id not in records or mark.jd_id in validated:
            raise ValueError("foreign or duplicate annotation identity")
        body = validate_annotation(records[mark.jd_id], mark.model_dump(), config)
        validated[mark.jd_id], supplied[mark.jd_id] = body, mark.model_dump()
    destination = output_path(store, output, batch.path) if output is not None else None
    protected = [str(Path(p).resolve()) for p in (batch.path, *input_paths)]
    if destination is not None:
        for path in protected:
            output_path(store, destination, Path(path))
    manifest = version_manifest(config, revision)
    version, run_id = digest(manifest), uuid4().hex
    members = []
    # No running state: before commit nothing exists; after commit replay publishes the original report.
    with store.conn:
        store.conn.execute("INSERT OR IGNORE INTO b30_versions VALUES (?,?)", (version, canonical(manifest)))
        store.conn.execute("INSERT INTO b30_inputs VALUES (?,?,?,?)", (run_id, str(batch.path), batch.digest, batch.raw_bytes))
        for record in batch.records:
            store.conn.execute("INSERT OR IGNORE INTO snapshots(namespace,jd_id,fingerprint,payload) VALUES (?,?,?,?)",
                (record.namespace, record.jd_id, record.fingerprint, record.payload_json))
            snapshot = store.conn.execute("SELECT id,payload FROM snapshots WHERE namespace=? AND jd_id=? AND fingerprint=?",
                (record.namespace, record.jd_id, record.fingerprint)).fetchone()
            if snapshot["payload"] != record.payload_json:
                raise ValueError("snapshot integrity mismatch")
            annotation_hash = digest(supplied.get(record.jd_id))
            saved = store.conn.execute("SELECT * FROM b30_results WHERE snapshot_id=? AND annotation_sha256=? AND version_id=?",
                (snapshot["id"], annotation_hash, version)).fetchone()
            body = validated.get(record.jd_id)
            if saved:
                if digest(parse_json(saved["body"])) != saved["sha256"] or parse_json(saved["body"]) != body:
                    raise ValueError("role result integrity mismatch")
                result_id = saved["id"]
            else:
                result_id = uuid4().hex
                store.conn.execute("INSERT INTO b30_results VALUES (?,?,?,?,?,?,?)", (result_id, snapshot["id"],
                    annotation_hash, version, canonical(body), digest(body), now()))
            members.append(dict(namespace=record.namespace, jd_id=record.jd_id, fingerprint=record.fingerprint,
                snapshot_id=snapshot["id"], result_id=result_id, reused=saved is not None, observation=record.observation,
                status="assertion_saved" if body is not None else "not_annotated", body=body))
            checkpoint("after_result")
        result = dict(run_id=run_id, schema_version="b30-report-1", mode="offline_role_assertions",
            input_path=str(batch.path), input_paths=protected, input_sha256=batch.digest, dataset=batch.namespace,
            annotations_sha256=digest([m.model_dump() for m in marks]), version_id=version, manifest=manifest,
            members=members, audit=dict(jd_records=len(members), assertion_saved=len(validated),
                                       not_annotated=len(members) - len(validated)),
            formal_statistics_eligible=False, semantic_validation="not_performed", created_at=now())
        store.conn.execute("INSERT INTO b30_reports VALUES (?,?,?)", (run_id, canonical(result), digest(result)))
        checkpoint("before_commit")
    checkpoint("after_commit")
    if destination is not None:
        publish(result, destination, run_id)
        checkpoint("after_output")
    return result


def replay(store, run_id):
    row = store.conn.execute("SELECT body,sha256 FROM b30_reports WHERE run_id=?", (run_id,)).fetchone()
    if row is None:
        raise ValueError("role report not found")
    result = parse_json(row["body"])
    if digest(result) != row["sha256"]:
        raise ValueError("role report integrity mismatch")
    source = store.conn.execute("SELECT raw_bytes,sha256 FROM b30_inputs WHERE run_id=?", (run_id,)).fetchone()
    if source is None or hashlib.sha256(source["raw_bytes"]).hexdigest() != source["sha256"] or source["sha256"] != result["input_sha256"]:
        raise ValueError("role input integrity mismatch")
    return result

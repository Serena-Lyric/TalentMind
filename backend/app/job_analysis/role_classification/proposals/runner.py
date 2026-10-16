"""Whole-run transactions, explicit snapshots, versioned suggestions and exact replay."""
import hashlib
from pathlib import Path
from uuid import uuid4

from pydantic import TypeAdapter

from ...foundation.inputs import InputRecord, canonical, check_public, digest, parse_json
from ...foundation.models import VersionName
from ...foundation.runner import publish, _output_path as output_path
from ...foundation.store import now
from .models import FamilyTaxonomy, validate_proposal
from .rules import suggest


def checkpoint(stage):
    """Lifecycle boundary for local interruption instrumentation."""


def version_manifest(taxonomy, revision):
    TypeAdapter(VersionName).validate_python(revision)
    root = Path(__file__).resolve().parents[2]
    paths = sorted(Path(__file__).parent.glob("*.py")) + [
        root / "role_classification" / name for name in ("models.py", "validation.py")
    ] + [root / "foundation" / name for name in ("inputs.py", "models.py", "store.py", "runner.py")
    ] + [root / "semantics/models.py"]
    sources = {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    return dict(schema_version="b31-manifest-1", revision=revision, taxonomy=taxonomy,
        source_sha256=sources, evidence_policy="exact-source-character-spans-v1",
        interpretation="finite_pending_family_suggestions")


def _validate_batch(batch):
    if not isinstance(batch.namespace, str) or not batch.namespace.strip():
        raise ValueError("explicit dataset namespace required")
    text = batch.raw_bytes.decode("utf-8-sig")
    rows = (parse_json(text) if batch.path.suffix.lower() == ".json" else
            [parse_json(line) for line in text.splitlines() if line.strip()] if batch.path.suffix.lower() == ".jsonl" else None)
    if not isinstance(rows, list) or not rows:
        raise ValueError("explicit nonempty snapshot required")
    restored = tuple(InputRecord.from_row(batch.namespace, row) for row in rows)
    if restored != batch.records or len({r.jd_id for r in restored}) != len(restored):
        raise ValueError("source bytes, identity and input records do not match")


def execute(store, batch, taxonomy, *, revision="v1", output=None, input_paths=()):
    check_public(taxonomy)
    config = FamilyTaxonomy.model_validate(taxonomy).model_dump()
    _validate_batch(batch)
    protected = [str(Path(p).resolve()) for p in (batch.path, *input_paths)]
    destination = output_path(store, output, batch.path) if output is not None else None
    if destination is not None:
        for path in protected:
            output_path(store, destination, Path(path))
    manifest = version_manifest(config, revision)
    version, run_id = digest(manifest), uuid4().hex
    members = []
    with store.conn:
        store.conn.execute("INSERT OR IGNORE INTO b31_versions VALUES (?,?)", (version, canonical(manifest)))
        store.conn.execute("INSERT INTO b31_inputs VALUES (?,?,?,?)", (run_id, str(batch.path), batch.digest, batch.raw_bytes))
        for position, record in enumerate(batch.records, 1):
            store.conn.execute("INSERT OR IGNORE INTO snapshots(namespace,jd_id,fingerprint,payload) VALUES (?,?,?,?)",
                (record.namespace, record.jd_id, record.fingerprint, record.payload_json))
            snapshot = store.conn.execute("SELECT id,payload FROM snapshots WHERE namespace=? AND jd_id=? AND fingerprint=?",
                (record.namespace, record.jd_id, record.fingerprint)).fetchone()
            if snapshot["payload"] != record.payload_json:
                raise ValueError("snapshot integrity mismatch")
            saved = store.conn.execute("SELECT * FROM b31_results WHERE snapshot_id=? AND version_id=?",
                (snapshot["id"], version)).fetchone()
            if saved:
                body = parse_json(saved["body"])
                if digest(body) != saved["sha256"]:
                    raise ValueError("suggestion result integrity mismatch")
                validate_proposal(record, body, config)
                result_id = saved["id"]
            else:
                body = validate_proposal(record, suggest(record, config), config)
                result_id = uuid4().hex
                store.conn.execute("INSERT INTO b31_results VALUES (?,?,?,?,?,?)",
                    (result_id, snapshot["id"], version, canonical(body), digest(body), now()))
            members.append(dict(namespace=record.namespace, jd_id=record.jd_id, fingerprint=record.fingerprint,
                input_position=position, observation=record.observation, snapshot_id=snapshot["id"],
                result_id=result_id, reused=saved is not None, body=body))
            checkpoint("after_result")
        result = dict(run_id=run_id, schema_version="b31-report-1", mode="offline_pending_family_suggestions",
            input_path=str(batch.path), input_paths=protected, input_sha256=batch.digest, dataset=batch.namespace,
            version_id=version, manifest=manifest, members=members,
            audit=dict(jd_records=len(members), with_family_candidates=sum(bool(m["body"]["candidates"]) for m in members),
                       unresolved=sum(m["body"]["resolution"] == "unresolved" for m in members)),
            review_status="pending_review", classification_complete=False, formal_statistics_eligible=False, created_at=now())
        store.conn.execute("INSERT INTO b31_reports VALUES (?,?,?)", (run_id, canonical(result), digest(result)))
        checkpoint("before_commit")
    checkpoint("after_commit")
    if destination is not None:
        publish(result, destination, run_id)
        checkpoint("after_output")
    return result


def replay(store, run_id):
    row = store.conn.execute("SELECT body,sha256 FROM b31_reports WHERE run_id=?", (run_id,)).fetchone()
    if row is None:
        raise ValueError("suggestion report not found")
    result = parse_json(row["body"])
    if digest(result) != row["sha256"]:
        raise ValueError("suggestion report integrity mismatch")
    source = store.conn.execute("SELECT raw_bytes,sha256 FROM b31_inputs WHERE run_id=?", (run_id,)).fetchone()
    if source is None or hashlib.sha256(source["raw_bytes"]).hexdigest() != source["sha256"] or source["sha256"] != result["input_sha256"]:
        raise ValueError("suggestion input integrity mismatch")
    return result

"""Read-only integrity/leakage audit. Reports no private text or semantic score."""
import hashlib
from pathlib import Path
import re
import unicodedata
import zipfile

from ..foundation.inputs import InputRecord, check_public, digest, parse_json


class BundleError(ValueError):
    """Only literal safe diagnostic codes may cross the CLI boundary."""


def body_key(text):
    """Exact normalized body only; near-duplicate/translation leakage needs human review."""
    text = text.split("职位描述:", 1)[-1].split("公司简介:", 1)[0]
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", text)).casefold()


def audit_bundle(manifest_path, archive=None, *, sample_ids=None):
    manifest_path = Path(manifest_path).resolve()
    root = manifest_path.parent
    manifest = parse_json(manifest_path.read_text(encoding="utf-8-sig"))
    check_public(manifest)
    if manifest["schema_version"] != "m2-p0-bundle-0.1" or not manifest["version"].strip():
        raise BundleError("unsupported_bundle_version")
    samples = manifest["samples"]
    selected_files = None
    if sample_ids is not None:
        if not sample_ids or len(set(sample_ids)) != len(sample_ids):
            raise BundleError("invalid_sample_selection")
        samples = [s for s in samples if s["id"] in sample_ids]
        if len(samples) != len(sample_ids) or {s["id"] for s in samples} != set(sample_ids):
            raise BundleError("unknown_or_duplicate_selected_sample")
        selected_files = {s[key] for s in samples for key in ("snapshot", "annotation")}
    verified = {}
    for name, sha in manifest["files"].items():
        if selected_files is not None and name not in selected_files:
            continue
        path = (root / name).resolve()
        if not path.is_relative_to(root) or path == root or Path(name).is_absolute():
            raise BundleError("bundle_path_escapes_private_root")
        if not path.is_file():
            raise BundleError("bundle_artifact_missing")
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != sha:
            raise BundleError("bundle_artifact_digest_mismatch")
        verified[name] = raw
    records = None
    if archive is not None:
        archive = Path(archive)
        if not archive.is_file():
            raise BundleError("source_archive_missing")
        if hashlib.sha256(archive.read_bytes()).hexdigest() != manifest["archive_sha256"]:
            raise BundleError("source_archive_digest_mismatch")
        with zipfile.ZipFile(archive) as z:
            records = {r["sha256"]: r for r in map(parse_json, z.read("records.jsonl").decode("utf-8").splitlines())}
    identities, bodies, visited_ids = {}, {}, set()
    counts = dict(samples=0, development=0, holdout=0, human_reviewed=0, semantic_metrics="not_computable")
    for sample in samples:
        sid, split = sample["id"], sample["split"]
        if sid in visited_ids or split not in {"development", "holdout"}:
            raise BundleError("duplicate_sample_or_invalid_split")
        visited_ids.add(sid)
        if sample["snapshot"] not in verified or sample["annotation"] not in verified:
            raise BundleError("sample_artifacts_must_be_hash_bound")
        row = parse_json(verified[sample["snapshot"]].decode("utf-8-sig"))
        record = InputRecord.from_row(manifest["namespace"], row)
        if record.fingerprint != sample.get("input_sha256"):
            raise BundleError("sample_input_version_mismatch")
        identity, body = (record.namespace, record.jd_id), body_key(row["raw_text"])
        if identities.get(identity, split) != split or bodies.get(body, split) != split:
            raise BundleError("cross_split_identity_body_leakage")
        identities[identity], bodies[body] = split, split
        if records is not None:
            original = records.get(sample.get("archive_record_sha256"))
            payload = {k: v for k, v in row.items() if k not in {"crawled_at", "captured_at"}}
            if not original or original["payload"] != payload or digest({"source": original["source"], "payload": payload}) != original["sha256"]:
                raise BundleError("snapshot_does_not_match_archived_source")
        ann = parse_json(verified[sample["annotation"]].decode("utf-8-sig"))
        check_public(ann)
        if ann.get("input_sha256") != record.fingerprint:
            raise BundleError("annotation_input_version_mismatch")
        for label in ann.get("human_labels", []):
            for ev in label.get("evidence", []):
                field, start, end = ev.get("field"), ev.get("start"), ev.get("end")
                if (field not in {"job_title", "raw_text", "duties", "experience", "requirements"}
                        or type(start) is not int or type(end) is not int
                        or ev.get("input_sha256") != record.fingerprint
                        or not 0 <= start < end <= len(row.get(field, ""))
                        or row.get(field, "")[start:end] != ev.get("quote")):
                    raise BundleError("annotation_evidence_mismatch")
        if ann["sample_id"] != sid or ann["status"] not in {"pending", "partial", "disputed", "human_reviewed"}:
            raise BundleError("annotation_identity_status_mismatch")
        if ann["status"] == "human_reviewed":
            required = ("reviewer", "reviewed_at", "confirmation_source")
            if not all(isinstance(ann.get(k), str) and ann[k].strip() for k in required) or ann.get("scope") != "full_input" or ann.get("disputes"):
                raise BundleError("human_truth_requires_actual_review_attribution_complete_scope_and_resolved_disputes")
            # An attestation is auditable metadata, not authentication or proof of semantic correctness.
            counts["human_reviewed"] += 1
        elif ann["status"] == "pending" and ann.get("human_labels"):
            raise BundleError("pending_drafts_cannot_contain_human_truth_labels")
        counts["samples"] += 1
        counts[split] += 1
    if not counts["samples"]:
        raise BundleError("empty_evaluation_bundle")
    if sample_ids is not None:
        counts.update(audit_scope=sorted(sample_ids), integrity_scope="selected_snapshot_and_annotation_files_only")
    return counts

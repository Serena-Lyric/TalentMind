"""Read-only integrity/leakage audit. Reports no private text or semantic score."""
import hashlib
from pathlib import Path
import re
import unicodedata
import zipfile

from ..foundation.inputs import InputRecord, check_public, digest, parse_json


def body_key(text):
    """Exact normalized body only; near-duplicate/translation leakage needs human review."""
    text = text.split("职位描述:", 1)[-1].split("公司简介:", 1)[0]
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", text)).casefold()


def audit_bundle(manifest_path, archive=None):
    manifest_path = Path(manifest_path).resolve()
    root = manifest_path.parent
    manifest = parse_json(manifest_path.read_text(encoding="utf-8-sig"))
    check_public(manifest)
    if manifest["schema_version"] != "m2-p0-bundle-0.1" or not manifest["version"].strip():
        raise ValueError("unsupported bundle version")
    verified = {}
    for name, sha in manifest["files"].items():
        path = (root / name).resolve()
        if not path.is_relative_to(root) or path == root or Path(name).is_absolute():
            raise ValueError("bundle path escapes private root")
        if not path.is_file():
            raise ValueError("bundle artifact missing")
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != sha:
            raise ValueError("bundle artifact digest mismatch")
        verified[name] = raw
    records = None
    if archive is not None:
        archive = Path(archive)
        if not archive.is_file():
            raise ValueError("source archive missing")
        if hashlib.sha256(archive.read_bytes()).hexdigest() != manifest["archive_sha256"]:
            raise ValueError("source archive digest mismatch")
        with zipfile.ZipFile(archive) as z:
            records = {r["sha256"]: r for r in map(parse_json, z.read("records.jsonl").decode("utf-8").splitlines())}
    identities, bodies, sample_ids = {}, {}, set()
    counts = dict(samples=0, development=0, holdout=0, human_reviewed=0, semantic_metrics="not_computable")
    for sample in manifest["samples"]:
        sid, split = sample["id"], sample["split"]
        if sid in sample_ids or split not in {"development", "holdout"}:
            raise ValueError("duplicate sample or invalid split")
        sample_ids.add(sid)
        if sample["snapshot"] not in verified or sample["annotation"] not in verified:
            raise ValueError("sample artifacts must be hash-bound")
        row = parse_json(verified[sample["snapshot"]].decode("utf-8-sig"))
        record = InputRecord.from_row(manifest["namespace"], row)
        if "input_sha256" in sample and record.fingerprint != sample["input_sha256"]:
            raise ValueError("sample input version mismatch")
        identity, body = (row["source"], record.jd_id), body_key(row["raw_text"])
        if identities.get(identity, split) != split or bodies.get(body, split) != split:
            raise ValueError("cross-split identity/body leakage")
        identities[identity], bodies[body] = split, split
        if records is not None:
            original = records.get(sample.get("archive_record_sha256"))
            payload = {k: v for k, v in row.items() if k not in {"crawled_at", "captured_at"}}
            if not original or original["payload"] != payload or digest({"source": original["source"], "payload": payload}) != original["sha256"]:
                raise ValueError("snapshot does not match archived source")
        ann = parse_json(verified[sample["annotation"]].decode("utf-8-sig"))
        check_public(ann)
        if "input_sha256" in ann and ann["input_sha256"] != record.fingerprint:
            raise ValueError("annotation input version mismatch")
        if ann["sample_id"] != sid or ann["status"] not in {"pending", "partial", "disputed", "human_reviewed"}:
            raise ValueError("annotation identity/status mismatch")
        if ann["status"] == "human_reviewed":
            required = ("reviewer", "reviewed_at", "confirmation_source")
            if not all(isinstance(ann.get(k), str) and ann[k].strip() for k in required) or ann.get("scope") != "full_input" or ann.get("disputes"):
                raise ValueError("human truth requires actual review attribution, complete scope and resolved disputes")
            # An attestation is auditable metadata, not authentication or proof of semantic correctness.
            counts["human_reviewed"] += 1
        elif ann["status"] == "pending" and ann.get("human_labels"):
            raise ValueError("pending drafts cannot contain human truth labels")
        counts["samples"] += 1
        counts[split] += 1
    if not counts["samples"]:
        raise ValueError("empty evaluation bundle")
    return counts

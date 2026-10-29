"""Immutable evaluation-condition releases. Receipt binding is not identity authentication."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from ..foundation.inputs import InputRecord, check_public, parse_json
from .case_assertions import audit_case_assertions, require


DEV_IDS = [f"DEV-{i:02d}" for i in range(1, 9)]
APPROVAL_SCOPES = {"core_assertion_sets", "semantic_equivalence_scope_and_metric_denominators",
                   "minimal_supplement_strategy"}


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _json(raw):
    value = parse_json(raw.decode("utf-8-sig"))
    require(isinstance(value, dict), "approval_artifact_must_be_object")
    check_public(value)
    return value


def _payload_path(root, name):
    require(isinstance(name, str) and name and "\\" not in name and ":" not in name
            and "HOLD" not in name.upper(), "invalid_approved_payload_path")
    relative = PurePosixPath(name)
    require(not relative.is_absolute() and ".." not in relative.parts and relative.as_posix() == name
            and relative.suffix == ".json" and name not in {"index.json", "release.json", "source-index.json"},
            "invalid_approved_payload_path")
    path = root / name
    require(path.resolve() == path and path.is_relative_to(root), "approved_payload_path_redirected")
    return path


def _bound_material(index_path, manifest_path, approval_path):
    index_path, manifest_path, approval_path = map(Path, (index_path, manifest_path, approval_path))
    index_raw, approval_raw = index_path.read_bytes(), approval_path.read_bytes()
    index, approval = _json(index_raw), _json(approval_raw)
    require(approval.get("record_type") == "owner_signoff_receipt"
            and all(isinstance(approval.get(k), str) and approval[k].strip() for k in
                    ("owner_identity", "confirmation_source", "confirmation_quote",
                     "confirmation_date_client_timezone", "transcribed_at_utc")), "actual_owner_receipt_required")
    recorded = datetime.fromisoformat(approval["transcribed_at_utc"])
    require(recorded.tzinfo is not None, "approval_record_time_requires_timezone")
    scopes = approval.get("scope")
    require(isinstance(scopes, list) and all(isinstance(s, str) for s in scopes)
            and APPROVAL_SCOPES <= set(scopes), "approval_scope_incomplete")
    require(isinstance(index.get("version"), str) and index["version"].strip()
            and approval.get("approved_index_sha256") == _sha(index_raw)
            and approval.get("approved_version") == index.get("version"), "approval_not_bound_to_source_index")
    ids = approval.get("approved_sample_ids", DEV_IDS)
    require(ids == DEV_IDS or ids == DEV_IDS + ["DEV-09"], "unsupported_approved_sample_scope")
    if len(ids) == 9:
        derivation = approval.get("approval_derivation")
        require(isinstance(derivation, dict) and isinstance(derivation.get("generation_consent_quote"), str)
                and derivation["generation_consent_quote"].strip(), "supplement_derivation_consent_required")
    require(index.get("business_status") == "pending_review" and index.get("cases") == ids,
            "approved_source_must_be_exact_existing_DEV_draft")
    files = index.get("files")
    require(isinstance(files, dict) and {f"cases/{sid}.json" for sid in ids} <= files.keys(),
            "approved_case_files_missing")
    root = index_path.parent.resolve()
    # Check the entire registry before opening any payload, including non-case attachments.
    paths = {name: _payload_path(root, name) for name in files}
    require(index.get("source_manifest_sha256") == _sha(manifest_path.read_bytes()),
            "approved_manifest_version_mismatch")
    payloads = {}
    for name, path in paths.items():
        raw = path.read_bytes()
        require(_sha(raw) == files[name], "approved_payload_digest_mismatch")
        payloads[name] = raw
    if len(ids) == 9:
        _check_supplement_derivation(payloads, approval["approval_derivation"])
    counts, units = dict.fromkeys("ABCD", 0), 0
    for sid in ids:
        case = _json(payloads[f"cases/{sid}.json"])
        require(case.get("sample_id") == sid, "approved_case_identity_mismatch")
        result = audit_case_assertions(paths[f"cases/{sid}.json"], manifest_path,
                                       expected_case_raw=payloads[f"cases/{sid}.json"], allowed_sample_ids=ids)
        units += result["applicable_units"]
        for kind, count in result["assertions"].items():
            counts[kind] += count
    summary = dict(business_status="approved", samples=len(ids), assertions=counts,
                   applicable_units=units, semantic_result="not_run")
    return index, index_raw, approval_raw, payloads, summary


def _check_supplement_derivation(payloads, consent):
    """Only rebind the original eight manifests; DEV-09 must keep the signed map."""
    required = {"provenance/baseline-index.json", "provenance/supplement-map.json",
                "provenance/supplement-snapshot.json"}
    required.update(f"provenance/baseline-cases/{sid}.json" for sid in DEV_IDS)
    require(required <= payloads.keys(), "supplement_derivation_basis_missing")
    baseline_raw, map_raw = (payloads[name] for name in
                             ("provenance/baseline-index.json", "provenance/supplement-map.json"))
    require(_sha(baseline_raw) == consent.get("baseline_index_sha256")
            and _sha(map_raw) == consent.get("supplement_map_sha256"), "derived_approval_basis_mismatch")
    baseline, mapping = _json(baseline_raw), _json(map_raw)
    require(baseline.get("cases") == DEV_IDS, "invalid_baseline_approval_scope")
    for sid in DEV_IDS:
        raw = payloads[f"provenance/baseline-cases/{sid}.json"]
        require(_sha(raw) == baseline["files"][f"cases/{sid}.json"], "original_condition_basis_mismatch")
        old, new = _json(raw), _json(payloads[f"cases/{sid}.json"])
        old.pop("source_manifest_sha256", None)
        new.pop("source_manifest_sha256", None)
        require(old == new, "original_approved_conditions_changed")
    case = _json(payloads["cases/DEV-09.json"])
    snapshot_raw = payloads["provenance/supplement-snapshot.json"]
    require(_sha(snapshot_raw) == mapping.get("source_snapshot_sha256"), "signed_supplement_snapshot_mismatch")
    # fingerprint excludes id: bind identity separately to the already reviewed full snapshot.
    namespace = _json(payloads["provenance/baseline-cases/DEV-01.json"])["namespace"]
    record = InputRecord.from_row(namespace, _json(snapshot_raw))
    require(case.get("namespace") == namespace and case.get("jd_id") == record.jd_id
            and case.get("input_sha256") == record.fingerprint, "signed_supplement_identity_mismatch")
    require(mapping.get("proposed_sample_id") == case.get("sample_id") == "DEV-09"
            and mapping.get("input_sha256") == case.get("input_sha256")
            and mapping.get("content_version") == case.get("input_version")
            and mapping.get("coverage") == case.get("coverage"), "supplement_map_binding_mismatch")
    keys = ("id", "class", "unit_ids", "support_unit_ids", "criterion", "equivalence_rule", "evidence")
    projection = lambda assertions: [{k: a[k] for k in keys} for a in assertions]
    require(projection(mapping["assertions"]) == projection(case["assertions"]), "signed_supplement_conditions_changed")


def audit_approved_assertions(release_path, manifest_path, approval_path):
    """Read only; the caller supplies the separately trusted owner receipt explicitly."""
    release_path = Path(release_path).resolve()
    release = _json(release_path.read_bytes())
    require(release.get("schema_version") == "p0-approved-assertions-1"
            and release.get("business_status") == "approved"
            and release.get("cases") in (DEV_IDS, DEV_IDS + ["DEV-09"])
            and release.get("source_index_file") == "source-index.json"
            and release.get("condition_files") == [f"cases/{sid}.json" for sid in release["cases"]]
            and release.get("process_files_do_not_override_conditions") is True
            and release.get("approval_scope") == "evaluation_conditions_only_not_knowledge_or_P0_closure"
            and isinstance(release.get("version"), str) and release["version"].strip(),
            "invalid_approved_release")
    index_path = release_path.parent / "source-index.json"
    require(index_path.resolve() == index_path, "approved_index_path_redirected")
    index, raw, approval_raw, _, summary = _bound_material(index_path, manifest_path, approval_path)
    require(release.get("source_index_sha256") == _sha(raw)
            and release["cases"] == index["cases"]
            and release.get("approval_sha256") == _sha(approval_raw)
            and release.get("source_manifest_sha256") == index["source_manifest_sha256"],
            "approved_release_binding_mismatch")
    return {"version": release["version"], **summary}


def create_approved_assertions(index_path, manifest_path, approval_path, output_dir,
                               *, version=None):
    """Create a new directory only. No automatic approval or modification of source data."""
    index_path, output_dir = Path(index_path).resolve(), Path(output_dir).absolute()
    require(output_dir.resolve() == output_dir and not output_dir.is_relative_to(index_path.parent),
            "approved_output_must_not_replace_source")
    if output_dir.exists():
        raise FileExistsError("approved_output_already_exists")
    index, index_raw, approval_raw, payloads, _ = _bound_material(index_path, manifest_path, approval_path)
    version = version if version is not None else f"p0-case-map-{2 if len(index['cases']) == 9 else 1}-approved"
    require(isinstance(version, str) and version.strip(), "approved_version_required")
    release = dict(schema_version="p0-approved-assertions-1", version=version, business_status="approved",
                   source_index_file="source-index.json", source_index_sha256=_sha(index_raw),
                   approval_sha256=_sha(approval_raw), source_manifest_sha256=index["source_manifest_sha256"],
                   cases=index["cases"], created_at=datetime.now(timezone.utc).isoformat(),
                   condition_files=[f"cases/{sid}.json" for sid in index["cases"]],
                   process_files_do_not_override_conditions=True,
                   approval_scope="evaluation_conditions_only_not_knowledge_or_P0_closure")
    output_dir.mkdir(parents=True, exist_ok=False)
    for name, raw in payloads.items():
        target = output_dir / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    (output_dir / "source-index.json").write_bytes(index_raw)
    # Written last: an interrupted copy has no valid release marker and is never auto-reused.
    (output_dir / "release.json").write_text(json.dumps(release, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return audit_approved_assertions(output_dir / "release.json", manifest_path, approval_path)

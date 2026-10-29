"""P0 proposal provenance checks, not a semantic grader or human approval mechanism."""
import hashlib
from pathlib import Path

from ..foundation.inputs import InputRecord, check_public, parse_json
from .bundle import audit_bundle


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def validate_case_assertions(case, row, annotation_raw):
    """Bind proposals to supplied source; the file reader audits registered annotations first."""
    check_public(case)
    annotation = parse_json(annotation_raw.decode("utf-8-sig"))
    require(isinstance(case, dict) and isinstance(annotation, dict), "invalid_case_structure")
    require(case.get("schema_version") == "p0-case-assertions-1", "unsupported_case_version")
    require(case.get("business_status") == "pending_review", "case_proposals_are_not_approved_truth")
    require(isinstance(case.get("input_version"), str) and case["input_version"].strip(), "case_content_version_missing")
    record = InputRecord.from_row(case["namespace"], row)
    require(case["jd_id"] == record.jd_id and case["sample_id"] == annotation["sample_id"], "case_identity_mismatch")
    require(case["input_sha256"] == annotation["input_sha256"] == record.fingerprint, "case_input_version_mismatch")
    require(case["annotation_sha256"] == hashlib.sha256(annotation_raw).hexdigest(), "case_annotation_digest_mismatch")
    require(annotation["status"] == "human_reviewed" and case["annotation_version"] == annotation["annotation_version"], "case_annotation_status_or_version_mismatch")
    units = {u["unit_id"]: u for u in annotation["human_labels"]}
    require(len(units) == len(annotation["human_labels"]), "duplicate_annotation_unit")
    applicable = {k for k, u in units.items() if u["dimension"] in {"duty", "requirement"}}
    coverage = case["coverage"]
    require(isinstance(coverage, dict) and set(coverage) == applicable and set(coverage.values()) <= {"A", "D"}, "incomplete_or_invalid_coverage_partition")
    counts, assigned, seen = dict.fromkeys("ABCD", 0), {"A": set(), "D": set()}, set()
    for assertion in case["assertions"]:
        aid, kind = assertion["id"], assertion["class"]
        require(isinstance(aid, str) and aid.strip() and aid not in seen and kind in counts, "invalid_or_duplicate_assertion")
        seen.add(aid)
        ids, support, evidence_ids = assertion["unit_ids"], assertion["support_unit_ids"], assertion["evidence_unit_ids"]
        require(all(isinstance(v, list) and all(isinstance(i, str) for i in v) for v in (ids, support, evidence_ids)), "invalid_assertion_unit_lists")
        require(ids and set(ids + support) <= units.keys() and len(ids) == len(set(ids)), "unknown_or_duplicate_assertion_unit")
        if "source_summaries" in assertion:
            require(assertion["source_summaries"] == {uid: units[uid].get("text", units[uid].get("judgment", "")) for uid in ids}, "copied_human_source_summary_mismatch")
        require(evidence_ids and set(evidence_ids) <= set(ids + support), "unbound_assertion_evidence_units")
        require(all(isinstance(assertion.get(k), str) and assertion[k].strip() for k in ("criterion", "equivalence_rule")), "missing_assertion_criterion_or_alignment_rule")
        expected = []
        for uid in evidence_ids:
            for ev in units[uid].get("evidence", []):
                if ev not in expected:
                    expected.append(ev)
        require(expected and assertion["evidence"] == expected, "assertion_evidence_does_not_match_human_source")
        for ev in expected:
            text = record.payload.get(ev["field"], "")
            require(type(ev["start"]) is int and type(ev["end"]) is int and 0 <= ev["start"] < ev["end"] <= len(text)
                    and ev["input_sha256"] == record.fingerprint and text[ev["start"]:ev["end"]] == ev["quote"], "assertion_source_evidence_mismatch")
        if kind in assigned:
            assigned[kind].update(set(ids) & applicable)
        counts[kind] += 1
    require(all(assigned[k] == {i for i, c in coverage.items() if c == k} for k in assigned), "assertion_coverage_class_mismatch")
    return dict(sample_id=case["sample_id"], assertions=counts, applicable_units=len(applicable), business_status="pending_review", semantic_result="not_run")


def audit_case_assertions(case_path, manifest_path):
    case = parse_json(Path(case_path).read_text(encoding="utf-8-sig"))
    require(isinstance(case, dict) and case.get("sample_id") in {f"DEV-{i:02d}" for i in range(1, 9)}, "case_scope_must_be_existing_DEV")
    manifest_path = Path(manifest_path).resolve()
    raw = manifest_path.read_bytes()
    manifest = parse_json(raw.decode("utf-8-sig"))
    require(case.get("source_manifest_sha256") == hashlib.sha256(raw).hexdigest(), "case_manifest_version_mismatch")
    sid = case["sample_id"]
    audit_bundle(manifest_path, sample_ids=[sid])
    sample = next(s for s in manifest["samples"] if s["id"] == sid)
    require(case["input_version"] == sample["content_version"], "case_content_version_mismatch")
    require(case["namespace"] == manifest["namespace"], "case_namespace_mismatch")
    row = parse_json((manifest_path.parent / sample["snapshot"]).read_text(encoding="utf-8-sig"))
    return validate_case_assertions(case, row, (manifest_path.parent / sample["annotation"]).read_bytes())

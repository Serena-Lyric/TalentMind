"""Validate source spans; preserve claims and complete context without semantic promotion."""
from collections import defaultdict

from ...foundation.inputs import InputRecord, check_public, parse_json
from ..proposals.models import resolve_taxonomy
from ..validation import _field_evidence, validate_evidence
from .models import Catalog, Submission


def validate_batch(batch):
    if not isinstance(batch.namespace, str) or not batch.namespace.strip():
        raise ValueError("explicit dataset required")
    text = batch.raw_bytes.decode("utf-8-sig")
    rows = (parse_json(text) if batch.path.suffix.lower() == ".json" else
            [parse_json(line) for line in text.splitlines() if line.strip()] if batch.path.suffix.lower() == ".jsonl" else None)
    if not isinstance(rows, list) or not rows:
        raise ValueError("explicit nonempty snapshot required")
    restored = tuple(InputRecord.from_row(batch.namespace, row) for row in rows)
    if restored != batch.records or len({r.jd_id for r in restored}) != len(restored):
        raise ValueError("snapshot bytes and records mismatch")


def validate_submission(batch, submission, catalog, *, taxonomy=None):
    families = {f["id"] for f in resolve_taxonomy(taxonomy)["job_family"]}
    check_public(catalog)
    config = Catalog.model_validate(catalog)
    check_public(submission)
    marks = Submission.model_validate(submission)
    validate_batch(batch)
    records = {r.jd_id: r for r in batch.records}
    annotations, all_ids = {}, set()
    for mark in marks.annotations:
        record = records.get(mark.jd_id)
        if record is None or mark.jd_id in annotations or (mark.namespace, mark.fingerprint) != (record.namespace, record.fingerprint):
            raise ValueError("foreign or duplicate annotation")
        ids = [c.id for c in mark.candidates] + [r.id for r in mark.relations]
        if len(ids) != len(set(ids)) or all_ids.intersection(ids):
            raise ValueError("duplicate stable candidate/relation ID")
        all_ids.update(ids)
        annotations[mark.jd_id] = mark
    bodies = []
    for record in batch.records:
        mark = annotations.get(record.jd_id)
        candidates, relations, reasons = [], [], ["formal_release_policy_unconfirmed"]
        if mark is None:
            reasons.append("not_submitted")
        else:
            ids = {c.id for c in mark.candidates}
            for claim in mark.candidates:
                if len(set(claim.family_candidates)) != len(claim.family_candidates) or not set(claim.family_candidates) <= families:
                    raise ValueError("invalid or duplicate family candidate")
                if claim.synthetic_only != (claim.origin == "synthetic_assertion") or (marks.mode == "synthetic_only" and not claim.synthetic_only):
                    raise ValueError("synthetic claims must be isolated")
                for ref in [*claim.name_evidence, *claim.evidence]:
                    validate_evidence(record, ref.model_dump())
                if not any(ref.quote == claim.raw_name for ref in claim.name_evidence):
                    raise ValueError("raw name requires its exact source quote")
                contexts = [_field_evidence(record, field) for field in dict.fromkeys(ref.field for ref in [*claim.name_evidence, *claim.evidence])]
                candidates.append(claim.model_dump() | dict(evidence_context=contexts, formal_admitted=False))
            for relation in mark.relations:
                if relation.source_id == relation.target_id or not {relation.source_id, relation.target_id} <= ids:
                    raise ValueError("relation must reference distinct candidates in this source/version")
                for ref in relation.evidence:
                    validate_evidence(record, ref.model_dump())
                relations.append(relation.model_dump() | dict(mapping_active=False, formal_admitted=False))
            if mark.material_kind != "undetermined" and not mark.material_evidence:
                raise ValueError("material claim requires evidence")
            for ref in mark.material_evidence:
                validate_evidence(record, ref.model_dump())
            for conflict in mark.conflicts:
                validate_evidence(record, conflict.title.model_dump())
                validate_evidence(record, conflict.duties.model_dump())
                if conflict.title.field != "job_title" or conflict.duties.field not in ("duties", "raw_text"):
                    raise ValueError("conflict requires separate title and duty fields")
            if mark.conflicts:
                reasons.append("title_duty_conflict")
        names, synonym_targets = defaultdict(list), defaultdict(set)
        for claim in candidates:
            # Comparison keys only: never replace the supplied names or resolve a mapping.
            for name in dict.fromkeys(n for n in (claim["raw_name"], claim["proposed_name"]) if n):
                names[name.strip().casefold()].append(claim["id"])
        name_audit = [dict(reason="name_has_multiple_candidates", name=name, candidate_ids=sorted(set(ids)))
                      for name, ids in sorted(names.items()) if len(set(ids)) > 1]
        for relation in relations:
            if relation["kind"] == "synonym":
                synonym_targets[relation["source_id"]].add(relation["target_id"])
        relation_audit = [dict(reason="multiple_synonym_targets", source_id=identity, target_ids=sorted(targets))
                          for identity, targets in sorted(synonym_targets.items()) if len(targets) > 1]
        if sum(c["responsibility"] == "core" for c in candidates) > 1:
            reasons.append("multiple_core_claims")
        if candidates:
            reasons.append("explicit_claims_require_review")
        bodies.append(dict(namespace=record.namespace, jd_id=record.jd_id, fingerprint=record.fingerprint,
            source_payload=record.payload, title_evidence=_field_evidence(record, "job_title"),
            duties_evidence=_field_evidence(record, "duties"), formal_jobs=config.formal_jobs,
            candidates=candidates, relations=relations, name_audit=name_audit, relation_audit=relation_audit,
            primary_job=dict(state="unresolved" if candidates else "unknown", value=None,
                             candidates=[c["id"] for c in candidates if c["kind"] != "technology_stack"]),
            material_kind=mark.material_kind if mark else "undetermined",
            material_evidence=[e.model_dump() for e in mark.material_evidence] if mark else [],
            conflicts=[c.model_dump() for c in mark.conflicts] if mark else [], notes=mark.notes if mark else "",
            reasons=reasons, review_status="pending_review", semantic_validation="not_performed",
            evidence_validation="source_spans_matched", classification_complete=False,
            formal_statistics_eligible=False, formal_admitted=False))
    return bodies

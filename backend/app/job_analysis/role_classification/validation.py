"""Deterministic source identity/spans and catalogue membership; no semantic verdict."""
from ..foundation.inputs import check_public
from .models import Annotation, DIMENSIONS, Evidence, Taxonomy


def validate_evidence(record, evidence):
    ref = Evidence.model_validate(evidence).model_dump()
    if (ref["namespace"], ref["jd_id"], ref["fingerprint"]) != (record.namespace, record.jd_id, record.fingerprint):
        raise ValueError("foreign source evidence")
    text = record.payload.get(ref["field"])
    if (not isinstance(text, str) or not ref["quote"].strip() or
            not 0 <= ref["start"] < ref["end"] <= len(text) or
            text[ref["start"]:ref["end"]] != ref["quote"]):
        raise ValueError("invalid source character span")
    return ref


def _field_evidence(record, field):
    text = record.payload.get(field)
    if not isinstance(text, str) or not text.strip():
        return None
    return dict(namespace=record.namespace, jd_id=record.jd_id, fingerprint=record.fingerprint,
                field=field, start=0, end=len(text), quote=text)


def validate_annotation(record, annotation, taxonomy):
    check_public(annotation)
    config = Taxonomy.model_validate(taxonomy)
    item = Annotation.model_validate(annotation)
    if (item.namespace, item.jd_id, item.fingerprint) != (record.namespace, record.jd_id, record.fingerprint):
        raise ValueError("annotation source identity mismatch")

    def check_decision(value, dimension):
        allowed = getattr(config, dimension)
        if any(term not in allowed for term in ([value.value] if value.value else []) + value.candidates):
            raise ValueError("value not in dimension taxonomy")
        for ref in value.evidence:
            validate_evidence(record, ref.model_dump())

    for dimension in DIMENSIONS:
        value = getattr(item, dimension)
        for entry in value if isinstance(value, list) else [value]:
            check_decision(entry, dimension)
    tracks = [d.value for d in item.technology_tracks if d.value is not None]
    if len(tracks) != len(set(tracks)):
        raise ValueError("duplicate technology track")
    if item.technology_tracks_status == "known":
        if not item.technology_tracks or any(d.state != "known" for d in item.technology_tracks):
            raise ValueError("known tracks require explicit values and evidence")
    elif item.technology_tracks_status == "unknown" and item.technology_tracks:
        raise ValueError("unknown tracks must be empty")
    auxiliary = set()
    for relation in item.auxiliary_roles:
        check_decision(relation.role, "canonical_job")
        if (item.canonical_job.state != "known" or relation.primary != item.canonical_job.value or
                relation.role.state != "known" or relation.role.value == relation.primary or
                relation.role.value in auxiliary):
            raise ValueError("auxiliary requires distinct known primary and role")
        auxiliary.add(relation.role.value)
        for ref in relation.evidence:
            validate_evidence(record, ref.model_dump())
    if item.material_kind != "undetermined" and not item.material_evidence:
        raise ValueError("material interpretation requires evidence")
    for ref in item.material_evidence:
        validate_evidence(record, ref.model_dump())
    for conflict in item.conflicts:
        validate_evidence(record, conflict.title.model_dump())
        validate_evidence(record, conflict.duties.model_dump())
        if conflict.title.field != "job_title" or conflict.duties.field not in ("duties", "raw_text"):
            raise ValueError("title/duties conflict requires separate source fields")
        value = getattr(item, conflict.dimension)
        state = item.technology_tracks_status if conflict.dimension == "technology_tracks" else value.state
        if state != "unresolved":
            raise ValueError("conflicting dimension must remain unresolved")
    return dict(annotation=item.model_dump(), source_payload=record.payload,
                title_evidence=_field_evidence(record, "job_title"),
                duties_evidence=_field_evidence(record, "duties"),
                evidence_validation="source_spans_matched", semantic_validation="not_performed",
                requires_review=True, classification_complete=False, formal_statistics_eligible=False)

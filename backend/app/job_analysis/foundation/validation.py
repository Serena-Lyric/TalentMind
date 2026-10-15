"""Exact quotation checks prove provenance only, never requirement semantics."""
from pydantic import ValidationError

from ...skills.normalizer import normalize
from .inputs import canonical, check_public, parse_json
from .models import FactClaim, Response


def validate_response(raw, record, alias_map):
    try:
        value = parse_json(raw) if isinstance(raw, str) else raw
        check_public(value)
        canonical(value)
        response = Response.model_validate(value)
    except (ValueError, TypeError, ValidationError):
        return {"status": "failed", "error": "response_parse_failed", "coverage": None, "facts": []}
    facts = []
    seen = set()
    for value in response.facts:
        encoded = canonical(value)
        if encoded in seen:
            continue
        seen.add(encoded)
        fact = {"claim": value, "evidence_status": "invalid_structure", "location": None,
                "semantic_status": "unreviewed", "canonical_name": None, "governance": "unresolved"}
        try:
            claim = FactClaim.model_validate(value)
        except ValidationError:
            facts.append(fact)
            continue
        fact.update(kind=claim.kind, name=claim.name, requirement=claim.requirement)
        if claim.kind == "skill":
            fact["canonical_name"] = normalize(claim.name, alias_map)
            fact["governance"] = "known" if fact["canonical_name"] else "candidate"
        evidence = claim.evidence
        if evidence is None or not evidence.quote.strip():
            fact["evidence_status"] = "missing_evidence"
        elif (evidence.namespace, evidence.jd_id) != (record.namespace, record.jd_id):
            fact["evidence_status"] = "foreign_jd"
        else:
            text = record.payload.get(evidence.field, "")
            start = text.find(evidence.quote)
            fact["evidence_status"] = "matched" if start >= 0 else "quote_not_found"
            if start >= 0:
                fact["location"] = {"field": evidence.field, "start": start, "end": start + len(evidence.quote)}
        facts.append(fact)
    complete = response.coverage == "complete" and all(f["evidence_status"] == "matched" for f in facts)
    return {"status": "completed" if complete else "partial", "coverage": response.coverage,
            "facts": facts, "error": None}

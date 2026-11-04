"""Exact-only P1 knowledge alignment; copied facts remain independently auditable."""
from __future__ import annotations

from copy import deepcopy
import re

from ..baseline.contract import validate_analysis
from ..foundation.inputs import digest
from .catalog import LoadedSnapshot
from .models import (
    AlignmentResult,
    Concept,
    ConceptRelation,
    MemberAlignment,
    RelatedConcept,
    RequirementAlignment,
    normalize_term,
)


SPLIT = re.compile(r"\s*(?:或|/|、|，|,|;|；)\s*")
INVERSE = {
    "broader_than": "narrower_than",
    "narrower_than": "broader_than",
    "related_to": "related_to",
    "version_of": "version_of",
    "exact_synonym": "exact_synonym",
}


def _index(knowledge: LoadedSnapshot) -> dict[str, tuple[Concept, bool]]:
    result = {}
    for concept in knowledge.snapshot.concepts:
        result[normalize_term(concept.name)] = (concept, False)
        for alias in concept.aliases:
            result[normalize_term(alias.term)] = (concept, True)
    return result


def _neighbors(concept_id: str, knowledge: LoadedSnapshot) -> list[RelatedConcept]:
    concepts = {item.id: item for item in knowledge.snapshot.concepts}
    result = []
    for relation in knowledge.snapshot.relations:
        if relation.source_id == concept_id:
            target_id, kind = relation.target_id, relation.kind
        elif relation.target_id == concept_id:
            target_id, kind = relation.source_id, INVERSE[relation.kind]
        else:
            continue
        target = concepts[target_id]
        result.append(RelatedConcept(
            concept_id=target.id,
            name=target.name,
            maturity=target.maturity,
            kind=kind,
            basis=relation.basis,
        ))
    return sorted(result, key=lambda item: (item.concept_id, item.kind))


def _compound_candidates(member: str, index: dict[str, tuple[Concept, bool]]) -> list[str]:
    parts = [part for part in SPLIT.split(member) if part.strip()]
    if len(parts) < 2:
        return []
    return sorted({index[normalize_term(part)][0].id for part in parts
                   if normalize_term(part) in index})


def _decision(claim_id: str, member: str, requirement, knowledge: LoadedSnapshot,
              index: dict[str, tuple[Concept, bool]]) -> MemberAlignment:
    candidates = _compound_candidates(member, index)
    if len(candidates) >= 2:
        return MemberAlignment(
            claim_id=claim_id,
            member=member,
            state="ambiguous",
            concept_id=None,
            concept_name=None,
            knowledge_status="ambiguous",
            candidate_concept_ids=candidates,
            related_concepts=[],
            source_evidence=[*requirement["scope_evidence"]],
            reason="Atomic P1 member contains multiple exact knowledge concepts; it was not split.",
        )
    found = index.get(normalize_term(member))
    if found is None:
        return MemberAlignment(
            claim_id=claim_id,
            member=member,
            state="unknown",
            concept_id=None,
            concept_name=None,
            knowledge_status="unknown",
            candidate_concept_ids=[],
            related_concepts=[],
            source_evidence=[*requirement["scope_evidence"]],
            reason="No exact canonical name or alias in this knowledge version; fuzzy matching and cooccurrence are not used.",
        )
    concept, via_alias = found
    return MemberAlignment(
        claim_id=claim_id,
        member=member,
        state="exact_synonym",
        concept_id=concept.id,
        concept_name=concept.name,
        knowledge_status=concept.maturity,
        candidate_concept_ids=[],
        related_concepts=_neighbors(concept.id, knowledge),
        source_evidence=[*requirement["scope_evidence"]],
        reason=("Exact alias declared in the bound knowledge version."
                if via_alias else "Exact canonical concept name in the bound knowledge version."),
    )


def align_analysis(analysis: dict, knowledge: LoadedSnapshot) -> AlignmentResult:
    """Create a new bound explanation; the P1 analysis object is never mutated."""
    checked = validate_analysis(deepcopy(analysis))
    source = checked.model_dump()
    source_sha256 = digest(source)
    index = _index(knowledge)
    requirements = []
    for claim in checked.claims:
        if claim.kind != "requirement" or claim.requirement is None:
            continue
        requirement = claim.requirement.model_dump()
        alignments = [
            _decision(claim.id, member, requirement, knowledge, index).model_copy(
                update={"source_evidence": [
                    *[item.model_dump() for item in claim.evidence],
                    *requirement["scope_evidence"],
                ]}
            )
            for member in requirement["members"]
        ]
        requirements.append(RequirementAlignment(
            claim_id=claim.id,
            source_requirement=deepcopy(requirement),
            alignments=alignments,
            semantic_review="machine_unreviewed",
        ))
    return AlignmentResult(
        schema_version="m2-knowledge-alignment-1",
        namespace=checked.namespace,
        jd_id=checked.jd_id,
        input_sha256=checked.input_sha256,
        input_version=checked.input_version,
        source_analysis_sha256=source_sha256,
        knowledge_id=knowledge.snapshot.id,
        knowledge_revision=knowledge.snapshot.revision,
        knowledge_sha256=knowledge.sha256,
        semantic_review="machine_unreviewed",
        requirements=requirements,
    )

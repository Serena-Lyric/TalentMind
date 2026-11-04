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
    CandidateProjectionBinding,
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


def _candidate_index(binding):
    if binding is None:
        return {}
    result = {}
    for concept in binding.projection.concepts:
        result.setdefault(concept.normalized_term, []).append(concept)
    return result


def _candidate_decision(claim_id: str, member: str, requirement, groups) -> MemberAlignment | None:
    concepts = groups.get(normalize_term(member), [])
    if not concepts:
        return None
    if len(concepts) > 1 or any(item.status == "disputed" for item in concepts):
        if len(concepts) < 2:
            return None
        return MemberAlignment(
            claim_id=claim_id,
            member=member,
            state="ambiguous",
            concept_id=None,
            concept_name=None,
            knowledge_status="ambiguous",
            candidate_concept_ids=sorted(item.concept_id for item in concepts),
            related_concepts=[],
            concept_source=None,
            source_evidence=[*requirement["scope_evidence"]],
            reason="Multiple isolated candidate interpretations match this exact surface form.",
        )
    concept = concepts[0]
    return MemberAlignment(
        claim_id=claim_id,
        member=member,
        state="exact_synonym",
        concept_id=concept.concept_id,
        concept_name=concept.surface,
        knowledge_status="candidate",
        candidate_concept_ids=[],
        related_concepts=[],
        concept_source="candidate",
        candidate_id=concept.candidate_id,
        candidate_version_sha256=concept.candidate_version_sha256,
        source_evidence=[*requirement["scope_evidence"]],
        reason="Exact, automatically corroborated candidate expression; formal admission remains disabled.",
    )


def _decision(claim_id: str, member: str, requirement, knowledge: LoadedSnapshot,
              index: dict[str, tuple[Concept, bool]], candidate_groups) -> MemberAlignment:
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
        candidate = _candidate_decision(claim_id, member, requirement, candidate_groups)
        if candidate is not None:
            return candidate
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
        concept_source="knowledge",
        candidate_id=None,
        candidate_version_sha256=None,
        source_evidence=[*requirement["scope_evidence"]],
        reason=("Exact alias declared in the bound knowledge version."
                if via_alias else "Exact canonical concept name in the bound knowledge version."),
    )


def align_analysis(analysis: dict, knowledge: LoadedSnapshot,
                   candidate_projection: CandidateProjectionBinding | None = None) -> AlignmentResult:
    """Create a new bound explanation; the P1 analysis object is never mutated."""
    checked = validate_analysis(deepcopy(analysis))
    source = checked.model_dump()
    source_sha256 = digest(source)
    index = _index(knowledge)
    candidate_groups = _candidate_index(candidate_projection)
    requirements = []
    for claim in checked.claims:
        if claim.kind != "requirement" or claim.requirement is None:
            continue
        requirement = claim.requirement.model_dump()
        source_evidence = [
            *[item.model_dump() for item in claim.evidence],
            *requirement["scope_evidence"],
        ]
        alignments = []
        for member in requirement["members"]:
            decision = _decision(claim.id, member, requirement, knowledge, index, candidate_groups)
            alignments.append(MemberAlignment.model_validate({
                **decision.model_dump(),
                "source_evidence": source_evidence,
            }))
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
        source_outcome=checked.outcome,
        source_coverage={key: value.model_dump() for key, value in checked.coverage.items()},
        knowledge_id=knowledge.snapshot.id,
        knowledge_revision=knowledge.snapshot.revision,
        knowledge_sha256=knowledge.sha256,
        candidate_projection_id=(candidate_projection.projection.id if candidate_projection else None),
        candidate_projection_revision=(candidate_projection.projection.revision if candidate_projection else None),
        candidate_projection_sha256=(candidate_projection.sha256 if candidate_projection else None),
        semantic_review="machine_unreviewed",
        requirements=requirements,
    )

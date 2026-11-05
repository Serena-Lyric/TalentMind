"""Deterministic version impact scans with conservative fallback."""
from __future__ import annotations

from ..foundation.inputs import digest
from .alignment import align_analysis
from .catalog import LoadedSnapshot
from .models import (AlignmentResult, CandidateProjectionBinding, ImpactReport,
                     context_key, normalize_term)


def _ids_by_key(items, key):
    return {
        (item[key] if isinstance(item, dict) else getattr(item, key)): item
        for item in items
    }


def _analysis_key(record: AlignmentResult) -> str:
    return f"{record.namespace}:{record.jd_id}:{record.source_analysis_sha256[:12]}"


def _alias_owners(snapshot):
    result = {}
    for concept in snapshot.concepts:
        result[normalize_term(concept.name)] = concept.id
        for alias in concept.aliases:
            result[normalize_term(alias.term)] = concept.id
    return result


def _candidate_map(binding):
    if binding is None:
        return {}
    return {
        (item.normalized_term, item.target, item.category, item.context_key): item
        for item in binding.projection.concepts
    }


def _candidate_signature(candidate_map, member, target, category, current_context):
    key = (normalize_term(member), target, category, current_context)
    item = candidate_map.get(key)
    return None if item is None else (item.concept_id, item.status, item.candidate_version_sha256)


def locate_impact(old: LoadedSnapshot, new: LoadedSnapshot,
                  records: list[AlignmentResult], *, old_candidate_projection=None,
                  new_candidate_projection=None) -> ImpactReport:
    checked = [AlignmentResult.model_validate(item.model_dump()) for item in records]
    if any(item.knowledge_sha256 != old.sha256 for item in checked):
        raise ValueError("alignment records must be bound to the old knowledge SHA")
    old_projection_sha = old_candidate_projection.sha256 if old_candidate_projection else None
    if any(item.candidate_projection_sha256 not in {None, old_projection_sha} for item in checked):
        raise ValueError("alignment records must be bound to the old candidate projection SHA")
    old_concepts = _ids_by_key(old.snapshot.concepts, "id")
    new_concepts = _ids_by_key(new.snapshot.concepts, "id")
    changed_concepts = sorted(
        concept_id for concept_id in old_concepts.keys() | new_concepts.keys()
        if old_concepts.get(concept_id) != new_concepts.get(concept_id)
    )
    old_aliases = _alias_owners(old.snapshot)
    new_aliases = _alias_owners(new.snapshot)
    changed_aliases = sorted(
        term for term in old_aliases.keys() | new_aliases.keys()
        if old_aliases.get(term) != new_aliases.get(term)
    )
    old_relations = {
        f"{item.source_id}:{item.kind}:{item.target_id}:{digest(item.model_dump())[:12]}"
        for item in old.snapshot.relations
    }
    new_relations = {
        f"{item.source_id}:{item.kind}:{item.target_id}:{digest(item.model_dump())[:12]}"
        for item in new.snapshot.relations
    }
    changed_relations = sorted(old_relations ^ new_relations)
    changed_relation_pairs = set()
    for item in [*old.snapshot.relations, *new.snapshot.relations]:
        key = f"{item.source_id}:{item.kind}:{item.target_id}:{digest(item.model_dump())[:12]}"
        if key in changed_relations:
            changed_relation_pairs.add((item.source_id, item.target_id))
    old_roles = _ids_by_key(old.snapshot.roles, "id")
    new_roles = _ids_by_key(new.snapshot.roles, "id")
    changed_roles = sorted(
        role_id for role_id in old_roles.keys() | new_roles.keys()
        if old_roles.get(role_id) != new_roles.get(role_id)
    )
    old_sources = _ids_by_key(old.snapshot.sources, "id")
    new_sources = _ids_by_key(new.snapshot.sources, "id")
    changed_sources = sorted(
        source_id for source_id in old_sources.keys() | new_sources.keys()
        if old_sources.get(source_id) != new_sources.get(source_id)
    )
    old_candidates = _candidate_map(old_candidate_projection)
    new_candidates = _candidate_map(new_candidate_projection)
    changed_candidate_keys = sorted(
        key for key in old_candidates.keys() | new_candidates.keys()
        if old_candidates.get(key) != new_candidates.get(key)
    )
    changed_candidate_ids = sorted({
        item.concept_id for key in changed_candidate_keys
        for item in (old_candidates.get(key), new_candidates.get(key)) if item is not None
    })
    candidate_projection_changed = (
        (old_candidate_projection.sha256 if old_candidate_projection else None)
        != (new_candidate_projection.sha256 if new_candidate_projection else None)
    )
    semantic_changes = (
        changed_concepts or changed_aliases or changed_relations or changed_roles or changed_sources
        or changed_candidate_keys
    )
    conservative = bool(old.sha256 != new.sha256 and not semantic_changes)
    reason = "Affected results were derived from versioned static and candidate knowledge changes."
    if changed_sources or changed_roles:
        conservative = True
        reason = "Source or role metadata changed; all supplied results were conservatively affected."
    if conservative:
        affected = [_analysis_key(item) for item in checked]
    else:
        affected = []
        for record in checked:
            touched = False
            for requirement in record.requirements:
                source = requirement.source_requirement
                context = context_key("\n".join(
                    evidence.quote
                    for member_alignment in requirement.alignments
                    for evidence in member_alignment.source_evidence
                ))
                for member_alignment in requirement.alignments:
                    decision_ids = {
                        member_alignment.concept_id,
                        *[neighbor.concept_id for neighbor in member_alignment.related_concepts],
                    }
                    if (member_alignment.concept_id in changed_concepts
                            or normalize_term(member_alignment.member) in changed_aliases
                            or any(neighbor.concept_id in changed_concepts
                                   for neighbor in member_alignment.related_concepts)
                            or any(left in decision_ids or right in decision_ids
                                   for left, right in changed_relation_pairs)):
                        touched = True
                    old_signature = _candidate_signature(
                        old_candidates, member_alignment.member, source["target"],
                        source["category"], context,
                    )
                    new_signature = _candidate_signature(
                        new_candidates, member_alignment.member, source["target"],
                        source["category"], context,
                    )
                    if old_signature != new_signature:
                        touched = True
            if touched:
                affected.append(_analysis_key(record))
    return ImpactReport(
        schema_version="m2-knowledge-impact-1",
        old_revision=old.snapshot.revision,
        new_revision=new.snapshot.revision,
        old_knowledge_sha256=old.sha256,
        new_knowledge_sha256=new.sha256,
        old_candidate_projection_sha256=old_projection_sha,
        new_candidate_projection_sha256=(new_candidate_projection.sha256
                                         if new_candidate_projection else None),
        candidate_projection_changed=candidate_projection_changed,
        changed_candidate_concept_ids=changed_candidate_ids,
        changed_concept_ids=changed_concepts,
        changed_aliases=changed_aliases,
        changed_relations=changed_relations,
        changed_role_ids=changed_roles,
        affected=sorted(set(affected)),
        conservative=conservative,
        reason=reason,
    )


def redeliver(analysis: dict, new_knowledge: LoadedSnapshot, *,
              candidate_projection=None) -> AlignmentResult:
    return align_analysis(analysis, new_knowledge, candidate_projection=candidate_projection)

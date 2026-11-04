"""Deterministic version impact scans with conservative fallback."""
from __future__ import annotations

from ..foundation.inputs import digest
from .alignment import align_analysis
from .catalog import LoadedSnapshot
from .models import AlignmentResult, ImpactReport, normalize_term


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


def locate_impact(old: LoadedSnapshot, new: LoadedSnapshot,
                  records: list[AlignmentResult]) -> ImpactReport:
    checked = [AlignmentResult.model_validate(item.model_dump()) for item in records]
    if any(item.knowledge_sha256 != old.sha256 for item in checked):
        raise ValueError("alignment records must be bound to the old knowledge SHA")
    old_concepts = _ids_by_key(old.snapshot.concepts, "id")
    new_concepts = _ids_by_key(new.snapshot.concepts, "id")
    changed_concepts = sorted(
        concept_id for concept_id in old_concepts.keys() | new_concepts.keys()
        if (old_concepts.get(concept_id) != new_concepts.get(concept_id))
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
    if changed_relations:
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
    semantic_changes = (
        changed_concepts or changed_aliases or changed_relations or changed_roles or changed_sources
    )
    conservative = bool(old.sha256 != new.sha256 and not semantic_changes)
    reason = (
        "The snapshot digest changed without a provable semantic impact set; all supplied results were conservatively affected."
        if conservative else
        "Affected results were derived from changed concept, exact alias, relation, role or source records."
    )
    if changed_sources:
        conservative = True
        reason = "Source metadata changed; all supplied results were conservatively affected."
    if changed_roles:
        # Alignment records alone cannot locate role-comparison consumers.
        conservative = True
        reason = "Role definitions changed and no role-comparison impact index was supplied; all supplied results were conservatively affected."
    if conservative:
        affected = [_analysis_key(item) for item in checked]
    else:
        affected = []
        for record in checked:
            touched = False
            for decision in record.alignments:
                decision_ids = {decision.concept_id, *[n.concept_id for n in decision.related_concepts]}
                if (decision.concept_id in changed_concepts
                        or normalize_term(decision.member) in changed_aliases
                        or any(neighbor.concept_id in changed_concepts for neighbor in decision.related_concepts)
                        or any(left in decision_ids or right in decision_ids
                               for left, right in changed_relation_pairs)):
                    touched = True
                    break
            if touched:
                affected.append(_analysis_key(record))
    return ImpactReport(
        schema_version="m2-knowledge-impact-1",
        old_revision=old.snapshot.revision,
        new_revision=new.snapshot.revision,
        old_knowledge_sha256=old.sha256,
        new_knowledge_sha256=new.sha256,
        changed_concept_ids=changed_concepts,
        changed_aliases=changed_aliases,
        changed_relations=changed_relations,
        changed_role_ids=changed_roles,
        affected=sorted(affected),
        conservative=conservative,
        reason=reason,
    )


def redeliver(analysis: dict, new_knowledge: LoadedSnapshot) -> AlignmentResult:
    return align_analysis(analysis, new_knowledge)

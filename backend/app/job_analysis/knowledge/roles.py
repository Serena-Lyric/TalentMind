"""Responsibility-first role comparison with explicit, evidence-bound boundaries."""
from __future__ import annotations

import re
import unicodedata

from ..baseline.contract import validate_analysis
from ..foundation.inputs import digest
from .catalog import LoadedSnapshot
from .models import (
    DutySnapshot,
    RoleBoundaryConflict,
    RoleComparison,
    RoleComparisonSet,
)


def _normal(value: str) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", value)).casefold()


def _anchors_match(text: str, anchors: list[list[str]]) -> bool:
    source = _normal(text)
    return all(any(_normal(term) in source for term in group) for group in anchors)


def compare_roles(analysis: dict, knowledge: LoadedSnapshot) -> RoleComparisonSet:
    checked = validate_analysis(analysis)
    duties = [
        DutySnapshot(
            id=claim.id,
            text=claim.text,
            core=claim.core,
            evidence=[item.model_dump() for item in claim.evidence],
        )
        for claim in checked.claims if claim.kind == "duty"
    ]
    comparisons = []
    for role in knowledge.snapshot.roles:
        covered = []
        conflicts = []
        for duty in duties:
            if any(_anchors_match(duty.text, item.anchors) for item in role.responsibilities):
                covered.append(duty.id)
            for boundary in role.boundaries:
                if _anchors_match(duty.text, boundary.anchors):
                    duty_evidence = [item.model_dump() for item in duty.evidence]
                    conflicts.append(RoleBoundaryConflict(
                        duty_id=duty.id,
                        boundary_id=boundary.id,
                        boundary_text=boundary.text,
                        duty_evidence=duty_evidence,
                        boundary_evidence=[item.model_dump() for item in boundary.evidence],
                        reason="The cited local duty matches this role's explicit boundary pattern.",
                    ))
        covered = sorted(set(covered))
        uncovered = sorted(duty.id for duty in duties if duty.id not in set(covered))
        if conflicts:
            judgment = "not_supported"
            reason = "Explicit role boundary matched one or more evidenced local duties."
        elif duties and covered and not uncovered:
            judgment = "supported"
            reason = "All local duties matched configured candidate responsibilities; scope is limited to this snapshot."
        elif covered:
            judgment = "unresolved"
            reason = "Some local duties matched, but uncovered duties remain unresolved."
        else:
            judgment = "unresolved"
            reason = "No local duty matched configured candidate responsibilities; this is not evidence that the role is excluded."
        comparisons.append(RoleComparison(
            role_id=role.id,
            role_revision=role.definition_version,
            role_maturity=role.maturity,
            judgment=judgment,
            covered_duty_ids=covered,
            uncovered_duty_ids=uncovered,
            conflicts=conflicts,
            reason=reason,
        ))
    checked_role_ids = sorted(role.id for role in knowledge.snapshot.roles)
    by_id = {item.role_id: item for item in comparisons}
    return RoleComparisonSet(
        schema_version="m2-role-comparison-1",
        namespace=checked.namespace,
        jd_id=checked.jd_id,
        input_sha256=checked.input_sha256,
        source_analysis_sha256=digest(checked.model_dump()),
        knowledge_id=knowledge.snapshot.id,
        knowledge_revision=knowledge.snapshot.revision,
        knowledge_sha256=knowledge.sha256,
        retrieval_scope="all_roles_in_bound_snapshot",
        scope_limitation="No claim is made about roles outside this bound knowledge snapshot.",
        checked_role_ids=checked_role_ids,
        duties=duties,
        comparisons=[by_id[role_id] for role_id in checked_role_ids],
    )

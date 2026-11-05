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

CLAUSE_SPLIT = re.compile(r"[，,；;。.!！?？\n]+")
NEGATION = re.compile(r"不|未|无|没|非|禁止|避免|无需|不需|不是|并未|没有")


def _positive_term(text: str, term: str) -> bool:
    source = _normal(text)
    target = _normal(term)
    start = 0
    while (position := source.find(target, start)) >= 0:
        prefix = CLAUSE_SPLIT.split(source[:position])[-1]
        if not NEGATION.search(prefix):
            return True
        start = position + len(target)
    return False


def _anchors_match(text: str, anchors: list[list[str]]) -> bool:
    return all(any(_positive_term(text, term) for term in group) for group in anchors)


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
    coverage_complete = checked.coverage["duties"].status == "complete"
    core_by_id = {duty.id: duty.core for duty in duties}
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
        if not coverage_complete:
            conflicts = []
            judgment = "unresolved"
            reason = "P1 duty coverage is not complete; strong role conclusions were withheld."
        elif conflicts and any(core_by_id[item.duty_id] is True for item in conflicts):
            judgment = "not_supported"
            reason = "A core local duty positively matched an explicit role boundary."
        elif conflicts:
            judgment = "unresolved"
            reason = "A boundary pattern matched, but local duty core status is not confirmed."
        elif (duties and covered and not uncovered
              and all(core_by_id[duty.id] is True for duty in duties)):
            judgment = "supported"
            reason = "All complete, core local duties matched candidate responsibilities; scope is limited to this snapshot."
        elif duties and covered and not uncovered:
            judgment = "unresolved"
            reason = "All duties matched, but one or more core-status fields are absent or false."
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
    comparison_status = "no_role_candidates" if not checked_role_ids else "completed"
    by_id = {item.role_id: item for item in comparisons}
    return RoleComparisonSet(
        schema_version="m2-role-comparison-1",
        namespace=checked.namespace,
        jd_id=checked.jd_id,
        input_sha256=checked.input_sha256,
        source_analysis_sha256=digest(checked.model_dump()),
        source_outcome=checked.outcome,
        source_coverage={key: value.model_dump() for key, value in checked.coverage.items()},
        knowledge_id=knowledge.snapshot.id,
        knowledge_revision=knowledge.snapshot.revision,
        knowledge_sha256=knowledge.sha256,
        retrieval_scope="all_roles_in_bound_snapshot",
        scope_limitation=("The bound snapshot has no role candidates; no role conclusion was made."
                          if not checked_role_ids else
                          "No claim is made about roles outside this bound knowledge snapshot."),
        comparison_status=comparison_status,
        checked_role_ids=checked_role_ids,
        duties=duties,
        comparisons=[by_id[role_id] for role_id in checked_role_ids],
    )

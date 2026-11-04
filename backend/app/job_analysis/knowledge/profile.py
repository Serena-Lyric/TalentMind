"""Rebuildable candidate profiles from version-bound alignments and role comparisons."""
from __future__ import annotations

from .models import (
    AlignmentResult,
    ProfileMember,
    ProfileMemberAlignment,
    ProfileRequirement,
    RoleComparisonSet,
    RoleProfile,
)


def build_profile(role_id: str, comparisons: RoleComparisonSet,
                  alignments: list[AlignmentResult]) -> RoleProfile:
    comparison = comparisons.for_role(role_id)
    if any((item.knowledge_id, item.knowledge_revision, item.knowledge_sha256) !=
           (comparisons.knowledge_id, comparisons.knowledge_revision, comparisons.knowledge_sha256)
           for item in alignments):
        raise ValueError("profile alignments require the same knowledge version as the comparison")
    by_source = {
        item.source_analysis_sha256: item
        for item in alignments
        if item.namespace == comparisons.namespace and item.jd_id == comparisons.jd_id
    }
    members = []
    if comparison.judgment == "supported":
        aligned = by_source.get(comparisons.source_analysis_sha256)
        if aligned is None:
            raise ValueError("supported comparison requires its bound P1 alignment")
        requirements = []
        for requirement in aligned.requirements:
            source = requirement.source_requirement
            decision_by_member = {item.member: item for item in requirement.alignments}
            requirements.append(ProfileRequirement(
                claim_id=requirement.claim_id,
                members=source["members"],
                alignments=[
                    ProfileMemberAlignment(
                        member=member,
                        state=decision_by_member[member].state,
                        concept_id=decision_by_member[member].concept_id,
                        knowledge_status=decision_by_member[member].knowledge_status,
                    )
                    for member in source["members"]
                ],
                state=source["state"],
                target=source["target"],
                category=source["category"],
                combination=source["combination"],
                open_set=source["open_set"],
                degree=source["degree"],
                degree_polarity=source["degree_polarity"],
                condition=source["condition"],
                semantic_review=requirement.semantic_review,
            ))
        members.append(ProfileMember(
            analysis_key=f"{comparisons.namespace}:{comparisons.jd_id}:{comparisons.source_analysis_sha256[:12]}",
            namespace=comparisons.namespace,
            jd_id=comparisons.jd_id,
            role_judgment="supported",
            duties=comparisons.duties,
            requirements=requirements,
        ))
    return RoleProfile(
        schema_version="m2-role-profile-1",
        role_id=comparison.role_id,
        role_revision=comparison.role_revision,
        role_maturity=comparison.role_maturity,
        knowledge_id=comparisons.knowledge_id,
        knowledge_revision=comparisons.knowledge_revision,
        knowledge_sha256=comparisons.knowledge_sha256,
        mode="candidate_profile",
        claim_scope="linked_members_only",
        not_market_statistics=True,
        not_formal_role=True,
        source_analysis_sha256s=sorted(item.source_analysis_sha256 for item in alignments
                                       if item.source_analysis_sha256 in by_source),
        members=members,
    )

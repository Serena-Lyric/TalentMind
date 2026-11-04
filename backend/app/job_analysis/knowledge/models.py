"""Strict knowledge contracts; source maturity never implies TalentMind admission."""
from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from ..baseline.contract import Coverage, Requirement
from ..foundation.inputs import check_public
from ..semantics.models import Evidence

Text = Annotated[str, StringConstraints(min_length=1, pattern=r"\S")]
StableId = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9._-]{0,95}$")]
Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
DateText = Annotated[str, StringConstraints(pattern=r"^\d{4}-\d{2}-\d{2}$")]
Maturity = Literal["test", "candidate", "formal"]
Category = Literal["technical_skill", "professional_skill", "engineering_practice", "soft_skill"]
RelationKind = Literal["exact_synonym", "broader_than", "narrower_than", "related_to", "version_of"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class SourceEvidence(Strict):
    source_id: StableId
    locator: Text
    quote: Text


class KnowledgeSource(Strict):
    id: StableId
    title: Text
    uri: Annotated[str, StringConstraints(pattern=r"^https://")]
    document_version: Text
    retrieved_on: DateText
    license_id: Text
    license_url: Annotated[str, StringConstraints(pattern=r"^https://")]
    use_constraint: Text
    sha256: Sha256


class Alias(Strict):
    term: Text
    scope: Text | None = None
    evidence: list[SourceEvidence] = Field(min_length=1)

    @model_validator(mode="after")
    def unpadded_term(self):
        if self.term != self.term.strip():
            raise ValueError("alias term must not be padded")
        return self


class Concept(Strict):
    id: StableId
    name: Text
    definition: Text
    category: Category
    maturity: Maturity
    aliases: list[Alias]
    evidence: list[SourceEvidence] = Field(min_length=1)
    approval_source: Text | None

    @model_validator(mode="after")
    def formal_requires_approval(self):
        if self.maturity == "formal" and not self.approval_source:
            raise ValueError("formal concept requires per-item approval evidence")
        return self


class ConceptRelation(Strict):
    source_id: StableId
    target_id: StableId
    kind: RelationKind
    basis: Text
    evidence: list[SourceEvidence] = Field(min_length=1)


class Responsibility(Strict):
    id: StableId
    text: Text
    anchors: list[list[Text]] = Field(min_length=1)
    evidence: list[SourceEvidence] = Field(min_length=1)

    @model_validator(mode="after")
    def usable_anchors(self):
        if any(not group for group in self.anchors):
            raise ValueError("responsibility anchor group cannot be empty")
        return self


class Boundary(Strict):
    id: StableId
    text: Text
    anchors: list[list[Text]] = Field(min_length=1)
    evidence: list[SourceEvidence] = Field(min_length=1)

    @model_validator(mode="after")
    def usable_anchors(self):
        if any(not group for group in self.anchors):
            raise ValueError("boundary anchor group cannot be empty")
        return self


class RoleDefinition(Strict):
    id: StableId
    name: Text
    definition_version: Text
    maturity: Maturity
    goals: list[Text] = Field(min_length=1)
    responsibilities: list[Responsibility] = Field(min_length=1)
    boundaries: list[Boundary]
    known_scope: list[Text] = Field(min_length=1)
    unresolved_boundaries: list[Text] = Field(min_length=1)
    evidence: list[SourceEvidence] = Field(min_length=1)
    approval_source: Text | None

    @model_validator(mode="after")
    def formal_requires_approval(self):
        if self.maturity == "formal" and not self.approval_source:
            raise ValueError("formal role requires per-definition approval evidence")
        return self


def normalize_term(value: str) -> str:
    """Exact lookup only: compatibility normalization, not fuzzy matching."""
    return unicodedata.normalize("NFKC", value).strip().casefold()


class KnowledgeSnapshot(Strict):
    schema_version: Literal["m2-knowledge-1"]
    id: StableId
    revision: Text
    purpose: Text
    created_on: DateText
    sources: list[KnowledgeSource] = Field(min_length=1)
    concepts: list[Concept] = Field(min_length=1)
    relations: list[ConceptRelation]
    roles: list[RoleDefinition] = Field(min_length=1)

    @model_validator(mode="after")
    def referential_and_identity_integrity(self):
        def unique(values, label):
            if len(values) != len(set(values)):
                raise ValueError(f"duplicate {label}")

        unique([item.id for item in self.sources], "source ID")
        unique([item.id for item in self.concepts], "concept ID")
        unique([item.id for item in self.roles], "role ID")
        source_ids = {item.id for item in self.sources}
        concept_ids = {item.id for item in self.concepts}
        for concept in self.concepts:
            for item in concept.evidence:
                if item.source_id not in source_ids:
                    raise ValueError("evidence references missing source")
            for alias in concept.aliases:
                for item in alias.evidence:
                    if item.source_id not in source_ids:
                        raise ValueError("alias evidence references missing source")
        owners = defaultdict(set)
        for concept in self.concepts:
            for term in [concept.name, *[alias.term for alias in concept.aliases]]:
                if not term.strip():
                    raise ValueError("blank concept name or alias")
                owners[normalize_term(term)].add(concept.id)
        ambiguous = sorted(term for term, ids in owners.items() if len(ids) > 1)
        if ambiguous:
            raise ValueError(f"ambiguous name or alias: {ambiguous[0]}")
        relation_keys = set()
        for relation in self.relations:
            if relation.source_id not in concept_ids or relation.target_id not in concept_ids:
                raise ValueError("relation references missing concept")
            if relation.source_id == relation.target_id:
                raise ValueError("self relation is not allowed")
            key = (relation.source_id, relation.target_id, relation.kind)
            if key in relation_keys:
                raise ValueError("duplicate concept relation")
            relation_keys.add(key)
            for item in relation.evidence:
                if item.source_id not in source_ids:
                    raise ValueError("relation evidence references missing source")
        for role in self.roles:
            ids = [item.id for item in role.responsibilities] + [item.id for item in role.boundaries]
            unique(ids, "role responsibility/boundary ID")
            for item in [*role.evidence,
                         *[evidence for responsibility in role.responsibilities for evidence in responsibility.evidence],
                         *[evidence for boundary in role.boundaries for evidence in boundary.evidence]]:
                if item.source_id not in source_ids:
                    raise ValueError("role evidence references missing source")
            for responsibility in [*role.responsibilities, *role.boundaries]:
                for group in responsibility.anchors:
                    if any(not re.search(r"\S", term) for term in group):
                        raise ValueError("blank comparison anchor")
        return self


def validate_snapshot(value: dict) -> KnowledgeSnapshot:
    check_public(value)
    return KnowledgeSnapshot.model_validate(value)


class RelatedConcept(Strict):
    concept_id: StableId
    name: Text
    maturity: Maturity
    kind: RelationKind
    basis: Text


class MemberAlignment(Strict):
    claim_id: StableId
    member: Text
    state: Literal["exact_synonym", "ambiguous", "unknown"]
    concept_id: StableId | None
    concept_name: Text | None
    knowledge_status: Literal["test", "candidate", "formal", "ambiguous", "unknown"]
    candidate_concept_ids: list[StableId]
    related_concepts: list[RelatedConcept]
    source_evidence: list[Evidence] = Field(min_length=1)
    reason: Text

    @model_validator(mode="after")
    def decision_shape(self):
        if self.state == "exact_synonym":
            if (self.concept_id is None or self.concept_name is None
                    or self.knowledge_status not in {"test", "candidate", "formal"}
                    or self.candidate_concept_ids):
                raise ValueError("exact alignment requires exactly one selected concept")
        elif self.state == "ambiguous":
            if (self.concept_id is not None or self.concept_name is not None
                    or self.knowledge_status != "ambiguous" or len(self.candidate_concept_ids) < 2):
                raise ValueError("ambiguous alignment cannot select one concept")
        elif (self.concept_id is not None or self.concept_name is not None
              or self.knowledge_status != "unknown" or self.candidate_concept_ids):
            raise ValueError("unknown alignment cannot claim knowledge")
        return self


class RequirementAlignment(Strict):
    claim_id: StableId
    source_requirement: dict
    alignments: list[MemberAlignment] = Field(min_length=1)
    semantic_review: Literal["machine_unreviewed"]

    @model_validator(mode="after")
    def one_decision_per_original_member(self):
        Requirement.model_validate(self.source_requirement)
        members = self.source_requirement.get("members")
        if not isinstance(members, list) or [item.member for item in self.alignments] != members:
            raise ValueError("alignment must preserve original member order and multiplicity")
        if any(item.claim_id != self.claim_id for item in self.alignments):
            raise ValueError("alignment claim identity mismatch")
        return self


class AlignmentResult(Strict):
    schema_version: Literal["m2-knowledge-alignment-1"]
    namespace: Text
    jd_id: Text
    input_sha256: Sha256
    input_version: Text
    source_analysis_sha256: Sha256
    source_outcome: Literal["complete", "partial", "failed", "not_run"]
    source_coverage: dict[str, Coverage]
    knowledge_id: StableId
    knowledge_revision: Text
    knowledge_sha256: Sha256
    semantic_review: Literal["machine_unreviewed"]
    requirements: list[RequirementAlignment]

    @property
    def alignments(self) -> list[MemberAlignment]:
        return [item for requirement in self.requirements for item in requirement.alignments]


class DutySnapshot(Strict):
    id: StableId
    text: Text
    core: bool | None
    evidence: list[Evidence] = Field(min_length=1)


class RoleBoundaryConflict(Strict):
    duty_id: StableId
    boundary_id: StableId
    boundary_text: Text
    duty_evidence: list[Evidence] = Field(min_length=1)
    boundary_evidence: list[SourceEvidence] = Field(min_length=1)
    reason: Text


class RoleComparison(Strict):
    role_id: StableId
    role_revision: Text
    role_maturity: Maturity
    judgment: Literal["supported", "unresolved", "not_supported"]
    covered_duty_ids: list[StableId]
    uncovered_duty_ids: list[StableId]
    conflicts: list[RoleBoundaryConflict]
    reason: Text

    @model_validator(mode="after")
    def exclusion_requires_explicit_boundary(self):
        if len(set(self.covered_duty_ids + self.uncovered_duty_ids)) != (
                len(self.covered_duty_ids) + len(self.uncovered_duty_ids)):
            raise ValueError("role duty coverage must not overlap or repeat")
        if self.judgment == "not_supported" and not self.conflicts:
            raise ValueError("not_supported requires an explicit boundary conflict")
        return self


class RoleComparisonSet(Strict):
    schema_version: Literal["m2-role-comparison-1"]
    namespace: Text
    jd_id: Text
    input_sha256: Sha256
    source_analysis_sha256: Sha256
    source_outcome: Literal["complete", "partial", "failed", "not_run"]
    source_coverage: dict[str, Coverage]
    knowledge_id: StableId
    knowledge_revision: Text
    knowledge_sha256: Sha256
    retrieval_scope: Literal["all_roles_in_bound_snapshot"]
    scope_limitation: Text
    checked_role_ids: list[StableId] = Field(min_length=1)
    duties: list[DutySnapshot]
    comparisons: list[RoleComparison] = Field(min_length=1)

    @model_validator(mode="after")
    def exact_checked_scope(self):
        if self.checked_role_ids != sorted(self.checked_role_ids):
            raise ValueError("checked role IDs must be sorted")
        if [item.role_id for item in self.comparisons] != self.checked_role_ids:
            raise ValueError("comparison list must match checked scope")
        duty_ids = {duty.id for duty in self.duties}
        if any(set(item.covered_duty_ids + item.uncovered_duty_ids) != duty_ids
               for item in self.comparisons):
            raise ValueError("every comparison must classify every local duty")
        return self

    def for_role(self, role_id: str) -> RoleComparison:
        for item in self.comparisons:
            if item.role_id == role_id:
                return item
        raise ValueError("role not present in comparison scope")


class ProfileMemberAlignment(Strict):
    member: Text
    state: Literal["exact_synonym", "ambiguous", "unknown"]
    concept_id: StableId | None
    knowledge_status: Literal["test", "candidate", "formal", "ambiguous", "unknown"]


class ProfileRequirement(Strict):
    claim_id: StableId
    members: list[Text] = Field(min_length=1)
    alignments: list[ProfileMemberAlignment] = Field(min_length=1)
    state: Literal["required", "preferred", "mentioned", "not_required", "uncertain"]
    target: Text
    category: Text | None
    combination: Text
    open_set: bool
    degree: Text | None
    degree_polarity: Literal["affirmed", "negated", "unresolved"] | None
    condition: Text | None
    semantic_review: Literal["machine_unreviewed"]

    @model_validator(mode="after")
    def one_alignment_per_member(self):
        if [item.member for item in self.alignments] != self.members:
            raise ValueError("profile requirement must preserve original members")
        return self


class ProfileMember(Strict):
    analysis_key: Text
    namespace: Text
    jd_id: Text
    role_judgment: Literal["supported"]
    duties: list[DutySnapshot] = Field(min_length=1)
    requirements: list[ProfileRequirement]


class RoleProfile(Strict):
    schema_version: Literal["m2-role-profile-1"]
    role_id: StableId
    role_revision: Text
    role_maturity: Maturity
    knowledge_id: StableId
    knowledge_revision: Text
    knowledge_sha256: Sha256
    mode: Literal["candidate_profile"]
    claim_scope: Literal["linked_members_only"]
    not_market_statistics: Literal[True]
    not_formal_role: Literal[True]
    source_analysis_sha256s: list[Sha256]
    members: list[ProfileMember]


class ImpactReport(Strict):
    schema_version: Literal["m2-knowledge-impact-1"]
    old_revision: Text
    new_revision: Text
    old_knowledge_sha256: Sha256
    new_knowledge_sha256: Sha256
    changed_concept_ids: list[StableId]
    changed_aliases: list[Text]
    changed_relations: list[Text]
    changed_role_ids: list[StableId]
    affected: list[Text]
    conservative: bool
    reason: Text

"""Strict knowledge contracts; source maturity never implies TalentMind admission."""
from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from ..foundation.inputs import check_public

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

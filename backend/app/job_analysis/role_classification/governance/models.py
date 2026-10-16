"""Candidate claims, relation proposals and attributed review events, never a release."""
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, model_validator

from ...foundation.models import VersionName
from ...semantics.models import Evidence
from ..models import Fingerprint, StrictModel, Text

StableID = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_-]{0,63}$")]
Nonblank = Annotated[str, StringConstraints(min_length=1, pattern=r"\S")]


class Catalog(StrictModel):
    schema_version: Literal["b32-catalog-1"]
    revision: VersionName
    formal_jobs: list[Text] = Field(max_length=0)


class Candidate(StrictModel):
    id: StableID
    raw_name: Nonblank
    proposed_name: Nonblank | None
    kind: Literal["job", "technology_stack", "mature_composite_candidate"]
    origin: Literal["synthetic_assertion", "manual_pending"]
    proposer: Nonblank
    synthetic_only: bool
    responsibility: Literal["core", "auxiliary", "unspecified"]
    family_candidates: list[Text]
    review_status: Literal["pending_review"]
    unresolved_reason: Nonblank
    name_evidence: list[Evidence] = Field(min_length=1)
    evidence: list[Evidence] = Field(min_length=1)


class Relation(StrictModel):
    id: StableID
    source_id: StableID
    target_id: StableID
    kind: Literal["synonym", "related_to", "specialization_of", "technology_direction_of", "possible_composite_of"]
    proposer: Nonblank
    basis: Nonblank
    evidence: list[Evidence] = Field(min_length=1)
    review_status: Literal["pending_review"]


class Conflict(StrictModel):
    title: Evidence
    duties: Evidence
    reason: Nonblank


class Annotation(StrictModel):
    namespace: Text
    jd_id: Text
    fingerprint: Fingerprint
    candidates: list[Candidate]
    relations: list[Relation]
    material_kind: Literal["undetermined", "possible_multiple_positions"]
    material_evidence: list[Evidence]
    conflicts: list[Conflict]
    notes: str


class Submission(StrictModel):
    schema_version: Literal["b32-submission-1"]
    revision: VersionName
    mode: Literal["synthetic_only", "manual_pending"]
    annotations: list[Annotation]


class Review(StrictModel):
    target_kind: Literal["candidate", "relation"]
    target_id: StableID
    result_version: Fingerprint
    decision: Literal["reviewed_accepted", "reviewed_rejected", "deferred", "withdrawn"]
    reviewer: Nonblank
    basis: Nonblank
    evidence_refs: list[Evidence] = Field(min_length=1)
    supersedes: StableID | None = None
    formal_admitted: Literal[False]

    @model_validator(mode="after")
    def withdrawal_requires_event(self):
        if self.decision == "withdrawn" and self.supersedes is None:
            raise ValueError("withdrawal must reference an earlier review event")
        return self

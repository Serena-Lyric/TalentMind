"""Strict pending claims; publication and quantitative fields are intentionally absent."""
from typing import Literal

from pydantic import Field

from ...foundation.models import VersionName
from ...semantics.models import Evidence
from ..models import Fingerprint, StrictModel, Text
from ..governance.models import Candidate, Conflict, Nonblank, StableID, Review as BaseReview


class FamilyAssertion(StrictModel):
    id: StableID
    family_id: Text
    responsibility: Literal['core', 'auxiliary', 'unspecified']
    evidence: list[Evidence] = Field(min_length=1)


class NamedAssertion(StrictModel):
    id: StableID
    value: Nonblank
    evidence: list[Evidence] = Field(min_length=1)


class Component(StrictModel):
    domain: Nonblank
    responsibility: Literal['core', 'auxiliary', 'unspecified']
    evidence: list[Evidence] = Field(min_length=1)


class PositionTarget(StrictModel):
    id: StableID
    raw_title: Nonblank
    title: Evidence
    identifier: Evidence | None
    section: Evidence
    duties: list[Evidence]
    requirements: list[Evidence]


class Assessment(StrictModel):
    id: StableID
    kind: Literal['family_identifiable_job_unknown', 'competing_canonical_candidates',
                  'integrated_composite_candidate', 'composite_unproven', 'possible_multiple_positions']
    origin: Literal['synthetic_assertion', 'manual_pending']
    proposer: Nonblank
    basis: Nonblank
    evidence: list[Evidence] = Field(min_length=1)
    components: list[Component]
    shared_delivery: Evidence | None
    position_targets: list[PositionTarget]


class Annotation(StrictModel):
    namespace: Text
    jd_id: Text
    fingerprint: Fingerprint
    origin: Literal['synthetic_assertion']
    proposer: Nonblank
    family_assertions: list[FamilyAssertion]
    candidates: list[Candidate]
    technology_tracks: list[NamedAssertion]
    seniority: list[NamedAssertion]
    assessments: list[Assessment]
    conflicts: list[Conflict]
    notes: str


class Submission(StrictModel):
    schema_version: Literal['b34-submission-1']
    revision: VersionName
    mode: Literal['synthetic_only']
    annotations: list[Annotation]


class Review(BaseReview):
    target_kind: Literal['candidate', 'family_assertion', 'technology_track', 'seniority', 'assessment', 'position_target']

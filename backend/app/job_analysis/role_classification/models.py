"""Strict assertion boundary; known means supplied, never independently verified."""
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..foundation.models import VersionName
from ..semantics.models import Evidence

Text = Annotated[str, Field(min_length=1, pattern=r"\S")]
Fingerprint = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Dimension = Literal["job_family", "canonical_job", "technology_tracks", "seniority"]
DIMENSIONS = ("job_family", "canonical_job", "technology_tracks", "seniority")


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Taxonomy(StrictModel):
    schema_version: Literal["b30-taxonomy-1"]
    revision: VersionName
    mode: Literal["empty", "synthetic_example"]
    job_family: list[Text]
    canonical_job: list[Text]
    technology_tracks: list[Text]
    seniority: list[Text]

    @model_validator(mode="after")
    def check_values(self):
        for dimension in DIMENSIONS:
            values = getattr(self, dimension)
            if len(values) != len(set(values)) or any(v != v.strip() for v in values):
                raise ValueError("duplicate or padded taxonomy value")
            if self.mode == "empty" and values:
                raise ValueError("empty taxonomy cannot contain values")
        return self


class Decision(StrictModel):
    state: Literal["known", "unknown", "unresolved"]
    value: Text | None
    candidates: list[Text]
    evidence: list[Evidence]
    reason: Text

    @model_validator(mode="after")
    def check_state(self):
        if self.state == "known":
            if self.value is None or not self.evidence or self.candidates:
                raise ValueError("known assertion requires one value and evidence")
        elif self.value is not None:
            raise ValueError("unknown/unresolved cannot assert a value")
        if self.candidates and (self.state != "unresolved" or not self.evidence):
            raise ValueError("candidates require unresolved with evidence")
        if len(set(self.candidates)) != len(self.candidates):
            raise ValueError("duplicate candidates")
        return self


class AuxiliaryRole(StrictModel):
    primary: Text
    role: Decision
    evidence: list[Evidence] = Field(min_length=1)


class Conflict(StrictModel):
    dimension: Dimension
    title: Evidence
    duties: Evidence
    reason: Text


class Annotation(StrictModel):
    namespace: Text
    jd_id: Text
    fingerprint: Fingerprint
    origin: Literal["synthetic_assertion", "manual_pending"]
    author: Text
    review_status: Literal["pending_review"]
    job_family: Decision
    canonical_job: Decision
    technology_tracks: list[Decision]
    technology_tracks_status: Literal["known", "unknown", "unresolved"]
    seniority: Decision
    auxiliary_roles: list[AuxiliaryRole]
    material_kind: Literal["undetermined", "single_role", "hybrid_role", "possible_multiple_positions"]
    material_evidence: list[Evidence]
    conflicts: list[Conflict]
    notes: str


class AnnotationBatch(StrictModel):
    schema_version: Literal["b30-annotations-1"]
    annotations: list[Annotation]

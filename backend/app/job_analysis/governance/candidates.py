"""Audit interfaces only. No path here can write to the formal dictionary."""
from typing import Literal

from pydantic import Field, field_validator

from ..foundation.store import now
from .catalog import Strict


class Review(Strict):
    candidate_id: str = Field(min_length=1)
    decision: Literal["reviewed_accepted", "reviewed_rejected", "deferred"]
    reviewer: str = Field(min_length=1)
    basis: str = Field(min_length=1)
    evidence_refs: list[str] = Field(min_length=1)
    candidate_version: str = Field(min_length=1)
    formal_admitted: Literal[False]
    created_at: str

    @field_validator("reviewer", "basis")
    @classmethod
    def nonblank_attribution(cls, value):
        if not value.strip():
            raise ValueError("nonblank review attribution required")
        return value

    @field_validator("evidence_refs")
    @classmethod
    def nonblank_references(cls, value):
        if not all(ref.strip() for ref in value):
            raise ValueError("nonblank review evidence references required")
        return value


def review_event(candidate, *, decision, reviewer, basis, evidence_refs):
    return Review.model_validate(dict(candidate_id=candidate["id"], decision=decision,
        reviewer=reviewer, basis=basis, evidence_refs=evidence_refs, candidate_version=candidate["version"],
        formal_admitted=False, created_at=now())).model_dump()


def validate_admission(candidate, review=None):
    if review is not None:
        review = Review.model_validate(review).model_dump()
        if (review["candidate_id"], review["candidate_version"]) != (candidate["id"], candidate["version"]):
            raise ValueError("review belongs to a different candidate/version")
    return dict(candidate_id=candidate["id"], allowed=False, policy_status="not_configured",
        review_status=review["decision"] if review else "pending_review",
        reasons=["automatic_admission_disabled", "validated_admission_policy_not_defined",
                 "independent_evidence_not_established"], formal_admitted=False)

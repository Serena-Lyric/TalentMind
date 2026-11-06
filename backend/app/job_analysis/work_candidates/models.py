"""P3 command boundary. No operation can grant a formal occupation identity."""
from typing import Annotated, Literal

from pydantic import Field, model_validator

from ..knowledge.models import Sha256, StableId, Strict, Text


class Binding(Strict):
    registry_id: Text
    revision: int = Field(ge=0)
    sha256: Sha256


class WorkRef(Strict):
    analysis_sha256: Sha256
    claim_id: Text


class Create(Strict):
    op: Literal["create"]
    candidate_id: StableId
    description: Text
    research_question: Text
    core_work: list[WorkRef] = Field(min_length=1)


class Link(Strict):
    op: Literal["link"]
    candidate_id: StableId
    analysis_sha256: Sha256
    work_ids: list[Text] = Field(min_length=1)
    reason: Text


class Verification(Strict):
    kind: Literal["synthetic_control", "external_review_record"]
    subject_sha256: Sha256
    document: Text
    document_sha256: Sha256
    quote: Text
    reviewer: Text
    provider_version: Text


class Replacement(Strict):
    analysis_sha256: Sha256
    work_ids: list[Text] = Field(min_length=1)


class Correct(Strict):
    op: Literal["correct"]
    relation_id: Sha256
    expected_sha256: Sha256
    decision: Literal["corroborates", "weakens", "rejects", "withdraw"]
    reason: Text
    verification: Verification | None
    replacement: Replacement | None = None
    counterevidence: list[WorkRef] = Field(default_factory=list)


class Describe(Strict):
    op: Literal["describe"]
    candidate_id: StableId
    expected_version: int = Field(ge=1)
    description: Text
    research_question: Text
    unresolved: list[Text] = Field(min_length=1)
    reason: Text


class Batch(Strict):
    schema_version: Literal["m2-work-batch-1"]
    batch_id: StableId
    baseline: Binding
    operation_version: Text
    analysis_sha256s: list[Sha256]
    operations: list[Annotated[Create | Link | Correct | Describe, Field(discriminator="op")]]

    @model_validator(mode="after")
    def unique_analyses(self):
        if len(self.analysis_sha256s) != len(set(self.analysis_sha256s)):
            raise ValueError("duplicate analysis reference")
        return self

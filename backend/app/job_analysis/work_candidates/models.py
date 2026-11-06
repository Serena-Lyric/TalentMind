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


class Batch(Strict):
    schema_version: Literal["m2-work-batch-1"]
    batch_id: StableId
    baseline: Binding
    operation_version: Text
    analysis_sha256s: list[Sha256]
    operations: list[Create]

    @model_validator(mode="after")
    def unique_analyses(self):
        if len(self.analysis_sha256s) != len(set(self.analysis_sha256s)):
            raise ValueError("duplicate analysis reference")
        return self

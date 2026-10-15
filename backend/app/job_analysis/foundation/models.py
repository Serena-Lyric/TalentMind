"""Boundary schemas and explicit dependency manifests, never credentials."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from .inputs import InputRecord, canonical, digest, parse_json

VersionName = Annotated[str, Field(pattern=r"^[A-Za-z0-9_.:/+\-]{1,160}$")]


class AnalyzerSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    extractor: VersionName
    prompt: VersionName
    model: VersionName
    configuration: VersionName


class Analyzer(Protocol):
    spec: AnalyzerSpec

    def analyze(self, record: InputRecord) -> dict | str:
        """Use the complete payload. Return coverage and per-JD fact claims."""
        ...


@dataclass(frozen=True)
class AnalysisVersion:
    manifest_json: str

    @property
    def key(self):
        return digest(self.manifest)

    @property
    def manifest(self):
        return parse_json(self.manifest_json)


def analysis_version(revision: str, spec: AnalyzerSpec, dictionary: list[dict]) -> AnalysisVersion:
    spec = AnalyzerSpec.model_validate(spec.model_dump())
    # Explicit revisions cover code changes; hashes freeze actual dictionary contents.
    return AnalysisVersion(canonical({"revision": revision, "dependencies": {
        "parser": "strict-json-v1", "cleaner": "identity-v1", "validator": "per-jd-substring-v1",
        "dictionary": digest(dictionary), **spec.model_dump()}}))


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    namespace: str
    jd_id: str
    field: Literal["job_title", "raw_text", "duties", "experience", "requirements"]
    quote: str


class FactClaim(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    kind: Literal["skill", "job"]
    name: Annotated[str, Field(min_length=1)]
    requirement: Literal["unclassified", "legacy_required", "legacy_bonus",
                         "explicit_required", "preferred", "mentioned", "explicit_not_required", "undetermined"]
    evidence: Evidence | None = None
    verified: bool | None = None


class Response(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    coverage: Literal["complete", "incomplete"]
    facts: list

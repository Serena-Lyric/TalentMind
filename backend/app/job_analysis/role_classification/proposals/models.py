"""Independent B3-1 contracts; the confirmed catalogue is only dimension one."""
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from ...foundation.inputs import check_public, parse_json
from ..models import StrictModel, Text, Fingerprint
from ..validation import validate_evidence
from ...foundation.models import VersionName
from ...semantics.models import Evidence

FAMILIES = {
    "software_engineering": "软件研发",
    "test_quality_engineering": "测试与质量工程",
    "data_ai": "数据与人工智能",
    "infrastructure_operations": "基础设施与运维",
    "network_information_security": "网络与信息安全",
    "embedded_system_software": "嵌入式与系统软件",
    "technical_services_delivery": "技术服务与交付",
}


class Family(StrictModel):
    id: Text
    label: Text
    scope: Text


class FamilyTaxonomy(StrictModel):
    schema_version: Literal["b31-family-taxonomy-1"]
    revision: VersionName
    mode: Literal["confirmed_families"]
    scope: Text
    job_family: list[Family]
    canonical_job: list[Text]
    technology_tracks: list[Text]
    seniority: list[Text]

    @model_validator(mode="after")
    def confirmed_only(self):
        ids = [f.id for f in self.job_family]
        if len(ids) != len(set(ids)) or {f.id: f.label for f in self.job_family} != FAMILIES:
            raise ValueError("exactly seven confirmed family IDs and labels required")
        if self.canonical_job or self.technology_tracks or self.seniority:
            raise ValueError("unconfirmed dimensions must remain empty")
        if any(text != text.strip() for f in self.job_family for text in (f.id, f.label, f.scope)):
            raise ValueError("padded catalogue values prohibited")
        return self


def load_taxonomy(path):
    path = Path(path)
    if path.suffix.lower() != ".json":
        raise ValueError("explicit JSON taxonomy required")
    value = parse_json(path.read_text(encoding="utf-8-sig"))
    check_public(value)
    return FamilyTaxonomy.model_validate(value).model_dump()


class Clue(StrictModel):
    kind: Literal["core", "auxiliary", "unspecified"]
    rule: Text
    evidence: Evidence


class Candidate(StrictModel):
    family_id: Text
    clues: list[Clue] = Field(min_length=1)


class TitleClue(StrictModel):
    family_id: Text
    evidence: Evidence


class ContextClue(StrictModel):
    reason: Text
    evidence: Evidence


class UnknownDimension(StrictModel):
    state: Literal["unknown"]
    value: None


class Proposal(StrictModel):
    schema_version: Literal["b31-proposal-1"]
    namespace: Text
    jd_id: Text
    fingerprint: Fingerprint
    source_payload: dict
    candidates: list[Candidate]
    title_clues: list[TitleClue]
    context_clues: list[ContextClue]
    primary_family_hint: Text | None
    resolution: Literal["proposed", "unresolved", "unknown"]
    reasons: list[Text]
    canonical_job: UnknownDimension
    technology_tracks: list[Text] = Field(max_length=0)
    seniority: UnknownDimension
    review_status: Literal["pending_review"]
    classification_complete: Literal[False]
    formal_statistics_eligible: Literal[False]
    semantic_validation: Literal["finite_deterministic_suggestions_only"]


def validate_proposal(record, body, taxonomy):
    check_public(body)
    config = FamilyTaxonomy.model_validate(taxonomy)
    item = Proposal.model_validate(body)
    if (item.namespace, item.jd_id, item.fingerprint) != (record.namespace, record.jd_id, record.fingerprint):
        raise ValueError("proposal source identity mismatch")
    if item.source_payload != record.payload:
        raise ValueError("proposal source payload mismatch")
    allowed = {f.id for f in config.job_family}
    ids = [c.family_id for c in item.candidates]
    if len(ids) != len(set(ids)) or not set(ids) <= allowed:
        raise ValueError("duplicate or foreign family candidate")
    for candidate in item.candidates:
        for clue in candidate.clues:
            validate_evidence(record, clue.evidence.model_dump())
            if clue.evidence.field not in ("duties", "raw_text"):
                raise ValueError("duty evidence must refer to duties or raw_text")
    for clue in item.title_clues:
        validate_evidence(record, clue.evidence.model_dump())
        if clue.evidence.field != "job_title" or clue.family_id not in allowed:
            raise ValueError("invalid title comparison")
    for clue in item.context_clues:
        validate_evidence(record, clue.evidence.model_dump())
    hint = item.primary_family_hint
    if item.resolution == "proposed":
        core = {c.family_id for c in item.candidates if any(s.kind == "core" for s in c.clues)}
        if core != {hint} or item.reasons or any(s.kind == "unspecified" for c in item.candidates for s in c.clues):
            raise ValueError("primary family hint requires unambiguous explicit core")
    elif hint is not None:
        raise ValueError("unresolved/unknown cannot propose a primary family")
    return item.model_dump()

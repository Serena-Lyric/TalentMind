"""Append-only candidate knowledge with deduplicated observations and no formal gate."""
from __future__ import annotations

import hashlib
import re
import unicodedata
from pathlib import Path
from typing import Literal

from pydantic import Field

from ..baseline.contract import validate_analysis
from ..foundation.inputs import digest
from ..foundation.store import safe_destination
from ..semantics.models import Evidence
from .alignment import AlignmentResult
from .models import Maturity, StableId, Strict, Text, normalize_term
from .storage import read_result, save_result


CAPABILITY_CUES = re.compile(
    r"要求|需要|熟悉|掌握|了解|具备|使用|运用|基于|至少|优先|技能|能力|经验"
)


class RequirementContext(Strict):
    state: Text
    target: Text
    category: Text | None
    members: list[Text] = Field(min_length=1)
    combination: Text
    open_set: bool
    degree: Text | None
    degree_polarity: Literal["affirmed", "negated", "unresolved"] | None
    condition: Text | None


class CandidateObservation(Strict):
    observation_key: str = Field(pattern=r"^[0-9a-f]{64}$")
    namespace: Text
    jd_id: Text
    source: Text
    input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    analysis_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    claim_id: StableId
    member: Text
    requirement_context: RequirementContext
    evidence: list[Evidence] = Field(min_length=1)
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class CandidateVersion(Strict):
    schema_version: Literal["m2-knowledge-candidate-1"]
    candidate_id: StableId
    surface: Text
    normalized_term: Text
    description: Text
    status: Literal["observing", "disputed", "withdrawn"]
    maturity: Maturity
    version: int = Field(ge=1)
    reason: Text
    referenced_observations: list[CandidateObservation] = Field(min_length=1)
    independent_evidence: int = Field(ge=1)
    verification_strength: Literal["single_independent_context", "multiple_independent_contexts"]
    competing_hypotheses: list[Text]
    formal_admission_allowed: Literal[False]


class AdmissionDecision(Strict):
    candidate_id: StableId
    candidate_version: int = Field(ge=1)
    allowed: Literal[False]
    status: Literal["formal_admission_disabled"]
    reasons: list[Text] = Field(min_length=1)


class StructuralDecision(Strict):
    action: Literal["merge", "split", "confirm_identity", "formal_admit", "publish_formal"]
    allowed: Literal[False]
    status: Literal["requires_human_decision"]
    reason: Text


def _content_digest(raw_text: str) -> str:
    normalized = re.sub(r"\s+", "", unicodedata.normalize("NFKC", raw_text)).casefold()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _clear_capability_context(requirement, member: str, evidence_text: str) -> bool:
    if requirement.target != "capability" or requirement.category is None:
        return False
    if len(normalize_term(member)) < 2:
        return False
    delimited = (requirement.combination != "single" or requirement.open_set
                 or len(requirement.members) > 1 or requirement.degree is not None
                 or requirement.condition is not None)
    return bool(delimited or CAPABILITY_CUES.search(evidence_text))


def admission_decision(candidate: CandidateVersion) -> AdmissionDecision:
    return AdmissionDecision(
        candidate_id=candidate.candidate_id,
        candidate_version=candidate.version,
        allowed=False,
        status="formal_admission_disabled",
        reasons=[
            "Formal skill admission thresholds are not approved.",
            "Machine observations and automatic revisions are not human confirmation.",
            "Independent evidence count is not a calibrated probability.",
        ],
    )


def structural_decision(action: str) -> StructuralDecision:
    if action not in {"merge", "split", "confirm_identity", "formal_admit", "publish_formal"}:
        raise ValueError("unknown structural action")
    return StructuralDecision(
        action=action,
        allowed=False,
        status="requires_human_decision",
        reason="This action changes knowledge identity or formal availability and requires explicit human confirmation.",
    )


class CandidateRegistry:
    def __init__(self, path: Path | str):
        self.root = safe_destination(path)
        self.root.mkdir(parents=True, exist_ok=True)

    def _versions(self, candidate_id: str) -> list[int]:
        root = self.root / "candidates" / candidate_id / "versions"
        if not root.exists():
            return []
        return sorted(int(item.name) for item in root.iterdir()
                      if item.is_dir() and item.name.isdigit())

    def read(self, candidate_id: str, version: int | None = None) -> CandidateVersion:
        versions = self._versions(candidate_id)
        if not versions:
            raise ValueError("candidate not found")
        selected = versions[-1] if version is None else version
        if selected not in versions:
            raise ValueError("candidate version not found")
        value = read_result(self.root / "candidates" / candidate_id / "versions" / str(selected))
        record = CandidateVersion.model_validate(value)
        if (record.candidate_id, record.version) != (candidate_id, selected):
            raise ValueError("candidate identity/version mismatch")
        return record

    def _write(self, value: CandidateVersion) -> CandidateVersion:
        path = self.root / "candidates" / value.candidate_id / "versions" / str(value.version)
        save_result(path, value.model_dump())
        return value

    def observe(self, analysis: dict, alignment: AlignmentResult) -> list[CandidateVersion]:
        checked = validate_analysis(analysis)
        bound = AlignmentResult.model_validate(alignment.model_dump())
        if bound.source_analysis_sha256 != digest(checked.model_dump()):
            raise ValueError("alignment belongs to a different P1 analysis")
        claims = {claim.id: claim for claim in checked.claims}
        observations = []
        for decision in bound.alignments:
            if decision.state != "unknown":
                continue
            claim = claims[decision.claim_id]
            if claim.requirement is None:
                continue
            requirement = claim.requirement
            evidence = [item.model_dump() for item in [*claim.evidence, *requirement.scope_evidence]]
            evidence_text = "\n".join(item["quote"] for item in evidence)
            if not _clear_capability_context(requirement, decision.member, evidence_text):
                continue
            observation_key = digest(dict(
                namespace=checked.namespace,
                jd_id=checked.jd_id,
                input_sha256=checked.input_sha256,
                claim_id=claim.id,
                member=decision.member,
            ))
            observations.append(CandidateObservation(
                observation_key=observation_key,
                namespace=checked.namespace,
                jd_id=checked.jd_id,
                source=str(checked.input_row.get("source", "unknown")),
                input_sha256=checked.input_sha256,
                analysis_sha256=bound.source_analysis_sha256,
                claim_id=claim.id,
                member=decision.member,
                requirement_context=RequirementContext(
                    state=requirement.state,
                    target=requirement.target,
                    category=requirement.category,
                    members=requirement.members,
                    combination=requirement.combination,
                    open_set=requirement.open_set,
                    degree=requirement.degree,
                    degree_polarity=requirement.degree_polarity,
                    condition=requirement.condition,
                ),
                evidence=evidence,
                content_sha256=_content_digest(str(checked.input_row["raw_text"])),
            ))
        return [self._observe_one(item) for item in observations]

    def _observe_one(self, observation: CandidateObservation) -> CandidateVersion:
        normalized = normalize_term(observation.member)
        candidate_id = "candidate-" + hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
        versions = self._versions(candidate_id)
        if not versions:
            return self._write(CandidateVersion(
                schema_version="m2-knowledge-candidate-1",
                candidate_id=candidate_id,
                surface=observation.member,
                normalized_term=normalized,
                description=f"待核对的能力表达：{observation.member}",
                status="observing",
                maturity="candidate",
                version=1,
                reason="Clear capability context created an evidence-bound candidate observation.",
                referenced_observations=[observation],
                independent_evidence=1,
                verification_strength="single_independent_context",
                competing_hypotheses=[],
                formal_admission_allowed=False,
            ))
        previous = self.read(candidate_id)
        if any(item.observation_key == observation.observation_key
               for item in previous.referenced_observations):
            return previous
        referenced = [*previous.referenced_observations, observation]
        independent = len({item.content_sha256 for item in referenced})
        strength = ("single_independent_context" if independent == 1
                    else "multiple_independent_contexts")
        return self._write(CandidateVersion(
            **previous.model_dump(exclude={
                "version", "referenced_observations", "independent_evidence",
                "verification_strength", "reason",
            }),
            version=previous.version + 1,
            reason="New source observation appended; independence is based on normalized content, not platform count.",
            referenced_observations=referenced,
            independent_evidence=independent,
            verification_strength=strength,
        ))

    def revise(self, candidate_id: str, description: str, reason: str,
               competing_hypotheses: list[str] | None = None) -> CandidateVersion:
        previous = self.read(candidate_id)
        return self._write(CandidateVersion(
            **previous.model_dump(exclude={"version", "description", "reason", "competing_hypotheses"}),
            version=previous.version + 1,
            description=description,
            reason=reason,
            competing_hypotheses=(previous.competing_hypotheses if competing_hypotheses is None
                                  else competing_hypotheses),
        ))

    def mark_disputed(self, candidate_id: str, reason: str,
                      competing_hypotheses: list[str]) -> CandidateVersion:
        previous = self.read(candidate_id)
        if not competing_hypotheses:
            raise ValueError("dispute requires at least one competing hypothesis")
        return self._write(CandidateVersion(
            **previous.model_dump(exclude={"version", "status", "reason", "competing_hypotheses"}),
            version=previous.version + 1,
            status="disputed",
            reason=reason,
            competing_hypotheses=competing_hypotheses,
        ))

    def withdraw(self, candidate_id: str, reason: str) -> CandidateVersion:
        previous = self.read(candidate_id)
        return self._write(CandidateVersion(
            **previous.model_dump(exclude={"version", "status", "reason"}),
            version=previous.version + 1,
            status="withdrawn",
            reason=reason,
        ))

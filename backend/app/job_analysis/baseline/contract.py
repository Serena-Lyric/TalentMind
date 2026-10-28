"""Additive M2 semantic boundary v0.1; does not project into legacy contracts."""
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..foundation.inputs import InputRecord, check_public
from ..semantics.models import Evidence, State

Text = Annotated[str, Field(min_length=1, pattern=r"\S")]
Sha = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
KnowledgeStatus = Literal["test", "candidate", "formal"]
DIMENSIONS = {"goals", "objects", "duties", "requirements", "relations", "classification"}


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Version(Strict):
    id: Text
    revision: Text
    sha256: Sha


class Knowledge(Version):
    status: KnowledgeStatus


class ReferenceSource(Strict):
    title: Text
    url: Annotated[str, Field(pattern=r"^https://")]
    document_version: Text
    locator: Text
    retrieved_on: Text
    sha256: Sha


class RoleReference(Strict):
    """P0 external occupation-source fixture, not the schema for all future role candidates."""
    id: Text
    name: Text
    definition_version: Text
    status: KnowledgeStatus
    drafted_by: Literal["agent_source_summary"]
    source_occupation_code: Text
    goals: list[Text] = Field(min_length=1)
    core_duties: list[Text] = Field(min_length=1)
    known_scope: list[Text] = Field(min_length=1)
    unresolved_boundaries: list[Text] = Field(min_length=1)
    use: Text
    sources: list[ReferenceSource] = Field(min_length=1)
    approval_source: Text | None

    @model_validator(mode="after")
    def formal_requires_approval(self):
        if self.status == "formal" and not self.approval_source:
            raise ValueError("formal role needs per-definition human approval evidence")
        return self


class Requirement(Strict):
    state: State
    target: Literal["capability", "experience", "domain", "education", "tenure", "certificate", "unresolved"]
    category: Literal["technical_skill", "professional_skill", "engineering_practice", "soft_skill"] | None
    members: list[Text] = Field(min_length=1)
    combination: Literal["single", "any_of", "all_of", "unresolved"]
    open_set: bool
    degree: Text | None
    degree_polarity: Literal["affirmed", "negated", "unresolved"] | None
    condition: Text | None
    reason: Text
    scope_evidence: list[Evidence] = Field(min_length=1)

    @model_validator(mode="after")
    def consistent(self):
        if (self.degree is None) != (self.degree_polarity is None):
            raise ValueError("degree and its polarity must be supplied together")
        if self.combination == "single" and len(self.members) != 1:
            raise ValueError("single requirement must have one member")
        if self.combination in {"any_of", "all_of"} and len(self.members) < 2:
            raise ValueError("combination must preserve multiple alternatives")
        if len(self.members) != len(set(self.members)):
            raise ValueError("duplicate requirement member")
        if self.target != "capability" and self.category is not None:
            raise ValueError("non-capability requirements are not skill categories")
        return self


class Claim(Strict):
    id: Text
    kind: Literal["goal", "object", "duty", "requirement"]
    text: Text
    evidence: list[Evidence] = Field(min_length=1)
    requirement: Requirement | None
    core: bool | None
    reason: Text

    @model_validator(mode="after")
    def typed_requirement(self):
        if (self.kind == "requirement") != (self.requirement is not None):
            raise ValueError("only requirement claims contain requirement semantics")
        return self


class Relation(Strict):
    duty_id: Text
    requirement_id: Text
    basis: Literal["explicit", "inferred", "unknown"]
    evidence: list[Evidence]
    reason: Text

    @model_validator(mode="after")
    def supported(self):
        if self.basis != "unknown" and not self.evidence:
            raise ValueError("explicit/inferred links require source context")
        return self


class Coverage(Strict):
    status: Literal["complete", "partial", "not_run", "failed"]
    reason: Text


class Alignment(Strict):
    claim_id: Text
    member: Text
    concept_id: Text | None
    knowledge_id: Text | None
    status: Literal["unknown", "test", "candidate", "formal"]
    reason: Text


class RoleConflict(Strict):
    """Explicit boundary in the parent judgment's versioned reference versus a source JD duty."""
    duty_id: Text
    boundary_locator: Text
    boundary_quote: Text
    reason: Text


class RoleJudgment(Strict):
    reference_id: Text
    reference_revision: Text
    knowledge_status: KnowledgeStatus
    judgment: Literal["supported", "unresolved", "not_supported"]
    covered_duty_ids: list[Text]
    uncovered_duty_ids: list[Text]
    conflicts: list[RoleConflict]
    reason: Text

    @model_validator(mode="after")
    def exclusion_needs_boundary_conflict(self):
        if self.judgment == "not_supported" and not self.conflicts:
            raise ValueError("not_supported requires an explicit boundary conflict; a coverage gap remains unresolved")
        return self


class Analysis(Strict):
    contract_version: Literal["m2-semantic-0.2"]
    namespace: Text
    jd_id: Text
    input_row: dict
    input_sha256: Sha
    input_version: Text
    analyzer: Version
    model: Version
    prompt: Version
    configuration: Version
    knowledge: list[Knowledge]
    outcome: Literal["complete", "partial", "failed", "not_run"]
    coverage: dict[str, Coverage]
    claims: list[Claim]
    alignments: list[Alignment]
    relations: list[Relation]
    role_judgments: list[RoleJudgment]
    semantic_review: Literal["machine_unreviewed"]

    @model_validator(mode="after")
    def bindings(self):
        row = InputRecord.from_row(self.namespace, self.input_row)
        if row.jd_id != self.jd_id or row.fingerprint != self.input_sha256:
            raise ValueError("input identity/content mismatch")
        if set(self.coverage) != DIMENSIONS:
            raise ValueError("every capability must report coverage")
        statuses = {v.status for v in self.coverage.values()}
        expected = ("complete" if statuses == {"complete"} else "not_run" if statuses == {"not_run"}
                    else "failed" if statuses <= {"failed", "not_run"} else "partial")
        if self.outcome != expected:
            raise ValueError("outcome disagrees with capability coverage")
        claims = {c.id: c for c in self.claims}
        if len(claims) != len(self.claims):
            raise ValueError("duplicate claim identity")
        for claim in self.claims:
            dimension = {"goal": "goals", "object": "objects", "duty": "duties", "requirement": "requirements"}[claim.kind]
            if self.coverage[dimension].status in {"failed", "not_run"}:
                raise ValueError("saved claims require complete or partial capability")
            evidence = list(claim.evidence)
            if claim.requirement:
                req = claim.requirement
                evidence += req.scope_evidence
                context = "\n".join(e.quote for e in req.scope_evidence)
                if any(value is not None and value not in context for value in (req.degree, req.condition)):
                    raise ValueError("degree/condition must retain literal scope evidence")
            for ev in evidence:
                self.check_evidence(ev, row)
        pairs = set()
        for relation in self.relations:
            duty, req = claims.get(relation.duty_id), claims.get(relation.requirement_id)
            if not duty or duty.kind != "duty" or not req or req.kind != "requirement":
                raise ValueError("relation endpoints must be local duty/requirement claims")
            pair = (relation.duty_id, relation.requirement_id)
            if pair in pairs:
                raise ValueError("duplicate relation pair")
            pairs.add(pair)
            for ev in relation.evidence:
                self.check_evidence(ev, row)
        if self.relations and self.coverage["relations"].status in {"failed", "not_run"}:
            raise ValueError("relations cannot be reported by a failed/unrun capability")
        standards = {k.id: k for k in self.knowledge}
        if len(standards) != len(self.knowledge):
            raise ValueError("duplicate knowledge identity")
        for alignment in self.alignments:
            claim = claims.get(alignment.claim_id)
            if not claim or not claim.requirement or alignment.member not in claim.requirement.members:
                raise ValueError("alignment must preserve an original requirement member")
            if alignment.status == "unknown":
                if alignment.concept_id is not None or alignment.knowledge_id is not None:
                    raise ValueError("unknown concept cannot claim canonical knowledge")
            else:
                standard = standards.get(alignment.knowledge_id)
                if not alignment.concept_id or not standard or standard.status != alignment.status:
                    raise ValueError("alignment knowledge/status mismatch")
        for judgment in self.role_judgments:
            ref = standards.get(judgment.reference_id)
            if not ref or (ref.revision, ref.status) != (judgment.reference_revision, judgment.knowledge_status):
                raise ValueError("role reference version/status mismatch")
            covered, uncovered = judgment.covered_duty_ids, judgment.uncovered_duty_ids
            if len(set(covered + uncovered)) != len(covered + uncovered):
                raise ValueError("duty coverage must not overlap or repeat")
            if any(i not in claims or claims[i].kind != "duty" for i in covered + uncovered):
                raise ValueError("role explanation must reference local duties")
            for conflict in judgment.conflicts:
                if conflict.duty_id not in claims or claims[conflict.duty_id].kind != "duty":
                    raise ValueError("role boundary conflict must reference an evidenced local duty")
        if self.role_judgments and self.coverage["classification"].status in {"failed", "not_run"}:
            raise ValueError("role judgments require usable classification coverage")
        return self

    def check_evidence(self, ev, row):
        if (ev.namespace, ev.jd_id, ev.fingerprint) != (self.namespace, self.jd_id, row.fingerprint):
            raise ValueError("foreign evidence identity/version")
        text = row.payload.get(ev.field, "")
        if not 0 <= ev.start < ev.end <= len(text) or text[ev.start:ev.end] != ev.quote:
            raise ValueError("evidence must match Python code-point [start,end) indices")


def validate_analysis(data) -> Analysis:
    check_public(data)
    return Analysis.model_validate(data)

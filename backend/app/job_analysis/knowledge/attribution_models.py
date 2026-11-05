"""Additive P2-2 reading contract, independent of P2-1 comparison v1."""
from typing import Literal
import hashlib

from pydantic import Field, model_validator

from ..baseline.contract import Analysis, Claim
from ..foundation.inputs import InputRecord, digest, parse_json
from ..semantics.models import Evidence
from .models import AlignmentResult, KnowledgeSource, RoleDefinition, Sha256, SourceEvidence, Strict, Text, validate_snapshot
from .role_policy import AttributionPolicy


class WorkSupport(Strict):
    claim_id: Text
    reference_id: Text
    action: Text
    object: Text
    importance: Literal["core", "auxiliary", "unknown"]
    basis: Literal["bounded_pattern_support"] = "bounded_pattern_support"
    jd_evidence: Evidence
    reference_evidence: list[SourceEvidence] = Field(min_length=1)


class DeliverySupport(Strict):
    claim_id: Text
    text: Text
    jd_evidence: Evidence
    reference_goals: list[Text] = Field(min_length=1)


class RoleExplanation(Strict):
    role_id: Text
    definition: RoleDefinition
    retrieval_clues: list[Text]
    judgment: Literal["core_candidate", "auxiliary", "hypothesis", "conflict", "unresolved"]
    supports: list[WorkSupport]
    context_supports: list[WorkSupport]
    deliveries: list[DeliverySupport]
    conflicts: list[WorkSupport]
    uncovered_duty_ids: list[Text]
    unmatched_reference_ids: list[Text]
    goal_claim_ids: list[Text]
    object_claim_ids: list[Text]
    unmatched_goal_claim_ids: list[Text]
    unmatched_object_claim_ids: list[Text]
    uncertainty: list[Text]
    reason: Text


class Retrieval(Strict):
    method_version: Literal["exhaustive-duty-reference-1"] = "exhaustive-duty-reference-1"
    ranking: Literal["unranked_exhaustive"] = "unranked_exhaustive"
    available_role_ids: list[Text]
    checked_role_ids: list[Text]
    recalled_role_ids: list[Text]
    scope_limitation: Text
    status: Literal["completed", "empty_catalog", "facts_unavailable"]


class AxisCandidate(Strict):
    value: Text
    strength: Literal["core_candidate", "local_hypothesis", "auxiliary", "explicit_mention"]
    role_ids: list[Text]
    claim_ids: list[Text]
    evidence: list[Evidence] = Field(min_length=1)
    reason: Text


class Axis(Strict):
    status: Literal["single", "multiple", "unresolved"]
    values: list[Text]
    candidates: list[AxisCandidate]
    reason: Text

    @model_validator(mode="after")
    def consistent(self):
        if len(set(self.values)) != len(self.values):
            raise ValueError("duplicate axis values")
        if not set(self.values) <= {c.value for c in self.candidates}:
            raise ValueError("axis value has no evidence candidate")
        expected = "unresolved" if not self.values else "single" if len(self.values) == 1 else "multiple"
        if self.status != expected:
            raise ValueError("axis status disagrees with selected values")
        return self


class Axes(Strict):
    family: Axis
    canonical_job: Axis
    technology_tracks: Axis
    seniority: Axis


class UnaccountedWork(Strict):
    claim_id: Text
    evidence: Evidence
    reason: Text


class AttributionResult(Strict):
    schema_version: Literal["m2-role-attribution-1"] = "m2-role-attribution-1"
    explanation_version: Literal["bounded-work-attribution-1", "bounded-work-attribution-2"] = "bounded-work-attribution-1"
    implementation_sha256: Sha256
    source_analysis_sha256: Sha256
    source_analysis: Analysis
    knowledge_id: Text
    knowledge_revision: Text
    knowledge_sha256: Sha256
    knowledge_json: Text
    knowledge_sources: list[KnowledgeSource]
    policy: AttributionPolicy
    policy_sha256: Sha256
    alignment: AlignmentResult
    retrieval: Retrieval
    comparisons: list[RoleExplanation]
    axes: Axes
    primary_role_id: Text | None
    auxiliary_role_ids: list[Text]
    work_shape: Literal["single_core_hypothesis", "parallel_core_hypothesis", "mixed_hypothesis",
                        "composite_hypothesis", "multi_position_advertisement", "unresolved"]
    shape_evidence: list[Evidence]
    limitations: list[Text]
    unaccounted_work: list[UnaccountedWork]
    identity_action: Literal["none"] = "none"
    semantic_review: Literal["machine_unreviewed"] = "machine_unreviewed"
    formal_statistics_eligible: Literal[False] = False
    change_kind: Literal["interpretation_only"] = "interpretation_only"
    reinterprets_sha256: Sha256 | None = None

    @property
    def source_claims(self) -> list[Claim]:
        return self.source_analysis.claims

    @model_validator(mode="after")
    def bindings(self):
        source = self.source_analysis
        if digest(source.model_dump()) != self.source_analysis_sha256:
            raise ValueError("source analysis digest mismatch")
        if digest(self.policy.model_dump()) != self.policy_sha256:
            raise ValueError("policy digest mismatch")
        if self.policy.knowledge_sha256 != self.knowledge_sha256:
            raise ValueError("policy knowledge binding mismatch")
        if hashlib.sha256(self.knowledge_json.encode("utf-8")).hexdigest() != self.knowledge_sha256:
            raise ValueError("embedded knowledge digest mismatch")
        knowledge = validate_snapshot(parse_json(self.knowledge_json))
        if (knowledge.id, knowledge.revision, knowledge.sources) != (
                self.knowledge_id, self.knowledge_revision, self.knowledge_sources):
            raise ValueError("embedded knowledge metadata mismatch")
        if (self.alignment.source_analysis_sha256 != self.source_analysis_sha256
                or self.alignment.knowledge_sha256 != self.knowledge_sha256):
            raise ValueError("alignment source/knowledge mismatch")
        checked = [item.role_id for item in self.comparisons]
        if (checked != sorted(set(checked)) or checked != self.retrieval.checked_role_ids
                or checked != self.retrieval.available_role_ids):
            raise ValueError("exhaustive comparison scope mismatch")
        if not set(self.retrieval.recalled_role_ids) <= set(checked):
            raise ValueError("foreign retrieval candidate")
        by_id = {item.role_id: item for item in self.comparisons}
        if self.primary_role_id is not None and (
                self.primary_role_id not in by_id or by_id[self.primary_role_id].judgment != "core_candidate"):
            raise ValueError("main role requires core comparison support")
        if self.primary_role_id is not None and self.axes.canonical_job.values != [self.primary_role_id]:
            raise ValueError("main role and canonical axis disagree")
        if self.primary_role_id is not None and self.unaccounted_work:
            raise ValueError("main role cannot conceal unexplained core work")
        if self.work_shape == "multi_position_advertisement" and (
                self.primary_role_id is not None or self.axes.canonical_job.values or not self.shape_evidence):
            raise ValueError("multi-position hypothesis cannot select one job")
        if any(i not in by_id or by_id[i].judgment != "auxiliary" for i in self.auxiliary_role_ids):
            raise ValueError("auxiliary role requires explicit comparison")
        claims = {c.id: c for c in source.claims}
        row = InputRecord.from_row(source.namespace, source.input_row)
        definitions = {r.id: r for r in knowledge.roles}
        if set(definitions) != set(by_id):
            raise ValueError("embedded knowledge role scope mismatch")
        rule_by_id = {r.role_id: r for r in self.policy.roles}
        def check_local(claim_id, evidence, kinds):
            claim = claims.get(claim_id)
            if claim is None or claim.kind not in kinds:
                raise ValueError("comparison evidence has wrong claim kind")
            source.check_evidence(evidence, row)
            if not any(ev.field == evidence.field and ev.start <= evidence.start < evidence.end <= ev.end
                       for ev in claim.evidence):
                raise ValueError("comparison evidence is outside bound claim")
            return claim

        for selected in self.axes.canonical_job.values:
            if selected not in by_id or by_id[selected].judgment != "core_candidate" or not rule_by_id[selected].canonical_candidate:
                raise ValueError("selected canonical job lacks core candidate support")
        for item in self.comparisons:
            if item.definition != definitions[item.role_id]:
                raise ValueError("role definition differs from bound knowledge")
            if item.judgment == "core_candidate" and (
                    not any(s.importance == "core" for s in item.supports) or not item.deliveries
                    or item.conflicts or source.coverage["duties"].status != "complete"
                    or item.definition.maturity == "test"):
                raise ValueError("core candidate lacks necessary evidence")
            refs = {r.id for r in item.definition.responsibilities + item.definition.boundaries}
            reference_by_id = {r.id: r for r in item.definition.responsibilities + item.definition.boundaries}
            for support in item.supports + item.conflicts + item.context_supports:
                if support.claim_id not in claims or support.reference_id not in refs:
                    raise ValueError("foreign comparison support")
                if support.reference_evidence != reference_by_id[support.reference_id].evidence:
                    raise ValueError("comparison reference evidence differs from definition")
                claim = check_local(support.claim_id, support.jd_evidence,
                                    {"goal", "object"} if support in item.context_supports else {"duty"})
                if support.importance == "core" and claim.core is not True:
                    raise ValueError("comparison core importance exceeds source claim")
                if claim.core is False and support.importance != "auxiliary":
                    raise ValueError("noncore source cannot become core or unknown")
            for delivery in item.deliveries:
                if delivery.claim_id not in claims:
                    raise ValueError("foreign delivery claim")
                check_local(delivery.claim_id, delivery.jd_evidence, {"duty", "goal"})
                if delivery.reference_goals != item.definition.goals:
                    raise ValueError("delivery reference goals differ from bound definition")
        for axis in Axes.model_fields:
            for candidate in getattr(self.axes, axis).candidates:
                if not set(candidate.claim_ids) <= claims.keys() or not set(candidate.role_ids) <= by_id.keys():
                    raise ValueError("foreign axis support")
                for evidence in candidate.evidence:
                    source.check_evidence(evidence, row)
                if self.explanation_version == "bounded-work-attribution-2" and axis == "technology_tracks":
                    if candidate.role_ids or not candidate.claim_ids or any(
                            claims[cid].kind not in {"duty", "goal"} for cid in candidate.claim_ids):
                        raise ValueError("technology candidate requires actual work claims, independent of roles")
                    for evidence in candidate.evidence:
                        if not any(ev.field == evidence.field and ev.start <= evidence.start < evidence.end <= ev.end
                                   for cid in candidate.claim_ids for ev in claims[cid].evidence):
                            raise ValueError("technology evidence is outside its work claims")
                        if candidate.value.casefold() not in evidence.quote.casefold():
                            raise ValueError("technology surface absent from actual work evidence")
        for evidence in self.shape_evidence:
            source.check_evidence(evidence, row)
        for gap in self.unaccounted_work:
            if gap.claim_id not in claims or claims[gap.claim_id].kind != "duty":
                raise ValueError("foreign unexplained duty")
            source.check_evidence(gap.evidence, row)
        return self

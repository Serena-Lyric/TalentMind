"""Version 2 adds local work and model retrieval without rewriting v1 history."""
from typing import Literal

from pydantic import model_validator

from ..foundation.inputs import InputRecord
from ..semantics.models import Evidence
from .attribution_models import AttributionResult, Axes, Axis, AxisCandidate
from .models import Strict, Text
from .models import Sha256, SourceEvidence
from pydantic import Field
from ..foundation.inputs import canonical, digest, parse_json


class Generation(Strict):
    seed: Literal[0] = 0
    temperature: Literal[0] = 0
    max_tokens: int = Field(ge=256, le=4096)
    context_size: int = Field(ge=2048, le=16384)


class ModelBinding(Strict):
    model_id: Text
    revision: Text
    source_url: Text
    license_id: Text
    model_sha256: Sha256
    runtime_sha256: Sha256
    runtime_version: Text
    generation: Generation


class SemanticSelection(Strict):
    unit_id: Text
    role_id: Text
    reference_id: Text
    relation: Literal["possible_support", "related", "insufficient"]
    reason: Text


class SemanticMatch(SemanticSelection):
    jd_evidence: Evidence
    reference_evidence: list[SourceEvidence] = Field(min_length=1)


class SemanticEvidence(Strict):
    status: Literal["not_run", "completed", "failed"]
    reason_code: Text
    binding: ModelBinding | None
    input_json: str | None
    prompt: str | None
    prompt_sha256: Sha256 | None
    response: str | None
    response_sha256: Sha256 | None
    matches: list[SemanticMatch]


def semantic_input_v1(result):
    """Frozen fact serialization for historical input validation, not inference."""
    units = [u for u in result.work_units if u.scope == "affirmed" and u.kind == "work"]
    claims = {c.id: c for c in result.source_claims}
    linked = []
    for relation in result.source_analysis.relations:
        if relation.basis == "unknown" or relation.duty_id not in {u.claim_id for u in units}:
            continue
        group = next((r for r in result.alignment.requirements if r.claim_id == relation.requirement_id), None)
        if group:
            linked.append(dict(duty_id=relation.duty_id, requirement_id=relation.requirement_id,
                relation_basis=relation.basis,
                alignments=[a.model_dump(include={"claim_id", "member", "state", "concept_id", "concept_name",
                    "knowledge_status", "concept_source", "candidate_id", "candidate_version_sha256"})
                    for a in group.alignments]))
    return dict(schema_version="local-work-reference-input-1", source_analysis_sha256=result.source_analysis_sha256,
        knowledge_sha256=result.knowledge_sha256,
        candidate_projection_sha256=result.alignment.candidate_projection_sha256,
        work=[dict(unit_id=u.id, quote=u.evidence.quote, p1_text=claims[u.claim_id].text,
                   importance=u.importance) for u in units],
        linked_knowledge=linked, work_links=[link.model_dump() for link in result.work_links],
        references=[dict(role_id=c.role_id, name=c.definition.name, maturity=c.definition.maturity,
            version=c.definition.definition_version,
            tasks=[dict(reference_id=r.id, text=r.text) for r in c.definition.responsibilities])
            for c in result.comparisons])


def semantic_input_v2(result):
    value = semantic_input_v1(result)
    value["schema_version"] = "local-work-reference-input-2"
    eligible = [u for u in result.work_units if u.scope == "affirmed" and u.kind == "work"]
    ids = {u.claim_id for u in eligible}
    value["work"] = [dict(unit_id=u.id, claim_id=u.claim_id, quote=u.evidence.quote,
                          importance=u.importance) for u in eligible]
    value["source_claims"] = [dict(claim_id=c.id, p1_text=c.text,
        evidence=[e.model_dump() for e in c.evidence]) for c in result.source_claims if c.id in ids]
    return value


class WorkUnit(Strict):
    id: Text
    claim_id: Text
    evidence: Evidence
    scope: Literal["affirmed", "negated", "conditional", "historical", "other_actor", "instructional"]
    importance: Literal["core", "auxiliary", "unknown"]
    kind: Literal["work", "context"]
    reference_status: Literal["pattern_supported", "retrieval_only", "unexplained", "not_asserted_work", "context_only"]
    reason: Text


class WorkLink(Strict):
    work_claim_id: Text
    context_claim_id: Text
    basis: Literal["source_context"]
    evidence: Evidence
    reason: Text


class AxisAssessment(Strict):
    status: Literal["evaluated", "not_evaluated"]
    reason_code: Text


def axis_evaluation_v1(result):
    """Availability of facts/references, independent for each axis."""
    duties = any(c.kind == "duty" for c in result.source_claims)
    work = any(c.kind in {"duty", "goal"} for c in result.source_claims)
    available = {c.role_id for c in result.comparisons}
    configured = {"family": any(r.role_id in available and r.family for r in result.policy.roles),
                  "canonical_job": any(r.role_id in available and r.canonical_candidate for r in result.policy.roles)}
    output = {}
    for name in ("family", "canonical_job", "technology_tracks", "seniority"):
        if name == "seniority":
            reason = "no_versioned_reference"
        elif not (work if name == "technology_tracks" else duties):
            reason = "no_work_facts"
        elif name != "technology_tracks" and not configured[name]:
            reason = "no_versioned_reference"
        else:
            reason = "local_work_evidence"
        output[name] = dict(status="evaluated" if reason == "local_work_evidence" else "not_evaluated",
                            reason_code=reason)
    return output


class ContextAxisCandidate(AxisCandidate):
    basis: Literal["source_pattern", "surface_work_use", "local_model"]
    semantic_match_key: Text | None


class ContextAxis(Axis):
    candidates: list[ContextAxisCandidate]


class ContextAxes(Axes):
    family: ContextAxis
    canonical_job: ContextAxis
    technology_tracks: ContextAxis
    seniority: ContextAxis


class ContextAttributionResult(AttributionResult):
    schema_version: Literal["m2-role-attribution-2"] = "m2-role-attribution-2"
    explanation_version: Literal["context-work-attribution-3", "context-work-attribution-4"] = "context-work-attribution-3"
    work_units: list[WorkUnit]
    work_links: list[WorkLink]
    axis_assessments: dict[str, AxisAssessment]
    semantic: SemanticEvidence
    axes: ContextAxes

    @model_validator(mode="after")
    def contextual_bindings(self):
        source = self.source_analysis
        row = InputRecord.from_row(source.namespace, source.input_row)
        claims = {c.id: c for c in source.claims}
        if set(self.axis_assessments) != {"family", "canonical_job", "technology_tracks", "seniority"}:
            raise ValueError("missing axis assessment")
        if self.explanation_version != "context-work-attribution-3":
            if {k: v.model_dump() for k, v in self.axis_assessments.items()} != axis_evaluation_v1(self):
                raise ValueError("axis evaluation lacks facts or reference")
            if any(c.basis == "local_model" for name in ContextAxes.model_fields
                   for c in getattr(self.axes, name).candidates):
                raise ValueError("unverified model proposal cannot enter business axes")
        if len({u.id for u in self.work_units}) != len(self.work_units):
            raise ValueError("duplicate work unit")
        for unit in self.work_units:
            claim = claims.get(unit.claim_id)
            if claim is None or claim.kind != "duty":
                raise ValueError("work unit requires duty claim")
            source.check_evidence(unit.evidence, row)
            if not any(e.field == unit.evidence.field and e.start <= unit.evidence.start
                       < unit.evidence.end <= e.end for e in claim.evidence):
                raise ValueError("work unit outside source claim")
            if unit.importance == "core" and claim.core is not True:
                raise ValueError("work unit cannot upgrade importance")
        units = {u.id: u for u in self.work_units}
        definitions = {r.role_id: r.definition for r in self.comparisons}
        if (self.semantic.response is None) != (self.semantic.response_sha256 is None):
            raise ValueError("semantic response binding incomplete")
        if self.semantic.response is not None and digest(self.semantic.response) != self.semantic.response_sha256:
            raise ValueError("semantic response digest mismatch")
        if self.semantic.status == "not_run" and any((self.semantic.binding, self.semantic.input_json,
                                                       self.semantic.prompt, self.semantic.prompt_sha256,
                                                       self.semantic.response, self.semantic.matches)):
            raise ValueError("unrun semantic inference cannot carry model evidence")
        if self.semantic.status != "not_run":
            saved_input = parse_json(self.semantic.input_json or "{}")
            expected_input = (semantic_input_v1(self) if saved_input.get("schema_version") == "local-work-reference-input-1"
                              else semantic_input_v2(self))
            if (self.semantic.binding is None or self.semantic.input_json != canonical(expected_input)
                    or self.semantic.prompt is None or self.semantic.prompt_sha256 != digest(self.semantic.prompt)
                    or not self.semantic.prompt.endswith("\nDATA_JSON\n" + self.semantic.input_json)):
                raise ValueError("semantic inference input binding mismatch")
        if self.semantic.status == "completed":
            if self.semantic.binding is None or self.semantic.prompt_sha256 is None or self.semantic.response is None:
                raise ValueError("semantic inference lacks model/input/output binding")
            selections = parse_json(self.semantic.response).get("matches")
            if selections != [SemanticSelection.model_validate(m.model_dump(include=set(SemanticSelection.model_fields))).model_dump()
                              for m in self.semantic.matches]:
                raise ValueError("semantic selections differ from raw response")
        elif self.semantic.matches:
            raise ValueError("uncompleted inference cannot have semantic matches")
        for match in self.semantic.matches:
            unit = units.get(match.unit_id)
            definition = definitions.get(match.role_id)
            reference = next((r for r in definition.responsibilities if r.id == match.reference_id), None) if definition else None
            if (unit is None or unit.scope != "affirmed" or unit.kind != "work" or reference is None
                    or match.jd_evidence != unit.evidence or match.reference_evidence != reference.evidence):
                raise ValueError("semantic match is not bound to eligible work and reference")
        keys = [(m.unit_id, m.role_id, m.reference_id) for m in self.semantic.matches]
        if len(set(keys)) != len(keys):
            raise ValueError("duplicate semantic match")
        semantic_by_key = {digest([m.unit_id, m.role_id, m.reference_id]): m for m in self.semantic.matches}
        rules = {r.role_id: r for r in self.policy.roles}
        for name in ContextAxes.model_fields:
            axis = getattr(self.axes, name)
            for candidate in axis.candidates:
                if candidate.basis != "local_model":
                    if candidate.semantic_match_key is not None:
                        raise ValueError("non-model candidate cannot borrow semantic evidence")
                    if candidate.basis == "surface_work_use":
                        if name != "technology_tracks":
                            raise ValueError("surface technology evidence cannot confirm another axis")
                    elif name in {"family", "canonical_job"}:
                        comparison = next((c for c in self.comparisons if candidate.role_ids == [c.role_id]), None)
                        rule = rules.get(comparison.role_id) if comparison else None
                        expected = (rule.family if name == "family" else comparison.role_id if rule.canonical_candidate else None) if rule else None
                        strength = ("auxiliary" if comparison.judgment == "auxiliary" else
                                    "core_candidate" if comparison.judgment == "core_candidate" else "local_hypothesis") if comparison else None
                        if (comparison is None or not comparison.supports or comparison.judgment == "conflict"
                                or candidate.value != expected or candidate.strength != strength
                                or candidate.claim_ids != sorted({s.claim_id for s in comparison.supports})
                                or candidate.evidence != [s.jd_evidence for s in comparison.supports]):
                            raise ValueError("pattern axis candidate lacks its comparison support")
                    else:
                        raise ValueError("axis has no configured pattern reference")
                    continue
                match = semantic_by_key.get(candidate.semantic_match_key)
                unit = units.get(match.unit_id) if match else None
                rule = rules.get(match.role_id) if match else None
                expected = match.role_id if match and name == "canonical_job" else rule.family if rule and name == "family" else None
                if (match is None or match.relation != "possible_support" or expected is None
                        or candidate.value != expected or candidate.strength != ("auxiliary" if unit.importance == "auxiliary" else "local_hypothesis")
                        or candidate.role_ids != [match.role_id] or candidate.claim_ids != [unit.claim_id]
                        or candidate.evidence != [unit.evidence]):
                    raise ValueError("model axis candidate exceeds its weak semantic evidence")
            if any(value not in {c.value for c in axis.candidates if c.basis != "local_model"}
                   for value in axis.values):
                raise ValueError("model-only candidate cannot become a selected axis value")
        if self.primary_role_id is not None:
            # Generative hypotheses may add candidates, never create sufficient
            # primary evidence or conceal gaps left by the source-pattern path.
            primary = next(c for c in self.comparisons if c.role_id == self.primary_role_id)
            if not any(s.basis == "source_pattern_support" and s.importance == "core" for s in primary.supports):
                raise ValueError("semantic hypothesis cannot select a primary role")
        for link in self.work_links:
            if (link.work_claim_id not in claims or claims[link.work_claim_id].kind != "duty"
                    or link.context_claim_id not in claims or claims[link.context_claim_id].kind not in {"goal", "object"}):
                raise ValueError("work link has foreign or wrong-kind claim")
            source.check_evidence(link.evidence, row)
            for cid in (link.work_claim_id, link.context_claim_id):
                if not any(e.field == link.evidence.field and link.evidence.start <= e.start
                           < e.end <= link.evidence.end for e in claims[cid].evidence):
                    raise ValueError("work link lacks both source claims")
        for item in self.comparisons:
            for support in item.supports + item.conflicts:
                if not any(u.claim_id == support.claim_id and u.scope == "affirmed"
                           and u.evidence.field == support.jd_evidence.field
                           and u.evidence.start <= support.jd_evidence.start
                           < support.jd_evidence.end <= u.evidence.end for u in self.work_units):
                    raise ValueError("support outside affirmed source work")
        if self.axis_assessments["seniority"].status == "not_evaluated" and self.axes.seniority.values:
            raise ValueError("unevaluated seniority cannot have selected values")
        return self

"""Separate scored proposals, machine task checks and occupational identity."""
from typing import Literal
import re

from pydantic import Field, model_validator

from ..foundation.inputs import InputRecord, canonical, digest, parse_json
from ..semantics.models import Evidence
from .models import Strict, Text, Sha256, SourceEvidence
from .work_context_models import ContextAttributionResult, ModelBinding, semantic_input_v2


class PairJudgment(Strict):
    action_relation: Literal["supported", "different", "unknown"]
    object_relation: Literal["supported", "different", "unknown"]
    execution_relation: Literal["performs_task", "enables_others", "topic_only", "unknown"]
    source_action: str
    source_object: str
    reference_action: str
    reference_object: str
    reason: Text = Field(max_length=320)


class ObjectJudgment(Strict):
    relation: Literal["same_type", "specific_form", "operational_component", "output_form",
                      "supporting_input", "different", "unknown"]
    reason: Text = Field(max_length=200)


class ObjectCheck(Strict):
    input_json: Text
    prompt: Text
    prompt_sha256: Sha256
    response: str | None
    response_sha256: Sha256 | None
    judgment: ObjectJudgment | None
    elapsed_seconds: float = Field(ge=0, allow_inf_nan=False)


class TaskProposal(Strict):
    id: Text
    claim_id: Text
    role_id: Text
    reference_id: Text
    retrieval_score: float | None = Field(ge=0, le=1, allow_inf_nan=False)
    lexical_score: float | None = Field(ge=0, le=1, allow_inf_nan=False)
    input_truncated: bool


class TaskSelection(Strict):
    method: Literal["dual-priority-task-budget-1", "explicit-given-pairs-1"] = "dual-priority-task-budget-1"
    status: Literal["not_run", "ranked", "given_pairs", "empty_catalog", "no_eligible_work"]
    retriever_binding: dict
    pairs_per_role: int = Field(ge=1, le=3)
    proposals: list[TaskProposal]
    selected_pair_ids: list[Text]
    checked_pair_ids: list[Text]
    pending_selected_pair_ids: list[Text]
    unchecked_pair_ids: list[Text]
    limitation: Text


class TaskAssessment(Strict):
    id: Text
    claim_id: Text
    role_id: Text
    reference_id: Text
    state: Literal["machine_supported", "different_work", "unresolved", "failed"]
    reason_code: Text
    judgment: PairJudgment | None
    source_action_evidence: Evidence | None
    source_object_evidence: Evidence | None
    reference_evidence: list[SourceEvidence] = Field(min_length=1)
    binding: ModelBinding
    prompt_format: Literal["qwen3-no-thinking", "qwen3-instruct"]
    input_json: Text
    prompt: Text
    prompt_sha256: Sha256
    response: str | None
    response_sha256: Sha256 | None
    elapsed_seconds: float = Field(ge=0, allow_inf_nan=False)
    object_check: ObjectCheck | None = Field(default=None, exclude_if=lambda value: value is None)


class CheckedWorkCandidate(Strict):
    assessment_id: Text
    role_id: Text
    reference_id: Text
    claim_id: Text
    family: Text | None
    maturity: Literal["test", "candidate", "formal"]
    basis: Literal["machine_pair_checked"] = "machine_pair_checked"
    semantic_review: Literal["machine_unreviewed"] = "machine_unreviewed"


def pair_identity(claim_id, role_id, reference_id):
    return "pair-" + digest([claim_id, role_id, reference_id])[:24]


# Frozen source-group guard for task-pair input v1. Evolving discourse parsers
# must use a new guard version, leaving historical checks readable.
_ACTIONS_V1 = "设计|开发|编写|修改|实现|构建|维护|管理|生成|编制|运行|执行|分析|优化|核验|验证|评测|清洗|抽取|加载|转换|制作|整理|实施|审阅|制定|组织|开展|测试|教学|授课"
_ACTIONS_V2 = _ACTIONS_V1 + "|研发"


def same_task_source_group(claim, first, second, version):
    if first.field != second.field:
        return False
    actions = _ACTIONS_V1 if version == "task-pair-input-1" else _ACTIONS_V2
    boundary = re.compile(r"[；;。.!！?？\n]+|同时|此外|另外|(?<!参)"
        r"(?:[，,]|并且|并|和|与|以及|及)(?=\s*(?:负责|承担|协助|辅助)?(?:" + actions + r"))")
    particle = "" if version == "task-pair-input-1" else "、|"
    for source in claim.evidence:
        if source.field != first.field:
            continue
        start = 0
        spans = []
        for split in boundary.finditer(source.quote):
            left = source.quote[start:split.start()]
            if re.fullmatch(r"(?:\s|负责|承担|并|和|与|及|" + particle + actions + r")+", left):
                continue  # Shared object follows coordinated bare predicates.
            spans.append((source.start+start, source.start+split.start()))
            start = split.end()
        spans.append((source.start+start, source.end))
        if any(begin <= min(first.start, second.start) and max(first.end, second.end) <= end
               for begin, end in spans):
            return True
    return False


def pair_input_v1(result, claim_id, role_id, reference_id):
    claim = next((c for c in result.source_claims if c.id == claim_id and c.kind == "duty"), None)
    role = next((c.definition for c in result.comparisons if c.role_id == role_id), None)
    ref = next((r for r in role.responsibilities if r.id == reference_id), None) if role else None
    if claim is None or ref is None:
        raise ValueError("task pair references absent duty or definition")
    auxiliary = semantic_input_v2(result)
    return dict(schema_version="task-pair-input-1", source_analysis_sha256=result.source_analysis_sha256,
        knowledge_sha256=result.knowledge_sha256, policy_sha256=result.policy_sha256,
        candidate_projection_sha256=result.alignment.candidate_projection_sha256,
        linked_knowledge=[k for k in auxiliary["linked_knowledge"] if k["duty_id"] == claim_id],
        work_links=[k for k in auxiliary["work_links"] if k["work_claim_id"] == claim_id],
        work=dict(claim_id=claim_id, source_fragments=[e.model_dump() for e in claim.evidence],
                  units=[u.model_dump() for u in result.work_units if u.claim_id == claim_id]),
        reference=dict(role_id=role_id, maturity=role.maturity, definition_version=role.definition_version,
                       reference_id=ref.id, text=ref.text, evidence=[e.model_dump() for e in ref.evidence]))


def pair_input_v2(result, claim_id, role_id, reference_id):
    value = pair_input_v1(result, claim_id, role_id, reference_id)
    value["schema_version"] = "task-pair-input-2"
    value["work"]["source_fragments"] = [{k: e[k] for k in ("field", "start", "end", "quote")}
                                         for e in value["work"]["source_fragments"]]
    value["work"]["units"] = [dict(quote=u["evidence"]["quote"], scope=u["scope"], kind=u["kind"],
                                    importance=u["importance"]) for u in value["work"]["units"]]
    omitted, linked = 0, []
    for relation in value["linked_knowledge"]:
        kept = [a for a in relation["alignments"] if a["state"] != "unknown"]
        omitted += len(relation["alignments"]) - len(kept)
        if kept:
            linked.append({**relation, "alignments": kept})
    value["linked_knowledge"] = linked
    value["unknown_alignment_members_retained_outside_prompt"] = omitted
    return value


def pair_input_v3(result, claim_id, role_id, reference_id):
    value = pair_input_v2(result, claim_id, role_id, reference_id)
    value.update(schema_version="task-pair-input-3", task_semantics="job_responsibility_not_past_execution")
    return value


def object_input_v1(assessment):
    draft = assessment.judgment
    parent_input = parse_json(assessment.input_json)
    return dict(schema_version="task-object-input-1", pair_id=assessment.id,
        pair_input_sha256=digest(assessment.input_json), pair_response_sha256=assessment.response_sha256,
        source_action=draft.source_action, source_object=draft.source_object,
        reference_action=draft.reference_action, reference_object=draft.reference_object,
        source_fragments=parent_input["work"]["source_fragments"],
        reference_task_text=parent_input["reference"]["text"])


def expected_pair_state(result, assessment):
    """Frozen v1 acceptance rules; literal binding does not certify semantics."""
    judgment = assessment.judgment
    if judgment is None:
        return "failed", "invalid_pair_response"
    if not all((judgment.source_action, judgment.source_object,
                judgment.reference_action, judgment.reference_object)):
        return "unresolved", "missing_action_or_object_evidence"
    if assessment.source_action_evidence is None or assessment.source_object_evidence is None:
        return "failed", "unbound_source_quote"
    claim = next(c for c in result.source_claims if c.id == assessment.claim_id)
    input_version = parse_json(assessment.input_json)["schema_version"]
    if not same_task_source_group(claim, assessment.source_action_evidence, assessment.source_object_evidence, input_version):
        return "unresolved", "action_object_different_work_groups"
    reference = pair_input_v1(result, assessment.claim_id, assessment.role_id, assessment.reference_id)["reference"]
    texts = [reference["text"]]
    if input_version == "task-pair-input-3":
        texts.extend(e["quote"] for e in reference["evidence"])
    if not all(any(quote in text for text in texts) for quote in (judgment.reference_action, judgment.reference_object)):
        return "failed", "unbound_reference_quote"
    for evidence in (assessment.source_action_evidence, assessment.source_object_evidence):
        touched = [u for u in result.work_units if u.claim_id == assessment.claim_id
                   and u.evidence.field == evidence.field and u.evidence.start < evidence.end
                   and evidence.start < u.evidence.end]
        if not touched or any(u.scope != "affirmed" for u in touched):
            return "unresolved", "source_scope_not_actual_work"
        if input_version == "task-pair-input-3" and not any(u.kind == "work" for u in touched):
            return "unresolved", "goal_or_context_is_not_work_object"
    action = assessment.source_action_evidence
    if not any(u.kind == "work" and u.scope == "affirmed" and u.claim_id == assessment.claim_id
               and u.evidence.field == action.field and u.evidence.start < action.end
               and action.start < u.evidence.end for u in result.work_units):
        return "unresolved", "goal_or_context_is_not_action"
    if judgment.execution_relation in {"enables_others", "topic_only"} or "different" in {
            judgment.action_relation, judgment.object_relation}:
        return "different_work", "work_action_object_or_execution_differs"
    if (judgment.action_relation == judgment.object_relation == "supported"
            and judgment.execution_relation == "performs_task"):
        if input_version == "task-pair-input-3":
            check = assessment.object_check
            if check is None:
                return "unresolved", "object_check_not_run"
            if check.judgment is None:
                return "failed", "object_check_invalid_or_failed"
            if check.judgment.relation in {"supporting_input", "different"}:
                return "different_work", "object_is_input_or_different_type"
            if check.judgment.relation == "unknown":
                return "unresolved", "object_type_unknown"
        return "machine_supported", "action_object_execution_machine_checked"
    return "unresolved", "semantic_relation_unknown"


class TaskAttributionResult(ContextAttributionResult):
    schema_version: Literal["m2-role-attribution-3"] = "m2-role-attribution-3"
    explanation_version: Literal["task-evidence-attribution-1", "task-evidence-attribution-2", "task-evidence-attribution-3"] = "task-evidence-attribution-1"
    task_selection: TaskSelection
    task_assessments: list[TaskAssessment]
    work_candidates: list[CheckedWorkCandidate]

    @model_validator(mode="after")
    def checked_bindings(self):
        by_id = {}
        row = InputRecord.from_row(self.source_analysis.namespace, self.source_analysis.input_row)
        for item in self.task_assessments:
            expected_id = pair_identity(item.claim_id, item.role_id, item.reference_id)
            if item.id != expected_id or item.id in by_id:
                raise ValueError("foreign or duplicate task assessment")
            by_id[item.id] = item
            input_version = parse_json(item.input_json).get("schema_version")
            factories = {"task-pair-input-1": pair_input_v1, "task-pair-input-2": pair_input_v2, "task-pair-input-3": pair_input_v3}
            factory = factories.get(input_version)
            if factory is None:
                raise ValueError("unknown task input version")
            if input_version.rsplit("-", 1)[1] != self.explanation_version.rsplit("-", 1)[1]:
                raise ValueError("task input and explanation versions differ")
            expected = factory(self, item.claim_id, item.role_id, item.reference_id)
            if item.input_json != canonical(expected) or not item.prompt.endswith("\nDATA_JSON\n" + item.input_json):
                raise ValueError("task pair input binding mismatch")
            if item.prompt_sha256 != digest(item.prompt):
                raise ValueError("task pair prompt digest mismatch")
            if (item.response is None) != (item.response_sha256 is None) or (
                    item.response is not None and item.response_sha256 != digest(item.response)):
                raise ValueError("task pair response digest mismatch")
            try:
                parsed = PairJudgment.model_validate(parse_json(item.response)) if item.response is not None else None
            except ValueError:
                parsed = None
            if parsed != item.judgment:
                raise ValueError("task judgment differs from bound response")
            if item.object_check is not None:
                check = item.object_check
                if item.judgment is None or check.input_json != canonical(object_input_v1(item)):
                    raise ValueError("object check input differs from pair response")
                if (check.prompt_sha256 != digest(check.prompt) or not check.prompt.endswith("\nDATA_JSON\n" + check.input_json)
                        or (check.response is None) != (check.response_sha256 is None)
                        or check.response is not None and check.response_sha256 != digest(check.response)):
                    raise ValueError("object check prompt/response binding mismatch")
                try:
                    parsed_object = ObjectJudgment.model_validate(parse_json(check.response)) if check.response is not None else None
                except ValueError:
                    parsed_object = None
                if parsed_object != check.judgment:
                    raise ValueError("object judgment differs from response")
            ref = expected["reference"]
            if [e.model_dump() for e in item.reference_evidence] != ref["evidence"]:
                raise ValueError("task source differs from reference")
            if item.judgment:
                claim = next(c for c in self.source_claims if c.id == item.claim_id)
                for evidence, quote in [(item.source_action_evidence, item.judgment.source_action),
                                        (item.source_object_evidence, item.judgment.source_object)]:
                    if evidence is not None:
                        self.source_analysis.check_evidence(evidence, row)
                    if evidence is not None and (evidence.quote != quote or not any(
                            e.field == evidence.field and e.start <= evidence.start < evidence.end <= e.end
                            and e.quote[evidence.start-e.start:evidence.end-e.start] == quote for e in claim.evidence)):
                        raise ValueError("task quote outside its source claim")
            if (item.state, item.reason_code) != expected_pair_state(self, item):
                raise ValueError("task state exceeds checked evidence")
        rules = {r.role_id: r for r in self.policy.roles}
        expected_candidates = [dict(assessment_id=a.id, role_id=a.role_id, reference_id=a.reference_id,
            claim_id=a.claim_id, family=rules[a.role_id].family if a.role_id in rules else None,
            maturity=next(c.definition.maturity for c in self.comparisons if c.role_id == a.role_id),
            basis="machine_pair_checked", semantic_review="machine_unreviewed")
            for a in self.task_assessments if a.state == "machine_supported"]
        if [c.model_dump() for c in self.work_candidates] != expected_candidates:
            raise ValueError("work candidate lacks a supported task assessment")
        ids = [p.id for p in self.task_selection.proposals]
        if len(set(ids)) != len(ids) or any(p.id != pair_identity(p.claim_id, p.role_id, p.reference_id)
                                         for p in self.task_selection.proposals):
            raise ValueError("task selection IDs invalid")
        actual_pairs = {(c.id, role.role_id, ref.id) for c in self.source_claims if c.kind == "duty"
                        for role in self.comparisons for ref in role.definition.responsibilities}
        if any((p.claim_id, p.role_id, p.reference_id) not in actual_pairs for p in self.task_selection.proposals):
            raise ValueError("proposal references absent source or task")
        selected = self.task_selection.selected_pair_ids
        if (not set(self.task_selection.selected_pair_ids) <= set(ids)
                or set(self.task_selection.unchecked_pair_ids) != set(ids) - set(self.task_selection.selected_pair_ids)):
            raise ValueError("task selection scope mismatch")
        if (len(set(selected)) != len(selected) or self.task_selection.checked_pair_ids != list(by_id)
                or not set(by_id) <= set(selected) or self.task_selection.pending_selected_pair_ids != [
                    p for p in selected if p not in by_id]):
            raise ValueError("task selection and executed assessments disagree")
        if self.task_selection.status in {"not_run", "empty_catalog", "no_eligible_work"} and (ids or by_id):
            raise ValueError("unrun task selection cannot carry checks")
        if self.task_selection.status == "given_pairs" and self.task_selection.method != "explicit-given-pairs-1":
            raise ValueError("given pair method mismatch")
        if self.task_selection.status == "ranked":
            if self.task_selection.method != "dual-priority-task-budget-1" or not self.task_selection.retriever_binding:
                raise ValueError("ranked selection lacks priority method binding")
            if any(p.retrieval_score is None or p.lexical_score is None for p in self.task_selection.proposals):
                raise ValueError("ranked proposal has no priority score")
            eligible = {u.claim_id for u in self.work_units if u.scope == "affirmed" and u.kind == "work"}
            if {(p.claim_id, p.role_id, p.reference_id) for p in self.task_selection.proposals} != {
                    pair for pair in actual_pairs if pair[0] in eligible}:
                raise ValueError("scored task pool is incomplete")
            for role in self.comparisons:
                if sum(p.id in selected and p.role_id == role.role_id for p in self.task_selection.proposals) > self.task_selection.pairs_per_role:
                    raise ValueError("selected pairs exceed declared role budget")
        return self

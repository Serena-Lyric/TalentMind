"""Compile untrusted semantic drafts to unchanged P0 claims and exact evidence."""
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import importlib.metadata
from pathlib import Path
import sys
import time
from typing import Literal

from pydantic import Field

from ..baseline.contract import Claim, Coverage, Relation, Requirement, Strict, Text, validate_analysis
from ..foundation.inputs import InputRecord, canonical, check_public, digest, parse_json
from ..semantics.models import Evidence
from .processor import Completion, Processor

DIMENSIONS = ("goals", "objects", "duties", "requirements", "relations")
KIND_DIMENSION = dict(goal="goals", object="objects", duty="duties", requirement="requirements")
PROMPT_PATH = Path(__file__).with_name("prompt.txt")
REFINE_INSTRUCTION = """上一条 assistant 消息是同一输入的待审核机器草稿，不是人工标签或事实标准。
请针对其潜在错误做一次定向复核，并输出同格式的完整修订JSON；正确项保留，不为改写而改写。
重点检查：职责/任职/背景边界、漏提、资格排除与不要求、优先/程度/经验对象、并列全部与任选/开放举例。
明确的“熟悉A、B、C”等非开放并列要求不能无理由退为组合未知；只有含“或/任选”才选一，含“如/等”不擅定全要。
重点复核每条explicit：引用的文字是否直接说该能力用于该项工作，而非同名工作、共同对象或行业常识。
只有同名/同JD或能帮助的联系不可升explicit；根据具体上下文最多inferred，无充分理由就不输出该边。
同时别删掉真实“使用/利用/基于/运用X完成Y”的直接用途。证据存在不证明关系等级或门槛正确。
只根据输入重审，保留可解释的真实未知；不要以一律未知回避明确的事实。不要自报通过分数。"""


class Locator(Strict):
    field: Literal["raw_text", "job_title", "duties", "requirements", "experience"]
    quote: Text
    occurrence: int | None = Field(default=None, ge=0)


class Draft(Strict):
    coverage: dict[str, Coverage]
    claims: list
    relations: list


class DraftRequirement(Requirement):
    scope_evidence: list[Locator] = Field(min_length=1)


class DraftClaim(Claim):
    evidence: list[Locator] = Field(min_length=1)
    requirement: DraftRequirement | None


class DraftRelation(Relation):
    evidence: list[Locator]


class DraftSchema(Draft):
    """Provider guidance uses precise item schemas; ingestion still validates items independently."""
    claims: list[DraftClaim]
    relations: list[DraftRelation]


def locate(value, record, adjustments=None):
    locator = Locator.model_validate(value)
    source = record.payload.get(locator.field, "")
    if not source and locator.field != "raw_text":
        raw = record.payload["raw_text"]
        # A nonexistent semantic field is not provenance. Re-anchor only a unique literal
        # match in the canonical raw source, never normalize text or guess among occurrences.
        if raw.count(locator.quote) == 1 and locator.occurrence in (None, 0):
            if adjustments is not None:
                adjustments.append(dict(requested_field=locator.field, actual_field="raw_text",
                                        reason="absent_field_unique_literal_raw_match"))
            locator = locator.model_copy(update={"field": "raw_text", "occurrence": None})
            source = raw
    positions, start = [], 0
    while (position := source.find(locator.quote, start)) >= 0:
        positions.append(position)
        start = position + 1
    index = locator.occurrence
    if index is None:
        if len(positions) != 1:
            raise ValueError("missing_or_ambiguous_quote")
        index = 0
    if index >= len(positions):
        raise ValueError("quote_occurrence_unavailable")
    start = positions[index]
    return Evidence(namespace=record.namespace, jd_id=record.jd_id, fingerprint=record.fingerprint,
                    field=locator.field, start=start, end=start + len(locator.quote), quote=locator.quote).model_dump()


def version(name, revision, value):
    return dict(id=name, revision=revision, sha256=digest(value))


def dependencies():
    # Freeze the actual implementation and contract bytes, not just a declared revision.
    paths = [*Path(__file__).parent.glob("*.py"),
             Path(__file__).parents[1] / "baseline/contract.py",
             Path(__file__).parents[1] / "semantics/models.py",
             Path(__file__).parents[1] / "foundation/store.py",
             Path(__file__).parents[1] / "foundation/inputs.py"]
    root = Path(__file__).parents[1]
    return dict(files={p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                       for p in sorted(paths)}, python=sys.version.split()[0],
                packages={p: importlib.metadata.version(p) for p in ("pydantic", "httpx")})


# A persistent worker must not relabel already loaded Python with later on-disk edits.
LOADED_DEPENDENCIES = dependencies()


def _outcome(coverage):
    statuses = {v["status"] for v in coverage.values()}
    return ("complete" if statuses == {"complete"} else "not_run" if statuses == {"not_run"}
            else "failed" if statuses <= {"failed", "not_run"} else "partial")


def _merge_claim(claims, item):
    # Only exact semantic duplicates merge; paraphrase equivalence remains a semantic judgment.
    def key(c):
        value = deepcopy(c)
        for k in ("id", "evidence", "reason"):
            value.pop(k)
        if value["requirement"]:
            for k in ("scope_evidence", "reason"):
                value["requirement"].pop(k)
        return canonical(value)

    for previous in claims:
        if key(previous) == key(item):
            for collection in ("evidence",):
                previous[collection] += [e for e in item[collection] if e not in previous[collection]]
            if previous["requirement"]:
                scope = previous["requirement"]["scope_evidence"]
                scope += [e for e in item["requirement"]["scope_evidence"] if e not in scope]
            return previous["id"]
    claims.append(item)
    return item["id"]


def _preserve_requirement_parts(item, adjustments):
    """Retain grounded statements without turning lost qualifications into broad negatives."""
    req = item.get("requirement")
    if item.get("kind") != "requirement" or not isinstance(req, dict):
        return False
    if req.get("target") in {"experience", "domain", "education", "tenure", "certificate", "unresolved"} and req.get("category") in {
            "technical_skill", "professional_skill", "engineering_practice", "soft_skill"}:
        req["category"] = None
        adjustments.append(dict(claim_id=item["id"], reason="discarded_inapplicable_skill_category"))
    for name in ("degree", "condition"):
        value = req.get(name)
        context = "\n".join(e["quote"] for e in req["scope_evidence"])
        if value is not None and value not in context:
            for evidence in item["evidence"]:
                if value in evidence["quote"] and evidence not in req["scope_evidence"]:
                    req["scope_evidence"].append(evidence)
                    adjustments.append(dict(claim_id=item["id"], component=name,
                                            reason="scope_extended_from_existing_claim_evidence"))
    context = "\n".join(e["quote"] for e in req["scope_evidence"])
    degree = req.get("degree")
    if (degree is not None and degree not in context and req.get("degree_polarity") == "affirmed"
            and req.get("state") in {"required", "preferred"}):
        # Never erase a condition or negated degree: that could invert/widen the requirement.
        if req.get("condition") is not None and req["condition"] not in context:
            return False
        req.update(degree=None, degree_polarity=None)
        req["reason"] += "；结构化程度不是连续原文，暂未解析，完整能力陈述和证据仍保留。"
        adjustments.append(dict(claim_id=item["id"], reason="nonliteral_positive_degree_unresolved"))
        return True
    return False


async def analyze(namespace: str, row: dict, input_version: str, processor: Processor, *, prior=None) -> dict:
    record = InputRecord.from_row(namespace, row)
    if not namespace.strip() or not input_version.strip():
        raise ValueError("explicit_input_version_and_namespace_required")
    schema = DraftSchema.model_json_schema()
    schema["$defs"]["Locator"]["properties"]["field"]["enum"] = [
        k for k in ("raw_text", "job_title", "duties", "requirements", "experience") if record.payload.get(k)]
    prompt = (PROMPT_PATH.read_text(encoding="utf-8") +
              "\n严格遵守以下实际 JSON Schema，所有 required 字段不可省略：\n" + canonical(schema))
    descriptor = deepcopy(processor.descriptor)
    lineage = None
    if prior is not None:
        previous = validate_analysis(prior["analysis"])
        if ((previous.namespace, previous.jd_id, previous.input_sha256, previous.input_version) !=
                (namespace, record.jd_id, record.fingerprint, input_version)):
            raise ValueError("refinement_requires_same_input_identity_and_version")
        if not isinstance(prior.get("completion"), str) or not prior["completion"].strip():
            raise ValueError("refinement_requires_existing_machine_draft")
        lineage = dict(previous_analysis_sha256=digest(previous.model_dump()),
                       previous_completion_sha256=digest(prior["completion"]), policy="semantic-postflight-1")
        descriptor["refinement"] = lineage
    check_public(descriptor)
    deps = deepcopy(LOADED_DEPENDENCIES)
    coverage = {d: dict(status="failed", reason="analysis_not_available") for d in DIMENSIONS}
    coverage["classification"] = dict(status="not_run", reason="P2 classification is outside P1")
    analysis = dict(contract_version="m2-semantic-0.2", namespace=namespace, jd_id=record.jd_id,
                    input_row=deepcopy(row), input_sha256=record.fingerprint, input_version=input_version,
                    analyzer=version("p1-understanding", "1", deps),
                    model=version(descriptor["model"], descriptor["model_revision"], descriptor),
                    prompt=version("p1-chinese-jd", "1", dict(system=prompt, refinement=REFINE_INSTRUCTION)
                                   if prior is not None else prompt),
                    configuration=version("p1-processor", "1", descriptor), knowledge=[],
                    outcome="failed", coverage=coverage, claims=[], relations=[], alignments=[],
                    role_judgments=[], semantic_review="machine_unreviewed")
    # Do not send identifiers, provenance, unrelated fields or human references to the provider.
    fields = {k: record.payload[k] for k in ("job_title", "raw_text", "duties", "requirements", "experience")
              if k in record.payload}
    messages = [dict(role="system", content=prompt), dict(role="user", content=canonical(fields))]
    if prior is not None:
        messages += [dict(role="assistant", content=prior["completion"]),
                     dict(role="user", content=REFINE_INSTRUCTION)]
    started = time.monotonic()
    started_at = datetime.now(timezone.utc).isoformat()
    try:
        completion = await processor.complete(messages)
    except Exception:
        # Provider/plugin exceptions may contain credentials or complete private request text.
        # Cancellation is a BaseException and intentionally leaves the reserved run pending.
        completion = Completion(status="processor_error")
    execution = dict(status=completion.status, elapsed_seconds=round(time.monotonic() - started, 3),
                     finish_reason=completion.finish_reason, metadata=completion.metadata, issues=[],
                     grounding_adjustments=[], started_at=started_at,
                     finished_at=datetime.now(timezone.utc).isoformat())
    result = dict(schema_version="m2-p1-run-1", analysis=analysis, execution=execution,
                  dependencies=deps, processor=descriptor, request=messages, completion=completion.content)
    if lineage is not None:
        result["lineage"] = lineage
    status = completion.status
    truncated = completion.finish_reason == "length"
    if status == "ok":
        status = "truncated" if truncated else "ok"
        if not completion.content.strip():
            status = "truncated" if truncated else "empty"
        else:
            try:
                raw = parse_json(completion.content)
            except (ValueError, TypeError):
                status = "truncated" if truncated else "invalid_json"
            else:
                try:
                    draft = Draft.model_validate(raw)
                    if set(draft.coverage) != set(DIMENSIONS):
                        raise ValueError("invalid_coverage_dimensions")
                except (ValueError, TypeError):
                    status = "truncated" if truncated else "invalid_structure"
                else:
                    coverage.update({d: v.model_dump() for d, v in draft.coverage.items()})
                    ids = Counter(c.get("id") for c in draft.claims if isinstance(c, dict)
                                  and isinstance(c.get("id"), str))
                    remap = {}
                    for index, value in enumerate(draft.claims):
                        kind = value.get("kind") if isinstance(value, dict) else None
                        dimension = KIND_DIMENSION.get(kind) if isinstance(kind, str) else None
                        try:
                            item = deepcopy(value)
                            if not isinstance(item, dict) or ids[item["id"]] != 1:
                                raise ValueError("invalid_claim_identity")
                            if dimension is None or coverage[dimension]["status"] in {"failed", "not_run"}:
                                raise ValueError("unavailable_dimension")
                            item["evidence"] = [locate(e, record, execution["grounding_adjustments"]) for e in item["evidence"]]
                            if item.get("requirement"):
                                item["requirement"]["scope_evidence"] = [locate(e, record, execution["grounding_adjustments"]) for e in
                                                                         item["requirement"]["scope_evidence"]]
                            partially_preserved = _preserve_requirement_parts(item, execution["grounding_adjustments"])
                            item = Claim.model_validate(item).model_dump()
                            trial = deepcopy(analysis)
                            trial["claims"] = [item]
                            trial["outcome"] = _outcome(coverage)
                            validate_analysis(trial)
                            remap[item["id"]] = _merge_claim(analysis["claims"], item)
                            if partially_preserved:
                                execution["issues"].append(dict(kind="claim_partially_preserved", index=index,
                                                                dimension=dimension, reason="positive_degree_unresolved"))
                                if coverage[dimension]["status"] == "complete":
                                    coverage[dimension] = dict(status="partial", reason="structured_positive_degree_unresolved")
                        except (ValueError, KeyError, TypeError):
                            execution["issues"].append(dict(kind="claim_rejected", index=index, dimension=dimension))
                            for d in ([dimension] if dimension else DIMENSIONS[:4]):
                                if coverage[d]["status"] == "complete":
                                    coverage[d] = dict(status="partial", reason="one_or_more_claims_rejected")
                    for index, value in enumerate(draft.relations):
                        try:
                            item = deepcopy(value)
                            item["duty_id"] = remap[item["duty_id"]]
                            item["requirement_id"] = remap[item["requirement_id"]]
                            item["evidence"] = [locate(e, record, execution["grounding_adjustments"]) for e in item["evidence"]]
                            item = Relation.model_validate(item).model_dump()
                            if item in analysis["relations"]:
                                continue
                            trial = deepcopy(analysis)
                            trial["relations"].append(item)
                            trial["outcome"] = _outcome(coverage)
                            validate_analysis(trial)
                            analysis["relations"].append(item)
                        except (ValueError, KeyError, TypeError):
                            execution["issues"].append(dict(kind="relation_rejected", index=index, dimension="relations"))
                            if coverage["relations"]["status"] == "complete":
                                coverage["relations"] = dict(status="partial", reason="one_or_more_relations_rejected")
                    if truncated:
                        for d in DIMENSIONS:
                            if coverage[d]["status"] == "complete":
                                coverage[d] = dict(status="partial", reason="provider_length_limit")
                    elif _outcome(coverage) in {"failed", "not_run"}:
                        status = _outcome(coverage)
                    elif execution["issues"] or any(v["status"] != "complete" for d, v in coverage.items()
                                                     if d != "classification"):
                        status = "partial"
                    elif not analysis["claims"]:
                        status = "no_recognized_results"
    execution["status"] = status
    analysis["outcome"] = _outcome(coverage)
    # Knowledge normalization is deferred; preserve every original term as an unknown alignment.
    analysis["alignments"] = [dict(claim_id=c["id"], member=m, concept_id=None, knowledge_id=None,
                                   status="unknown", reason="knowledge alignment not run in P1")
                              for c in analysis["claims"] if c["requirement"]
                              for m in c["requirement"]["members"]]
    result["analysis"] = validate_analysis(analysis).model_dump()
    return result

"""Source-scoped work explanations; local evidence is independent of primary identity."""
import re

from ..foundation.inputs import InputRecord, digest
from .attribution_models import WorkSupport, UnaccountedWork
from .work_context_models import ContextAttributionResult, WorkUnit, WorkLink, axis_evaluation_v1
from .work_evidence import AUXILIARY, CLAUSES, STATEMENTS, CONDITION, PREDICATES, evidence_slice, frame_hits, same_work_group

# These are grammatical scope guards, not job-specific synonyms. Unhandled
# discourse remains a documented limitation; model similarity cannot waive them.
NEGATED = re.compile(r"无需|无须|禁止|避免|不(?!同|断|少|仅|变|可或缺)|未(?!来)")
HISTORY = re.compile(r"曾经|过去|经验|经历|熟悉|掌握|精通|了解")
OTHER = re.compile(r"(?:客户|他人|供应商|公司|其他.{0,6}|开发团队|团队)(?:负责|承担|完成)"
                   r"|(?:由|让|交给|委托|要求|安排)(?:客户|他人|供应商|开发团队|团队)")
INSTRUCTION = re.compile(r"介绍|讲解|讲授|培训|教学|授课|演示|销售.{0,8}(?:课程|软件)")
CONTEXT = re.compile(r"^\s*(?:以便|以满足|从而|确保|为.{0,30}提供|旨在|使得)")
LINK = re.compile(r"以便|以满足|从而|确保|为了|用于|为.{0,30}提供")
COORDINATED_WORK = re.compile(r"(?<!参)(?:并且|并|以及|同时|另外|此外|和|与|及)(?=\s*(?:负责|承担)|\s*(?:协助|辅助)?(?:"
    + PREDICATES + r"|制定|编制|组织|开展|进行|接待|采购|沟通|跟进|协调|实施|测试))")


def scope_of(evidence, row):
    text = row.payload.get(evidence.field, "")
    statement = next((s for s in STATEMENTS.finditer(text)
                      if s.start() <= evidence.start < s.end()), None)
    prefix = text[statement.start():evidence.start] if statement else ""
    local_prefix = re.split(r"[，,]", prefix)[-1]
    local = local_prefix + evidence.quote
    # A later condition cannot govern earlier work. Cropping a P1 quotation
    # cannot remove a governing prefix; coordination preserves that scope.
    before = prefix + evidence.quote
    if CONDITION.search(before):
        return "conditional"
    explicit_self = re.match(r"\s*(?:本人|本岗位)负责", evidence.quote)
    negative_context = local if explicit_self or re.match(r"\s*(?:仅|只)负责", evidence.quote) else before
    if NEGATED.search(negative_context):
        return "negated"
    independent = explicit_self or (re.match(r"\s*负责", evidence.quote) and re.search(r"[，,]\s*$", prefix))
    history_context = local if explicit_self or (independent and re.search(r"熟悉|掌握|精通|了解", prefix)) else before
    if HISTORY.search(history_context):
        return "historical"
    if OTHER.search(local if explicit_self else before):
        return "other_actor"
    if (INSTRUCTION.search(local if independent else before) or re.search(r"的(?:课程|教学|培训|介绍|讲解|演示)", evidence.quote)
            or re.search(r"(?:软件系统|软件服务|应用程序|代码|程序|软件)(?:开发|设计)?(?:相关|的)?(?:课程|教材|培训|教程)", evidence.quote)):
        return "instructional"
    return "affirmed"


def work_units(analysis):
    row = InputRecord.from_row(analysis.namespace, analysis.input_row)
    result, seen = [], set()
    for claim in analysis.claims:
        if claim.kind != "duty":
            continue
        for ev in claim.evidence:
            parts = []
            for clause in CLAUSES.finditer(ev.quote):
                start = clause.start()
                for split in COORDINATED_WORK.finditer(clause.group()):
                    end = clause.start() + split.start()
                    # Coordinated predicates before their first object share it.
                    if re.fullmatch(r"(?:\s|负责|承担|和|与|并|及|" + PREDICATES + r")+", ev.quote[start:end]):
                        continue
                    if start < end:
                        parts.append((start, end))
                    start = clause.start() + split.end()
                if start < clause.end():
                    parts.append((start, clause.end()))
            for start, end in parts:
                part = evidence_slice(ev, start, end)
                if not re.search(r"[A-Za-z\u4e00-\u9fff]", part.quote):
                    continue  # List numbering/punctuation is not a work assertion.
                key = (claim.id, part.field, part.start, part.end)
                if key in seen:
                    continue
                seen.add(key)
                scope = scope_of(part, row)
                auxiliary = claim.core is False or AUXILIARY.search(part.quote)
                kind = "context" if CONTEXT.search(part.quote) else "work"
                result.append(WorkUnit(
                    id="work-" + digest(key)[:20], claim_id=claim.id, evidence=part, scope=scope,
                    importance="auxiliary" if auxiliary else "core" if claim.core is True else "unknown",
                    kind=kind, reference_status="not_asserted_work" if scope != "affirmed" else
                    "context_only" if kind == "context" else "unexplained",
                    reason="P2对原引用片段的局部解释；P1事实与重要性不改写，未命中参照不证明新职业。",
                ))
    return result


def source_supports(units, frames, references):
    refs = {r.id: r for r in references}
    found, seen = [], set()
    for unit in units:
        if unit.scope != "affirmed" or unit.kind != "work":
            continue
        for frame in frames:
            for start, end, action, obj, auxiliary in frame_hits(unit.evidence.quote, frame):
                ev = evidence_slice(unit.evidence, start, end)
                key = (unit.id, frame.reference_id, ev.start, ev.end, action, obj)
                if key in seen:
                    continue
                seen.add(key)
                found.append(WorkSupport(claim_id=unit.claim_id, reference_id=frame.reference_id,
                    action=action, object=obj, importance="auxiliary" if auxiliary else unit.importance,
                    basis="source_pattern_support", jd_evidence=ev,
                    reference_evidence=refs[frame.reference_id].evidence))
    return found


def context_links(analysis):
    row = InputRecord.from_row(analysis.namespace, analysis.input_row)
    links, seen = [], set()
    duties = [c for c in analysis.claims if c.kind == "duty"]
    for duty in duties:
        for context in (c for c in analysis.claims if c.kind in {"goal", "object"}):
            for left in duty.evidence:
                for right in context.evidence:
                    if left.field != right.field:
                        continue
                    text = row.payload.get(left.field, "")
                    statement = next((s for s in STATEMENTS.finditer(text)
                        if s.start() <= min(left.start, right.start) and max(left.end, right.end) <= s.end()), None)
                    if statement is None or not LINK.search(statement.group()):
                        continue
                    # Multiple distinct duties in the sentence make attribution
                    # ambiguous. Keep their facts, without lending each the goal.
                    if any(c.id != duty.id and any(e.field == left.field and statement.start() <= e.start < e.end <= statement.end()
                                                   for e in c.evidence) for c in duties):
                        continue
                    ev = left.model_copy(update=dict(start=statement.start(), end=statement.end(), quote=statement.group()))
                    if scope_of(ev, row) != "affirmed":
                        continue
                    key = (duty.id, context.id, ev.field, ev.start, ev.end)
                    if key not in seen:
                        seen.add(key)
                        links.append(WorkLink(work_claim_id=duty.id, context_claim_id=context.id,
                            basis="source_context", evidence=ev,
                            reason="两项P1事实共享带目标/用途连接的原文语句；仅为P2上下文关系，不补写P1成果或核心性。"))
    return links


def contextualize(baseline):
    from .attribution import _axis
    from .attribution_models import AxisCandidate
    units = work_units(baseline.source_analysis)
    row = InputRecord.from_row(baseline.source_analysis.namespace, baseline.source_analysis.input_row)
    rules = {r.role_id: r for r in baseline.policy.roles}
    comparisons = []
    complete = baseline.source_analysis.coverage["duties"].status == "complete"
    for old in baseline.comparisons:
        rule = rules.get(old.role_id)
        supports = source_supports(units, rule.frames, old.definition.responsibilities) if rule else []
        conflicts = source_supports(units, rule.boundary_frames, old.definition.boundaries) if rule else []
        core = any(s.importance == "core" for s in supports)
        judgment = ("conflict" if any(s.importance == "core" for s in conflicts) else
                    "auxiliary" if supports and all(s.importance == "auxiliary" for s in supports) else
                    "core_candidate" if core and complete and not conflicts and old.definition.maturity != "test" else
                    "hypothesis" if supports else "unresolved")
        deliveries = [d for d in old.deliveries if scope_of(d.jd_evidence, row) == "affirmed"
            and any(s.claim_id == d.claim_id and same_work_group(s.jd_evidence, d.jd_evidence, row) for s in supports)]
        context = [s for s in old.context_supports if scope_of(s.jd_evidence, row) == "affirmed"]
        comparisons.append(old.model_copy(update=dict(supports=supports, conflicts=conflicts, deliveries=deliveries,
            context_supports=context,
            judgment=judgment, uncovered_duty_ids=[c.id for c in baseline.source_claims
                if c.kind == "duty" and c.id not in {s.claim_id for s in supports}],
            unmatched_reference_ids=[r.id for r in old.definition.responsibilities
                if r.id not in {s.reference_id for s in supports}],
            uncertainty=list(dict.fromkeys([*old.uncertainty, "source_pattern_not_semantic_equivalence"])),
            reason="局部原文对账与重要性分别解释；核心候选不等于可选主岗，无交付词不补写成果。")))
    gaps = []
    for unit in units:
        matches = [s for c in comparisons for s in c.supports if s.claim_id == unit.claim_id
                   and s.jd_evidence.field == unit.evidence.field
                   and unit.evidence.start <= s.jd_evidence.start < s.jd_evidence.end <= unit.evidence.end]
        if matches:
            unit.reference_status = "pattern_supported"
        elif unit.scope == "affirmed" and unit.kind == "work" and unit.importance != "auxiliary":
            gaps.append(UnaccountedWork(claim_id=unit.claim_id, evidence=unit.evidence,
                reason="该工作的重要性为核心或未知，当前参照不能解释；保留局部候选并暂不选主岗位。"))
    families, jobs = [], []
    for item in comparisons:
        rule = rules.get(item.role_id)
        if not rule or not item.supports or item.judgment == "conflict":
            continue
        strength = "auxiliary" if item.judgment == "auxiliary" else "core_candidate" if item.judgment == "core_candidate" else "local_hypothesis"
        common = dict(strength=strength, role_ids=[item.role_id], claim_ids=sorted({s.claim_id for s in item.supports}),
                      evidence=[s.jd_evidence for s in item.supports], reason=item.reason)
        if rule.family:
            families.append(AxisCandidate(value=rule.family, **common))
        if rule.canonical_candidate:
            jobs.append(AxisCandidate(value=item.role_id, **common))
    core_roles = [j.value for j in jobs if j.strength == "core_candidate"]
    selected = core_roles if not gaps else []
    main = selected[0] if len(selected) == 1 else None
    shape = "parallel_core_hypothesis" if len(core_roles) > 1 else "single_core_hypothesis" if main else "unresolved"
    if baseline.work_shape == "multi_position_advertisement":
        main, selected, shape = None, [], baseline.work_shape
    elif main and rules[main].composite_reference:
        shape = "composite_hypothesis"
    elif baseline.work_shape == "mixed_hypothesis" and not main:
        shape = "mixed_hypothesis"
    value = baseline.model_dump()
    value.update(schema_version="m2-role-attribution-2", explanation_version="context-work-attribution-4",
        comparisons=[c.model_dump() for c in comparisons], work_units=[u.model_dump() for u in units],
        work_links=[l.model_dump() for l in context_links(baseline.source_analysis)],
        unaccounted_work=[g.model_dump() for g in gaps], primary_role_id=main, work_shape=shape,
        auxiliary_role_ids=[c.role_id for c in comparisons if c.judgment == "auxiliary"],
        axis_assessments=axis_evaluation_v1(baseline),
        semantic=dict(status="not_run", reason_code="no_local_model", binding=None,
                      input_json=None, prompt=None, prompt_sha256=None, response=None, response_sha256=None, matches=[]))
    value["axes"]["family"] = _axis(families).model_dump()
    value["axes"]["canonical_job"] = _axis(jobs, selected).model_dump()
    tracks = []
    claims = {c.id: c for c in baseline.source_claims}
    for candidate in baseline.axes.technology_tracks.candidates:
        safe = [e for e in candidate.evidence if scope_of(e, row) == "affirmed"]
        if safe:
            ids = [cid for cid in candidate.claim_ids if any(
                origin.field == e.field and origin.start <= e.start < e.end <= origin.end
                for origin in claims[cid].evidence for e in safe)]
            tracks.append(candidate.model_copy(update=dict(evidence=safe, claim_ids=ids)))
    value["axes"]["technology_tracks"] = _axis(tracks).model_dump()
    for name, axis in value["axes"].items():
        for candidate in axis["candidates"]:
            candidate.update(basis="surface_work_use" if name == "technology_tracks" else "source_pattern",
                             semantic_match_key=None)
    value["retrieval"]["recalled_role_ids"] = [c.role_id for c in comparisons if c.supports or c.retrieval_clues]
    return ContextAttributionResult.model_validate(value)

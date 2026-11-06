"""Offline retrieval -> work comparison -> independent four-axis hypotheses."""
from pathlib import Path
import hashlib
import re

from ..baseline.contract import validate_analysis
from ..foundation.inputs import InputRecord, canonical, digest
from .alignment import align_analysis
from .attribution_models import (
    AttributionResult, Axes, Axis, AxisCandidate, DeliverySupport,
    Retrieval, RoleExplanation, WorkSupport,
)
from .models import CandidateProjectionBinding, validate_snapshot
from .catalog import LoadedSnapshot
from .role_policy import BoundPolicy, bind_policy
from .storage import read_result
from .tracks import technology_candidates
from .roles import _anchors_match
from .work_evidence import (
    AUXILIARY, PREDICATES, claim_matches, delivery_matches, evidence_slice,
    same_work_group, work_groups, source_conditioned,
)


def _implementation_digest():
    root = Path(__file__).parent
    paths = list(root.glob("*.py")) + [
        root.parent / "baseline" / "contract.py", root.parent / "semantics" / "models.py",
        root.parent / "foundation" / "inputs.py",
    ]
    return digest({p.relative_to(root.parent).as_posix(): hashlib.sha256(
        p.read_bytes().replace(b"\r\n", b"\n")).hexdigest() for p in sorted(paths)})


# Bind to loaded code, not to a later edited file in a long-running process.
IMPLEMENTATION_SHA256 = _implementation_digest()
MULTIPLE = re.compile(
    r"(?:招|招聘).{0,40}(?:工程师|开发|测试|分析师).{0,4}[一二两三四五六七八九十\d]+名"
    r"[、，,；;].{0,24}(?:工程师|开发|测试|分析师).{0,4}[一二两三四五六七八九十\d]+名"
    r"|(?:招聘|招收)(?:多个|两个|[2-9]个)(?:岗位|职位)"
)
NUMBERED = re.compile(r"(?:岗位|职位)([一二三1-3])[：:]")


def read_attribution(path: Path | str) -> AttributionResult:
    """Read historical results against their embedded facts, definitions and rules."""
    value = read_result(path)
    if value.get("schema_version") == "m2-role-attribution-4":
        from .work_comparison import WorkComparisonResult
        return WorkComparisonResult.model_validate(value)
    if value.get("schema_version") == "m2-role-attribution-3":
        from .task_models import TaskAttributionResult
        return TaskAttributionResult.model_validate(value)
    if value.get("schema_version") == "m2-role-attribution-2":
        from .work_context_models import ContextAttributionResult
        return ContextAttributionResult.model_validate(value)
    return AttributionResult.model_validate(value)


def _validate_dependencies(knowledge, policy, projection):
    snapshot = validate_snapshot(knowledge.snapshot.model_dump())
    bound = bind_policy(policy.policy.model_dump(), policy.path)
    if bound.sha256 != policy.sha256 or bound.policy.knowledge_sha256 != knowledge.sha256:
        raise ValueError("policy knowledge/digest binding mismatch")
    rules = {r.role_id: r for r in bound.policy.roles}
    if not set(rules) <= {r.id for r in snapshot.roles}:
        raise ValueError("policy references absent role")
    for role in snapshot.roles:
        rule = rules.get(role.id)
        if rule is None:
            continue
        for frames, refs in [(rule.frames, role.responsibilities), (rule.boundary_frames, role.boundaries)]:
            if not {f.reference_id for f in frames} <= {r.id for r in refs}:
                raise ValueError("comparison frame references absent definition item")
    if projection is not None:
        CandidateProjectionBinding.model_validate(projection.model_dump())
        if digest(projection.projection.model_dump()) != projection.sha256:
            raise ValueError("candidate projection digest mismatch")
    return rules


def _supports(claims, frames, references, row):
    refs = {r.id: r for r in references}
    found = []
    for claim in claims:
        for frame in frames:
            for action, obj, auxiliary, ev in claim_matches(claim, frame, row):
                found.append(WorkSupport(
                    claim_id=claim.id, reference_id=frame.reference_id,
                    action=action, object=obj, jd_evidence=ev,
                    reference_evidence=refs[frame.reference_id].evidence,
                    importance=("auxiliary" if auxiliary or claim.core is False else
                                "core" if claim.core is True else "unknown"),
                ))
    return found


def _axis(candidates, values=None, reason="仅表示当前版本中的有界机器候选；不是人工确认或正式统计归属。"):
    if values is None:
        values = sorted({c.value for c in candidates if c.strength != "auxiliary"})
    return Axis(status="unresolved" if not values else "single" if len(values) == 1 else "multiple",
                values=values, candidates=candidates, reason=reason)


def attribute_roles(analysis: dict, knowledge: LoadedSnapshot, policy: BoundPolicy,
                    candidate_projection: CandidateProjectionBinding | None = None, *,
                    method="bounded", local_model=None, task_retriever=None, pairs_per_role=1) -> AttributionResult:
    if method in {"evidence", "work"}:
        if local_model is None or task_retriever is None:
            raise ValueError("task evidence method needs explicit local model and retriever")
        context = attribute_roles(analysis, knowledge, policy, candidate_projection, method="context")
        if method == "work":
            from .work_comparison import start_work_comparison, compare_source_work
            return compare_source_work(start_work_comparison(context), task_retriever, local_model, pairs_per_role)
        from .task_comparison import start_comparison, compare_selected
        return compare_selected(start_comparison(context), task_retriever, local_model, pairs_per_role)
    if task_retriever is not None:
        raise ValueError("task retriever requires task comparison method")
    if method == "context":
        from .work_context import contextualize
        result = contextualize(attribute_roles(analysis, knowledge, policy, candidate_projection))
        if local_model is not None:
            from .local_semantics import infer_locally
            result = infer_locally(result, local_model)
        return result
    if local_model is not None:
        raise ValueError("local semantics requires context method")
    if method != "bounded":
        raise ValueError("unknown attribution method")
    checked = validate_analysis(analysis)
    row = InputRecord.from_row(checked.namespace, checked.input_row)
    rules = _validate_dependencies(knowledge, policy, candidate_projection)
    alignment = align_analysis(checked.model_dump(), knowledge, candidate_projection)
    duties = [c for c in checked.claims if c.kind == "duty"]
    goals_objects = [c for c in checked.claims if c.kind in {"goal", "object"}]
    kind_by_id = {c.id: c.kind for c in checked.claims}
    duty_complete = checked.coverage["duties"].status == "complete"
    explanations = []
    for role in sorted(knowledge.snapshot.roles, key=lambda r: r.id):
        rule = rules.get(role.id)
        supports = _supports(duties, rule.frames, role.responsibilities, row) if rule else []
        conflicts = _supports(duties, rule.boundary_frames, role.boundaries, row) if rule else []
        context = _supports(goals_objects, rule.frames, role.responsibilities, row) if rule else []
        supported_ids = {s.claim_id for s in supports}
        deliveries = []
        if rule:
            for claim in duties + [c for c in goals_objects if c.kind == "goal"]:
                # Delivery must be attached to this role's supported work claim, or be
                # a separately evidenced goal. Never borrow a different role's duty.
                if claim.kind == "duty" and claim.id not in supported_ids:
                    continue
                local_support = [s for s in supports + context if s.claim_id == claim.id]
                for ev in delivery_matches(claim, rule.deliveries, row):
                    if not any(same_work_group(s.jd_evidence, ev, row) for s in local_support):
                        continue
                    deliveries.append(DeliverySupport(claim_id=claim.id, text=ev.quote,
                                                       jd_evidence=ev, reference_goals=role.goals))
        uncovered = [d.id for d in duties if d.id not in supported_ids]
        uncertainty = ["machine_unreviewed", "finite_reference_scope", *role.unresolved_boundaries]
        if role.maturity != "formal":
            uncertainty.append("reference_" + role.maturity)
        if not rule:
            uncertainty.append("comparison_rule_missing")
        if not duty_complete:
            uncertainty.append("p1_duties_" + checked.coverage["duties"].status)
        for dimension in ("goals", "objects"):
            if checked.coverage[dimension].status != "complete":
                uncertainty.append("p1_" + dimension + "_" + checked.coverage[dimension].status)
        if any(s.importance == "unknown" for s in supports):
            uncertainty.append("core_status_unknown")
        if any(d.core is None for d in duties):
            uncertainty.append("unresolved_work_importance")
        if not deliveries:
            uncertainty.append("delivery_not_evidenced")
        core = [s for s in supports if s.importance == "core"]
        if any(s.importance == "core" for s in conflicts):
            judgment = "conflict"
        elif supports and all(s.importance == "auxiliary" for s in supports):
            judgment = "auxiliary"
        elif (core and duty_complete and deliveries and not conflicts
              and all(d.core is not None for d in duties) and role.maturity != "test"):
            judgment = "core_candidate"
        elif supports:
            judgment = "hypothesis"
        else:
            judgment = "unresolved"
        clues = [r.id for r in role.responsibilities if any(_anchors_match(d.text, r.anchors) for d in duties)]
        explanations.append(RoleExplanation(
            role_id=role.id, definition=role, supports=supports, conflicts=conflicts, deliveries=deliveries,
            context_supports=context,
            judgment=judgment, retrieval_clues=clues, uncovered_duty_ids=uncovered,
            unmatched_reference_ids=[r.id for r in role.responsibilities
                                     if r.id not in {s.reference_id for s in supports}],
            goal_claim_ids=sorted({s.claim_id for s in context if kind_by_id[s.claim_id] == "goal"}),
            object_claim_ids=sorted({s.claim_id for s in context if kind_by_id[s.claim_id] == "object"}),
            unmatched_goal_claim_ids=[c.id for c in goals_objects if c.kind == "goal" and c.id not in {s.claim_id for s in context}],
            unmatched_object_claim_ids=[c.id for c in goals_objects if c.kind == "object" and c.id not in {s.claim_id for s in context}],
            uncertainty=uncertainty,
            reason={"conflict": "局部正向责任与定义中的明确边界相抵触；仅限引用责任，不排除所有相邻职业。",
                    "auxiliary": "有对应责任，但原文/核心字段仅支持辅助关联。",
                    "core_candidate": "核心责任与明确交付具有局部双侧支持；仍为受限机器候选。",
                    "hypothesis": "有局部职责依据，事实覆盖、重要性或交付证据不足以确定主岗位。",
                    "unresolved": "当前规则未能对账责任；参考或表达缺口不等于该职业被排除。"}[judgment],
        ))

    family_candidates, canonical_candidates = [], []
    for item in explanations:
        rule = rules.get(item.role_id)
        if not rule or not item.supports or item.judgment == "conflict":
            continue
        strength = ("auxiliary" if item.judgment == "auxiliary" else
                    "core_candidate" if item.judgment == "core_candidate" else "local_hypothesis")
        arguments = dict(strength=strength, role_ids=[item.role_id],
                         claim_ids=sorted({s.claim_id for s in item.supports}),
                         evidence=[s.jd_evidence for s in item.supports], reason=item.reason)
        if rule.family:
            family_candidates.append(AxisCandidate(value=rule.family, **arguments))
        if rule.canonical_candidate:
            canonical_candidates.append(AxisCandidate(value=item.role_id, **arguments))

    core_roles = [c.value for c in canonical_candidates if c.strength == "core_candidate"]
    core_covered = {s.claim_id for item in explanations if item.role_id in core_roles
                    for s in item.supports if s.importance == "core"}
    unaccounted_work = []
    for duty in duties:
        if duty.core is not True:
            continue
        for ev in duty.evidence:
            for start, end, group in work_groups(ev.quote):
                part = evidence_slice(ev, start, end)
                # These are unexplained work spans, not new P1 claims or exclusions.
                if AUXILIARY.search(group) or source_conditioned(part, row) or not re.search(PREDICATES, group):
                    continue
                if not any(s.claim_id == duty.id and same_work_group(part, s.jd_evidence, row)
                           for item in explanations for s in item.supports):
                    unaccounted_work.append(dict(claim_id=duty.id, evidence=part,
                                                reason="当前参考/规则未能解释该核心工作片段；不构成排除或新职业证明。"))
    unaccounted_core = bool(unaccounted_work) or any(d.core is True and d.id not in core_covered
                                                   and not AUXILIARY.search(d.text) for d in duties)
    main = core_roles[0] if len(core_roles) == 1 and not unaccounted_core else None
    shape = ("single_core_hypothesis" if main else "parallel_core_hypothesis" if len(core_roles) > 1
             else "unresolved")
    mixed_evidence = []
    # Multiple labels for the same work cannot establish a mixed job. Require
    # different directions AND independently evidenced work fragments.
    for first in explanations:
        first_rule = rules.get(first.role_id)
        if not first_rule or not first_rule.family or first.judgment == "conflict":
            continue
        for second in explanations:
            second_rule = rules.get(second.role_id)
            if (not second_rule or not second_rule.family or second.judgment == "conflict"
                    or first_rule.family == second_rule.family):
                continue
            for left in first.supports:
                for right in second.supports:
                    if not same_work_group(left.jd_evidence, right.jd_evidence, row):
                        mixed_evidence = [left.jd_evidence, right.jd_evidence]
    if mixed_evidence and shape != "parallel_core_hypothesis":
        shape = "mixed_hypothesis"
    if len(core_roles) == 1 and rules[core_roles[0]].composite_reference and main:
        shape = "composite_hypothesis"
    shape_evidence = []
    for field in ("job_title", "raw_text", "duties"):
        text = str(checked.input_row.get(field, ""))
        numbered = list(NUMBERED.finditer(text))
        matches = list(MULTIPLE.finditer(text))
        if len({m.group(1) for m in numbered}) >= 2:
            matches += numbered
        for match in matches:
            shape_evidence.append(dict(namespace=checked.namespace, jd_id=checked.jd_id, fingerprint=row.fingerprint,
                                       field=field, start=match.start(), end=match.end(), quote=match.group()))
    selected_jobs = core_roles if not unaccounted_core else []
    if shape_evidence:
        main, selected_jobs, shape = None, [], "multi_position_advertisement"
    else:
        shape_evidence = mixed_evidence

    tracks = technology_candidates(checked, policy.policy.track_terms)
    limitations = ["machine_unreviewed", "bounded_patterns_not_general_entailment", "no_market_accuracy_claim",
                   policy.policy.scope_limitation, "seniority_reference_not_configured"]
    for dimension in ("goals", "objects", "duties", "requirements"):
        if checked.coverage[dimension].status != "complete":
            limitations.append("p1_" + dimension + "_" + checked.coverage[dimension].status)
    if unaccounted_core:
        limitations.append("unaccounted_core_work")
    checked_ids = [i.role_id for i in explanations]
    return AttributionResult(
        explanation_version="bounded-work-attribution-2",
        implementation_sha256=IMPLEMENTATION_SHA256, source_analysis_sha256=digest(checked.model_dump()),
        source_analysis=checked, knowledge_id=knowledge.snapshot.id, knowledge_revision=knowledge.snapshot.revision,
        knowledge_sha256=knowledge.sha256, knowledge_sources=knowledge.snapshot.sources,
        knowledge_json=(knowledge.raw or canonical(knowledge.snapshot.model_dump()).encode("utf-8")).decode("utf-8"),
        policy=policy.policy, policy_sha256=policy.sha256, alignment=alignment,
        retrieval=Retrieval(available_role_ids=checked_ids, checked_role_ids=checked_ids,
                            recalled_role_ids=[i.role_id for i in explanations if i.supports or i.retrieval_clues],
                            scope_limitation=policy.policy.scope_limitation,
                            status="empty_catalog" if not checked_ids else "facts_unavailable" if not duties else "completed"),
        comparisons=explanations,
        axes=Axes(family=_axis(family_candidates), canonical_job=_axis(canonical_candidates, selected_jobs),
                  technology_tracks=_axis(tracks), seniority=_axis([], [], "当前没有可用的版本化级别标准；年限和技能程度不换算级别。")),
        primary_role_id=main, auxiliary_role_ids=[i.role_id for i in explanations if i.judgment == "auxiliary"],
        work_shape=shape, shape_evidence=shape_evidence, limitations=limitations,
        unaccounted_work=unaccounted_work,
    )

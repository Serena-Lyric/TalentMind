"""Actually executed offline role research for delivery; no occupational release."""
from pathlib import Path

from ..foundation.inputs import digest
from .attribution import attribute_roles
from .role_policy import bind_policy, load_policy
from .work_semantics import VERSION, explain_work, source_work as explain_source


def _policy(knowledge):
    for path in sorted((Path(__file__).parent / "policies").glob("role-attribution.v*.json")):
        policy = load_policy(path)
        if policy.policy.knowledge_sha256 == knowledge.sha256:
            return policy
    # A changed or smaller catalogue cannot inherit unrelated reference mappings.
    return bind_policy(dict(schema_version="m2-role-policy-1", revision="unconfigured-knowledge-1",
        knowledge_sha256=knowledge.sha256, family_source="No matching versioned role policy",
        roles=[], track_terms=[], scope_limitation="当前知识没有匹配的版本化职责适配策略；保留参照文本和源职责缺口。"))


def _base_summary(result):
    return dict(schema_version="m2-role-research-1", method_version=VERSION,
        namespace=result.source_analysis.namespace, jd_id=result.source_analysis.jd_id,
        input_sha256=result.source_analysis.input_sha256,
        source_analysis_sha256=result.source_analysis_sha256, knowledge_sha256=result.knowledge_sha256,
        policy_sha256=result.policy_sha256, policy_revision=result.policy.revision,
        implementation_sha256=result.implementation_sha256,
        reference_role_ids=[c.role_id for c in result.comparisons],
        primary_role_id=None, formal_statistics_eligible=False, semantic_review="machine_unreviewed",
        knowledge_gaps=["当前仅检查reference_role_ids所列有限参照，目录外工作未评价。",
                        "缺少岗位级别参照；年限、熟练度不换算seniority。"],
        limitations=["局部方面支持不证明整岗等价；未识别表述不是反证。",
                    "无独立职业人工真值，不计算precision/recall。"],
        semantic_precision=None, semantic_recall=None)


def _axes(result, supports):
    rules = {r.role_id: r for r in result.policy.roles}
    axes = {}
    for name in ("family", "canonical_job"):
        candidates = []
        for role_id in sorted({s["role_id"] for s in supports}):
            rule = rules.get(role_id)
            value = rule.family if rule and name == "family" else role_id if rule and rule.canonical_candidate else None
            if not value:
                continue
            candidates.append(dict(value=value, role_id=role_id,
                claim_ids=sorted({s["claim_id"] for s in supports if s["role_id"] == role_id}),
                basis="local_task_aspects", semantic_review="machine_unreviewed",
                maturity=next(c.definition.maturity for c in result.comparisons if c.role_id == role_id)))
        axes[name] = dict(status="research_candidates" if candidates else "unresolved", candidates=candidates,
                          selected_values=[], reason="仅局部职责候选；未据此选择完整岗位。")
    tech = result.axes.technology_tracks
    axes["technology_tracks"] = dict(status="research_candidates" if tech.candidates else "unresolved",
        candidates=[c.model_dump() for c in tech.candidates], selected_values=[],
        reason="仅实际工作中出现的技术方向，不由技能熟练度或单纯共现推断。")
    axes["seniority"] = dict(status="not_evaluated", candidates=[], selected_values=[], reason="no_versioned_reference")
    return axes


def build_delivery_research(analysis, knowledge, *, candidate_projection=None):
    """Use the caller's frozen snapshot; no network, DB, implicit model or writes."""
    policy = _policy(knowledge)
    result = attribute_roles(analysis, knowledge, policy, candidate_projection, method="context")
    rules = {r.role_id: r for r in policy.policy.roles}
    source_work, supports, assessments = [], [], []
    for claim in result.source_claims:
        if claim.kind != "duty":
            continue
        # Exact P1 source spans, never its paraphrase, supply the new interpretation.
        source = explain_source(claim.model_dump(), analysis)
        views = [u['view'] for u in source['matched_source_units']]
        source_work.append(dict(claim_id=claim.id, core=claim.core, evidence=[e.model_dump() for e in claim.evidence],
                               matched_source_units=source['matched_source_units'], views=views))
        source_keys = {(f["action"], f["object"]) for view in views for f in view["frames"] if f["scope"] == "affirmed"}
        for comparison in result.comparisons:
            rule = rules.get(comparison.role_id)
            for ref in comparison.definition.responsibilities:
                frame = next((f for f in rule.frames if f.reference_id == ref.id), None) if rule else None
                target_texts = [f"{action} {obj}" for action in frame.actions for obj in frame.objects] if frame else [ref.text]
                target_keys = {(f["action"], f["object"]) for text in target_texts for f in explain_work(text)["frames"]}
                shared = source_keys & target_keys
                # Generic software is only a role task aspect here; candidate-to-
                # candidate matching uses object_detail and all duties separately.
                state = "bounded_source_supported" if shared else "unresolved"
                item = dict(claim_id=claim.id, role_id=comparison.role_id, reference_id=ref.id, state=state,
                    reason="shared_source_task_aspect" if shared else "no_bounded_task_aspect",
                    matched_aspects=[dict(action=a, object=o) for a, o in sorted(shared)])
                assessments.append(item)
                if shared:
                    supports.append({**item, "importance": source['importance'],
                        "basis": "bounded_source_pattern", "semantic_review": "machine_unreviewed",
                        "source_evidence": [e.model_dump() for e in claim.evidence],
                        "reference_evidence": [e.model_dump() for e in ref.evidence]})
    supported = {s["claim_id"] for s in supports}
    uncovered = []
    for work in source_work:
        covered_aspects = {(a["action"], a["object"]) for s in supports if s["claim_id"] == work["claim_id"]
                           for a in s["matched_aspects"]}
        source_gaps = [gap for view in work["views"] for gap in view["gaps"]]
        remaining = [f for view in work["views"] for f in view["frames"]
                     if f["scope"] == "affirmed" and (f["action"], f["object"]) not in covered_aspects]
        if work["claim_id"] not in supported or source_gaps or remaining:
            uncovered.append(dict(claim_id=work["claim_id"], core=work["core"],
                reason="no_supported_task_aspect" if work["claim_id"] not in supported else "partial_source_work_uncovered",
                source_gaps=source_gaps, uncovered_aspects=remaining))
    summary = _base_summary(result)
    summary.update(status="bounded_research_completed", evidence_kind="bounded_offline_rules", model_calls=0,
        source_work=source_work, local_supports=supports, task_assessments=assessments,
        axes=_axes(result, supports), refutations=[],
        uncovered_work=uncovered,
        coverage=dict(pool_pairs=len(assessments), selected_pairs=len(assessments), checked_pairs=len(assessments),
                      unchecked_pairs=0, pending_pairs=0, failed_pairs=0))
    summary["result_sha256"] = digest(summary)
    return summary


def build_research_summary(result):
    """Project an explicitly supplied, validated source-work result without inference."""
    summary = _base_summary(result)
    summary['method_version'] = {'source-bound-work-comparison-3': 'bounded-work-semantics-1',
                                 'source-bound-work-comparison-4': 'bounded-work-semantics-2',
                                 'source-bound-work-comparison-5': VERSION}.get(
                                     result.explanation_version, result.explanation_version)
    supports = [dict(claim_id=c.claim_id, role_id=c.role_id, reference_id=c.reference_id,
        importance=c.importance, basis="machine_pair_checked", semantic_review=c.semantic_review)
        for c in result.work_candidates]
    selection = result.task_selection
    checked_claims = {a.claim_id for a in result.task_assessments}
    summary.update(status="model_research_recorded", evidence_kind="saved_model_results",
        source_work=[u.model_dump() for u in result.work_units], local_supports=supports,
        axes=_axes(result, supports), task_assessments=[a.model_dump() for a in result.task_assessments],
        refutations=[], uncovered_work=[dict(claim_id=u.claim_id, importance=u.importance,
            reason="not_checked" if u.claim_id not in checked_claims else "no_supported_task_aspect")
            for u in result.work_units if u.claim_id not in {s["claim_id"] for s in supports}],
        coverage=dict(pool_pairs=len(selection.proposals), selected_pairs=len(selection.selected_pair_ids),
            checked_pairs=len(selection.checked_pair_ids), unchecked_pairs=len(selection.unchecked_pair_ids),
            pending_pairs=len(selection.pending_selected_pair_ids),
            failed_pairs=sum(a.state == "failed" for a in result.task_assessments)))
    summary["result_sha256"] = digest(summary)
    return summary

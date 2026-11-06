"""Version-bound research suggestions. This module has no confirmation/write path."""
from itertools import combinations

from ..foundation.inputs import digest
from .models import Binding


def structural_suggestions(state):
    result = []

    def add(kind, ids, reason, evidence, alternatives, **extra):
        subjects = {cid: dict(candidate_version=state["candidates"][cid]["version"],
                               candidate_sha256=digest(state["candidates"][cid]),
                               relation_sha256s={rid: digest(r) for rid, r in sorted(state["relations"].items())
                                                if r["candidate_id"] == cid}) for cid in sorted(ids)}
        value = dict(schema_version="m2-work-suggestion-1", registry_id=state["registry_id"], kind=kind,
                     subjects=subjects, reason=reason, evidence=evidence, competing_explanations=alternatives,
                     nature="machine_research_suggestion", status="unconfirmed", formal_effect=False,
                     confirmation="unavailable_no_trusted_identity", **extra)
        result.append(dict(id=digest(value), **value))

    for cid, candidate in sorted(state["candidates"].items()):
        research = candidate["research"]
        members = research["member_explanations"]
        active = [m for m in members if m["relation_state"] not in {"withdrawn", "rejected_proposal"}]
        if research["status"] == "disputed" or (len(research["content_groups"]) > 1 and not research["shared_statements"]):
            add("review_split", [cid], "反证或无完整逐字共同陈述，需要检查范围；不据此判定语义不兼容",
                [dict(relation_id=m["relation_id"], analysis_sha256=m["analysis_sha256"],
                      selected_work_ids=m["selected_work_ids"], counterevidence=m["counterevidence"]) for m in members],
                ["可能是同工作异表述", "可能是辅助/混合职责", "可能是误关联，需要收窄或另立候选"])
        eligible = [m for m in active if m["eligibility"] == "local_research_only"]
        if not eligible or len(eligible) != len(active):
            continue
        supported = [set(r["role_id"] for r in m["role_explanations"] if r["judgment"] == "supported") for m in eligible]
        for role_id in sorted(set.intersection(*supported)):
            add("review_role", [cid], "当前有限目录比较覆盖所列成员；不代表已正式归类或排除其他职业",
                [dict(analysis_sha256=m["analysis_sha256"], comparison_sha256=m["role_comparison_sha256"]) for m in eligible],
                ["候选/测试标准可能不充分", "可能存在快照外更适合的职业", "需可信负责人确认正式归属"],
                role_id=role_id, knowledge=research["knowledge"])
    for left, right in combinations(sorted(state["candidates"]), 2):
        a, b = (state["candidates"][cid]["research"]["comparison_work"] for cid in (left, right))
        shared = sorted({(r["analysis_sha256"], r["claim_id"]) for r in a} & {(r["analysis_sha256"], r["claim_id"]) for r in b})
        if shared:
            add("review_overlap", [left, right], "候选存在同源局部工作引用，可能重叠但不能自动合并身份",
                [dict(analysis_sha256=s, claim_id=i) for s, i in shared],
                ["同一 JD 可以有多个独立工作组合", "共同局部责任不等于整个工作组合相同", "候选可能重复，需检查全部成员和反证"])
    return sorted(result, key=lambda s: s["id"])


def check_suggestion(store, suggestion_id, expected_binding):
    """Read-only applicability check. Hashes authenticate scope, never a human."""
    state = store.read()
    if Binding.model_validate(expected_binding).model_dump() != state["binding"]:
        raise ValueError("stale suggestion baseline")
    suggestion = next((s for s in state.get("structural_suggestions", []) if s["id"] == suggestion_id), None)
    if suggestion is None:
        raise ValueError("unknown or stale suggestion")
    for cid, subject in suggestion["subjects"].items():
        relations = {rid: digest(r) for rid, r in sorted(state["relations"].items()) if r["candidate_id"] == cid}
        if (digest(state["candidates"][cid]) != subject["candidate_sha256"]
                or relations != subject["relation_sha256s"]):
            raise ValueError("stale suggestion subjects")
    return dict(suggestion=suggestion, binding=state["binding"], applicable=True,
                confirmation="unavailable_no_trusted_identity", formal_effect=False)

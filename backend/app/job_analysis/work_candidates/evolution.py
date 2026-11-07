"""Bounded automatic source projections, without certifying open-world work semantics."""
from collections import defaultdict
import re

from ..foundation.inputs import digest
from ..knowledge.alignment import align_analysis
from ..knowledge.roles import compare_roles
from .retrieval import compare_work


def _normal(text):
    return re.sub(r"\s+", "", text).casefold()


def _refs(values):
    return sorted({(r["analysis_sha256"], r["claim_id"]) for r in values})


def _difference(new, old):
    return [dict(analysis_sha256=s, claim_id=i) for s, i in sorted(set(_refs(new)) - set(_refs(old)))]


def _member(store, relation, knowledge):
    sha = relation["analysis_sha256"]
    analysis = store.source("analysis", sha)
    work = [c for c in analysis["claims"] if c["kind"] in {"duty", "goal", "object"}]
    eligibility = (relation["state"] if relation["state"] in {"withdrawn", "rejected_proposal", "disputed"}
                   else "competing_analysis_versions" if relation["needs_reassessment"] else "local_research_only")
    comparison = compare_roles(analysis, knowledge).model_dump()
    comparison_sha = store.put_source("comparison", comparison)
    alignment_sha = store.put_source("alignment", align_analysis(analysis, knowledge).model_dump())
    duties = [c for c in work if c["kind"] == "duty"]
    scope = dict(
        selected_duty_ids=sorted(c["id"] for c in duties if c["id"] in relation["work_ids"]),
        auxiliary_duty_ids=sorted(c["id"] for c in duties if c.get("core") is False),
        uncovered_core_duty_ids=sorted(c["id"] for c in duties if c.get("core") is True and c["id"] not in relation["work_ids"]),
        unknown_importance_duty_ids=sorted(c["id"] for c in duties if c.get("core") is None),
        uncovered_duty_ids=sorted(c["id"] for c in duties if c["id"] not in relation["work_ids"]),
        bounded_work_checks=[dict(claim_id=c["id"], comparison=compare_work(c, c, analysis, analysis)) for c in duties],
        whole_group_confirmed=False)
    return dict(relation_id=relation["id"], relation_sha256=digest(relation), namespace=analysis["namespace"],
                jd_id=analysis["jd_id"], analysis_sha256=sha, input_sha256=analysis["input_sha256"],
                selected_work_ids=sorted(set(relation["work_ids"])), work_context=work,
                unselected_duty_ids=sorted(c["id"] for c in work if c["kind"] == "duty" and c["id"] not in relation["work_ids"]),
                coverage=analysis["coverage"], outcome=analysis["outcome"], semantic_review=analysis["semantic_review"],
                eligibility=eligibility, relation_state=relation["state"], semantic_validation=relation["semantic_validation"],
                human_confirmation=relation["human_confirmation"], source_independence="unknown",
                pending_analysis_sha256s=relation["pending_analysis_sha256s"],
                superseded_analysis_sha256s=relation["superseded_analysis_sha256s"],
                counterevidence=relation.get("last_correction", {}).get("counterevidence", []),
                discovery=relation.get("discovery", {"kind": "legacy_unspecified"}), semantic_scope=scope,
                role_comparison_sha256=comparison_sha, alignment_sha256=alignment_sha,
                role_explanations=comparison["comparisons"], role_scope=comparison["retrieval_scope"],
                analyzer_versions={k: analysis[k] for k in ("analyzer", "model", "prompt", "configuration")})


def _semantic_common(store, members):
    """Every selected work pair needs direct support, never a connected-component merge."""
    scopes = [[(c, store.source('analysis', m['analysis_sha256'])) for c in m["work_context"] if c["kind"] == "duty" and c.get("core") is not False
               and c["id"] in m["selected_work_ids"]] for m in members]
    if not scopes or any(not scope for scope in scopes):
        return []
    result = []
    for anchor in scopes[0]:
        selected = [anchor]
        comparisons = []
        for scope in scopes[1:]:
            match = None
            for candidate in scope:
                checks = [compare_work(candidate[0], prior[0], candidate[1], prior[1]) for prior in selected]
                if all(check["state"] == "supported" for check in checks):
                    match = candidate
                    comparisons.extend(checks)
                    break
            if match is None:
                break
            selected.append(match)
        if len(selected) == len(scopes) and all(compare_work(c, c, a, a)["state"] == "supported" for c, a in selected):
            result.append(dict(text=anchor[0]["text"], references=[dict(analysis_sha256=m["analysis_sha256"], claim_id=c[0]["id"])
                               for m, c in zip(members, selected)], comparisons=comparisons,
                               nature="bounded_semantic_local_overlap_not_group_confirmation"))
    return result


def _project(store, baseline, state, cid, knowledge, policy):
    prior = baseline["candidates"].get(cid, {}).get("research", {})
    relations = [r for _, r in sorted(state["relations"].items()) if r["candidate_id"] == cid]
    members = [_member(store, r, knowledge) for r in relations]
    eligible = [m for m in members if m["eligibility"] == "local_research_only"]
    selected, by_member, contents = [], [], defaultdict(list)
    for member in eligible:
        duties = { _normal(c["text"]): c for c in member["work_context"]
                  if c["kind"] == "duty" and c["id"] in member["selected_work_ids"] }
        by_member.append(duties)
        selected += [dict(analysis_sha256=member["analysis_sha256"], claim_id=c["id"]) for c in duties.values()]
        a = store.source("analysis", member["analysis_sha256"])
        content_sha = digest({k: _normal(a["input_row"].get(k, "")) for k in ("raw_text", "duties", "requirements", "experience")})
        contents[content_sha].append(member["relation_id"])
    # Exact local intersections describe evidence overlap, not semantic core or independent support.
    complete = (len(eligible) == len([m for m in members if m["relation_state"] not in {"withdrawn", "rejected_proposal"}])
                and all(m["coverage"]["duties"]["status"] == "complete" and not m["unselected_duty_ids"] for m in eligible))
    common = set.intersection(*(set(d) for d in by_member)) if len(contents) > 1 and complete else set()
    prior_shared = {_normal(s["text"]): s["text"] for s in prior.get("shared_statements", [])}
    shared = [dict(text=prior_shared.get(key, by_member[0][key]["text"]),
                   references=[dict(analysis_sha256=m["analysis_sha256"], claim_id=d[key]["id"])
                               for m, d in zip(eligible, by_member)],
                   nature="literal_overlap_not_semantic_confirmation") for key in sorted(common)]
    semantic_shared = _semantic_common(store, eligible) if len(contents) > 1 else []
    shared_refs = {(r["analysis_sha256"], r["claim_id"]) for s in semantic_shared for r in s["references"]}
    for member in members:
        member["semantic_scope"]["member_specific_duty_ids"] = sorted(c["id"] for c in member["work_context"]
            if c["kind"] == "duty" and c["id"] in member["selected_work_ids"]
            and (member["analysis_sha256"], c["id"]) not in shared_refs)
    historical = {digest(r): r for r in relations}
    if cid in baseline["candidates"]:
        for item in store.history(cid):
            old_state = store.read(item["binding"]["revision"])
            for r in old_state["relations"].values():
                if r["candidate_id"] == cid:
                    historical[digest(r)] = r
    unresolved = ["work_semantics_not_independently_validated", "source_independence_unknown"]
    if not complete:
        unresolved.append("full_member_scope_not_covered")
    if len(contents) > 1 and not shared:
        unresolved.append("no_literal_common_responsibility_not_proof_of_incompatibility")
    for m in members:
        if m["eligibility"] != "local_research_only":
            unresolved.append(m["relation_id"] + ":" + m["eligibility"])
    scopes = {}
    for m in eligible:
        selected_duties = {_normal(c["text"]): c["text"] for c in m["work_context"]
                           if c["kind"] == "duty" and c["id"] in m["selected_work_ids"]}
        text = "；".join(selected_duties[k] for k in sorted(selected_duties))
        key = _normal(text)
        scopes.setdefault(key, prior.get("scope_descriptions", {}).get(key, text))
    description = ("研究假设；逐成员职责范围（不确认同组）：" + " | ".join(scopes[k] for k in sorted(scopes)) if scopes
                   else "研究假设暂停：没有当前可比较的工作依据；历史与反证仍保留")
    if shared:
        description += "。当前逐字共同陈述（未确认语义共同核心）：" + "；".join(s["text"] for s in shared)
    if semantic_shared:
        description += "。有界语义共同工作（仅局部、未确认整岗同组）：" + "；".join(s["text"] for s in semantic_shared)
    if any(m["semantic_scope"]["auxiliary_duty_ids"] for m in members):
        description += "。辅助职责单列，不作为共同核心扩张依据"
    if any(m["semantic_scope"]["uncovered_core_duty_ids"] for m in members):
        description += "。存在未覆盖核心职责，见逐成员差异与未覆盖范围"
    if any(m["eligibility"] == "disputed" for m in members):
        description += "。存在反证关系，不能扩充共同职责解释该成员"
    return dict(schema_version="m2-work-research-1", nature="machine_hypothesis", policy=policy,
                status="disputed" if any(m["eligibility"] == "disputed" for m in members)
                else "observing" if selected else "no_active_basis",
                description=description, scope_descriptions=scopes, comparison_work=_difference(selected, []),
                comparison_nature="local_evidence_retrieval_not_group_confirmation",
                shared_statements=shared, semantic_shared_statements=semantic_shared,
                whole_group_confirmed=False, member_explanations=members,
                historical_relations=[dict(sha256=s, relation=r) for s, r in sorted(historical.items())],
                historical_explanations=[_member(store, r, knowledge) for _, r in sorted(historical.items())],
                knowledge=dict(id=knowledge.snapshot.id, revision=knowledge.snapshot.revision, sha256=knowledge.sha256),
                content_groups=[dict(content_sha256=s, relation_ids=sorted(ids), source_independence="unknown")
                                for s, ids in sorted(contents.items())],
                semantic_validation="bounded_machine_comparison", independent_support=None, human_confirmation="not_confirmed",
                controlled_support_relation_ids=sorted(m["relation_id"] for m in eligible
                                                      if m["relation_state"] == "controlled_support"),
                formal_identity=None, unresolved=sorted(set(unresolved)))


def _meaning(projection):
    """Repeated source identities add provenance, not another effective hypothesis."""
    scopes = {}
    for m in projection["member_explanations"]:
        work = {digest([c["kind"], _normal(c["text"]), c["core"]]): dict(kind=c["kind"], text=_normal(c["text"]), core=c["core"])
                for c in m["work_context"]}
        scope = dict(work=[work[k] for k in sorted(work)],
                     selected=sorted({_normal(c["text"]) for c in m["work_context"] if c["id"] in m["selected_work_ids"]}),
                     eligibility=m["eligibility"], validation="machine_unreviewed" if m["semantic_validation"] in
                     {"not_run", "bounded_machine_comparison"} else m["semantic_validation"],
                     coverage={k: v["status"] for k, v in m["coverage"].items()},
                     analyzer_versions=m["analyzer_versions"],
                     roles=[{k: r[k] for k in ("role_id", "role_revision", "role_maturity", "judgment")}
                            for r in m["role_explanations"]])
        scopes[digest(scope)] = scope
    return digest(dict(scopes=[scopes[k] for k in sorted(scopes)],
                       shared_texts=[_normal(s["text"]) for s in projection["shared_statements"]],
                       semantic_shared_texts=sorted(_normal(s["text"]) for s in projection["semantic_shared_statements"]),
                       status=projection["status"], knowledge=projection["knowledge"], policy=projection["policy"]))


def evolve_candidates(store, baseline, state, knowledge, policy):
    """Called after all comparisons/operations, inside the one P3 transaction."""
    report = {}
    for cid, candidate in sorted(state["candidates"].items()):
        old = baseline["candidates"].get(cid, {}).get("research")
        projection = _project(store, baseline, state, cid, knowledge, policy)
        projection["effective_hypothesis_sha256"] = _meaning(projection)
        previous = {k: v for k, v in (old or {}).items() if k != "version"}
        source_changed = projection != previous
        changed = projection["effective_hypothesis_sha256"] != (old or {}).get("effective_hypothesis_sha256")
        projection["version"] = ((old or {}).get("version", 0) + 1) if changed else old["version"]
        candidate["research"] = projection
        causes = []
        if source_changed:
            if old is None:
                causes.append("initial_source_reconstruction")
            else:
                for field, cause in (("knowledge", "knowledge_reinterpretation"), ("policy", "policy_reinterpretation"),
                                     ("member_explanations", "member_evidence_or_analysis_changed")):
                    if projection[field] != old[field]:
                        causes.append(cause)
            # Candidate version increments once, even if P3 also changed its member list this batch.
            candidate["version"] = baseline["candidates"].get(cid, {}).get("version", 0) + 1
        report[cid] = dict(applied=changed, evidence_updated=source_changed,
                           reason="effective_source_projection_changed" if changed else "no_effective_evidence_change",
                           causes=causes, baseline=baseline["binding"],
                           previous_research_sha256=digest(old) if old else None, effective_research_sha256=digest(projection),
                           effective_version=projection["version"],
                           added_comparison_work=_difference(projection["comparison_work"], (old or {}).get("comparison_work", [])),
                           removed_comparison_work=_difference((old or {}).get("comparison_work", []), projection["comparison_work"]),
                           change_nature="candidate_research_not_market_change")
    return report


def evidence_changes(store, baseline, analyses):
    """Separate observation/content/processor changes; none measures market demand."""
    previous = defaultdict(list)
    for sha in baseline["analysis_sha256s"]:
        a = store.source("analysis", sha)
        previous[(a["namespace"], a["jd_id"])].append((sha, a))
    result = {}
    for sha, a in sorted(analyses.items()):
        old = previous[(a["namespace"], a["jd_id"])]
        new = sha not in baseline["analysis_sha256s"]
        def content(value):
            return {k: value["input_row"].get(k) for k in ("raw_text", "duties", "requirements", "experience", "job_title")}
        result[sha] = dict(previous_analysis_sha256s=sorted(s for s, _ in old),
                           observation="repeat" if not new else "new_analysis" if old else "new_jd_identity",
                           recruitment_content_changed=new and any(content(a) != content(v) for _, v in old),
                           analyzer_changed=new and any(any(a[k] != v[k] for k in ("analyzer", "model", "prompt", "configuration")) for _, v in old),
                           claims_changed=new and any(a["claims"] != v["claims"] for _, v in old),
                           comparison_scope="any_prior_analysis_same_jd_identity", independent_demand=None)
    return result

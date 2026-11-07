"""Direct bounded work comparisons; lexical retrieval remains an explicit baseline."""
import re
from collections import defaultdict

from ..foundation.inputs import digest
from ..knowledge.work_semantics import compare_work as compare_text_work, source_work


def compare_work(left, right, left_analysis, right_analysis):
    """P1 paraphrases cannot remove a negation or add responsibility to its source."""
    sources = [source_work(left, left_analysis), source_work(right, right_analysis)]
    result = compare_text_work(*sources)
    for side, source in zip(('left', 'right'), sources):
        result[side]['matched_source_units'] = source['matched_source_units']
    return result


def _grams(text):
    text = re.sub(r"\s+", "", text).casefold()
    return {text[i:i+2] for i in range(len(text)-1)}


def retrieve(store, analysis, candidates, limit=10, *, relations=None):
    duties = [c for c in analysis["claims"] if c["kind"] == "duty"]
    matches, lexical_matches, checks = [], [], {}
    baselines = {}
    for cid, candidate in sorted(candidates.items()):
        pairs, lexical_pairs = [], []
        member_pairs = defaultdict(list)
        if "research" in candidate:
            references = candidate["research"]["comparison_work"]
        elif relations is not None:
            # Legacy snapshots have relations even when they predate effective projections.
            references = [dict(analysis_sha256=r["analysis_sha256"], claim_id=i)
                          for _, r in sorted(relations.items()) if r["candidate_id"] == cid
                          and r["state"] not in {"withdrawn", "rejected_proposal", "disputed"} and not r["needs_reassessment"]
                          for i in sorted(set(r["work_ids"]))]
        else:
            raise ValueError("legacy candidate retrieval requires frozen relations")
        baselines[cid] = dict(candidate_version=candidate["version"],
                             research_sha256=digest(candidate["research"]) if "research" in candidate else None,
                             effective_hypothesis_sha256=candidate.get("research", {}).get("effective_hypothesis_sha256"),
                             comparison_work=references)
        for reference in references:
            source = store.source("analysis", reference["analysis_sha256"])
            anchor = next(c for c in source["claims"] if c["id"] == reference["claim_id"])
            if anchor["kind"] != "duty":
                continue
            member_pairs[reference["analysis_sha256"]]  # every member participates, including unsupported
            for duty in duties:
                overlap = len(_grams(duty["text"]) & _grams(anchor["text"]))
                pair = dict(duty_id=duty["id"], core_reference=reference, lexical_overlap=overlap)
                if overlap >= 2:
                    lexical_pairs.append(pair)
                judgment = compare_work(duty, anchor, analysis, source)
                eligible = duty.get("core") is not False and anchor.get("core") is not False
                # Exact re-observation preserves a local scope even when the vocabulary cannot
                # interpret it. It remains explicitly literal, never a semantic equivalence claim.
                repeated = (re.sub(r"\s+", "", source_work(duty, analysis)["text"]).casefold() == re.sub(r"\s+", "", source_work(anchor, source)["text"]).casefold()
                            and judgment["left"]["scope"] == judgment["right"]["scope"] == "affirmed"
                            and judgment["left"]["importance"] != "auxiliary"
                            and judgment["right"]["importance"] != "auxiliary"
                            and not any(judgment[side]['context_restricts_quote'] for side in ('left', 'right')))
                supported = eligible and (judgment["state"] == "supported" or repeated)
                checked = dict(**pair, comparison=judgment, eligible_local_scope=eligible,
                               importance_known=duty.get("core") is True and anchor.get("core") is True,
                               local_support=supported, evidence_nature="bounded_semantic" if judgment["state"] == "supported"
                               else "exact_local_text_repetition" if repeated else "unsupported")
                member_pairs[reference["analysis_sha256"]].append(checked)
                if supported:
                    pairs.append(checked)
        members = [dict(analysis_sha256=sha, comparisons=values,
                        supported_duty_ids=sorted({p["duty_id"] for p in values
                            if p["local_support"]}))
                   for sha, values in sorted(member_pairs.items())]
        # The SAME incoming responsibility must be directly supported by EVERY current member.
        # A->B and B->C or different duties bridging members cannot create a group by transitivity.
        common = set.intersection(*(set(m["supported_duty_ids"]) for m in members)) if members else set()
        disputed = sorted(rid for rid, relation in (relations or {}).items()
                          if relation["candidate_id"] == cid and relation["state"] == "disputed")
        if disputed:
            common = set()  # keep existing evidence, but unresolved counterevidence blocks expansion
        pairs = [p for p in pairs if p["duty_id"] in common]
        checks[cid] = dict(eligible=bool(common), members=members, supported_duty_ids=sorted(common),
                           counterevidence_relation_ids=disputed,
                           reason="unresolved_counterevidence" if disputed else "direct_support_each_member" if common else "no_direct_common_work_across_members",
                           whole_group_confirmed=False)
        if lexical_pairs:
            lexical_matches.append(dict(candidate_id=cid, pairs=lexical_pairs,
                                        priority=max(p["lexical_overlap"] for p in lexical_pairs)))
        if common:
            matches.append(dict(candidate_id=cid, pairs=pairs, priority=len(common),
                                scope="local_work_only", whole_group_confirmed=False))
    matches.sort(key=lambda item: (-item["priority"], item["candidate_id"]))
    lexical_matches.sort(key=lambda item: (-item["priority"], item["candidate_id"]))
    return dict(status="hints_only" if duties else "no_usable_duties", semantic_status="bounded_machine_comparison",
                mode="direct_member_work_research", matches=matches[:limit],
                lexical_matches=lexical_matches[:limit], candidate_checks=checks,
                matched_candidate_ids=[m["candidate_id"] for m in matches[:limit]],
                truncated=len(matches) > limit, checked_candidates=len(candidates),
                candidate_baselines=baselines,
                limitation="有界动作/对象与责任语境比较仅支持局部研究；未知词义可能漏检，未独立验收整岗同组。字面旧基线仅供对照，不写成员。")

"""Literal work overlap retrieves research leads, never semantic membership."""
import re

from ..foundation.inputs import digest


def _grams(text):
    text = re.sub(r"\s+", "", text).casefold()
    return {text[i:i+2] for i in range(len(text)-1)}


def retrieve(store, analysis, candidates, limit=10, *, relations=None):
    duties = [c for c in analysis["claims"] if c["kind"] == "duty"]
    matches = []
    baselines = {}
    for cid, candidate in sorted(candidates.items()):
        pairs = []
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
            for duty in duties:
                overlap = len(_grams(duty["text"]) & _grams(anchor["text"]))
                if overlap >= 2:
                    pairs.append(dict(duty_id=duty["id"], core_reference=reference, lexical_overlap=overlap))
        if pairs:
            matches.append(dict(candidate_id=cid, pairs=pairs, priority=max(p["lexical_overlap"] for p in pairs)))
    matches.sort(key=lambda item: (-item["priority"], item["candidate_id"]))
    return dict(status="hints_only" if duties else "no_usable_duties", semantic_status="not_evaluated",
                mode="literal_work_research_only", matches=matches[:limit],
                matched_candidate_ids=[m["candidate_id"] for m in matches[:limit]],
                truncated=len(matches) > limit, checked_candidates=len(candidates),
                candidate_baselines=baselines,
                limitation="字面检索可能漏掉等价改写，也可能命中同工具异责任；不得解释为同组结论")

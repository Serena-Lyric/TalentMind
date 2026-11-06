"""Atomic batch lifecycle on a single frozen baseline, independent of P2-2."""
from copy import deepcopy
from pathlib import Path
import hashlib
import re

from ..baseline.contract import validate_analysis
from ..foundation.inputs import check_public, digest
from ..knowledge.alignment import align_analysis
from .models import Batch


def algorithm_version():
    files = sorted(Path(__file__).parent.glob("*.py"))
    return dict(id="p3-work-research", revision="1", sha256=digest(
        {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}))


def _claim(store, reference):
    value = store.source("analysis", reference["analysis_sha256"])
    claim = next((c for c in value["claims"] if c["id"] == reference["claim_id"]), None)
    if claim is None or claim["kind"] not in {"duty", "goal", "object"}:
        raise ValueError("work reference requires a duty/goal/object claim")
    return value, claim


def _relation(candidate_id, analysis, sha, work_ids, baseline, reason):
    key = digest([candidate_id, analysis["namespace"], analysis["jd_id"]])
    value = dict(id=key, candidate_id=candidate_id, namespace=analysis["namespace"], jd_id=analysis["jd_id"],
                 analysis_sha256=sha, work_ids=work_ids, state="pending_review", reason=reason,
                 baseline=baseline, source_binding="validated_p1_quotes", semantic_validation="not_run",
                 human_confirmation="not_confirmed", formal_identity=None)
    return key, value


def _grams(text):
    text = re.sub(r"\s+", "", text).casefold()
    return {text[i:i+2] for i in range(len(text)-1)}


def apply_batch(store, request, analyses, knowledge):
    check_public(request)
    command = Batch.model_validate(request)
    request_sha = digest(dict(request=request, knowledge_sha256=knowledge.sha256))
    if set(analyses) != set(command.analysis_sha256s):
        raise ValueError("analysis input set must match batch references")
    for sha, value in analyses.items():
        if digest(value) != sha:
            raise ValueError("analysis digest mismatch")
        validate_analysis(value)
    store.conn.execute("BEGIN IMMEDIATE")
    try:
        previous = store.conn.execute("SELECT revision,request_sha256 FROM batches WHERE batch_id=?", (command.batch_id,)).fetchone()
        if previous:
            if previous[1] != request_sha:
                raise ValueError("batch ID already used for different content")
            result = store.read(previous[0])
            store.conn.commit()
            return result
        baseline = store.read()
        if command.baseline.model_dump() != baseline["binding"]:
            raise ValueError("stale or foreign candidate baseline")
        state = deepcopy(baseline)
        state["revision"] += 1
        alignment_refs = {}
        for sha, value in analyses.items():
            store.put_source("analysis", value)
            alignment = align_analysis(value, knowledge).model_dump()
            alignment_refs[sha] = store.put_source("alignment", alignment)
        knowledge_ref = store.put_source("knowledge", knowledge.snapshot.model_dump())
        changed = set()
        searches = []
        # All automatic comparisons read baseline core evidence, never this batch's revisions/members.
        for sha, analysis in sorted(analyses.items()):
            duties = [c for c in analysis["claims"] if c["kind"] == "duty"]
            matches = []
            for cid, candidate in sorted(baseline["candidates"].items()):
                anchors = [_claim(store, r)[1] for r in candidate["core_work"]]
                pairs = [(c["id"], r["claim_id"]) for c in duties for r, anchor in zip(candidate["core_work"], anchors)
                         if anchor["kind"] == "duty" and len(_grams(c["text"]) & _grams(anchor["text"])) >= 2]
                if pairs:
                    matches.append((cid, sorted({p[0] for p in pairs})))
            for cid, ids in matches[:10]:
                key, rel = _relation(cid, analysis, sha, ids, baseline["binding"],
                                     "工作陈述字面交集仅作研究线索；目标、对象与完整责任关系尚未独立验证")
                if key not in state["relations"]:
                    state["relations"][key] = rel
                    changed.add(cid)
            searches.append(dict(analysis_sha256=sha, status="hints_only" if duties else "no_usable_duties",
                                 matched_candidate_ids=[c for c, _ in matches[:10]],
                                 truncated=len(matches) > 10, checked_candidates=len(baseline["candidates"])))
        for operation in command.operations:
            op = operation.model_dump()
            cid = op["candidate_id"]
            if cid in state["candidates"]:
                raise ValueError("candidate already exists")
            referenced = [_claim(store, r) for r in op["core_work"]]
            if not any(c["kind"] == "duty" for _, c in referenced):
                raise ValueError("candidate needs a concrete duty")
            state["candidates"][cid] = dict(id=cid, version=0, status="observing", maturity="candidate",
                                            description=op["description"], research_question=op["research_question"],
                                            core_work=op["core_work"], description_nature="machine_hypothesis",
                                            competing_candidate_ids=sorted(baseline["candidates"]),
                                            unresolved=["完整工作同组语义未验证", "来源独立性未验证"], members=[])
            for sha in sorted({r["analysis_sha256"] for r in op["core_work"]}):
                analysis = store.source("analysis", sha)
                ids = [r["claim_id"] for r in op["core_work"] if r["analysis_sha256"] == sha]
                key, rel = _relation(cid, analysis, sha, ids, baseline["binding"], "显式建立的机器工作组合观察假设")
                state["relations"][key] = rel
            changed.add(cid)
        for cid in sorted(changed):
            candidate = state["candidates"][cid]
            candidate["version"] += 1
            candidate["members"] = sorted(rid for rid, rel in state["relations"].items()
                                           if rel["candidate_id"] == cid and rel["state"] != "withdrawn")
        state["analysis_sha256s"] = sorted(set(state["analysis_sha256s"]) | set(analyses))
        identities, contents = set(), set()
        for rel in state["relations"].values():
            if rel["state"] == "withdrawn":
                continue
            identities.add((rel["namespace"], rel["jd_id"]))
            a = store.source("analysis", rel["analysis_sha256"])
            contents.add(digest({k: re.sub(r"\s+", "", a["input_row"].get(k, ""))
                                 for k in ("raw_text", "duties", "requirements", "experience")}))
        state["counts"] = dict(linked_jd_identities=len(identities), unique_content_groups=len(contents),
                               independent_evidence=None, vacancies=None)
        state["report"] = dict(batch_id=command.batch_id, baseline=baseline["binding"],
                               algorithm=algorithm_version(), operation_version=command.operation_version,
                               knowledge=dict(id=knowledge.snapshot.id, revision=knowledge.snapshot.revision,
                                              source_sha256=knowledge.sha256, stored_sha256=knowledge_ref),
                               alignments=alignment_refs, observations=sorted(analyses), searches=searches,
                               change_nature="candidate_research_not_market_change")
        store.append(command.batch_id, request_sha, state)
        result = store.read(state["revision"])
        store.conn.commit()
        return result
    except BaseException:
        store.conn.rollback()
        raise

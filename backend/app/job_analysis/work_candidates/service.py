"""Atomic batch lifecycle on a single frozen baseline, independent of P2-2."""
from copy import deepcopy
from pathlib import Path
import hashlib
import re

from ..baseline.contract import validate_analysis
from ..foundation.inputs import check_public, digest
from ..knowledge.alignment import align_analysis
from .models import Batch
from .retrieval import retrieve
from .evolution import evolve_candidates, evidence_changes
from .suggestions import structural_suggestions


def algorithm_version():
    root = Path(__file__).parent.parent
    files = {*root.joinpath("work_candidates").glob("*.py"), *root.joinpath("knowledge").glob("*.py"),
             root / "baseline/contract.py", root / "foundation/inputs.py", root / "foundation/store.py",
             root / "semantics/models.py", root / "understanding/storage.py"}
    dependencies = {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}
    return dict(id="p4-work-research", revision="1", sha256=digest(dependencies), dependencies=dependencies)


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
                 human_confirmation="not_confirmed", formal_identity=None,
                 analysis_selection="unreviewed_representative",
                 source_independence="unknown", pending_analysis_sha256s=[], superseded_analysis_sha256s=[], needs_reassessment=False)
    return key, value


def review_subject(relation, candidate, decision, replacement=None, counterevidence=None):
    """Bind a review artifact to exact scope and prior state, not a nearby quotation."""
    return digest(dict(relation_sha256=digest(relation), candidate_sha256=digest(candidate), decision=decision,
                       replacement=replacement, counterevidence=counterevidence or []))


def _correct(store, operation, baseline, state, analyses):
    op = operation.model_dump()
    old = baseline["relations"].get(op["relation_id"])
    if old is None or digest(old) != op["expected_sha256"]:
        raise ValueError("stale or unknown relation version")
    cid = old["candidate_id"]
    verification = op["verification"]
    semantic = "not_run"
    artifact_sha = None
    if verification is not None:
        subject = review_subject(old, baseline["candidates"][cid], op["decision"], op["replacement"], op["counterevidence"])
        if (verification["subject_sha256"] != subject or subject not in verification["quote"]
                or verification["quote"] not in verification["document"]
                or hashlib.sha256(verification["document"].encode("utf-8")).hexdigest() != verification["document_sha256"]):
            raise ValueError("review subject/document binding mismatch")
        if verification["kind"] == "synthetic_control":
            refs = baseline["candidates"][cid]["core_work"] + [dict(analysis_sha256=old["analysis_sha256"], claim_id=i)
                                                              for i in old["work_ids"]] + op["counterevidence"]
            if op["replacement"]:
                refs += [dict(analysis_sha256=op["replacement"]["analysis_sha256"], claim_id=i) for i in op["replacement"]["work_ids"]]
            if any(store.source("analysis", r["analysis_sha256"])["namespace"] != "synthetic" for r in refs):
                raise ValueError("synthetic control cannot verify real inputs")
            semantic = "synthetic_control_only"
        else:
            semantic = "external_record_unverified"
        artifact_sha = store.put_source("review", verification)
    for reference in op["counterevidence"]:
        _claim(store, reference)
    relation = state["relations"][old["id"]]
    if op["replacement"]:
        replacement = op["replacement"]
        sha = replacement["analysis_sha256"]
        if sha not in analyses:
            raise ValueError("replacement must bind a batch analysis")
        analysis = analyses[sha]
        if (analysis["namespace"], analysis["jd_id"]) != (old["namespace"], old["jd_id"]):
            raise ValueError("replacement must preserve same JD identity")
        claims = [_claim(store, dict(analysis_sha256=sha, claim_id=i))[1] for i in replacement["work_ids"]]
        if not any(c["kind"] == "duty" for c in claims):
            raise ValueError("replacement requires a concrete duty")
        relation["superseded_analysis_sha256s"] = sorted((set(relation["superseded_analysis_sha256s"]) | {old["analysis_sha256"]}) - {sha})
        relation["analysis_sha256"], relation["work_ids"] = sha, replacement["work_ids"]
        relation["pending_analysis_sha256s"] = [s for s in relation["pending_analysis_sha256s"] if s != sha]
        relation["needs_reassessment"] = bool(relation["pending_analysis_sha256s"])
    relation.update(state={"withdraw": "withdrawn", "weakens": "disputed", "rejects": "rejected_proposal",
                           "corroborates": "controlled_support" if semantic == "synthetic_control_only" else "pending_review"}[op["decision"]],
                    reason=op["reason"], semantic_validation=semantic,
                    last_correction=dict(previous_sha256=digest(old), decision=op["decision"],
                                         baseline=baseline["binding"], verification_sha256=artifact_sha,
                                         counterevidence=op["counterevidence"], replacement=op["replacement"]))
    return cid


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
        # All comparisons read the same effective old projection, never this batch's revisions/members.
        for sha, analysis in sorted(analyses.items()):
            search = retrieve(store, analysis, baseline["candidates"], relations=baseline["relations"])
            for match in search["matches"]:
                cid = match["candidate_id"]
                ids = sorted({pair["duty_id"] for pair in match["pairs"]})
                key, rel = _relation(cid, analysis, sha, ids, baseline["binding"],
                                     "工作陈述字面交集仅作研究线索；目标、对象与完整责任关系尚未独立验证")
                if key not in state["relations"]:
                    state["relations"][key] = rel
                    changed.add(cid)
            search["analysis_sha256"] = sha
            search["baseline_member_relation_sha256s"] = {rid: digest(r) for rid, r in baseline["relations"].items()
                                                          if r["candidate_id"] in search["matched_candidate_ids"]}
            search["counterevidence_relation_ids"] = sorted(rid for rid, r in baseline["relations"].items()
                                                           if r["candidate_id"] in search["matched_candidate_ids"]
                                                           and r["state"] in {"disputed", "rejected_proposal", "withdrawn"})
            searches.append(search)
        touched = set()
        for operation in command.operations:
            op = operation.model_dump()
            target = (op["op"], op.get("relation_id", op.get("candidate_id")))
            if op["op"] == "link":
                source = analyses.get(op["analysis_sha256"])
                if source is None:
                    raise ValueError("explicit link must bind a batch input")
                target += (source["namespace"], source["jd_id"])
            if target in touched:
                raise ValueError("duplicate operation target in one batch")
            touched.add(target)
            if op["op"] == "correct":
                changed.add(_correct(store, operation, baseline, state, analyses))
                continue
            cid = op["candidate_id"]
            if op["op"] in {"link", "describe"} and cid not in baseline["candidates"]:
                raise ValueError("candidate is not in frozen baseline")
            if op["op"] == "describe":
                if op["expected_version"] != baseline["candidates"][cid]["version"]:
                    raise ValueError("stale candidate version")
                state["candidates"][cid].update({k: op[k] for k in ("description", "research_question", "unresolved")})
                state["candidates"][cid]["description_revision_reason"] = op["reason"]
                changed.add(cid)
                continue
            if op["op"] == "link":
                if op["analysis_sha256"] not in analyses:
                    raise ValueError("explicit link must bind a batch input")
                source = analyses[op["analysis_sha256"]]
                claims = [_claim(store, dict(analysis_sha256=op["analysis_sha256"], claim_id=i))[1] for i in op["work_ids"]]
                if not any(c["kind"] == "duty" for c in claims):
                    raise ValueError("link needs a concrete duty")
                key, rel = _relation(cid, source, op["analysis_sha256"], op["work_ids"], baseline["binding"], op["reason"])
                if key in baseline["relations"]:
                    raise ValueError("existing relation requires version-bound correct operation")
                state["relations"][key] = rel
                changed.add(cid)
                continue
            if cid in state["candidates"]:
                raise ValueError("candidate already exists")
            referenced = [_claim(store, r) for r in op["core_work"]]
            if not any(c["kind"] == "duty" for _, c in referenced):
                raise ValueError("candidate needs a concrete duty")
            state["candidates"][cid] = dict(id=cid, version=0, status="observing", maturity="candidate",
                                            description=op["description"], research_question=op["research_question"],
                                            core_work=op["core_work"], description_nature="machine_hypothesis",
                                            checked_candidate_ids=sorted(baseline["candidates"]),
                                            competing_candidate_ids=sorted({m["candidate_id"] for a, _ in referenced
                                                                          for m in retrieve(store, a, baseline["candidates"], relations=baseline["relations"])["matches"]}),
                                            unresolved=["完整工作同组语义未验证", "来源独立性未验证"], members=[])
            for sha in sorted({r["analysis_sha256"] for r in op["core_work"]}):
                analysis = store.source("analysis", sha)
                ids = [r["claim_id"] for r in op["core_work"] if r["analysis_sha256"] == sha]
                key, rel = _relation(cid, analysis, sha, ids, baseline["binding"], "显式建立的机器工作组合观察假设")
                # Multiple seed versions are competing interpretations, not last-write-wins facts.
                state["relations"].setdefault(key, rel)
            changed.add(cid)
        state["analysis_sha256s"] = sorted(set(state["analysis_sha256s"]) | set(analyses))
        versions = {}
        for sha in state["analysis_sha256s"]:
            source = store.source("analysis", sha)
            versions.setdefault((source["namespace"], source["jd_id"]), set()).add(sha)
        # Reconcile after every operation so create/link cannot erase versions observed earlier.
        for rel in state["relations"].values():
            pending = sorted(versions[(rel["namespace"], rel["jd_id"])] - {rel["analysis_sha256"]}
                             - set(rel["superseded_analysis_sha256s"]))
            if pending != rel["pending_analysis_sha256s"] or bool(pending) != rel["needs_reassessment"]:
                rel["pending_analysis_sha256s"], rel["needs_reassessment"] = pending, bool(pending)
                changed.add(rel["candidate_id"])
        for cid in sorted(changed):
            candidate = state["candidates"][cid]
            candidate["version"] += 1
            candidate["members"] = sorted(rid for rid, rel in state["relations"].items()
                                           if rel["candidate_id"] == cid and rel["state"] not in {"withdrawn", "rejected_proposal"})
        algorithm = algorithm_version()
        evolution = evolve_candidates(store, baseline, state, knowledge, algorithm)
        state["structural_suggestions"] = structural_suggestions(state)
        identities, contents = set(), {}
        for rel in state["relations"].values():
            if rel["state"] in {"withdrawn", "rejected_proposal"}:
                continue
            identities.add((rel["namespace"], rel["jd_id"]))
            a = store.source("analysis", rel["analysis_sha256"])
            content_sha = digest({k: re.sub(r"\s+", "", a["input_row"].get(k, ""))
                                  for k in ("raw_text", "duties", "requirements", "experience")})
            contents.setdefault(content_sha, set()).add((a["namespace"], a["jd_id"]))
        state["content_groups"] = [dict(content_sha256=sha, jd_identities=[dict(namespace=n, jd_id=j) for n, j in sorted(ids)],
                                        source_independence="unknown") for sha, ids in sorted(contents.items())]
        state["counts"] = dict(linked_jd_identities=len(identities), unique_content_groups=len(contents),
                               independent_evidence=None, vacancies=None)
        reassessment = []
        if baseline["report"] and baseline["report"]["knowledge"]["source_sha256"] != knowledge.sha256:
            reassessment.append("knowledge_changed")
        seen_identities = {(a["namespace"], a["jd_id"]) for sha in baseline["analysis_sha256s"]
                           for a in [store.source("analysis", sha)]}
        observation_nature = {sha: ("duplicate_analysis" if sha in baseline["analysis_sha256s"] else
                                    "new_analysis_same_identity" if (a["namespace"], a["jd_id"]) in seen_identities else
                                    "new_jd_identity") for sha, a in analyses.items()}
        state["report"] = dict(batch_id=command.batch_id, baseline=baseline["binding"],
                               algorithm=algorithm, operation_version=command.operation_version, evolution=evolution,
                               knowledge=dict(id=knowledge.snapshot.id, revision=knowledge.snapshot.revision,
                                              source_sha256=knowledge.sha256, stored_sha256=knowledge_ref),
                               alignments=alignment_refs, observations=sorted(analyses), searches=searches,
                               observation_nature=observation_nature,
                               evidence_changes=evidence_changes(store, baseline, analyses),
                               inputs={sha: {k: a[k] for k in ("namespace", "jd_id", "input_sha256", "input_version", "analyzer",
                                                                "model", "prompt", "configuration", "outcome", "coverage", "semantic_review")}
                                       for sha, a in sorted(analyses.items())}, reassessment_reasons=reassessment,
                               change_nature="candidate_research_not_market_change")
        store.append(command.batch_id, request_sha, state)
        result = store.read(state["revision"])
        store.conn.commit()
        return result
    except BaseException:
        store.conn.rollback()
        raise

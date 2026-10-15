"""Rebuild an offline evidence inventory from frozen members, never recruitment rates."""
from collections import Counter

from .inputs import canonical, digest, parse_json
from .store import now


def business_result(members):
    statuses = Counter(m["status"] for m in members)
    facts = [fact for m in members for fact in m["facts"]]
    validation = Counter(f["evidence_status"] for f in facts)
    return {
        "scope": "offline_evidence_audit", "jd_records": len(members),
        "completed_records": statuses["completed"], "partial_records": statuses["partial"],
        "failed_records": statuses["failed"],
        "unfinished_records": sum(n for key, n in statuses.items() if key not in ("completed", "partial", "failed")),
        "completed_zero_skill_records": sum(m["status"] == "completed" and not any(
            f.get("kind") == "skill" for f in m["facts"]) for m in members),
        "matched_facts": validation["matched"], "unvalidated_facts": len(facts) - validation["matched"],
        "candidate_facts": sum(f["governance"] == "candidate" for f in facts),
        "evidence_status_counts": dict(sorted(validation.items())),
        "formal_statistics_eligible": False,
        "formal_statistics_reasons": ["independent_positions_unresolved", "requirement_semantics_unreviewed"],
    }


def build(store, run_id, aggregate_revision):
    run = store.run(run_id)
    members = []
    for row in store.conn.execute("""SELECT s.*,t.attempt_id FROM tasks t JOIN snapshots s ON s.id=t.snapshot_id
                                    WHERE t.run_id=? ORDER BY s.namespace,s.jd_id""", (run_id,)):
        attempt = store.attempt(row["attempt_id"])
        state = attempt["status"] if attempt else "pending"
        membership = ("included" if state == "completed" else "excluded" if state == "failed" else "incomplete")
        members.append({"namespace": row["namespace"], "jd_id": row["jd_id"], "snapshot_id": row["id"],
            "fingerprint": row["fingerprint"], "analysis_version": run["version_id"],
            "attempt_id": row["attempt_id"], "status": state, "eligibility": membership,
            "reason": "complete_evidence_audit" if state == "completed" else (attempt["error"] or "analysis_or_evidence_incomplete") if attempt else "not_analyzed",
            "facts": attempt["facts"] if attempt else []})
    version = {"revision": aggregate_revision, "rules": "offline-evidence-inventory-v1"}
    manifest = {"aggregate_version": version, "members": members}
    aggregate_id = digest(manifest)
    business = business_result(members)
    with store.conn:
        store.conn.execute("INSERT OR IGNORE INTO aggregates VALUES (?,?,?,?,?,?)",
            (aggregate_id, run_id, canonical(manifest), canonical(business), digest(business), now()))
        store.conn.execute("UPDATE runs SET aggregate_id=?,status='facts_committed' WHERE id=?", (aggregate_id, run_id))
    return replay(store, aggregate_id) | {"run_id": run_id, "input_sha256": run["input_sha256"]}


def replay(store, aggregate_id):
    row = store.conn.execute("SELECT * FROM aggregates WHERE id=?", (aggregate_id,)).fetchone()
    if row is None:
        raise ValueError("aggregate not found")
    manifest = parse_json(row["manifest"])
    for member in manifest["members"]:
        attempt = store.attempt(member["attempt_id"])
        if (attempt is None and member["facts"]) or (attempt and attempt["facts"] != member["facts"]):
            raise ValueError("aggregate fact history mismatch")
    business = business_result(manifest["members"])
    if digest(business) != row["business_sha256"] or canonical(business) != row["business"]:
        raise ValueError("aggregate result integrity mismatch")
    versions = {member["analysis_version"] for member in manifest["members"]}
    manifests = {key: parse_json(store.conn.execute("SELECT manifest FROM versions WHERE id=?", (key,)).fetchone()[0]) for key in sorted(versions)}
    return manifest | {"aggregate_id": aggregate_id, "business": business, "business_sha256": row["business_sha256"],
                       "analysis_manifests": manifests,
                       "analysis_manifest": next(iter(manifests.values())) if len(manifests) == 1 else None}

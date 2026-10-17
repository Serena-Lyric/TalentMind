"""Read-only comparison of a verified legacy snapshot and an in-memory projection.

Run this module, never rebuild_m2_graph, for offline diagnostics. No DB imports.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
from itertools import combinations
import json
from pathlib import Path

from app.integration.rebuild_m2_graph import build_graph_data


def _integrity(graph: dict) -> dict:
    ids = [node["id"] for node in graph["nodes"]]
    keys = [(edge["source"], edge["target"], edge["type"]) for edge in graph["edges"]]
    known = set(ids)
    if len(ids) != len(known) or len(keys) != len(set(keys)) or any(s not in known or t not in known for s, t, _ in keys):
        raise ValueError("Snapshot integrity failure: duplicate node/edge or dangling endpoint")
    counts = Counter(edge["type"] for edge in graph["edges"])
    return {"nodes": len(ids), "edges": len(keys), "related_to": counts["RELATED_TO"],
            "requires": counts["REQUIRES"], "applies_to": counts["APPLIES_TO"]}


def _skill_sets(graph: dict) -> dict[str, set[str]]:
    sets = {node["id"]: set() for node in graph["nodes"] if node["type"] == "job"}
    for edge in graph["edges"]:
        if edge["type"] == "REQUIRES":
            sets[edge["source"]].add(edge["target"])
    return sets


def _complete_pairs(sets: dict[str, set[str]]) -> tuple[set[tuple[str, str]], int]:
    """Independent all-pairs oracle, not the builder's inverted index."""
    pairs = set()
    candidates = 0
    for left, right in combinations(sorted(sets), 2):
        shared = sets[left] & sets[right]
        if shared:
            candidates += 1
            if len(shared) / len(sets[left] | sets[right]) >= .35:
                pairs.add((left, right))
    return pairs, candidates


def _pairs(graph: dict) -> set[tuple[str, str]]:
    return {tuple(sorted((e["source"], e["target"]))) for e in graph["edges"] if e["type"] == "RELATED_TO"}


def _pair_rows(pairs: set[tuple[str, str]]) -> list[dict]:
    return [{"source": s, "target": t} for s, t in sorted(pairs)]


def diagnose_snapshot(path: Path) -> dict:
    raw = path.read_bytes()
    snapshot = json.loads(raw)
    before = _integrity(snapshot)
    old_pairs, old_candidates = _complete_pairs(_skill_sets(snapshot))
    stored_pairs = _pairs(snapshot)
    nodes = {node["id"]: node for node in snapshot["nodes"]}
    scenarios: dict[str, list[str]] = defaultdict(list)
    for edge in snapshot["edges"]:
        if edge["type"] == "APPLIES_TO":
            scenarios[edge["source"]].append(nodes[edge["target"]]["name"])
    rows = []
    for node in snapshot["nodes"]:
        if node["type"] == "job":
            rows.append(dict(node, id=len(rows) + 1, m2_job_id=node["id"].removeprefix("job:"),
                             job_name=node.get("name", ""), job_name_zh=node.get("name_zh", ""),
                             source_jd_count=node.get("jd_count", 0), scenarios=scenarios[node["id"]]))
    graph = build_graph_data(rows, [])
    after = _integrity(graph)
    new_pairs, new_candidates = _complete_pairs(_skill_sets(graph))
    if new_pairs != _pairs(graph) or new_candidates != graph["audit"]["candidate_pair_count"]:
        raise ValueError("Candidate completeness check failed")
    if path.read_bytes() != raw:
        raise ValueError("Snapshot changed during read-only diagnosis")
    return {"snapshot_sha256": hashlib.sha256(raw).hexdigest(), "before": before, "after": after,
            "legacy_complete": {"candidate_pairs": old_candidates, "related_to": len(old_pairs),
                                "missing_from_snapshot": _pair_rows(old_pairs - stored_pairs),
                                "unexpected_in_snapshot": _pair_rows(stored_pairs - old_pairs)},
            "corrected": {"candidate_pairs": new_candidates,
                          "added_vs_snapshot": _pair_rows(new_pairs - stored_pairs),
                          "removed_vs_snapshot": _pair_rows(stored_pairs - new_pairs),
                          "added_vs_legacy_complete": _pair_rows(new_pairs - old_pairs),
                          "removed_vs_legacy_complete": _pair_rows(old_pairs - new_pairs)},
            "audit": graph["audit"],
            "limitations": ["Reconstruction uses stored job required/bonus arrays and stored industry edges only.",
                            "Lost raw skill details, overwritten industry names and original JD evidence cannot be recovered.",
                            "This is a legacy projection comparison, not M2 five-state analysis or a production migration."]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path, help="Explicit input graph.json; report goes only to stdout")
    args = parser.parse_args()
    print(json.dumps(diagnose_snapshot(args.snapshot), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

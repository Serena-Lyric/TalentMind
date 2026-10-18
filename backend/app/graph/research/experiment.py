"""Explicit file input and new-directory output. No database or network imports."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
from itertools import combinations
import importlib.metadata
import json
from pathlib import Path
import platform
from statistics import median
import sys
from time import perf_counter
import tracemalloc

from app.graph.diagnose_snapshot import diagnose_snapshot
from app.integration.rebuild_m2_graph import build_graph_data
from .algorithms import adjusted_rand, community_run, graph_metrics, local_path, pair_scores, structural_summary

ROOT = Path(__file__).resolve().parents[4]
THRESHOLDS = (.10, .20, .25, .35, .50)
RESOLUTIONS = (.5, 1., 2.)
SEEDS = (7, 19, 42)


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def read_snapshot(path: Path) -> dict:
    graph = json.loads(path.read_bytes())
    ids = [n["id"] for n in graph["nodes"]]
    if len(set(ids)) != len(ids) or any(n["type"] not in {"job", "skill", "industry"} for n in graph["nodes"]):
        raise ValueError("Invalid node identity/type")
    known = set(ids)
    keys = [(e["source"], e["target"], e["type"]) for e in graph["edges"]]
    if len(set(keys)) != len(keys) or any(a not in known or b not in known for a, b, _ in keys):
        raise ValueError("Invalid edge endpoints/duplicates")
    return graph


def project_snapshot(snapshot: dict) -> dict:
    """Same lossy reconstruction scope as #21's diagnosis, without original skill details."""
    names = {n["id"]: n["name"] for n in snapshot["nodes"] if n["type"] == "industry"}
    scenarios = defaultdict(list)
    for edge in snapshot["edges"]:
        if edge["type"] == "APPLIES_TO":
            scenarios[edge["source"]].append(names[edge["target"]])
    rows = []
    for index, node in enumerate(n for n in snapshot["nodes"] if n["type"] == "job"):
        rows.append(dict(node, id=index + 1, m2_job_id=node["id"].removeprefix("job:"),
                         job_name=node.get("name", ""), job_name_zh=node.get("name_zh", ""),
                         source_jd_count=node.get("jd_count", 0), scenarios=scenarios[node["id"]]))
    return build_graph_data(rows, [])


def skill_sets(graph: dict, exclude_conflicts: bool = False) -> dict[str, set[str]]:
    sets = {n["id"]: set() for n in graph["nodes"] if n["type"] == "job"}
    for edge in graph["edges"]:
        if edge["type"] == "REQUIRES" and not (exclude_conflicts and edge.get("status_conflict")):
            sets[edge["source"]].add(edge["target"])
    return sets


def run_experiment(snapshot_path: Path) -> dict:
    import networkx as nx
    import igraph
    import leidenalg
    start = perf_counter()
    # Memory is sampled in the parent experiment, not used to compare native vs Python algorithms.
    tracemalloc.start()
    tracked = [snapshot_path, ROOT / "backend/app/skills/skill_dict_seed.json",
               ROOT / "backend/app/integration/rebuild_m2_graph.py", ROOT / "backend/app/graph/diagnose_snapshot.py",
               ROOT / "backend/app/job_analysis/semantics/models.py",
               ROOT / "backend/app/job_analysis/canonical_catalog/release.empty.v1.json",
               ROOT / "backend/app/graph/builder.py", ROOT / "backend/app/routers/mvp.py",
               ROOT / "backend/app/integration/import_graph.py", ROOT / "frontend/src/components/GraphPanorama.vue",
               ROOT / "frontend/src/api/graph.ts", *sorted(Path(__file__).parent.glob("*.py"))]
    source_bytes = {p: p.read_bytes() for p in tracked}
    hashes = {p.relative_to(ROOT).as_posix() if p.is_relative_to(ROOT) else "external_snapshot": hashlib.sha256(raw).hexdigest()
              for p, raw in source_bytes.items()}
    normalized_hashes = {p.relative_to(ROOT).as_posix() if p.is_relative_to(ROOT) else "external_snapshot":
                         hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest() for p, raw in source_bytes.items()}
    raw = read_snapshot(snapshot_path)
    diagnostic = diagnose_snapshot(snapshot_path)
    # Keep the full source mapping reproducible through the existing diagnostic CLI;
    # avoid duplicating 11k rows in this experiment's review artifact.
    mappings = diagnostic["audit"].pop("entity_mappings")
    diagnostic["audit"]["entity_mappings_count"] = len(mappings)
    diagnostic["audit"]["entity_mappings_sha256"] = digest(mappings)
    projected = project_snapshot(raw)
    sets = skill_sets(projected)
    scores = pair_scores(sets)
    raw_scores = pair_scores(skill_sets(raw))
    conflicts_removed = pair_scores(skill_sets(projected, True))
    projection_seconds = perf_counter() - start
    pair_lookup = {(r["source"], r["target"]): r for r in scores}
    graphs, runs, partitions, community_members, stability, timings = [], [], {}, {}, [], []
    for metric in ("jaccard", "idf_jaccard"):
        for threshold in THRESHOLDS:
            edges = [dict(source=r["source"], target=r["target"], score=r[metric]) for r in scores if r[metric] >= threshold]
            graph = nx.Graph()
            graph.add_nodes_from(sorted(sets))
            graph.add_weighted_edges_from((e["source"], e["target"], e["score"]) for e in edges)
            graph_key = f"{metric}:{threshold:.2f}"
            graphs.append(dict(key=graph_key, metric=metric, threshold=threshold, **graph_metrics(graph),
                               edges_sha256=digest(edges),
                               legacy_identity_edges=sum(r[metric] >= threshold for r in raw_scores),
                               conflict_excluded_edges=sum(r[metric] >= threshold for r in conflicts_removed)))
            for method in ("louvain", "leiden"):
                for resolution in RESOLUTIONS:
                    results = []
                    for seed in SEEDS:
                        tick = perf_counter()
                        result = community_run(list(sets), edges, method, resolution, seed)
                        elapsed = perf_counter() - tick
                        repeat = community_run(list(sets), edges, method, resolution, seed)
                        if result != repeat:
                            raise ValueError("Non-deterministic same-seed partition")
                        members = result.pop("members")
                        fingerprint = digest(members)
                        partitions[fingerprint] = [digest(group) for group in members]
                        community_members.update({digest(group): group for group in members})
                        runs.append(dict(graph=graph_key, method=method, resolution=resolution, seed=seed,
                                         partition_sha256=fingerprint, same_seed_repeat_equal=True, **result))
                        timings.append(dict(graph=graph_key, method=method, resolution=resolution, seed=seed, seconds=elapsed))
                        results.append(members)
                    stability.append(dict(graph=graph_key, method=method, resolution=resolution,
                                          pairwise_seed_ari=[adjusted_rand(a, b) for a, b in combinations(results, 2)],
                                          active_node_count=sum(graph.degree(n) > 0 for n in graph),
                                          active_pairwise_seed_ari=[adjusted_rand(
                                              [v for g in a if (v := [n for n in g if graph.degree(n) > 0])],
                                              [v for g in b if (v := [n for n in g if graph.degree(n) > 0])])
                                              for a, b in combinations(results, 2)]))
    # Representative examples are selected mechanically; no human labels are invented.
    names = {n["id"]: n.get("name_zh") or n.get("name") for n in projected["nodes"]}
    high = sorted(scores, key=lambda r: (-r["idf_jaccard"], r["source"], r["target"]))[:5]
    downranked = sorted(scores, key=lambda r: (r["idf_jaccard"] - r["jaccard"], r["source"], r["target"]))[:5]
    singleton = sorted((r for r in scores if len(r["shared"]) == 1), key=lambda r: (-r["jaccard"], r["source"], r["target"]))[:3]
    def explain(row):
        left, right = row["source"], row["target"]
        refs = []
        for skill in row["shared"]:
            refs.append(dict(skill=skill, paths=local_path({"nodes": projected["nodes"], "edges": [
                e for e in projected["edges"] if e["type"] == "REQUIRES" and e["target"] == skill]}, left, right, 2)))
        # Use full-graph edge indexes, not the filtered graph's indexes, for consumer tracing.
        for ref in refs:
            for step in ref["paths"]["steps"]:
                step["projection_edge_index"] = projected["edges"].index(step["edge"])
        return dict(**row, source_label=names[left], target_label=names[right], shared_association_paths=refs)
    sample_pairs = sorted(sets)
    no_local = next(((a, b) for a, b in combinations(sample_pairs, 2) if (a, b) not in pair_lookup), None)
    path_cases = []
    for label, pair in [("high_shared", (high[0]["source"], high[0]["target"]) if high else None), ("no_shared_skill", no_local)]:
        if pair:
            path_cases.append(dict(case=label, source=pair[0], target=pair[1],
                                   within_2=local_path(projected, *pair, 2), within_4=local_path(projected, *pair, 4)))
    # Reference every reconstructed legacy occurrence back to the exact stored array offset.
    raw_jobs = {n["id"]: n for n in raw["nodes"] if n["type"] == "job"}
    checked = 0
    for edge in projected["edges"]:
        if edge["type"] == "REQUIRES":
            for name, field, index in zip(edge["source_names"], edge["source_fields"], edge["source_indices"]):
                if raw_jobs[edge["source"]][field][index] != name:
                    raise ValueError("Legacy occurrence source index mismatch")
                checked += 1
    identity_cases = diagnostic["audit"]["legacy_id_collisions"]
    counts = lambda graph: dict(nodes=dict(Counter(n["type"] for n in graph["nodes"])),
                                edges=dict(Counter(e["type"] for e in graph["edges"])))
    source_counts = Counter(platform for node in raw_jobs.values() for platform in node.get("source", []))
    deterministic = dict(schema_version="m3-p2-0-research-1", source_hashes=hashes, normalized_lf_source_hashes=normalized_hashes,
        software={p: importlib.metadata.version(p) for p in ("networkx", "igraph", "leidenalg", "texttable")},
        parameters=dict(thresholds=THRESHOLDS, resolutions=RESOLUTIONS, seeds=SEEDS,
                        idf="1+ln((N+1)/(df+1))", presence_only=True, community_objective="weighted_generalized_modularity",
                        leiden_iterations=-1, fixed_community_count=None),
        snapshot=counts(raw), projection=counts(projected), diagnostic=diagnostic,
        projection_sha256=digest(projected), pair_scores_sha256=digest(scores),
        candidate_pairs=len(scores), all_job_pairs=len(sets) * (len(sets) - 1) // 2,
        source_occurrences_verified=checked, source_platform_job_counts=dict(sorted(source_counts.items())),
        structural=structural_summary(projected), graphs=graphs, community_runs=runs,
        partitions=partitions, community_members=community_members, seed_stability=stability,
        examples=dict(high_shared=[explain(r) for r in high], idf_downranked=[explain(r) for r in downranked],
                      single_shared=[explain(r) for r in singleton], paths=path_cases, identity_collisions=identity_cases),
        formal_catalog_count=len(json.loads((ROOT / "backend/app/job_analysis/canonical_catalog/release.empty.v1.json").read_bytes())["formal_jobs"]),
        interpretation="structural legacy snapshot experiments; not verified JD semantics, career classes or learning order")
    for path in tracked:
        key = path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else "external_snapshot"
        if hashlib.sha256(path.read_bytes()).hexdigest() != hashes[key]:
            raise ValueError("Source changed during experiment")
    peak = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()
    # Preserve original byte hashes, but offer an additional comparison across Git
    # text checkouts. This does not equate different software/native builds.
    portable = json.loads(json.dumps(deterministic))
    portable["source_hashes"] = normalized_hashes
    snapshot_key = snapshot_path.relative_to(ROOT).as_posix() if snapshot_path.is_relative_to(ROOT) else "external_snapshot"
    portable["diagnostic"]["snapshot_sha256"] = normalized_hashes[snapshot_key]
    return dict(deterministic=deterministic, deterministic_sha256=digest(deterministic), portable_lf_sha256=digest(portable),
                runtime=dict(python=sys.version, platform=platform.platform(),
                             projection_and_pair_seconds=projection_seconds, total_seconds=perf_counter() - start,
                             python_tracemalloc_peak_bytes=peak, native_memory_included=False,
                             community_timings=timings, timing_median_seconds=median(t["seconds"] for t in timings)))


def write_artifacts(output: Path, result: dict) -> None:
    output = output.resolve()
    protected = [ROOT / folder for folder in ("exchange", "input", "output", "frontend", "backend/app", ".git")]
    if any(output == p or output.is_relative_to(p.resolve()) for p in protected):
        raise ValueError("Output is in a protected source/snapshot directory")
    output.mkdir(parents=True, exist_ok=False)
    (output / "results.json").write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="A NEW directory; existing paths are refused")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("--output must be a new directory")
    result = run_experiment(args.snapshot.resolve())
    write_artifacts(args.output, result)
    print(json.dumps({"deterministic_sha256": result["deterministic_sha256"], "runtime": result["runtime"]["total_seconds"]}))

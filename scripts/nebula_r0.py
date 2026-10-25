"""Issue #24: read-only snapshot research. Never imports application/database code."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
from itertools import combinations
import json
import math
from pathlib import Path
import platform
import time

import networkx as nx
import numpy as np

SEED = 24
ROOT = Path(__file__).resolve().parents[1]


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def topology(raw):
    nodes = sorted(raw["nodes"], key=lambda n: n["id"])
    by_id = {n["id"]: n for n in nodes}
    if len(nodes) != len(by_id):
        raise ValueError("Duplicate node IDs")
    graph = nx.Graph()
    graph.add_nodes_from(by_id)
    directed = nx.DiGraph()
    directed.add_nodes_from(by_id)
    skills = {n["id"]: set() for n in nodes if n["type"] == "job"}
    parents = defaultdict(set)
    edge_keys = set()
    for e in raw["edges"]:
        a, b, kind = e["source"], e["target"], e["type"]
        if a not in by_id or b not in by_id or a == b:
            raise ValueError(f"Invalid edge: {e}")
        key = (a, b, kind)
        if key in edge_keys:
            raise ValueError(f"Duplicate edge: {key}")
        edge_keys.add(key)
        graph.add_edge(a, b)
        directed.add_edge(a, b)
        if kind in ("REQUIRES", "APPLIES_TO"):
            if by_id[a]["type"] != "job" or by_id[b]["type"] != {"REQUIRES": "skill", "APPLIES_TO": "industry"}[kind]:
                raise ValueError(f"Unexpected bipartite endpoint: {e}")
            parents[b].add(a)
            if kind == "REQUIRES":
                skills[a].add(b)
    return nodes, by_id, graph, directed, skills, parents


def projection(skills, method="jaccard", excluded=frozenset()):
    sets = {j: s - excluded for j, s in sorted(skills.items())}
    inverted = defaultdict(list)
    for job, values in sets.items():
        for skill in sorted(values):
            inverted[skill].append(job)
    idf = {s: 1 + math.log((len(sets) + 1) / (len(js) + 1)) for s, js in inverted.items()}
    weights = {s: (idf[s] if method == "idf" else 1) for s in inverted}
    totals = {j: sum(weights[s] for s in sorted(ss)) for j, ss in sets.items()}
    overlaps = defaultdict(float)
    for s, jobs in sorted(inverted.items()):
        for pair in combinations(jobs, 2):
            overlaps[pair] += weights[s]
    result = nx.Graph()
    result.add_nodes_from(sets)
    for (a, b), overlap in sorted(overlaps.items()):
        result.add_edge(a, b, weight=overlap / (totals[a] + totals[b] - overlap))
    return result


def partition(graph, seed=SEED, resolution=1):
    if graph.number_of_edges() == 0:
        return [{n} for n in graph]
    return sorted(nx.community.louvain_communities(graph, seed=seed, resolution=resolution, weight="weight"), key=lambda c: (-len(c), min(c)))


def ari(first, second):
    a = {n: i for i, group in enumerate(first) for n in group}
    b = {n: i for i, group in enumerate(second) for n in group}
    choose = lambda n: n * (n - 1) / 2
    contingency = Counter((a[n], b[n]) for n in a)
    pair_total = choose(len(a))
    aa, bb = sum(choose(len(c)) for c in first), sum(choose(len(c)) for c in second)
    expected = aa * bb / pair_total if pair_total else 0
    maximum = (aa + bb) / 2
    return (sum(choose(n) for n in contingency.values()) - expected) / (maximum - expected) if maximum != expected else 1.0


def evaluate(graph, groups, skills):
    lookup = {n: i for i, group in enumerate(groups) for n in group}
    total = graph.size(weight="weight")
    internal = sum(d["weight"] for a, b, d in graph.edges(data=True) if lookup[a] == lookup[b])
    shared = defaultdict(set)
    for job, values in sorted(skills.items()):
        for s in values:
            shared[s].add(lookup[job])
    return {
        "communities": len(groups), "non_singleton": sum(len(c) > 1 for c in groups),
        "sizes": sorted((len(c) for c in groups), reverse=True),
        "projection_edges": graph.number_of_edges(),
        "modularity": round(nx.community.modularity(graph, groups, weight="weight"), 6) if total else 0,
        "internal_weight_fraction": round(internal / total, 6) if total else 0,
        "skills_spanning_communities": sum(len(v) > 1 for v in shared.values()),
    }


def unit(key):
    return int(hashlib.sha256(key.encode()).hexdigest()[:12], 16) / (16 ** 12 - 1)


def ordered_subgraph(graph, ids):
    # NetworkX subgraph views can enumerate a set rather than insertion order.
    # Rebuild explicitly before any seeded solver so process hash salts do not
    # assign the same random numbers to different entity identities.
    wanted = set(ids)
    result = nx.Graph()
    result.add_nodes_from(sorted(wanted))
    result.add_edges_from((a, b, dict(d)) for a, b, d in sorted(graph.edges(data=True), key=lambda e: (e[0], e[1])) if a in wanted and b in wanted)
    return result


def space(nodes, by_id, skills, parents, projected, groups):
    job_group = {n: f"C{i+1:02d}" for i, group in enumerate(groups) for n in group}
    aggregate = nx.Graph()
    aggregate.add_nodes_from(sorted(set(job_group.values())))
    for a, b, edge in projected.edges(data=True):
        x, y = job_group[a], job_group[b]
        if x != y:
            old = aggregate.get_edge_data(x, y, {}).get("weight", 0)
            aggregate.add_edge(x, y, weight=old + edge["weight"])
    main_ids = {f"C{i+1:02d}" for i, group in enumerate(groups) if len(group) > 2}
    connected_ids = [c for c in aggregate if c in main_ids and aggregate.degree[c] > 0]
    for _, _, edge in aggregate.edges(data=True):
        edge["layout_weight"] = 1 + math.log1p(edge["weight"])
    centers = nx.spring_layout(ordered_subgraph(aggregate, connected_ids), seed=SEED, weight="layout_weight", iterations=180, scale=1150, method="force") if connected_ids else {}
    # Disconnected communities get a separate deterministic shelf, so isolates cannot
    # collapse the connected skeleton through spring_layout's global rescaling.
    for index, cid in enumerate(c for c in aggregate if c not in centers):
        centers[cid] = [1850 + (index % 4) * 180, -650 + (index // 4) * 220]
    positions, communities = {}, []
    frequency = Counter(s for ss in skills.values() for s in ss)
    for i, group in enumerate(groups):
        cid = f"C{i+1:02d}"
        ordered = sorted(group)
        subgraph = ordered_subgraph(projected, ordered)
        radius = 80 + 25 * math.sqrt(len(group))
        local = nx.spring_layout(subgraph, seed=SEED, iterations=100, scale=radius, method="force")
        for job in ordered:
            positions[job] = [float(centers[cid][0] + local[job][0]), float(centers[cid][1] + local[job][1]), (unit(cid) - .5) * 550 + (unit(job) - .5) * 140]
        counts = Counter(s for j in ordered for s in skills[j])
        # Descriptive terms are observed skills; these are NOT an approved occupation taxonomy.
        terms = sorted(counts, key=lambda s: (-counts[s] / len(group) * math.log((len(skills) + 1) / (frequency[s] + 1)), s))[:5]
        communities.append({"id": cid, "jobCount": len(group), "terms": [by_id[s]["name"] for s in terms], "center": [float(centers[cid][0]), float(centers[cid][1]), (unit(cid) - .5) * 550], "radius": radius, "sampleJobIds": ordered[:5]})
    leaves = defaultdict(list)
    for n in nodes:
        if n["type"] != "job":
            leaves[tuple(sorted(parents[n["id"]]))].append(n["id"])
    for owners, values in sorted(leaves.items()):
        center = [sum(positions[j][k] for j in owners) / len(owners) for k in range(3)] if owners else [3300, 3300, 0]
        for index, node_id in enumerate(sorted(values)):
            angle = unit(node_id) * math.tau
            # Packing slots only: leaf angles/depth encode no additional knowledge relation.
            radius = (32 + 12 * math.sqrt(index + 1)) if len(owners) == 1 else 22
            positions[node_id] = [center[0] + math.cos(angle) * radius, center[1] + math.sin(angle) * radius, center[2] + (unit(node_id + ":z") - .5) * 110]
    result = []
    for n in nodes:
        nid = n["id"]
        memberships = Counter(job_group[j] for j in sorted(parents[nid]))
        cid = job_group[nid] if n["type"] == "job" else (sorted(memberships, key=lambda c: (-memberships[c], c))[0] if memberships else None)
        degree = len(parents[nid])
        result.append({"nodeId": nid, "type": n["type"], "label": n.get("name_zh") or n.get("display_name") or n["name"],
                       "communityId": cid, "communityMembership": dict(sorted(memberships.items())),
                       "xyz": [round(v, 5) for v in positions[nid]], "importance": 1 if n["type"] == "job" else round(math.log1p(degree), 5),
                       "visibleLevel": 0 if n["type"] == "job" else (1 if degree > 1 else 2),
                       "properties": n})
    return result, communities


def research(raw):
    nodes, by_id, graph, directed, skills, parents = topology(raw)
    job_count = len(skills)
    top = sorted(((s, len(js)) for s, js in parents.items() if by_id[s]["type"] == "skill"), key=lambda x: (-x[1], x[0]))
    comparisons, partitions, projected = {}, {}, {}
    for method in ("jaccard", "idf"):
        projected[method] = projection(skills, method)
        groups = partition(projected[method])
        partitions[method] = groups
        summary = evaluate(projected[method], groups, skills)
        summary["seed_ari"] = {str(s): round(ari(groups, partition(projected[method], seed=s)), 6) for s in (25, 26)}
        summary["resolution_sizes"] = {str(r): sorted((len(c) for c in partition(projected[method], resolution=r)), reverse=True) for r in (.7, 1.3)}
        removed = projection(skills, method, {s for s, _ in top[:5]})
        summary["remove_top5_ari"] = round(ari(groups, partition(removed)), 6)
        comparisons[method] = summary
    output_nodes, communities = space(nodes, by_id, skills, parents, projected["idf"], partitions["idf"])
    edges = []
    for index, edge in enumerate(sorted(raw["edges"], key=lambda e: (e["source"], e["target"], e["type"]))):
        edges.append({"edgeId": f"snapshot:{index:05d}", "source": edge["source"], "target": edge["target"], "type": edge["type"], "properties": edge})
    summary = {"nodes": len(nodes), "edges": len(edges), "node_types": dict(sorted(Counter(n["type"] for n in nodes).items())),
               "edge_types": dict(sorted(Counter(e["type"] for e in edges).items())),
               "components": sorted((len(c) for c in nx.connected_components(graph)), reverse=True),
               "strong_components": sorted((len(c) for c in nx.strongly_connected_components(directed)), reverse=True),
               "isolates": len(list(nx.isolates(graph))), "projection_isolates": len(list(nx.isolates(projected["idf"]))),
               "degree_histograms": {kind: dict(sorted(Counter(graph.degree[n["id"]] for n in nodes if n["type"] == kind).items())) for kind in ("job", "skill", "industry")},
               "degree_one": {kind: sum(graph.degree[n["id"]] == 1 for n in nodes if n["type"] == kind) for kind in ("job", "skill", "industry")},
               "shared_skills": sum(count > 1 for _, count in top), "top_skills": top[:20],
               "top5_pair_contributions": sum(math.comb(count, 2) for _, count in top[:5]),
               "all_pair_contributions": sum(math.comb(count, 2) for _, count in top),
               "comparisons": comparisons, "partition_ari_jaccard_idf": round(ari(partitions["jaccard"], partitions["idf"]), 6),
               "chosen": "idf", "communities": communities,
               "parameters": {"seed": SEED, "resolution": 1, "projection_threshold": 0, "idf": "1 + ln((N_jobs + 1)/(df + 1))", "weight": "sum(idf of intersection) / sum(idf of union)", "community_method": "Louvain; skills only, no scenario or RELATED_TO edges", "geometry": "NetworkX spring: major centers 1+ln(1+sum projected weights), scale1150; community jobs spring scale80+25sqrt(size); <=2-job communities on separate shelf (edges preserved); leaf packing and hash depth are visual only"}}
    summary["strong_component_count"] = len(summary.pop("strong_components"))
    data = {"nodes": output_nodes, "edges": edges, "communities": communities}
    return summary, data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "exchange/m3/graph.json")
    parser.add_argument("--output", type=Path, default=ROOT / "frontend/prototypes/nebula-r0/public/data.json")
    parser.add_argument("--report", type=Path, default=ROOT / "docs/review/issue-24-r0-analysis.json")
    args = parser.parse_args()
    source = args.source.resolve()
    protected = [ROOT / "exchange", ROOT / "backend"]
    for dest in (args.output.resolve(), args.report.resolve()):
        if dest == source or any(dest.is_relative_to(p) for p in protected):
            parser.error("Research outputs must not overwrite source/exchange/backend")
    started = time.perf_counter()
    original = source.read_bytes()
    summary, data = research(json.loads(original))
    metadata = {"source": source.relative_to(ROOT).as_posix(), "sourceSha256": hashlib.sha256(original).hexdigest(),
                "sourceVersion": json.loads(original).get("metadata", {}), "protocolVersion": "r0-1", "seed": SEED,
                "networkx": nx.__version__, "numpy": np.__version__, "python": platform.python_version(), "layoutSha256": digest(data)}
    data["metadata"] = metadata
    summary["metadata"] = metadata
    summary["calculation_seconds"] = round(time.perf_counter() - started, 3)
    assert source.read_bytes() == original
    assert len(data["nodes"]) == len({n["nodeId"] for n in data["nodes"]})
    assert all(math.isfinite(v) for n in data["nodes"] for v in n["xyz"])
    for dest, value in ((args.output, data), (args.report, summary)):
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    print(json.dumps({"metadata": metadata, "seconds": summary["calculation_seconds"], "sizes": {k: v["sizes"] for k, v in summary["comparisons"].items()}}, ensure_ascii=False))


if __name__ == "__main__":
    main()

"""Reproducible structural experiments; requirement semantics are never inferred."""
from collections import Counter, defaultdict, deque
from itertools import combinations
import math
from statistics import median


def pair_scores(sets: dict[str, set[str]]) -> list[dict]:
    """Complete inverted index; IDF measures this snapshot's distinctiveness only."""
    inverted = defaultdict(list)
    for job, skills in sorted(sets.items()):
        for skill in sorted(skills):
            inverted[skill].append(job)
    idf = {skill: 1 + math.log((len(sets) + 1) / (len(jobs) + 1)) for skill, jobs in inverted.items()}
    shared = defaultdict(list)
    for skill, jobs in sorted(inverted.items()):
        for pair in combinations(jobs, 2):
            shared[pair].append(skill)
    result = []
    for (left, right), common in sorted(shared.items()):
        union = sets[left] | sets[right]
        result.append(dict(source=left, target=right, shared=common,
                           jaccard=len(common) / len(union),
                           idf_jaccard=sum(idf[s] for s in common) / sum(idf[s] for s in sorted(union))))
    # Independent exhaustive oracle catches candidate truncation, not just scores.
    oracle = {(a, b) for a, b in combinations(sorted(sets), 2) if sets[a] & sets[b]}
    if oracle != set(shared):
        raise ValueError("Incomplete shared-skill candidates")
    return result


def graph_metrics(graph) -> dict:
    import networkx as nx
    components = sorted((len(c) for c in nx.connected_components(graph)), reverse=True)
    return dict(nodes=len(graph), edges=graph.number_of_edges(), isolates=nx.number_of_isolates(graph),
                components=len(components), component_sizes=components,
                largest_component=components[0] if components else 0,
                density=nx.density(graph))


def community_run(nodes: list[str], edges: list[dict], method: str, resolution: float, seed: int) -> dict:
    import networkx as nx
    graph = nx.Graph()
    graph.add_nodes_from(sorted(nodes))
    graph.add_weighted_edges_from((e["source"], e["target"], e["score"])
                                 for e in sorted(edges, key=lambda e: (e["source"], e["target"])))
    if not graph.number_of_edges():
        groups = [{n} for n in graph]
    elif method == "louvain":
        groups = nx.community.louvain_communities(graph, weight="weight", resolution=resolution, seed=seed)
    elif method == "leiden":
        import igraph as ig
        import leidenalg as la
        names = sorted(nodes)
        index = {name: i for i, name in enumerate(names)}
        ordered = sorted(graph.edges(data="weight"))
        igraph = ig.Graph(n=len(names), edges=[(index[a], index[b]) for a, b, _ in ordered], directed=False)
        partition = la.find_partition(igraph, la.RBConfigurationVertexPartition,
                                      weights=[w for _, _, w in ordered], resolution_parameter=resolution,
                                      n_iterations=-1, seed=seed)
        groups = [{names[i] for i in group} for group in partition]
    else:
        raise ValueError("Unknown community method")
    members = sorted((sorted(g) for g in groups), key=lambda g: (-len(g), g))
    total = graph.size(weight="weight")
    internal = 0.0
    conductances = []
    disconnected = 0
    for group in members:
        subgraph = graph.subgraph(group)
        disconnected += int(not nx.is_connected(subgraph))
        inside = subgraph.size(weight="weight")
        internal += inside
        volume = sum(graph.degree(n, weight="weight") for n in group)
        denominator = min(volume, 2 * total - volume)
        if denominator > 1e-12:
            conductances.append(max(0.0, volume - 2 * inside) / denominator)
    return dict(members=members, sizes=[len(g) for g in members],
                nontrivial_communities=sum(len(g) > 1 for g in members),
                disconnected_communities=disconnected,
                modularity=nx.community.modularity(graph, groups, weight="weight", resolution=resolution) if total else None,
                internal_weight_fraction=internal / total if total else None,
                median_conductance=median(conductances) if conductances else None)


def adjusted_rand(left: list[list[str]], right: list[list[str]]) -> float:
    """ARI without a scikit-learn dependency; labels and community order do not matter."""
    a = {node: i for i, group in enumerate(left) for node in group}
    b = {node: i for i, group in enumerate(right) for node in group}
    if set(a) != set(b):
        raise ValueError("Partitions cover different nodes")
    choose2 = lambda n: n * (n - 1) // 2
    total = choose2(len(a))
    if not total:
        return 1.0
    cells = Counter((a[n], b[n]) for n in a)
    observed = sum(choose2(n) for n in cells.values())
    row = sum(choose2(len(g)) for g in left)
    column = sum(choose2(len(g)) for g in right)
    expected = row * column / total
    maximum = (row + column) / 2
    return (observed - expected) / (maximum - expected) if maximum != expected else 1.0


def local_path(graph: dict, source: str, target: str, max_hops: int) -> dict | None:
    """Bounded undirected explanation using only stored association edges, not RELATED_TO."""
    known = {n["id"] for n in graph["nodes"]}
    if source not in known or target not in known:
        return None
    adjacency = defaultdict(list)
    for index, edge in enumerate(graph["edges"]):
        if edge["type"] in {"REQUIRES", "APPLIES_TO"}:
            adjacency[edge["source"]].append((edge["target"], index, False))
            adjacency[edge["target"]].append((edge["source"], index, True))
    queue = deque([(source, [source], [])])
    visited = {source}
    while queue:
        node, path, steps = queue.popleft()
        if node == target:
            return dict(node_ids=path, steps=steps, interpretation="stored_association_only")
        if len(steps) >= max_hops:
            continue
        for neighbor, index, reverse in sorted(adjacency[node]):
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, path + [neighbor], steps + [dict(
                    projection_edge_index=index, traversed_reverse=reverse, edge=graph["edges"][index])]))
    return None


def structural_summary(graph: dict) -> dict:
    """Counts to size a future layout; no coordinates or visual acceptance implied."""
    nodes = {n["id"]: n for n in graph["nodes"]}
    degrees = Counter()
    job_skills = defaultdict(set)
    for edge in graph["edges"]:
        if edge["type"] in {"REQUIRES", "APPLIES_TO"}:
            degrees[edge["source"]] += 1
            degrees[edge["target"]] += 1
        if edge["type"] == "REQUIRES":
            job_skills[edge["source"]].add(edge["target"])
    skill_degrees = {n: degrees[n] for n in nodes if nodes[n]["type"] == "skill"}
    industry_degrees = {n: degrees[n] for n in nodes if nodes[n]["type"] == "industry"}
    return dict(skill_degree_histogram={str(k): v for k, v in sorted(Counter(skill_degrees.values()).items())},
                industry_degree_histogram={str(k): v for k, v in sorted(Counter(industry_degrees.values()).items())},
                shared_skills=sum(d > 1 for d in skill_degrees.values()),
                leaf_skills=sum(d == 1 for d in skill_degrees.values()),
                isolated_skills=sum(d == 0 for d in skill_degrees.values()),
                max_job_skill_count=max(map(len, job_skills.values()), default=0),
                top_skill_hubs=[dict(id=n, jobs=d) for n, d in sorted(skill_degrees.items(), key=lambda x: (-x[1], x[0]))[:10]],
                max_one_hop_nodes=max((1 + d for n, d in degrees.items() if nodes[n]["type"] == "job"), default=0))

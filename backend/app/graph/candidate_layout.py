"""P2.1 historical-ID layout, read-only; no database, builder or GDS imports."""
import argparse
from collections import Counter, defaultdict
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path

from .research.algorithms import pair_scores, community_run

PARAMETERS = dict(threshold=.10, method='leiden', resolution=1.0, seed=42,
                  objective='weighted_generalized_modularity', iterations=-1,
                  projection='historical REQUIRES presence; original IDs; no semantic repair')


def snapshot_hash(data: bytes) -> str:
    return hashlib.sha256(data.replace(b'\r\n', b'\n')).hexdigest()


def jitter(identity: str, salt: str = '') -> float:
    return int(hashlib.sha256((identity+salt).encode()).hexdigest()[:8], 16)/0xffffffff


def build_layout(graph: dict, input_hash: str, *, partition=None, similarity=None) -> dict:
    kinds = {n['id']:n['type'] for n in graph['nodes']}
    if len(kinds) != len(graph['nodes']):
        raise ValueError('Duplicate node identity')
    sets = {n:set() for n,t in kinds.items() if t == 'job'}
    parents = defaultdict(set)
    degree = Counter()
    for edge in graph['edges']:
        a,b = edge['source'],edge['target']
        if a not in kinds or b not in kinds:
            raise ValueError('Missing endpoint')
        degree.update([a,b])
        if edge['type'] == 'REQUIRES':
            sets[a].add(b)
        if kinds[a] == 'job' and kinds[b] != 'job':
            parents[b].add(a)
    if similarity is None:
        similarity = [dict(source=e['source'],target=e['target'],score=e['jaccard'],shared=e['shared'])
                      for e in pair_scores(sets) if e['jaccard'] >= PARAMETERS['threshold']]
    if partition is None:
        partition = community_run(sorted(sets),similarity,'leiden',1.,42)['members']
    links = defaultdict(list)
    for edge in similarity:
        links[edge['source']].append((edge['target'],edge['score']))
        links[edge['target']].append((edge['source'],edge['score']))
    positions, memberships, groups = {}, {}, []
    # Community identities depend on members, not numeric labels or array order.
    ordered = sorted(partition, key=lambda g:(-len(g),sorted(g)))
    for i, group in enumerate(ordered):
        group = sorted(group)
        isolated = len(group) == 1 and not links[group[0]]
        cid = None if isolated else hashlib.sha256('\n'.join(group).encode()).hexdigest()
        r = 32 + 55 * math.sqrt((i+.5)/len(ordered))
        branch = i % 4
        angle = branch*math.pi/2 + 4.8*(r/100)**.8 + .12*math.sin(r*.09+branch)
        cx,cy = 6*r*math.cos(angle), 6*r*math.sin(angle)*.65
        spread = min(80, 14+math.sqrt(len(group))*6)
        for j,n in enumerate(group):
            t = j*2.39996323 + jitter(n)*.4
            distance = spread*math.sqrt((j+.5)/len(group))
            positions[n] = [cx+math.cos(t)*distance,cy+math.sin(t)*distance*.65]
            memberships[n] = cid
        # Weighted intra-community relaxation actually consumes similarity scores.
        for _ in range(24):
            updated = {}
            for n in group:
                neighbors = [(m,w) for m,w in links[n] if m in group]
                if not neighbors:
                    continue
                mass = sum(w for _,w in neighbors)
                updated[n] = [positions[n][axis]*.9 + .1*sum(positions[m][axis]*w for m,w in neighbors)/mass for axis in (0,1)]
            positions.update(updated)
        groups.append(dict(id=cid,members=group,isolate=isolated,semantic_label=None))
    result = []
    for node in graph['nodes']:
        n = node['id']; owners = sorted(parents[n]); related = sorted({memberships[j] for j in owners if memberships[j] is not None})
        if n not in positions:
            if owners:
                center = [sum(positions[j][axis] for j in owners)/len(owners) for axis in (0,1)]
                angle = jitter(n)*math.tau; radius = 10+22*jitter(n,'radius')
                positions[n] = [center[0]+math.cos(angle)*radius,center[1]+math.sin(angle)*radius*.65]
            else:
                angle = jitter(n)*math.tau
                positions[n] = [620*math.cos(angle),420*math.sin(angle)]
        result.append(dict(id=n,x=round(positions[n][0]*5,5),y=round(positions[n][1]*5,5),degree=degree[n],
                           adjacent_jobs=owners, community=memberships.get(n), communities=related))
    return dict(schema_version='m3-p2-1-layout-v1',snapshot_sha256_lf=input_hash,
                algorithm_source='PR32@377e9b8:research/algorithms.py',parameters=PARAMETERS,
                interpretation='candidate structural layout; historical snapshot; not formal job catalog or verified JD semantics',
                nodes=result,communities=groups,derived_edges=similarity,
                partition_sha256=hashlib.sha256(json.dumps(ordered,separators=(',',':'),ensure_ascii=False).encode()).hexdigest())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[3]
    allowed = (root/'exchange/m3/overlays').resolve()
    output = args.output.resolve()
    if not output.is_relative_to(allowed) or output.exists():
        parser.error('Output must be a NEW file under exchange/m3/overlays')
    data = args.snapshot.read_bytes()
    result = build_layout(json.loads(data),snapshot_hash(data))
    result['software'] = {p:importlib.metadata.version(p) for p in ('networkx','igraph','leidenalg')}
    result['algorithm_source_sha256_lf'] = snapshot_hash(Path(__file__).with_name('research').joinpath('algorithms.py').read_bytes())
    result['generator_sha256_lf'] = snapshot_hash(Path(__file__).read_bytes())
    result['snapshot_sha256_bytes'] = hashlib.sha256(data).hexdigest()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(dict(nodes=len(result['nodes']),derived_edges=len(result['derived_edges']),communities=len(result['communities']),sha256_lf=result['snapshot_sha256_lf'])))


if __name__ == '__main__':
    main()

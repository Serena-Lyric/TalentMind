"""Read-only candidate layout checks; never uses database or production builders."""
import json
from pathlib import Path


def test_shared_memberships_and_isolates_are_not_first_owner():
    from app.graph.candidate_layout import build_layout
    graph = dict(nodes=[dict(id=n, type=t) for n,t in [('a','job'),('b','job'),('c','job'),('s','skill'),('leaf','skill')]],
                 edges=[dict(source=a,target=b,type='REQUIRES') for a,b in [('a','s'),('b','s'),('a','leaf')]])
    result = build_layout(graph, 'test', partition=[['a','b'],['c']], similarity=[dict(source='a',target='b',score=.5,shared=['s'])])
    nodes = {n['id']:n for n in result['nodes']}
    assert nodes['s']['adjacent_jobs'] == ['a','b']
    assert nodes['s']['degree'] == 2
    assert nodes['leaf']['degree'] == 1
    assert nodes['c']['community'] is None
    assert len(result['derived_edges']) == 1


def test_shipped_artifact_binds_all_historical_identities():
    from app.graph.candidate_layout import snapshot_hash
    root = Path(__file__).resolve().parents[2]
    source = root/'exchange/m3/graph.json'
    artifact = json.loads((root/'exchange/m3/overlays/p2-1-layout.json').read_text(encoding='utf-8'))
    graph = json.loads(source.read_bytes())
    assert artifact['snapshot_sha256_lf'] == snapshot_hash(source.read_bytes())
    assert {n['id'] for n in artifact['nodes']} == {n['id'] for n in graph['nodes']}
    assert len(artifact['nodes']) == 7845
    assert artifact['parameters']['threshold'] == .10
    assert artifact['parameters']['method'] == 'leiden'

"""Read existing run-bound historical graphs; generation uses delivery_bundle."""
import hashlib
import json
from app.job_analysis.foundation.inputs import digest
from .candidate_layout import snapshot_hash

FILES = {'manifest.json', 'facts.json', 'sources.json', 'layout.json', 'derived.json'}

def binding(engine, run_id):
    report = engine.report(run_id)
    inputs = engine._inputs(run_id)
    if len(inputs) != len(report['items']) or any(row != item['input'] for row, item in zip(inputs, report['items'])):
        raise ValueError('M2 report input mismatch')
    return report, dict(run_id=run_id, report_sha256=digest(report), input_sha256=report['input_sha256'],
                        versions=report['versions'])

def read_bundle(engine, run_id, name='manifest.json'):
    if name not in FILES:
        raise ValueError('unknown graph artifact')
    _, expected = binding(engine, run_id)
    root = engine.root / 'graphs' / run_id
    if not root.exists():
        raise ValueError('M2 candidate graph not generated yet')
    manifest = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))
    if (manifest['m2_product'] != expected
            or manifest['data_version'] != digest(dict(m2=expected, projection=manifest['implementation']))):
        raise ValueError('M2 graph version binding mismatch')
    if set(manifest['artifacts']) != FILES - {'manifest.json'}:
        raise ValueError('graph artifact hash inventory mismatch')
    for file, sha in manifest['artifacts'].items():
        if file not in FILES - {'manifest.json'} or hashlib.sha256((root / file).read_bytes()).hexdigest() != sha:
            raise ValueError('graph artifact hash mismatch')
    return manifest if name == 'manifest.json' else json.loads((root / name).read_text(encoding='utf-8'))

def graph_info(engine, run_id):
    manifest = read_bundle(engine, run_id)
    sha = snapshot_hash((engine.root / 'graphs' / run_id / 'manifest.json').read_bytes())
    return dict(run_id=run_id, manifest=manifest, manifest_sha256=sha,
        url=f'/?graphDataset=real&m2Run={run_id}&m2Graph={sha}&graphSpace=node-field-v1#/graph')

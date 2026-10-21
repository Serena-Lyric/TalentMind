"""Project one immutable M2 product report; never execute M2 or write Neo4j."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

from app.job_analysis.foundation.inputs import InputRecord, digest
from app.job_analysis.product.workflow import adapted, evidence_audit
from .real_pipeline import project, derive, code_hashes, write_json
from .candidate_layout import snapshot_hash

FILES = {'manifest.json', 'facts.json', 'sources.json', 'layout.json', 'derived.json'}


def implementation():
    return dict(code_hashes(), product_projection=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())


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


def build_bundle(engine, run_id):
    report, reference = binding(engine, run_id)
    root = engine.root / 'graphs' / run_id
    if root.exists():
        return read_bundle(engine, run_id)
    sources = dict(schema_version='m3-real-sources-1', input_sha256=report['input_sha256'], records=[])
    for item in report['items']:
        row = item['input']
        stages = item['stages']
        decision = stages['b1']['result'] or {}
        overlay = stages['b22']['result'] if stages['b22']['status'] == 'saved' else None
        eligible = bool(overlay and overlay['status'] == 'overlay_saved'
                        and decision.get('validity') != 'invalid' and decision.get('scope_status') != 'out_of_scope')
        namespace = 'mysql-jd_pool:' + str(row.get('id')) + ':' + digest(adapted(row))
        payload = {k: v for k, v in adapted(row).items() if k not in {'id', 'crawled_at'}}
        fingerprint = digest(payload)
        if eligible:
            record = InputRecord.from_row(namespace, adapted(row))
            for stage in stages.values():
                if stage['status'] != 'saved':
                    continue
                member = stage['result']
                if (member['namespace'], member['jd_id'], member['fingerprint']) != (namespace, record.jd_id, record.fingerprint):
                    raise ValueError('M2 stage identity mismatch')
                native_path = engine.root / 'native-reports' / (stage['run_id'] + '.json')
                if not native_path.resolve().is_relative_to((engine.root / 'native-reports').resolve()):
                    raise ValueError('invalid native report path')
                native = json.loads(native_path.read_text(encoding='utf-8'))
                if native['members'] != [member] or native.get('version_id', native.get('screening_version')) != stage['version_id']:
                    raise ValueError('M2 native report binding mismatch')
            body = overlay['body']
            if (body['source_payload'] != payload or body['original_semantics'] != stages['b2']['result']['body']
                    or evidence_audit(body, row)['invalid']):
                raise ValueError('M2 source evidence mismatch')
        sources['records'].append(dict(namespace=namespace, jd_id=str(row.get('id')), fingerprint=fingerprint,
            payload=payload, observation=row.get('crawled_at'), screening=decision,
            eligible=eligible, governance=overlay['body'] if eligible else None,
            m2_reference={s: {k: v for k, v in stage.items() if k != 'result'} for s, stage in stages.items()},
            final_status=item['final_status'], formal_statistics_eligible=False))
    graph, sets = project(sources)
    parent = root.parent
    parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=run_id + '-', dir=parent))
    try:
        write_json(temporary / 'sources.json', sources)
        write_json(temporary / 'facts.json', graph)
        derived, layout = derive(graph, sets, snapshot_hash((temporary / 'facts.json').read_bytes()))
        write_json(temporary / 'derived.json', derived)
        write_json(temporary / 'layout.json', layout)
        eligible_count = sum(r['eligible'] for r in sources['records'])
        manifest = dict(schema_version='m3-real-bundle-1', pipeline_version='m2-product-projection-v1',
            m2_product=reference, input_sha256=report['input_sha256'], implementation=implementation(),
            data_version=digest(dict(m2=reference, projection=implementation())),
            counts=dict(input=len(sources['records']), eligible_jd=eligible_count,
                excluded_or_pending=len(sources['records']) - eligible_count,
                scope_pending=sum(r['eligible'] and r['screening'].get('scope_status') == 'needs_review' for r in sources['records']),
                fact_nodes=len(graph['nodes']), fact_edges=len(graph['edges']),
                states=dict(Counter(e['state'] for e in graph['edges']))),
            formal_statistics_eligible=False, analysis_complete=False, semantic_review='not_performed',
            interpretation='Saved M2 candidate observations including scope-pending records; never confirmed requirements or B3 occupations',
            artifacts={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in temporary.glob('*.json')})
        write_json(temporary / 'manifest.json', manifest)
        try:
            temporary.rename(root)
        except FileExistsError:
            pass
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    return read_bundle(engine, run_id)


def graph_info(engine, run_id, create=False):
    manifest = build_bundle(engine, run_id) if create else read_bundle(engine, run_id)
    sha = snapshot_hash((engine.root / 'graphs' / run_id / 'manifest.json').read_bytes())
    return dict(run_id=run_id, manifest=manifest, manifest_sha256=sha,
        url=f'/?graphDataset=real&m2Run={run_id}&m2Graph={sha}&graphSpace=node-field-v1#/graph')

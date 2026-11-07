"""Immutable new-delivery graph projection. No model calls or historical fallback.

Only persisted analyses are projected. Requirements stay grouped; research links
remain hypotheses, and withdrawn/rejected associations are never reactivated.
"""
from copy import deepcopy
from functools import lru_cache
import hashlib
import json
import re
from pathlib import Path
import threading
from urllib.parse import quote

from app.job_analysis.baseline.contract import validate_analysis
from app.job_analysis.foundation.inputs import digest
from .candidate_layout import build_layout
from .research.algorithms import pair_scores, community_run

FILES = {'manifest.json', 'facts.json', 'sources.json', 'layout.json'}
_WRITE_LOCK = threading.RLock()

def _text(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n'

def _sha(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()

def _run(service, run_id):
    if not isinstance(run_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', run_id):
        raise ValueError('invalid delivery graph run identity')
    result = service.get(run_id)
    if result.get('run_id') != run_id:
        raise ValueError('delivery graph run binding mismatch')
    return result

@lru_cache(maxsize=4)
def _bundle(result_text):
    result = json.loads(result_text)
    sources, nodes, edges, sets, by_analysis = [], {}, [], {}, {}
    for item in result['items']:
        analysis = item.get('analysis')
        row = (analysis or {}).get('input_row') or item.get('row') or item.get('input') or {}
        record = dict(namespace=item['namespace'], jd_id=str(item['jd_id']), payload=deepcopy(row),
                      fingerprint=(analysis or {}).get('input_sha256', ''), observation=item.get('observation'),
                      identity_status=row.get('identity_status') or 'unknown', content_eligible=row.get('content_eligible'),
                      eligible=analysis is not None, analysis=analysis, governance=analysis,
                      screening=dict(execution_status=item['status'], reason_codes=[item.get('reason')] if item.get('reason') else []),
                      analysis_sha256=item.get('analysis_sha256'), formal_statistics_eligible=False)
        index = len(sources)
        sources.append(record)
        if analysis is None:
            continue
        validate_analysis(analysis)
        if digest(analysis) != item.get('analysis_sha256') or (analysis['namespace'], analysis['jd_id']) != (record['namespace'], record['jd_id']):
            raise ValueError('delivery graph analysis identity mismatch')
        jid = 'jd:' + quote(record['namespace'], safe='') + ':' + quote(record['jd_id'], safe='')
        by_analysis[item['analysis_sha256']] = (jid, index, analysis)
        nodes[jid] = dict(id=jid, type='job', name=row.get('job_title') or record['jd_id'],
                          entity_semantics='original_jd_record_not_standard_occupation_or_vacancy',
                          source_records=[index], identity_status=record['identity_status'],
                          content_eligible=record['content_eligible'], source=[row.get('source', '')],
                          status=item['status'], formal_statistics_eligible=False)
        sets[jid] = set()
        for claim in analysis['claims']:
            requirement = claim.get('requirement')
            if requirement is None or requirement['target'] != 'capability':
                continue
            for member in requirement['members']:
                sid = 'skill:' + quote(member, safe='')
                nodes.setdefault(sid, dict(id=sid, type='skill', name=member, source_records=[]))
                if index not in nodes[sid]['source_records']:
                    nodes[sid]['source_records'].append(index)
                independent = requirement['combination'] == 'single' and not requirement['condition'] and not requirement['open_set']
                edges.append(dict(id=f'claim:{index}:{claim["id"]}:{member}', source=jid, target=sid,
                    type='HAS_SKILL_STATEMENT', member=member, statement_id=claim['id'], statement=claim,
                    requirement=requirement, state=requirement['state'], relation=requirement['combination'],
                    condition=requirement['condition'], degree=requirement['degree'], conflict=False,
                    evidence=claim['evidence'][0], source_record=index, independent_requirement=independent,
                    semantic_review='machine_unreviewed', formal_statistics_eligible=False))
                if independent and requirement['state'] in {'required', 'preferred'}:
                    sets[jid].add(sid)
    work = result.get('work') or {}
    for cid, candidate in work.get('candidates', {}).items():
        nid = 'work:' + quote(cid, safe='')
        nodes[nid] = dict(id=nid, type='job', name='研究候选 · ' + candidate['description'],
                         entity_semantics='work_research_candidate_not_formal_occupation', source_records=[],
                         candidate=deepcopy(candidate), formal_statistics_eligible=False)
        sets[nid] = set()
        for rid in candidate.get('members', []):
            relation = work.get('relations', {}).get(rid)
            if not relation or relation.get('state') in {'withdrawn', 'rejected_proposal'}:
                continue
            bound = by_analysis.get(relation['analysis_sha256'])
            if bound is None:
                continue  # A historic source is not silently rebound to the current JD.
            jid, index, analysis = bound
            nodes[nid]['source_records'].append(index)
            claims = [c for c in analysis['claims'] if c['id'] in relation.get('work_ids', [])]
            evidence = next((e for c in claims for e in c['evidence']), None)
            if evidence is None:
                raise ValueError('candidate relation source claim missing')
            edges.append(dict(id='research:'+rid, source=nid, target=jid, type='RELATED_TO',
                              source_record=index, evidence=evidence, state=relation['state'],
                              research_relation=deepcopy(relation), relation='research_hypothesis',
                              semantic_review='machine_unreviewed', formal_statistics_eligible=False))
    graph = dict(schema_version='m3-delivery-facts-1', nodes=sorted(nodes.values(), key=lambda n:n['id']),
                 edges=sorted(edges, key=lambda e:e['id']))
    facts_text = _text(graph)
    similarity = [dict(source=e['source'], target=e['target'], score=e['jaccard'], shared=e['shared'])
                  for e in pair_scores(sets) if e['jaccard'] >= .10]
    partition = community_run(sorted(sets), similarity, 'leiden', 1., 42)['members'] if sets else []
    layout = build_layout(graph, _sha(facts_text), partition=partition, similarity=similarity)
    layout['interpretation'] = 'Display-only grouping of unconditional single requirements; no formal occupation classification'
    contents = {'facts.json':facts_text, 'sources.json':_text(dict(records=sources, work=work)), 'layout.json':_text(layout)}
    binding = dict(run_id=result['run_id'], request_sha256=result['request_sha256'],
                   result_sha256=_sha(result_text), knowledge_sha256=(result.get('knowledge') or {}).get('sha256'))
    manifest = dict(schema_version='m3-delivery-bundle-1', data_version=digest(binding), delivery=binding,
                    history_origin=result.get('history_origin'),
                    counts=dict(input=len(sources),eligible_jd=sum(r['eligible'] for r in sources),
                                excluded_or_pending=sum(not r['eligible'] for r in sources)),
                    artifacts={name:_sha(content) for name, content in contents.items()},
                    semantic_review='machine_unreviewed', formal_statistics_eligible=False)
    contents['manifest.json'] = _text(manifest)
    return contents

def _snapshot_path(service, run_id, snapshot):
    if not isinstance(run_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', run_id):
        raise ValueError('invalid delivery graph run identity')
    if not isinstance(snapshot, str) or not re.fullmatch(r'[a-f0-9]{64}', snapshot):
        raise ValueError('invalid delivery graph snapshot identity')
    root = Path(service.root).resolve()
    path = root / 'graphs' / run_id / snapshot
    if path.resolve() != path or not path.is_relative_to(root):
        raise ValueError('redirected graph snapshot prohibited')
    return path


def read_bundle(service, run_id, name='manifest.json', snapshot=None):
    if name not in FILES:
        raise ValueError('unknown graph artifact')
    # Internal callers may explicitly create a snapshot; HTTP readers always bind
    # the supplied URL digest and never consult the current delivery head.
    if snapshot is None:
        snapshot = graph_info(service, run_id)['manifest_sha256']
    path = _snapshot_path(service, run_id, snapshot)
    def read(file):
        target = path / file
        if target.resolve() != target or target.stat().st_nlink != 1:
            raise ValueError('redirected graph artifact prohibited')
        return target.read_text(encoding='utf-8')
    try:
        manifest_text = read('manifest.json')
        manifest = json.loads(manifest_text)
        if _sha(manifest_text) != snapshot or manifest['delivery']['run_id'] != run_id:
            raise ValueError('delivery graph snapshot binding mismatch')
        if set(manifest['artifacts']) != FILES - {'manifest.json'}:
            raise ValueError('delivery graph artifact inventory mismatch')
        for file, expected in manifest['artifacts'].items():
            if _sha(read(file)) != expected:
                raise ValueError('delivery graph artifact hash mismatch')
        return manifest_text if name == 'manifest.json' else read(name)
    except (OSError, KeyError, json.JSONDecodeError) as exc:
        raise ValueError('bound delivery graph snapshot unavailable') from exc


def graph_info(service, run_id):
    # Freeze one exact read, including partial progress. Later resume/update cannot
    # change the artifact URL or its source evidence.
    contents = _bundle(_text(_run(service, run_id)))
    sha = _sha(contents['manifest.json'])
    path = _snapshot_path(service, run_id, sha)
    with _WRITE_LOCK:
        path.mkdir(parents=True, exist_ok=True)
        for name in [*sorted(FILES - {'manifest.json'}), 'manifest.json']:
            target = path / name
            if target.resolve() != target:
                raise ValueError('redirected graph artifact prohibited')
            if target.exists():
                if target.stat().st_nlink != 1 or target.read_text(encoding='utf-8') != contents[name]:
                    raise ValueError('immutable graph snapshot content mismatch')
            else:
                with target.open('x', encoding='utf-8', newline='\n') as stream:
                    stream.write(contents[name])
    read_bundle(service, run_id, 'manifest.json', sha)
    return dict(run_id=run_id, manifest=json.loads(contents['manifest.json']), manifest_sha256=sha,
                url=f'/?graphDataset=delivery&m2DeliveryRun={quote(run_id,safe="")}&m2Graph={sha}&graphSpace=node-field-v1#/graph')

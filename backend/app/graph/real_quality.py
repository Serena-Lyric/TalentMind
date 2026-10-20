"""Offline paired diagnostics and pending review excerpts; no self-certified accuracy."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re

from ..job_analysis.foundation.inputs import digest, parse_json
from .real_pipeline import verify_bundle, write_json
from ..integration.real_jd_export import validate_destination


def load(path):
    path = Path(path)
    manifest = verify_bundle(path)
    sources = parse_json((path / 'sources.json').read_text(encoding='utf-8'))
    facts = parse_json((path / 'facts.json').read_text(encoding='utf-8'))
    return manifest, sources['records'], facts


def input_kind(record):
    p = record['payload']
    if not p.get('raw_text', '').strip():
        return 'empty_raw_text_not_recoverable'
    if not any(p.get(f) for f in ('duties', 'requirements')) and not re.search(
            r'职位描述|岗位职责|工作职责|工作内容|任职要求|职位要求', p['raw_text']):
        return 'list_or_unstructured_only_no_activity_inference'
    return 'body_present_requires_rule_or_source_review'


def summary(path):
    manifest, records, facts = load(path)
    result = dict(data_version=manifest['data_version'], input_sha256=manifest['input_sha256'],
        counts=manifest['counts'], platforms={}, semantic_reasons={}, b2_states={},
        b2_issues={}, b22_unresolved_fragments=0, b22_candidates=0)
    for platform in sorted({r['payload']['source'] for r in records}):
        rows = [r for r in records if r['payload']['source'] == platform]
        result['platforms'][platform] = dict(input=len(rows), eligible=sum(r['eligible'] for r in rows),
            fields_present={f:sum(bool(r['payload'].get(f)) for r in rows) for f in ('raw_text','duties','requirements','experience')},
            input_kinds=dict(Counter(input_kind(r) for r in rows)),
            validity=dict(Counter(r['screening']['validity'] for r in rows)),
            scope=dict(Counter(r['screening']['scope_status'] or 'not_applicable' for r in rows)),
            reasons=dict(Counter(c for r in rows for c in r['screening']['reason_codes'])))
    semantics = [r['governance']['original_semantics'] for r in records if r['governance']]
    result['b2_states'] = dict(Counter(s['state'] for d in semantics for s in d['statements']))
    result['semantic_reasons'] = dict(Counter(s['reason'] for d in semantics for s in d['statements']))
    result['b2_issues'] = dict(Counter(i['reason'] for d in semantics for i in d['issues']))
    result['b22_unresolved_fragments'] = sum(len(r['governance']['unresolved_fragments']) for r in records if r['governance'])
    result['b22_candidates'] = sum(len(r['governance']['candidates']) for r in records if r['governance'])
    result['b2_execution'] = manifest['m2_audits']['semantics']
    return result


def compare(before, after):
    first, old, old_graph = load(before)
    second, new, new_graph = load(after)
    if first['input_sha256'] != second['input_sha256'] or [(r['namespace'],r['jd_id'],r['fingerprint']) for r in old] != [
            (r['namespace'],r['jd_id'],r['fingerprint']) for r in new]:
        raise ValueError('paired comparison requires identical frozen input and namespace')
    def anchors(graph):
        return {(e['source_record'],e['evidence']['field'],e['evidence']['start'],e['evidence']['end'],e['target']): e for e in graph['edges']}
    left, right = anchors(old_graph), anchors(new_graph)
    transitions = Counter((left[k]['state'],right[k]['state']) for k in left.keys() & right.keys())
    return dict(schema_version='real-quality-comparison-1', before=summary(before), after=summary(after),
        b1_transitions=[dict(jd_id=a['jd_id'], platform=a['payload']['source'], input_kind=input_kind(a),
            before=a['screening']['scope_status'], after=b['screening']['scope_status']) for a,b in zip(old,new)],
        shared_anchor_states={a+'->'+b:n for (a,b),n in sorted(transitions.items())},
        removed_anchors=len(left.keys()-right.keys()), added_anchors=len(right.keys()-left.keys()),
        metrics=dict(status='not_evaluated_no_human_signoff', precision=None, recall=None,
            note='counts and paired state changes are diagnostics, not correctness; use governance.evaluation after real human signoff'))


def review_items(path, limit=32):
    """Minimized controlled-local excerpts; automated filtering is not certified anonymization."""
    manifest, records, facts = load(path)
    buckets = {}
    sensitive = re.compile(r'https?://|[\w.+-]+@[\w.-]+|(?<!\d)1[3-9]\d{9}(?!\d)|公司|责任者|氏名|住所|联系人')
    def add(record, ev, predicted, kind, *, context=None, target=None, scope=None, section=None):
        # Long/identifying passages stay in the controlled source viewer, not the review excerpt pack.
        context = context or ev
        scope = scope or []
        if (len(ev['quote']) > 240 or len(context['quote']) > 1800
                or any(sensitive.search(e['quote']) for e in [ev, context, *scope])):
            return
        item = dict(sample_id=digest(dict(namespace=record['namespace'],jd_id=record['jd_id'],evidence=ev,target=target)),
            source_reference=dict(namespace=record['namespace'],jd_id=record['jd_id'],fingerprint=record['fingerprint']),
            platform=record['payload']['source'], evidence=ev, context=context, target=target,
            scope_evidence=scope, rule_section=section, input_kind=input_kind(record),
            rule_prediction=predicted, kind=kind, human_state=None, disputed=None,
            review_status='pending_human_review', reviewer=None, review_note=None)
        buckets.setdefault((item['platform'],kind,predicted), []).append(item)
    for record in records:
        if not record['eligible']:
            for ev in record['screening']['evidence']:
                if ev.get('signal') == 'reviewed_content' or (ev['field'] == 'job_title' and ev.get('signal') != 'technical_title'):
                    continue
                add(record, ev, record['screening']['scope_status'], 'screening')
                break
    for edge in facts['edges']:
        record = records[edge['source_record']]
        statement = edge['statement']
        add(record, statement['evidence'], edge['state'], 'skill_statement',
            context=statement['context'], target=dict(name=edge['normalization']['canonical'], evidence=edge['evidence']),
            scope=statement['scope_evidence'], section=statement['section'])
    items, seen = [], set()
    while len(items) < limit and any(buckets.values()):
        for key in sorted(buckets, key=str):
            if not buckets[key] or len(items) == limit:
                continue
            item = buckets[key].pop(0)
            if item['sample_id'] not in seen:
                seen.add(item['sample_id'])
                items.append(item)
    return items


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before', type=Path, required=True)
    parser.add_argument('--after', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = validate_destination(args.output)
    report = compare(args.before, args.after)
    items = review_items(args.after)
    output.mkdir(parents=True)
    write_json(output / 'comparison.json', report)
    write_json(output / 'review-pending.json', dict(schema_version='real-quality-review-draft-1',
        data_version=report['after']['data_version'], label_source='unreviewed_rule_predictions_not_gold',
        privacy_status='controlled_local_minimized_draft_requires_manual_redaction_before_sharing',
        metrics_status=report['metrics']['status'], items=items))
    print(json.dumps(dict(before=report['before']['counts'], after=report['after']['counts'], review_items=len(items)), ensure_ascii=True))


if __name__ == '__main__':
    main()

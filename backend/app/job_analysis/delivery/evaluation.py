"""Bound DEV diagnostics. Span overlap is a review hint, never semantic accuracy."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from ..baseline.contract import validate_analysis
from ..baseline.approved_assertions import audit_approved_assertions
from ..foundation.inputs import canonical, digest, parse_json
from ..foundation.runner import dictionary, publish
from .store import DeliveryStore


def _overlap(left, right):
    return any(a['field'] == b['field'] and max(a['start'], b['start']) < min(a['end'], b['end'])
               for a in left for b in right)


def evaluate(analysis, annotation, case, assessment=None):
    validate_analysis(analysis)
    if analysis['input_sha256'] != annotation['input_sha256'] or analysis['input_sha256'] != case['input_sha256']:
        raise ValueError('evaluation input mismatch')
    if any(case.get(k, analysis[k]) != analysis[k] for k in ('namespace', 'jd_id', 'input_version')):
        raise ValueError('evaluation identity/version mismatch')
    labels = [u for u in annotation['human_labels'] if u['dimension'] in {'duty', 'requirement'}]
    by_id = {u['unit_id']: u for u in labels}
    if len(by_id) != len(labels): raise ValueError('duplicate reference unit')
    predictions = {c['id']: c for c in analysis['claims'] if c['kind'] in {'duty', 'requirement'}}
    decisions, conditions = {}, {}
    assertion_ids = {a['id'] for a in case['assertions']}
    if assessment is not None:
        if (assessment.get('kind') != 'agent_diagnostic' or
                assessment.get('analysis_sha256') != digest(analysis) or
                assessment.get('annotation_sha256') != digest(annotation) or
                assessment.get('case_sha256') != digest(case)):
            raise ValueError('unbound diagnostic assessment')
        for unit in assessment['units']:
            uid = unit['unit_id']
            if (uid not in by_id or uid in decisions or unit['verdict'] not in {'matched', 'partial', 'missed', 'wrong', 'unknown'}
                    or not unit.get('reason') or not set(unit['prediction_ids']) <= set(predictions)):
                raise ValueError('invalid unit diagnostic')
            if any(predictions[p]['kind'] != by_id[uid]['dimension'] for p in unit['prediction_ids']):
                raise ValueError('prediction/reference kind mismatch')
            if unit['verdict'] in {'matched', 'partial', 'wrong'} and not unit['prediction_ids']:
                raise ValueError('diagnostic requires prediction evidence')
            decisions[uid] = unit
        for condition in assessment['conditions']:
            cid = condition['id']
            if (cid not in assertion_ids or cid in conditions or condition['verdict'] not in {'pass', 'fail', 'unknown'}
                    or not condition.get('reason')):
                raise ValueError('invalid condition diagnostic')
            conditions[cid] = condition
    units, hints = {}, []
    for kind in ('duty', 'requirement'):
        counters = dict(total=0, matched=0, partial=0, missed=0, wrong=0, unknown=0)
        for label in (u for u in labels if u['dimension'] == kind):
            counters['total'] += 1
            decision = decisions.get(label['unit_id'])
            counters[decision['verdict'] if decision else 'unknown'] += 1
            candidates = [c['id'] for c in predictions.values() if c['kind'] == kind
                          and _overlap(c['evidence'], label['evidence'])]
            hints.append(dict(unit_id=label['unit_id'], dimension=kind, source_span_prediction_ids=candidates,
                              diagnostic=decision, semantic_match_not_inferred=True))
        units[kind] = counters
    condition_counts = dict(total=len(case['assertions']), **{'pass':0, 'fail':0, 'unknown':0, 'unassessed':0})
    by_class = {kind:dict(total=0, **{'pass':0, 'fail':0, 'unknown':0, 'unassessed':0}) for kind in 'ABCD'}
    for assertion in case['assertions']:
        verdict = conditions.get(assertion['id'], {}).get('verdict', 'unassessed')
        condition_counts[verdict] += 1
        group = by_class[assertion['class']]
        group['total'] += 1
        group[verdict] += 1
    assigned = {p for u in decisions.values() for p in u['prediction_ids']}
    return dict(schema_version='m2-dev-diagnostic-1', sample_id=case['sample_id'],
                analysis_sha256=digest(analysis), annotation_sha256=digest(annotation), case_sha256=digest(case),
                assessment_kind='agent_diagnostic' if assessment else 'unassessed', units=units, unit_details=hints,
                conditions=condition_counts, conditions_by_class=by_class, condition_details=list(conditions.values()),
                diagnostic_coverage=dict(assessed_units=len(decisions), unassessed_units=len(labels)-len(decisions),
                                         explicit_unknown_units=sum(u['verdict']=='unknown' for u in decisions.values())),
                unadjudicated_prediction_ids=sorted(set(predictions) - assigned),
                requirement_states=dict(Counter(c['requirement']['state'] for c in predictions.values() if c['requirement'])),
                unknown_requirement_claims=[c['id'] for c in predictions.values() if c['requirement'] and
                    (c['requirement']['state'] == 'uncertain' or c['requirement']['target'] == 'unresolved')],
                semantic_precision=None, semantic_recall=None,
                real_grouping=dict(denominator=0, accuracy=None), evolution_accuracy=None,
                limitation='DEV is development-exposed; Agent diagnostic is not independent human adjudication; source spans are hints only')


def lexical_baseline(analysis, seed):
    """Existing fixed skill lexicon, source text only; no human labels or learned state."""
    text = analysis['input_row']['raw_text']
    entries = seed['skills'] if isinstance(seed, dict) else seed
    hits = []
    for skill in entries:
        name = skill.get('name') or skill.get('canonical_name') or skill.get('canonical')
        terms = [name, *skill.get('aliases', [])]
        for term in terms:
            if not isinstance(term, str) or not term: continue
            position = text.casefold().find(term.casefold())
            if position >= 0:
                hits.append(dict(term=term, field='raw_text', start=position, end=position + len(term), state='mentioned'))
    return dict(id='existing-lexicon-mention-only-1', seed_sha256=digest(seed), hits=hits,
                duties=[], relations=[], requirement_logic='not_supported',
                limitation='Mentions do not establish requirement, negation, alternatives or degree; no role/group inference')


def main():
    parser = argparse.ArgumentParser(description='Evaluate exact saved delivery runs against approved DEV conditions, zero network')
    parser.add_argument('--state', required=True, type=Path)
    parser.add_argument('--suite', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    try:
        suite = parse_json(args.suite.read_text(encoding='utf-8-sig'))
        sample_ids = [entry['sample_id'] for entry in suite['cases']]
        if not sample_ids or len(sample_ids) != len(set(sample_ids)):
            raise ValueError('empty or repeated evaluation cases; compare reruns in separate suites')
        approval = audit_approved_assertions(Path(suite['release']), Path(suite['manifest']), Path(suite['approval']))
        release = parse_json(Path(suite['release']).read_text(encoding='utf-8-sig'))
        seed = dictionary()
        results, bindings = [], []
        with DeliveryStore(args.state, readonly=True) as store:
            for entry in suite['cases']:
                sid = entry['sample_id']
                if sid not in release['cases'] or not sid.startswith('DEV-'): raise ValueError('DEV only')
                case = parse_json((Path(suite['release']).parent / 'cases' / (sid + '.json')).read_text(encoding='utf-8-sig'))
                raw = Path(entry['annotation']).read_bytes()
                if hashlib.sha256(raw).hexdigest() != case['annotation_sha256']: raise ValueError('annotation digest mismatch')
                annotation = parse_json(raw.decode('utf-8-sig'))
                run = store.read(entry['run_id'])
                item = next(i for i in run['items'] if i['namespace'] == case['namespace'] and i['jd_id'] == case['jd_id'])
                assessment = parse_json(Path(entry['assessment']).read_text(encoding='utf-8-sig')) if entry.get('assessment') else None
                result = evaluate(item['analysis'], annotation, case, assessment)
                baseline = lexical_baseline(item['analysis'], seed)
                baseline['reference_requirement_units'] = len([u for u in annotation['human_labels'] if u['dimension'] == 'requirement'])
                baseline['reference_state_agreement_hints'] = sum(u['state'] == 'mentioned' and any(
                    _overlap([hit], u['evidence']) for hit in baseline['hits']) for u in annotation['human_labels'] if u['dimension'] == 'requirement')
                result['baseline'] = baseline
                results.append(result)
                bindings.append(dict(run_id=run['run_id'], request_sha256=run['request_sha256'], counts=run['counts'],
                                     knowledge=run['knowledge'], input_mode=item['input_mode'], reuse=item['reuse']))
        report = dict(schema_version='m2-p6-dev-evaluation-1', suite_sha256=digest(suite), approval_audit=approval,
                      cases=results, runs=bindings, total_cases=len(results), fresh_network_requests=0,
                      cost_this_evaluation=0, independent_human_grouping_denominator=0, independent_market_accuracy=None,
                      not_evaluated=['HOLD', 'P2-2 full role assignment', 'real grouping', 'real evolution direction', 'market representativeness'])
        publish(report, args.output, 'evaluation')
        print(json.dumps(dict(status='ok', cases=len(results), fresh_network_requests=0, independent_market_accuracy=None)))
        return 0
    except (ValueError, OSError, KeyError, TypeError, StopIteration):
        print(json.dumps(dict(status='rejected', reason='invalid_or_unavailable_bound_DEV_material')))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())

"""Read-only retired M2 history plus the OS lease shared by current delivery.

No legacy execution, migration, recovery write or new review mutation is exposed.
"""
from collections import Counter
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3

from ..foundation.inputs import digest
from ..foundation.store import now, safe_destination

STAGES = ('b1', 'b2', 'b22', 'b3')
TERMINAL = {'processed', 'partial', 'needs_review', 'input_invalid', 'failed'}

class Lease:
    """One worker across processes; released by OS after a crash."""
    def __init__(self, path):
        self.file = path.open('a+b')
        try:
            self.file.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.file.close()
            raise RuntimeError('another M2 worker is active') from None

    def close(self):
        self.file.close()

def adapted(row):
    # Original frozen row stays intact. Optional SQL NULL is absence, not invented prose.
    return {k: v for k, v in row.items() if not (k in {'duties', 'experience', 'requirements'} and v is None)}

def evidence_audit(value, row):
    found = set()
    invalid = 0
    def walk(node):
        nonlocal invalid
        if isinstance(node, dict):
            if {'field', 'start', 'end', 'quote'} <= node.keys():
                field, start, end, quote = (node[k] for k in ('field', 'start', 'end', 'quote'))
                text = row.get(field)
                if isinstance(text, str) and type(start) is int and type(end) is int and 0 <= start < end <= len(text) and text[start:end] == quote:
                    found.add((field, start, end, quote))
                else: invalid += 1
            for child in node.values(): walk(child)
        elif isinstance(node, list):
            for child in node: walk(child)
    walk(value)
    return dict(matched=len(found), invalid=invalid)

def _machine_sha256(item, versions):
    value = dict(item)
    value.setdefault('identity_status', 'unknown')
    value.setdefault('content_eligible', None)
    value.setdefault('identity_evidence', None)
    payload = {
        key: value.get(key)
        for key in (
            'ordinal', 'jd_id', 'source', 'title', 'input_sha256', 'warnings',
            'final_status', 'reason', 'identity_status', 'content_eligible',
            'identity_evidence', 'formal_statistics_eligible',
            'confirmed_demand_eligible', 'evidence', 'stages',
        )
    }
    payload['versions'] = versions
    return digest(payload)

def _latest_reviews(reviews):
    latest = {}
    for event in reviews:
        latest[event['ordinal']] = event
    return latest

def _effective_human_reviews(reviews):
    b1_scope = None
    b2_statements = {}
    b3_categories = {}
    conflicts = []
    annotation_event_count = 0
    legacy_review_count = 0
    for event in reviews:
        annotations = event.get('human_annotations')
        if not isinstance(annotations, dict):
            legacy_review_count += 1
            continue
        annotation_event_count += 1
        provenance = {
            'review_id': event['review_id'],
            'event_sha256': event['sha256'],
            'reviewer': event['reviewer'],
            'reviewed_at': event['reviewed_at'],
            'machine_sha256': event['machine_sha256'],
            'input_sha256': event['input_sha256'],
        }
        scope = annotations.get('b1_scope')
        if scope is not None:
            effective = dict(scope, provenance=provenance)
            if b1_scope is not None and b1_scope['scope_status'] != effective['scope_status']:
                conflicts.append({
                    'dimension': 'b1_scope',
                    'key': 'b1',
                    'previous': b1_scope,
                    'effective': effective,
                })
            b1_scope = effective
        for statement in annotations.get('b2_statements', []):
            effective = dict(statement, provenance=provenance)
            previous = b2_statements.get(statement['statement_id'])
            if previous is not None and (
                previous['human_state'] != effective['human_state']
                or previous['skill_ids'] != effective['skill_ids']
            ):
                conflicts.append({
                    'dimension': 'b2_statement',
                    'key': statement['statement_id'],
                    'previous': previous,
                    'effective': effective,
                })
            b2_statements[statement['statement_id']] = effective
        for category in annotations.get('b3_categories', []):
            effective = dict(category, provenance=provenance)
            previous = b3_categories.get(category['family_id'])
            if previous is not None and previous['human_decision'] != effective['human_decision']:
                conflicts.append({
                    'dimension': 'b3_category',
                    'key': category['family_id'],
                    'previous': previous,
                    'effective': effective,
                })
            b3_categories[category['family_id']] = effective
    return {
        'schema_version': 'm2-human-effective-1',
        'b1_scope': b1_scope,
        'b2_statements': [b2_statements[key] for key in sorted(b2_statements)],
        'b3_categories': [b3_categories[key] for key in sorted(b3_categories)],
        'conflicts': conflicts,
        'event_count': len(reviews),
        'annotation_event_count': annotation_event_count,
        'legacy_review_count': legacy_review_count,
        'has_dimension_truth': b1_scope is not None or bool(b2_statements) or bool(b3_categories),
    }

class History:
    def __init__(self, root):
        self.root = safe_destination(root)

    @contextmanager
    def db(self):
        path = self.root / 'workflow.sqlite3'
        if not path.is_file():
            raise ValueError('historical M2 store not found')
        if path.resolve() != path or path.stat().st_nlink != 1:
            raise ValueError('redirected historical M2 store prohibited')
        conn = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _row(self, run_id):
        if not isinstance(run_id, str) or not re.fullmatch(r'[a-f0-9]{32}', run_id):
            raise ValueError('invalid M2 run_id')
        with self.db() as conn:
            row = conn.execute('SELECT * FROM product_runs WHERE id=?', (run_id,)).fetchone()
        if row is None: raise ValueError('M2 run not found')
        return dict(row)

    def _inputs(self, run_id):
        row = self._row(run_id)
        data = row['input_json'].encode('utf-8')
        path = self.root / 'runs' / run_id / 'input.json'
        if hashlib.sha256(data).hexdigest() != row['input_sha256'] or path.read_bytes() != data:
            raise ValueError('frozen input integrity mismatch')
        return json.loads(row['input_json'])

    def _items(self, run_id):
        with self.db() as conn:
            return [json.loads(r[0]) for r in conn.execute('SELECT body FROM product_items WHERE run_id=? ORDER BY ordinal', (run_id,))]

    def get(self, run_id):
        row = self._row(run_id)
        items = self._items(run_id)
        reviews = self.reviews(run_id)
        latest = _latest_reviews(reviews)
        reviews_by_ordinal = {
            ordinal: [event for event in reviews if event['ordinal'] == ordinal]
            for ordinal in latest
        }
        compact = []
        for item in items:
            copy = {k: v for k, v in item.items() if k != 'stages'}
            copy.setdefault('identity_status', 'unknown')
            copy.setdefault('content_eligible', None)
            copy.setdefault('identity_evidence', None)
            copy['stages'] = {s: {k: v for k, v in stage.items() if k != 'result'} for s, stage in item['stages'].items()}
            copy['machine_sha256'] = _machine_sha256(item, json.loads(row['versions']))
            copy['human_review'] = latest.get(item['ordinal'])
            copy['human_effective'] = _effective_human_reviews(reviews_by_ordinal.get(item['ordinal'], []))
            compact.append(copy)
        return dict(execution_available=False, disposition='historical_read_only_select_inputs_for_new_delivery', run_id=run_id, status=row['status'], reason=row['reason'], created_at=row['created_at'],
            finished_at=row['finished_at'], parent_run_id=row['parent_id'], input_sha256=row['input_sha256'],
            versions=json.loads(row['versions']), selection=json.loads(row['selection']), provenance=json.loads(row['provenance']),
            items=compact, summary=summarize(items, reviews), formal_statistics_eligible=False,
            artifacts=dict(sqlite=str(self.root / 'analysis.sqlite3'), workflow=str(self.root / 'workflow.sqlite3'),
                input=str(self.root / 'runs' / run_id / 'input.json'), report=str(self.root / 'reports' / (run_id + '.json'))))

    def item(self, run_id, ordinal):
        rows = self._inputs(run_id)
        if type(ordinal) is not int or not 1 <= ordinal <= len(rows): raise ValueError('M2 item not found')
        body = self._items(run_id)[ordinal - 1]
        body.setdefault('identity_status', 'unknown')
        body.setdefault('content_eligible', None)
        body.setdefault('identity_evidence', None)
        run = self._row(run_id)
        reviews = [event for event in self.reviews(run_id) if event['ordinal'] == ordinal]
        return dict(
            body,
            input=rows[ordinal - 1],
            input_provenance=self.get(run_id)['provenance'],
            machine_sha256=_machine_sha256(body, json.loads(run['versions'])),
            human_review=reviews[-1] if reviews else None,
            human_effective=_effective_human_reviews(reviews),
            reviews=reviews,
        )

    def reviews(self, run_id):
        self._row(run_id)
        with self.db() as conn:
            rows = conn.execute(
                'SELECT id,body,sha256 FROM product_reviews WHERE run_id=? ORDER BY rowid',
                (run_id,),
            ).fetchall()
        events = []
        for row in rows:
            body = json.loads(row['body'])
            if digest(body) != row['sha256']:
                raise ValueError('human review integrity mismatch')
            events.append(dict(body, review_id=row['id'], sha256=row['sha256']))
        return events

    def review_export(self, run_id):
        row = self._row(run_id)
        items = self._items(run_id)
        inputs = self._inputs(run_id)
        reviews = self.reviews(run_id)
        latest = _latest_reviews(reviews)
        versions = json.loads(row['versions'])
        reviewed_items = []
        for item, source_row in zip(items, inputs):
            human = latest.get(item['ordinal'])
            if human is None:
                continue
            reviewed_items.append({
                'ordinal': item['ordinal'],
                'jd_id': item.get('jd_id'),
                'source': item.get('source'),
                'input_sha256': item.get('input_sha256'),
                'input': source_row,
                'machine': {
                    'sha256': _machine_sha256(item, versions),
                    'final_status': item.get('final_status'),
                    'reason': item.get('reason'),
                    'versions': versions,
                    'stages': item.get('stages'),
                },
                'human_review': human,
                'human_effective': _effective_human_reviews(
                    [event for event in reviews if event['ordinal'] == item['ordinal']]
                ),
                'review_events': [event for event in reviews if event['ordinal'] == item['ordinal']],
            })
        return {
            'schema_version': 'm2-human-review-export-1',
            'generated_at': now(),
            'run': {
                'run_id': run_id,
                'status': row['status'],
                'input_sha256': row['input_sha256'],
                'selection': json.loads(row['selection']),
                'versions': versions,
            },
            'summary': summarize(items, reviews)['review'],
            'items': reviewed_items,
            'reviews': reviews,
            'formal_statistics_eligible': False,
        }

    def list_runs(self):
        if not (self.root / 'workflow.sqlite3').exists(): return []
        with self.db() as conn:
            rows = conn.execute('SELECT id,status,created_at,finished_at,reason,parent_id,input_sha256 FROM product_runs ORDER BY rowid DESC LIMIT 100').fetchall()
        return [dict(run_id=row['id'], **{k: row[k] for k in row.keys() if k != 'id'}) for row in rows]

    def report(self, run_id):
        self._row(run_id)
        with self.db() as conn:
            saved = conn.execute('SELECT body,sha256 FROM product_reports WHERE run_id=?', (run_id,)).fetchone()
        if saved is None: raise ValueError('M2 report not published yet')
        body = json.loads(saved['body'])
        if digest(body) != saved['sha256']: raise ValueError('report integrity mismatch')
        return body

def summarize(items, reviews=None):
    total = len(items)
    finals = Counter(i['final_status'] for i in items)
    latest_reviews = _latest_reviews(reviews or [])
    review_decisions = Counter(event['decision'] for event in latest_reviews.values())
    summary = dict(input_total=total, finalized=sum(finals[s] for s in TERMINAL),
        stage_complete=sum(all(i['stages'][s]['status'] == 'saved' for s in STAGES) for i in items),
        final_counts={s: finals[s] for s in ('pending', 'stopped', 'interrupted', 'processed', 'partial', 'needs_review', 'input_invalid', 'failed')},
        b1=Counter(dict.fromkeys(('valid','invalid','undetermined','not_evaluated','in_scope','out_of_scope','needs_review','not_applicable','failed','blocked','pending','running'), 0)),
        b2=Counter(dict.fromkeys(('completed','partial','failed','blocked','pending','running','no_recognized_skills','unresolved_jds','statements_required','statements_preferred','statements_mentioned','statements_not_required','statements_uncertain'), 0)),
        b22=Counter(dict.fromkeys(('processed','failed','blocked','pending','running','candidate_jds','candidates','semantic_conflict_jds','unresolved_jds','unresolved_fragments'), 0)),
        b3=Counter(dict.fromkeys(('candidate_jds','pending_review','unable_to_classify','failed','blocked','pending','running'), 0)),
        identity=Counter(dict.fromkeys(('verified','pending','unknown'), 0)),
        content=Counter(dict.fromkeys(('eligible','ineligible','unknown'), 0)),
        review=dict(
            total_items=total,
            reviewed_items=len(latest_reviews),
            unreviewed_items=total - len(latest_reviews),
            accepted=review_decisions['accepted'],
            rejected=review_decisions['rejected'],
            needs_followup=review_decisions['needs_followup'],
        ),
        evidence=dict(outputs_with_evidence=0, outputs_without_evidence=0, matched_spans=0, invalid_spans=0, unparseable_jds=finals['input_invalid']),
        interpretation='工程处理覆盖，不是语义准确率；各阶段互相重叠的指标不可相加', formal_statistics_eligible=False)
    for item in items:
        summary['identity'][item.get('identity_status') or 'unknown'] += 1
        eligible = item.get('content_eligible')
        summary['content'][
            'eligible' if eligible is True else 'ineligible' if eligible is False else 'unknown'
        ] += 1
        b1, b2, gov, b3 = (item['stages'][s]['result'] for s in STAGES)
        if b1:
            summary['b1'][b1['validity']] += 1
            summary['b1'][b1['scope_status'] or 'not_applicable'] += 1
        for stage, key in (('b1', 'b1'), ('b2', 'b2'), ('b22', 'b22'), ('b3', 'b3')):
            status = item['stages'][stage]['status']
            if status != 'saved': summary[key][status] += 1
        if b1 and b1['execution_status'] in {'failed', 'input_failed'}: summary['b1']['failed'] += 1
        if b2:
            summary['b2'][b2['status']] += 1
            body = b2['body']
            if body:
                summary['b2']['no_recognized_skills'] += body['outcome'] == 'no_recognized_skills'
                summary['b2']['unresolved_jds'] += bool(body['issues']) or any(s['state'] == 'uncertain' for s in body['statements'])
                for s in body['statements']: summary['b2']['statements_' + s['state']] += 1
        if gov and gov['body']:
            body = gov['body']
            summary['b22']['processed'] += 1
            summary['b22']['candidate_jds'] += bool(body['candidates'])
            summary['b22']['candidates'] += len(body['candidates'])
            conflicts = any(e['conflict'] for e in body['original_semantics']['effective'])
            summary['b22']['semantic_conflict_jds'] += conflicts
            summary['b22']['unresolved_jds'] += bool(body['unresolved_fragments'] or body['review_mentions'] or body['candidates'])
            summary['b22']['unresolved_fragments'] += len(body['unresolved_fragments'])
        if b3:
            summary['b3']['candidate_jds'] += bool(b3['body']['candidates'])
            summary['b3']['pending_review'] += b3['body']['review_status'] == 'pending_review'
            summary['b3']['unable_to_classify'] += not b3['body']['candidates']
        for stage in item['stages'].values():
            if stage['result'] is not None:
                # With no source text every evidence object counts as an unmatched object here.
                objects = evidence_audit(stage['result'], {})['invalid']
                summary['evidence']['outputs_with_evidence' if objects else 'outputs_without_evidence'] += 1
        summary['evidence']['matched_spans'] += item['evidence']['matched']
        summary['evidence']['invalid_spans'] += item['evidence']['invalid']
    summary['b22']['catalog_conflict_assessment'] = 'not_evaluated'
    return summary

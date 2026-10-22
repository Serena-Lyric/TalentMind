"""Durable local tasks; native M2 stores own the analysis history, never MySQL writes."""
from collections import Counter
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import threading
from uuid import uuid4

from ..foundation.inputs import canonical, check_public, digest, read_snapshot
from ..foundation.runner import publish
from ..foundation.store import now, safe_destination
from ..role_classification.proposals.models import FAMILY_VERSIONS
from . import source

STAGES = ('b1', 'b2', 'b22', 'b3')
TERMINAL = {'processed', 'partial', 'needs_review', 'input_invalid', 'failed'}
MODULE = Path(__file__).resolve().parents[1]
APP = MODULE.parent


def versions(revision):
    if not isinstance(revision, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}', revision):
        raise ValueError('invalid version revision')
    files = sorted(p for folder in ('job_analysis', 'skills') for p in (APP / folder).rglob('*') if p.suffix in {'.py', '.json'})
    cleaner = APP / 'collect/cleaner.py'
    if cleaner.exists(): files.append(cleaner)
    return dict(revision=revision, adapter='optional-null-omission-v1',
        implementation=digest({p.relative_to(APP).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}),
        scope='software-related-offline/2026-10-15-v1', taxonomy='families.v3',
        interpretation='bounded_rules_candidates_only_not_accuracy')


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


def warnings(row):
    result = []
    for field in ('source', 'job_title', 'raw_text', 'duties', 'experience'):
        if row.get(field) in (None, ''): result.append('missing_' + field)
    if row.get('source') not in {'boss', 'liepin', 'zhaopin', 'linkedin', 'hn', 'dataset'}:
        result.append('source_unrecognized')
    result.append('historical_detail_completeness_not_verified')
    return result


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


def _human_annotations(item, value):
    if value is None:
        return None
    if not isinstance(value, dict) or not set(value) <= {'b1_scope', 'b2_statements', 'b3_categories'}:
        raise ValueError('invalid human annotation')
    scope = value.get('b1_scope')
    statements = value.get('b2_statements', [])
    categories = value.get('b3_categories', [])
    if not isinstance(statements, list) or not isinstance(categories, list):
        raise ValueError('invalid human annotation lists')
    if scope is None and not statements and not categories:
        raise ValueError('human annotation is empty')

    normalized_scope = None
    if scope is not None:
        if not isinstance(scope, dict) or not set(scope) <= {'scope_status', 'note'}:
            raise ValueError('invalid human annotation scope')
        scope_status = scope.get('scope_status')
        note = scope.get('note', '')
        if not isinstance(scope_status, str) or scope_status not in {
            'in_scope', 'out_of_scope', 'needs_review', 'not_applicable',
        }:
            raise ValueError('invalid human annotation scope status')
        if not isinstance(note, str) or len(note) > 1000:
            raise ValueError('invalid human annotation scope note')
        normalized_scope = {'scope_status': scope_status, 'note': note}

    b2 = item['stages']['b2']
    b2_body = (b2.get('result') or {}).get('body') or {}
    b22 = item['stages']['b22']
    b22_body = (b22.get('result') or {}).get('body') or {}
    skills = {skill['id']: skill for skill in b22_body.get('skills', [])}
    statements_by_id = {
        statement['id']: statement
        for statement in b2_body.get('statements', [])
    }
    normalized_statements = []
    seen = set()
    for annotation in statements:
        if not isinstance(annotation, dict) or not set(annotation) <= {
            'statement_id', 'skill_ids', 'human_state', 'note',
        }:
            raise ValueError('invalid human annotation statement')
        statement_id = annotation.get('statement_id')
        skill_ids = annotation.get('skill_ids', [])
        human_state = annotation.get('human_state')
        note = annotation.get('note', '')
        if not isinstance(statement_id, str) or statement_id not in statements_by_id:
            raise ValueError('human annotation statement is missing from machine result')
        if not isinstance(skill_ids, list) or len(skill_ids) > 20 or any(
            not isinstance(skill_id, str)
            or skill_id not in skills
            or statement_id not in skills[skill_id]['statement_ids']
            for skill_id in skill_ids
        ):
            raise ValueError('invalid human annotation skills')
        if len(skill_ids) != len(set(skill_ids)):
            raise ValueError('duplicate human annotation skill')
        if not isinstance(human_state, str) or human_state not in {
            'required', 'preferred', 'mentioned', 'not_required', 'uncertain', 'not_skill',
        }:
            raise ValueError('invalid human annotation skill state')
        if not isinstance(note, str) or len(note) > 1000:
            raise ValueError('invalid human annotation statement note')
        if statement_id in seen:
            raise ValueError('duplicate human annotation statement')
        seen.add(statement_id)
        normalized_statements.append({
            'statement_id': statement_id,
            'skill_ids': skill_ids,
            'human_state': human_state,
            'note': note,
        })

    allowed_families = set(FAMILY_VERSIONS['families-v3'])
    normalized_categories = []
    seen = set()
    for annotation in categories:
        if not isinstance(annotation, dict) or not set(annotation) <= {
            'family_id', 'human_decision', 'note',
        }:
            raise ValueError('invalid human annotation category')
        family_id = annotation.get('family_id')
        human_decision = annotation.get('human_decision')
        note = annotation.get('note', '')
        if not isinstance(family_id, str) or family_id not in allowed_families:
            raise ValueError('invalid human annotation family')
        if not isinstance(human_decision, str) or human_decision not in {
            'accepted', 'rejected', 'needs_followup',
        }:
            raise ValueError('invalid human annotation category decision')
        if not isinstance(note, str) or len(note) > 1000:
            raise ValueError('invalid human annotation category note')
        if family_id in seen:
            raise ValueError('duplicate human annotation category')
        seen.add(family_id)
        normalized_categories.append({
            'family_id': family_id,
            'human_decision': human_decision,
            'note': note,
        })

    return {
        'b1_scope': normalized_scope,
        'b2_statements': normalized_statements,
        'b3_categories': normalized_categories,
    }


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


class Workflow:
    def __init__(self, root):
        self.root = safe_destination(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._thread = None
        self._mutex = threading.Lock()
        with self.db() as conn:
            conn.executescript('''
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS product_runs (
                    id TEXT PRIMARY KEY, input_json TEXT NOT NULL, input_sha256 TEXT NOT NULL,
                    selection TEXT NOT NULL, provenance TEXT NOT NULL, versions TEXT NOT NULL,
                    parent_id TEXT, status TEXT NOT NULL, created_at TEXT NOT NULL,
                    finished_at TEXT, reason TEXT, stop INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS product_items (
                    run_id TEXT NOT NULL REFERENCES product_runs(id), ordinal INTEGER NOT NULL,
                    body TEXT NOT NULL, PRIMARY KEY(run_id,ordinal));
                CREATE TABLE IF NOT EXISTS product_reports (
                    run_id TEXT PRIMARY KEY REFERENCES product_runs(id), body TEXT NOT NULL, sha256 TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS product_reviews (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL, ordinal INTEGER NOT NULL,
                    machine_sha256 TEXT NOT NULL, body TEXT NOT NULL,
                    sha256 TEXT NOT NULL, created_at TEXT NOT NULL,
                    FOREIGN KEY(run_id,ordinal) REFERENCES product_items(run_id,ordinal));
                CREATE TRIGGER IF NOT EXISTS product_frozen BEFORE UPDATE OF
                    input_json,input_sha256,selection,provenance,versions,parent_id ON product_runs
                    BEGIN SELECT RAISE(ABORT,'immutable product input and versions'); END;
                CREATE TRIGGER IF NOT EXISTS product_no_delete BEFORE DELETE ON product_runs
                    BEGIN SELECT RAISE(ABORT,'immutable product run'); END;
                CREATE TRIGGER IF NOT EXISTS product_report_update BEFORE UPDATE ON product_reports
                    BEGIN SELECT RAISE(ABORT,'immutable product report'); END;
                CREATE TRIGGER IF NOT EXISTS product_report_delete BEFORE DELETE ON product_reports
                    BEGIN SELECT RAISE(ABORT,'immutable product report'); END;
                CREATE TRIGGER IF NOT EXISTS product_review_update BEFORE UPDATE ON product_reviews
                    BEGIN SELECT RAISE(ABORT,'immutable product review'); END;
                CREATE TRIGGER IF NOT EXISTS product_review_delete BEFORE DELETE ON product_reviews
                    BEGIN SELECT RAISE(ABORT,'immutable product review'); END;
            ''')
        try:
            lease = Lease(self.root / 'worker.lock')
        except RuntimeError:
            pass
        else:
            try:
                with self.db() as conn:
                    interrupted = [row[0] for row in conn.execute("SELECT id FROM product_runs WHERE status IN ('running','stopping','publishing')")]
                    conn.execute("UPDATE product_runs SET status='interrupted',reason='process_interrupted' WHERE status IN ('running','stopping','publishing')")
                for run_id in interrupted: self._pause_items(run_id, 'interrupted', 'process_interrupted')
            finally: lease.close()

    @contextmanager
    def db(self):
        conn = sqlite3.connect(self.root / 'workflow.sqlite3', timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys=ON')
        conn.execute('PRAGMA recursive_triggers=ON')
        try:
            with conn: yield conn
        finally: conn.close()

    @property
    def busy(self):
        return self._thread is not None and self._thread.is_alive()

    def join(self, timeout):
        if self._thread is not None: self._thread.join(timeout)

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

    def create(self, selection):
        selection = source.Selection.model_validate(selection)
        rows, provenance = source.read_mysql(selection)
        return self._freeze(rows, selection.model_dump(), provenance, 'v1')

    def _freeze(self, rows, selection, provenance, revision, parent_id=None):
        if not rows or len(rows) > 5000: raise ValueError('selection must contain 1..5000 JD rows')
        check_public(rows)
        manifest = versions(revision)
        run_id = uuid4().hex
        text = canonical(rows)
        sha = hashlib.sha256(text.encode('utf-8')).hexdigest()
        path = self.root / 'runs' / run_id
        path.mkdir(parents=True)
        (path / 'input.json').write_bytes(text.encode('utf-8'))
        with self.db() as conn:
            conn.execute('INSERT INTO product_runs VALUES (?,?,?,?,?,?,?,\'queued\',?,NULL,NULL,0)',
                (run_id, text, sha, canonical(selection), canonical(provenance), canonical(manifest), parent_id, now()))
            for ordinal, row in enumerate(rows, 1):
                identity_status = row.get('identity_status') or 'unknown'
                content_eligible = row.get('content_eligible')
                identity_evidence = row.get('identity_evidence')
                if content_eligible is not None:
                    content_eligible = bool(int(content_eligible))
                if isinstance(identity_evidence, str) and identity_evidence.strip():
                    identity_evidence = json.loads(identity_evidence)
                if not isinstance(identity_evidence, dict):
                    identity_evidence = None
                content_invalid = content_eligible is False
                body = dict(ordinal=ordinal, jd_id=row.get('id'), source=row.get('source'),
                    title=row.get('job_title'), input_sha256=digest(row), warnings=warnings(row),
                    final_status='input_invalid' if content_invalid else 'pending',
                    reason='content_ineligible' if content_invalid else None,
                    identity_status=identity_status, content_eligible=content_eligible,
                    identity_evidence=identity_evidence,
                    formal_statistics_eligible=False,
                    confirmed_demand_eligible=False, evidence=dict(matched=0, invalid=0),
                    stages={stage: dict(
                        status='blocked' if content_invalid else 'pending',
                        run_id=None, result=None,
                        reason='content_ineligible' if content_invalid else None,
                    ) for stage in STAGES})
                conn.execute('INSERT INTO product_items VALUES (?,?,?)', (run_id, ordinal, canonical(body)))
        return self.get(run_id)

    def replay(self, run_id, revision='v1'):
        row = self._row(run_id)
        return self._freeze(self._inputs(run_id), json.loads(row['selection']), json.loads(row['provenance']), revision, run_id)

    def _items(self, run_id):
        with self.db() as conn:
            return [json.loads(r[0]) for r in conn.execute('SELECT body FROM product_items WHERE run_id=? ORDER BY ordinal', (run_id,))]

    def _save_item(self, run_id, item):
        with self.db() as conn:
            conn.execute('UPDATE product_items SET body=? WHERE run_id=? AND ordinal=?', (canonical(item), run_id, item['ordinal']))

    def _pause_items(self, run_id, status, reason):
        for item in self._items(run_id):
            if item['final_status'] not in TERMINAL:
                item.update(final_status=status, reason=reason)
                for stage in item['stages'].values():
                    if stage['status'] == 'running': stage.update(status='pending', reason=reason)
                self._save_item(run_id, item)

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
        return dict(run_id=run_id, status=row['status'], reason=row['reason'], created_at=row['created_at'],
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

    def review(self, run_id, ordinal, event):
        row = self._row(run_id)
        if row['status'] not in {'completed', 'completed_with_issues'}:
            raise ValueError('run must be complete before human review')
        if type(ordinal) is not int:
            raise ValueError('M2 item not found')
        items = self._items(run_id)
        if not 1 <= ordinal <= len(items):
            raise ValueError('M2 item not found')
        if not isinstance(event, dict):
            raise ValueError('invalid human review event')
        decision = event.get('decision')
        if decision not in {'accepted', 'rejected', 'needs_followup'}:
            raise ValueError('invalid human review decision')
        reviewer = event.get('reviewer')
        if not isinstance(reviewer, str) or not reviewer.strip() or len(reviewer.strip()) > 80:
            raise ValueError('human review reviewer is required')
        note = event.get('note')
        if not isinstance(note, str) or len(note) > 4000:
            raise ValueError('invalid human review note')
        supplied_machine = event.get('machine_sha256')
        if not isinstance(supplied_machine, str) or not re.fullmatch(r'[a-f0-9]{64}', supplied_machine):
            raise ValueError('human review machine_sha256 is required')
        item = items[ordinal - 1]
        versions = json.loads(row['versions'])
        machine_sha256 = _machine_sha256(item, versions)
        if supplied_machine != machine_sha256:
            raise ValueError('human review machine result changed')
        human_annotations = _human_annotations(item, event.get('annotations'))
        reviewed_at = now()
        body = {
            'schema_version': 'm2-human-review-1',
            'run_id': run_id,
            'ordinal': ordinal,
            'jd_id': item.get('jd_id'),
            'input_sha256': item.get('input_sha256'),
            'machine_sha256': machine_sha256,
            'versions': versions,
            'machine_status': item.get('final_status'),
            'decision': decision,
            'reviewer': reviewer.strip(),
            'note': note,
            'reviewed_at': reviewed_at,
            'formal_truth_claim': False,
        }
        if human_annotations is not None:
            body['human_annotations'] = human_annotations
        event_sha256 = digest(body)
        with self.db() as conn:
            cursor = conn.execute(
                'INSERT INTO product_reviews '
                '(run_id,ordinal,machine_sha256,body,sha256,created_at) '
                'VALUES (?,?,?,?,?,?)',
                (run_id, ordinal, machine_sha256, canonical(body), event_sha256, reviewed_at),
            )
            review_id = cursor.lastrowid
        return dict(body, review_id=review_id, sha256=event_sha256)

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
        with self.db() as conn:
            rows = conn.execute('SELECT id,status,created_at,finished_at,reason,parent_id,input_sha256 FROM product_runs ORDER BY rowid DESC LIMIT 100').fetchall()
        return [dict(run_id=row['id'], **{k: row[k] for k in row.keys() if k != 'id'}) for row in rows]

    def start(self, run_id):
        with self._mutex:
            if self.busy: raise RuntimeError('another M2 worker is active')
            row = self._row(run_id)
            if row['status'] not in {'queued', 'stopped', 'interrupted', 'publication_failed'}:
                raise ValueError('run cannot start; create a versioned replay')
            if json.loads(row['versions']) != versions(json.loads(row['versions'])['revision']):
                raise ValueError('analysis version changed; create a versioned replay')
            self._inputs(run_id)
            lease = Lease(self.root / 'worker.lock')
            try:
                with self.db() as conn:
                    conn.execute("UPDATE product_runs SET status='running',reason=NULL,stop=0 WHERE id=?", (run_id,))
                self._thread = threading.Thread(target=self._work, args=(run_id, lease), daemon=True, name='m2-' + run_id)
                self._thread.start()
            except BaseException:
                lease.close()
                with self.db() as conn:
                    conn.execute("UPDATE product_runs SET status='interrupted',reason='worker_start_failed' WHERE id=?", (run_id,))
                raise
        return self.get(run_id)

    def stop(self, run_id):
        with self._mutex:
            row = self._row(run_id)
            if row['status'] not in {'running', 'stopping', 'queued'}: return self.get(run_id)
            status = 'stopping' if row['status'] in {'running', 'stopping'} else 'stopped'
            with self.db() as conn:
                conn.execute('UPDATE product_runs SET status=?,stop=1,reason=\'user_requested_stop\' WHERE id=?', (status, run_id))
            if status == 'stopped': self._pause_items(run_id, 'stopped', 'user_requested_stop')
        return self.get(run_id)

    def _work(self, run_id, lease):
        try:
            rows = self._inputs(run_id)
            revision = json.loads(self._row(run_id)['versions'])['revision']
            for row, item in zip(rows, self._items(run_id)):
                if item['final_status'] in TERMINAL: continue
                for stage in STAGES:
                    if self._row(run_id)['stop']:
                        self._pause_items(run_id, 'stopped', 'user_requested_stop')
                        with self.db() as conn:
                            conn.execute("UPDATE product_runs SET status='stopped',reason='user_requested_stop' WHERE id=?", (run_id,))
                        return
                    if item['stages'][stage]['status'] not in {'pending', 'running'}: continue
                    item['stages'][stage]['status'] = 'running'
                    self._save_item(run_id, item)
                    try:
                        native = self._execute_stage(stage, row, run_id, item, revision)
                        item['stages'][stage] = dict(status='saved', run_id=native['run_id'], version_id=native['version_id'],
                            result=native['member'], reason=None)
                    except Exception:
                        item['stages'][stage] = dict(status='failed', run_id=None, result=None, reason=stage + '_execution_failed')
                    if stage == 'b1':
                        member = item['stages']['b1']['result']
                        if member and member['execution_status'] == 'input_failed':
                            item['final_status'], item['reason'] = 'input_invalid', member['execution_error']
                    failed = item['stages'][stage]['status'] == 'failed' or (
                        item['stages'][stage]['result'] or {}).get('status') == 'failed' or (
                        stage == 'b1' and (item['stages'][stage]['result'] or {}).get('execution_status') == 'failed')
                    if failed:
                        item['final_status'], item['reason'] = 'failed', stage + '_execution_failed'
                    if item['final_status'] in {'failed', 'input_invalid'}:
                        for later in STAGES[STAGES.index(stage) + 1:]:
                            item['stages'][later].update(status='blocked', reason=item['reason'])
                    item['evidence'] = evidence_audit(item['stages'], row)
                    self._save_item(run_id, item)
                    if item['final_status'] in {'failed', 'input_invalid'}: break
                if item['final_status'] not in {'failed', 'input_invalid'}:
                    b1 = item['stages']['b1']['result']
                    b2 = item['stages']['b2']['result']['body']
                    b3 = item['stages']['b3']['result']['body']
                    review = b1['scope_status'] != 'in_scope' or b1['validity'] != 'valid' or any(
                        s['state'] == 'uncertain' for s in b2['statements']) or b3['review_status'] == 'pending_review'
                    item['final_status'] = 'needs_review' if review else 'partial' if b2['coverage'] != 'complete' else 'processed'
                    item['reason'] = 'bounded_rules_and_pending_classification' if review else 'bounded_semantic_scope'
                    self._save_item(run_id, item)
            self._publish(run_id)
        except Exception:
            self._pause_items(run_id, 'interrupted', 'workflow_execution_failed')
            with self.db() as conn:
                conn.execute("UPDATE product_runs SET status='interrupted',reason='workflow_execution_failed' WHERE id=?", (run_id,))
        finally: lease.close()

    def _execute_stage(self, stage, row, run_id, item, revision):
        from ..screening import runner as b1
        from ..screening.store import ScreeningStore
        from ..semantics import runner as b2
        from ..semantics.store import SemanticStore
        from ..governance import runner as b22
        from ..governance.store import GovernanceStore
        from ..role_classification.proposals import runner as b3
        from ..role_classification.proposals.store import ProposalStore
        # Native B1 heads retain old valid inputs even when a later same-ID input is invalid.
        # A content-bound namespace freezes exactly one identity/version for all four stages.
        namespace = 'mysql-jd_pool:' + str(row.get('id')) + ':' + digest(adapted(row))
        path = self.root / 'runs' / run_id / ('item-' + str(item['ordinal']) + '.json')
        path.write_text(canonical([adapted(row)]), encoding='utf-8')
        state = self.root / 'analysis.sqlite3'
        output = self.root / 'native-reports'
        if stage == 'b1':
            scope = json.loads((MODULE / 'screening/software-related.offline.json').read_text(encoding='utf-8'))
            with ScreeningStore(state) as store:
                report = b1.execute(store, path, namespace, scope=scope, rules_revision=revision, output=output)
            version = report['screening_version']
        elif stage == 'b2':
            batch = read_snapshot(path, namespace)
            with SemanticStore(state) as store:
                report = b2.execute(store, batch, rules_revision=revision, output=output)
            version = report['version_id']
        elif stage == 'b22':
            with GovernanceStore(state) as store:
                report = b22.execute(store, item['stages']['b2']['run_id'], revision=revision, output=output)
            version = report['version_id']
        else:
            batch = read_snapshot(path, namespace)
            taxonomy = json.loads((MODULE / 'role_classification/proposals/families.v3.json').read_text(encoding='utf-8'))
            with ProposalStore(state) as store:
                report = b3.execute(store, batch, taxonomy, revision=revision, output=output)
            version = report['version_id']
        if len(report['members']) != 1 or str(report['members'][0]['jd_id']) != str(row.get('id')):
            raise ValueError('native stage membership mismatch')
        return dict(run_id=report['run_id'], version_id=version, member=report['members'][0])

    def _publish(self, run_id):
        with self.db() as conn:
            saved = conn.execute('SELECT body,sha256 FROM product_reports WHERE run_id=?', (run_id,)).fetchone()
        if saved:
            body = json.loads(saved['body'])
            if digest(body) != saved['sha256']: raise ValueError('report integrity mismatch')
        else:
            items = self._items(run_id)
            status = 'completed' if all(i['final_status'] == 'processed' for i in items) else 'completed_with_issues'
            body = self.get(run_id)
            body.update(status=status, finished_at=now(), reason=None)
            body['items'] = [dict(item, input=row) for item, row in zip(items, self._inputs(run_id))]
            with self.db() as conn:
                conn.execute('INSERT INTO product_reports VALUES (?,?,?)', (run_id, canonical(body), digest(body)))
                conn.execute("UPDATE product_runs SET status='publishing',finished_at=?,reason=NULL WHERE id=?", (body['finished_at'], run_id))
        try:
            publish(body, self.root / 'reports', run_id)
        except (OSError, ValueError):
            with self.db() as conn:
                conn.execute("UPDATE product_runs SET status='publication_failed',reason='report_publication_failed' WHERE id=?", (run_id,))
            return
        with self.db() as conn:
            conn.execute('UPDATE product_runs SET status=?,reason=NULL WHERE id=?', (body['status'], run_id))

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

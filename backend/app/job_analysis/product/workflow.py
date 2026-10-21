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
                CREATE TRIGGER IF NOT EXISTS product_frozen BEFORE UPDATE OF
                    input_json,input_sha256,selection,provenance,versions,parent_id ON product_runs
                    BEGIN SELECT RAISE(ABORT,'immutable product input and versions'); END;
                CREATE TRIGGER IF NOT EXISTS product_no_delete BEFORE DELETE ON product_runs
                    BEGIN SELECT RAISE(ABORT,'immutable product run'); END;
                CREATE TRIGGER IF NOT EXISTS product_report_update BEFORE UPDATE ON product_reports
                    BEGIN SELECT RAISE(ABORT,'immutable product report'); END;
                CREATE TRIGGER IF NOT EXISTS product_report_delete BEFORE DELETE ON product_reports
                    BEGIN SELECT RAISE(ABORT,'immutable product report'); END;
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
                body = dict(ordinal=ordinal, jd_id=row.get('id'), source=row.get('source'),
                    title=row.get('job_title'), input_sha256=digest(row), warnings=warnings(row),
                    final_status='pending', reason=None, formal_statistics_eligible=False,
                    confirmed_demand_eligible=False, evidence=dict(matched=0, invalid=0),
                    stages={stage: dict(status='pending', run_id=None, result=None, reason=None) for stage in STAGES})
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
        compact = []
        for item in items:
            copy = {k: v for k, v in item.items() if k != 'stages'}
            copy['stages'] = {s: {k: v for k, v in stage.items() if k != 'result'} for s, stage in item['stages'].items()}
            compact.append(copy)
        return dict(run_id=run_id, status=row['status'], reason=row['reason'], created_at=row['created_at'],
            finished_at=row['finished_at'], parent_run_id=row['parent_id'], input_sha256=row['input_sha256'],
            versions=json.loads(row['versions']), selection=json.loads(row['selection']), provenance=json.loads(row['provenance']),
            items=compact, summary=summarize(items), formal_statistics_eligible=False,
            artifacts=dict(sqlite=str(self.root / 'analysis.sqlite3'), workflow=str(self.root / 'workflow.sqlite3'),
                input=str(self.root / 'runs' / run_id / 'input.json'), report=str(self.root / 'reports' / (run_id + '.json'))))

    def item(self, run_id, ordinal):
        rows = self._inputs(run_id)
        if type(ordinal) is not int or not 1 <= ordinal <= len(rows): raise ValueError('M2 item not found')
        body = self._items(run_id)[ordinal - 1]
        return dict(body, input=rows[ordinal - 1], input_provenance=self.get(run_id)['provenance'])

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


def summarize(items):
    total = len(items)
    finals = Counter(i['final_status'] for i in items)
    summary = dict(input_total=total, finalized=sum(finals[s] for s in TERMINAL),
        stage_complete=sum(all(i['stages'][s]['status'] == 'saved' for s in STAGES) for i in items),
        final_counts={s: finals[s] for s in ('pending', 'stopped', 'interrupted', 'processed', 'partial', 'needs_review', 'input_invalid', 'failed')},
        b1=Counter(dict.fromkeys(('valid','invalid','undetermined','not_evaluated','in_scope','out_of_scope','needs_review','not_applicable','failed','blocked','pending','running'), 0)),
        b2=Counter(dict.fromkeys(('completed','partial','failed','blocked','pending','running','no_recognized_skills','unresolved_jds','statements_required','statements_preferred','statements_mentioned','statements_not_required','statements_uncertain'), 0)),
        b22=Counter(dict.fromkeys(('processed','failed','blocked','pending','running','candidate_jds','candidates','semantic_conflict_jds','unresolved_jds','unresolved_fragments'), 0)),
        b3=Counter(dict.fromkeys(('candidate_jds','pending_review','unable_to_classify','failed','blocked','pending','running'), 0)),
        evidence=dict(outputs_with_evidence=0, outputs_without_evidence=0, matched_spans=0, invalid_spans=0, unparseable_jds=finals['input_invalid']),
        interpretation='工程处理覆盖，不是语义准确率；各阶段互相重叠的指标不可相加', formal_statistics_eligible=False)
    for item in items:
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

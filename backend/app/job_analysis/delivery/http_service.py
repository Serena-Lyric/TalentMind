"""Local web orchestration of the real delivery runner; selection never executes a model."""
import asyncio
from datetime import date, datetime
import os
from pathlib import Path
import threading
from uuid import uuid4

from ..foundation.inputs import digest, parse_json
from ..foundation.store import now, safe_destination
from ..knowledge.catalog import load_snapshot
from ..product import source
from ..product.workflow import adapted
from ..understanding.cloud import CloudConfig, CloudProcessor
from .runner import execute, resume, LOADED, ensure_loaded
from .store import DeliveryStore

KNOWLEDGE = Path(__file__).parents[1] / 'knowledge/catalog/role-references.v3'


def configured_processor():
    config = os.environ.get('TALENTMIND_M2_CONFIG')
    key = os.environ.get('TALENTMIND_M2_KEY_FILE')
    if not config or not key:
        raise RuntimeError('尚未配置 M2 处理器；设置 TALENTMIND_M2_CONFIG 与 TALENTMIND_M2_KEY_FILE 后显式开始')
    return CloudProcessor(CloudConfig.model_validate(parse_json(Path(config).read_text(encoding='utf-8-sig'))),
                          Path(key).read_text(encoding='utf-8-sig'))


def _query(ids=None, limit=50, offset=0):
    connection = source.connect()
    try:
        with connection.cursor() as cursor:
            cursor.execute('START TRANSACTION READ ONLY')
            if ids is not None:
                cursor.execute('SELECT * FROM jd_pool WHERE id IN (' + ','.join(['%s'] * len(ids)) + ') ORDER BY id', tuple(ids))
                rows = cursor.fetchall()
                total = len(rows)
            else:
                cursor.execute('SELECT COUNT(*) AS total FROM jd_pool')
                total = cursor.fetchone()['total']
                cursor.execute('SELECT * FROM jd_pool ORDER BY id DESC LIMIT %s OFFSET %s', (limit, offset))
                rows = cursor.fetchall()
    finally:
        connection.rollback()
        connection.close()
    return [source.normalize_identity({k: str(v) if isinstance(v, (datetime, date)) else v
                                       for k, v in row.items()}) for row in rows], total


def available_inputs(limit=50, offset=0):
    rows, total = _query(limit=limit, offset=offset)
    return dict(items=[dict(row, jd_id=row['id'], title=row.get('job_title')) for row in rows],
                total=total, limit=limit, offset=offset, counting_unit='jd_pool_rows')


class DeliveryService:
    def __init__(self, root, *, processor_factory=configured_processor, select_rows=None, knowledge=KNOWLEDGE, history_roots=()):
        self.root = safe_destination(root)
        self.processor_factory = processor_factory
        self.select_rows = select_rows or (lambda ids: _query(ids)[0])
        self.knowledge = knowledge
        self.history_roots = tuple(safe_destination(path) for path in history_roots)
        self._mutex = threading.RLock()
        self._thread = None
        self._active = None
        self._stop = threading.Event()

    def create(self, jd_ids):
        if (not jd_ids or len(jd_ids) > 100 or any(type(i) is not int or i < 1 for i in jd_ids)
                or len(set(jd_ids)) != len(jd_ids)):
            raise ValueError('explicit selection requires 1..100 unique JD IDs')
        with self._mutex:
            if self._active: raise RuntimeError('another delivery run is active')
            rows = self.select_rows(jd_ids)
            if {row['id'] for row in rows} != set(jd_ids) or len(rows) != len(jd_ids):
                raise ValueError('selected JD missing; refresh the selection')
            if any(row.get('content_eligible') in (False, 0) for row in rows):
                raise ValueError('selected JD is content ineligible')
            processor = self.processor_factory()
            run_id = uuid4().hex
            with DeliveryStore(self.root, create=True) as store:
                for (pending_id,) in store.conn.execute('SELECT run_id FROM requests'):
                    if store.read(pending_id)['status'] not in {'completed', 'abandoned'}:
                        raise RuntimeError('unfinished delivery run; resume or explicitly abandon it before selecting a new analysis')
                command = dict(schema_version='m2-delivery-request-1', baseline=store.candidates.read()['binding'],
                               items=[dict(namespace='mysql-jd_pool', row=adapted(row), input_version=digest(row)) for row in rows],
                               operations=[], research_sources=True)
                asyncio.run(execute(store, run_id, command, load_snapshot(self.knowledge), processor=processor, stop=lambda: True))
                prepared = store.read(run_id)
                prepared['status'] = 'prepared'
                store.append(run_id, 'progress', prepared)
                store.append(run_id, 'web_metadata', dict(created_at=now(), selected_ids=jd_ids))
            return self.get(run_id)

    def _locate(self, run_id):
        found = []
        for root in (self.root, *self.history_roots):
            if not (root / 'delivery.db').exists(): continue
            with DeliveryStore(root, readonly=True) as store:
                if store.conn.execute('SELECT 1 FROM requests WHERE run_id=?', (run_id,)).fetchone():
                    found.append(root)
        if len(found) != 1:
            raise ValueError('unknown or ambiguous delivery run')
        return found[0]

    def get(self, run_id):
        root = self._locate(run_id)
        with DeliveryStore(root, readonly=True) as store:
            value = store.read(run_id)
            saved = store.request(run_id)
            metadata = store.latest(run_id, 'web_metadata') or {}
            for item in value['items']:
                frozen = saved['request']['items'][item['index']]
                item.update(input=frozen['row'], input_version=frozen['input_version'])
            value.update(created_at=metadata.get('created_at'), engine='delivery',
                         execution_available=root == self.root and value['status'] != 'abandoned',
                         history_origin='web' if root == self.root else root.parent.name,
                         result_sha256=digest(value), execution_active=self._active == run_id)
            if value['status'] == 'running' and self._active != run_id:
                value.update(status='interrupted', reason='worker_not_active_resume_with_original_dependencies')
            return value

    def item(self, run_id, index):
        result = self.get(run_id)
        if not 0 <= index < len(result['items']): raise ValueError('delivery item not found')
        return dict(result['items'][index], run_id=run_id, request_sha256=result['request_sha256'])

    def list_runs(self):
        ids = []
        for root in (self.root, *self.history_roots):
            if not (root / 'delivery.db').exists(): continue
            with DeliveryStore(root, readonly=True) as store:
                ids.extend(row[0] for row in store.conn.execute('SELECT run_id FROM requests ORDER BY rowid DESC LIMIT 100'))
        return [{k: v for k, v in self.get(run_id).items() if k in {
            'run_id', 'status', 'counts', 'request_sha256', 'created_at', 'knowledge', 'result_sha256', 'engine', 'reason',
            'history_origin', 'execution_available'}} for run_id in ids]

    def start(self, run_id):
        with self._mutex:
            if self._locate(run_id) != self.root: raise ValueError('history is read-only; explicitly select a new analysis')
            if self._active: raise RuntimeError('another delivery run is active')
            with DeliveryStore(self.root, readonly=True) as store:
                saved = store.request(run_id)
                if store.latest(run_id, 'result') is not None: raise ValueError('completed run is immutable')
                if store.read(run_id)['status'] == 'abandoned': raise ValueError('abandoned run is read-only')
            processor = self.processor_factory()
            if processor.descriptor != saved['processor']: raise ValueError('resume requires original processor descriptor')
            if saved['dependencies'] != LOADED: raise ValueError('resume requires original dependencies; select a new analysis')
            ensure_loaded()
            self._active = run_id
            self._stop.clear()
            ready, errors = threading.Event(), []
            self._thread = threading.Thread(target=self._work, args=(run_id, processor, ready, errors), daemon=True)
            self._thread.start()
            if not ready.wait(15):
                self._stop.set()
                raise RuntimeError('delivery worker startup timed out; inspect the saved task')
            if errors: raise RuntimeError('delivery worker unavailable; another worker may own the store')
            return self.get(run_id)

    def _work(self, run_id, processor, ready, errors):
        try:
            with DeliveryStore(self.root) as store:
                try:
                    progress = store.read(run_id)
                    progress['status'] = 'running'
                    store.append(run_id, 'progress', progress)
                    ready.set()
                    asyncio.run(resume(store, run_id, processor=processor, stop=self._stop.is_set))
                except Exception:
                    partial = store.read(run_id)
                    if partial['status'] != 'completed':
                        partial.update(status='interrupted', reason='delivery_failed_resume_with_original_dependencies')
                        store.append(run_id, 'progress', partial)
        except Exception:
            errors.append('worker_unavailable')
        finally:
            self._active = None
            ready.set()

    def stop(self, run_id):
        with self._mutex:
            if self._locate(run_id) != self.root: raise ValueError('history is read-only')
            result = self.get(run_id)
            if result['status'] == 'completed': raise ValueError('completed run is immutable')
            if result['status'] == 'abandoned': raise ValueError('abandoned run is read-only')
            if self._active == run_id:
                self._stop.set()
                result['stop_requested'] = True
                return result
            if self._active: raise RuntimeError('another delivery run is active')
            with DeliveryStore(self.root) as store:
                value = store.read(run_id)
                value['status'] = 'stopped'
                store.append(run_id, 'progress', value)
            return self.get(run_id)

    def abandon(self, run_id):
        with self._mutex:
            if self._locate(run_id) != self.root: raise ValueError('history is read-only')
            if self._active: raise RuntimeError('stop the active worker before abandoning a task')
            with DeliveryStore(self.root) as store:
                value = store.read(run_id)
                if value['status'] == 'completed': raise ValueError('completed run is immutable')
                value.update(status='abandoned', reason='explicitly_abandoned_results_preserved')
                store.append(run_id, 'progress', value)
            return self.get(run_id)

    def join(self, timeout):
        if self._thread is not None: self._thread.join(timeout)

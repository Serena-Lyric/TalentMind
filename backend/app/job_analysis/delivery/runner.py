"""Explicit dependencies, conservative P1 reuse and exact candidate-commit recovery."""
from copy import deepcopy
import hashlib
from pathlib import Path
import sqlite3
from typing import Annotated

from pydantic import Field, model_validator

from ..baseline.contract import Strict, Text, validate_analysis
from ..foundation.inputs import InputRecord, digest, parse_json
from ..foundation.runner import publish
from ..knowledge.alignment import align_analysis
from ..knowledge.candidates import CandidateRegistry
from ..knowledge.catalog import LoadedSnapshot
from ..knowledge.models import validate_snapshot
from ..knowledge.roles import compare_roles
from ..understanding.core import LOADED_DEPENDENCIES, PROMPT_PATH
from ..understanding.runtime import understand
from ..work_candidates.models import Binding, Create, Link, Correct, Describe
from ..work_candidates.service import algorithm_version, apply_batch


class Item(Strict):
    namespace: Text
    row: dict
    input_version: Text
    analysis: dict | None = None
    p1: dict | None = None

    @model_validator(mode='after')
    def bound_input(self):
        record = InputRecord.from_row(self.namespace, self.row)
        if self.analysis is not None and self.p1 is not None:
            raise ValueError('choose explicit analysis or manifest-bound P1 run')
        analysis = self.analysis if self.analysis is not None else (self.p1['analysis'] if self.p1 else None)
        if analysis is not None:
            value = validate_analysis(analysis)
            if (value.namespace, value.jd_id, value.input_sha256, value.input_version) != (
                    record.namespace, record.jd_id, record.fingerprint, self.input_version):
                raise ValueError('analysis/input binding mismatch')
        return self


class Request(Strict):
    schema_version: str
    baseline: Binding
    items: list[Item] = Field(min_length=1)
    operations: list[Annotated[Create | Link | Correct | Describe, Field(discriminator='op')]]
    research_sources: bool = False

    @model_validator(mode='after')
    def identities(self):
        if self.schema_version != 'm2-delivery-request-1': raise ValueError('unknown request version')
        ids = [(i.namespace, str(i.row['id'])) for i in self.items]
        if len(ids) != len(set(ids)): raise ValueError('duplicate JD identity')
        return self


def dependencies():
    root = Path(__file__).parents[1]
    return dict(p1=LOADED_DEPENDENCIES, prompt_sha256=hashlib.sha256(PROMPT_PATH.read_bytes()).hexdigest(),
                downstream=algorithm_version(),
                reused_helpers={name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                                for name in ('foundation/runner.py', 'product/workflow.py')},
                delivery=digest({p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                 for p in sorted(Path(__file__).parent.glob('*.py'))}))


LOADED = dependencies()


def ensure_loaded():
    # P1 reads the prompt at call time; P4 hashes files at commit time. Neither may drift
    # underneath the immutable delivery dependency binding in a long-lived worker.
    if dependencies() != LOADED:
        raise ValueError('loaded dependencies changed on disk; restart the worker')


def checkpoint(stage):
    """Durable lifecycle boundary for local progress instrumentation."""


def complete(analysis, p1=None):
    return (bool(analysis['claims']) and all(analysis['coverage'][d]['status'] == 'complete'
                for d in ('goals', 'objects', 'duties', 'requirements', 'relations'))
            and (p1 is None or p1['execution']['status'] == 'ok'))


async def execute(store, run_id, request, knowledge, *, processor=None, stop=None, output=None):
    ensure_loaded()
    command = Request.model_validate(request)
    descriptor = deepcopy(processor.descriptor) if processor is not None else None
    if descriptor is None and any(i.analysis is None and i.p1 is None for i in command.items):
        raise ValueError('explicit processor required for raw JD')
    raw = (knowledge.path / 'knowledge.json').read_bytes()
    if hashlib.sha256(raw).hexdigest() != knowledge.sha256:
        raise ValueError('knowledge changed since load')
    frozen = dict(request=command.model_dump(), dependencies=LOADED, processor=descriptor,
                  knowledge=dict(raw_hex=raw.hex(), sha256=knowledge.sha256))
    store.prepare(run_id, frozen)
    if store.latest(run_id, 'result') is None and store.latest(run_id, 'progress') is None:
        store.append(run_id, 'progress', _result(store, run_id, frozen, {}, None, 'prepared'))
    checkpoint('after_prepare')
    return await resume(store, run_id, processor=processor, stop=stop, output=output)


def _result(store, run_id, saved, items, work, status):
    rows = []
    counts = dict(complete=0, partial=0, unknown=0, failed=0, not_run=0)
    for index, item in enumerate(saved['request']['items']):
        result = deepcopy(items.get(index))
        if result is None:
            result = dict(index=index, namespace=item['namespace'], jd_id=str(item['row']['id']),
                          status='not_run', reason='not_executed', analysis=None)
        counts[result['status']] += 1
        rows.append(result)
    return dict(schema_version='m2-delivery-result-1', run_id=run_id, request_sha256=digest(saved),
                status=status, counts=counts, items=rows, work=work, dependencies=saved['dependencies'],
                stage_results=store.stages(run_id),
                knowledge=dict(sha256=saved['knowledge']['sha256']),
                semantic_review='machine_unreviewed', market_accuracy=None,
                work_semantics='bounded_literal_research_only', formal_role_assignment='not_available',
                privacy='local_private_contains_source_text')


async def resume(store, run_id, *, processor=None, stop=None, output=None):
    saved = store.request(run_id)
    finished = store.latest(run_id, 'result')
    if finished is not None:
        if output is not None: publish(finished, output, run_id)
        return finished
    if saved['dependencies'] != LOADED:
        raise ValueError('resume requires original code and prompt dependencies; start a new run')
    ensure_loaded()
    if saved['processor'] is not None and (processor is None or processor.descriptor != saved['processor']):
        raise ValueError('resume requires original processor descriptor')
    raw = bytes.fromhex(saved['knowledge']['raw_hex'])
    if hashlib.sha256(raw).hexdigest() != saved['knowledge']['sha256']:
        raise ValueError('frozen knowledge digest mismatch')
    knowledge = LoadedSnapshot(Path('.'), validate_snapshot(parse_json(raw.decode('utf-8'))), saved['knowledge']['sha256'])
    items = store.item_results(run_id)
    for index, source in enumerate(saved['request']['items']):
        ensure_loaded()
        if index in items: continue
        if stop and stop():
            result = _result(store, run_id, saved, items, None, 'stopped')
            store.append(run_id, 'progress', result)
            return result
        record = InputRecord.from_row(source['namespace'], source['row'])
        # Knowledge is deliberately absent: a knowledge update reinterprets P1, not its source facts.
        key = digest(dict(namespace=record.namespace, jd_id=record.jd_id, input_sha256=record.fingerprint,
                          input_version=source['input_version'], processor=saved['processor'],
                          p1=LOADED['p1'], prompt=LOADED['prompt_sha256'],
                          supplied_analysis=source['analysis'], supplied_p1=source['p1']))
        cached = store.cached(key)
        p1 = source['p1']
        reuse = dict(p1=False, from_run_id=None)
        if cached:
            origin, item = cached
            analysis, p1 = item['analysis'], item['p1']
            reuse = dict(p1=True, from_run_id=origin)
        elif source['analysis'] is not None:
            analysis = source['analysis']
        elif p1 is not None:
            analysis = p1['analysis']
        else:
            def retain(stage, value):
                store.append(run_id, 'p1_stage', dict(index=index, stage=stage, p1=value))
                store.append(run_id, 'progress', _result(store, run_id, saved, items, None, 'running'))
            p1 = await understand(source['namespace'], source['row'], source['input_version'], processor,
                                  on_stage=retain)
            analysis = p1['analysis']
        validate_analysis(analysis)
        is_complete = complete(analysis, p1)
        statuses = {analysis['coverage'][d]['status'] for d in ('goals', 'objects', 'duties', 'requirements', 'relations')}
        status = ('not_run' if analysis['outcome'] == 'not_run' or (p1 and p1['execution']['status'] == 'not_run') else
                  'complete' if is_complete else 'failed' if statuses <= {'failed', 'not_run'} else
                  'unknown' if not analysis['claims'] else 'partial')
        item = dict(index=index, namespace=record.namespace, jd_id=record.jd_id, observation=record.observation,
                    input_sha256=record.fingerprint, analysis=analysis, analysis_sha256=digest(analysis), p1=p1,
                    status=status, p1_key=key, p1_complete=is_complete, reuse=reuse,
                    role_assignment=dict(status='unavailable', reason='p2_2_not_validated'),
                    input_mode='controlled_analysis' if source['analysis'] is not None else
                               'historical_p1_run' if source['p1'] is not None else 'processor_execution')
        try:
            # Observe the unprojected facts, so an existing candidate cannot hide
            # fresh evidence. Governance never reopens withdrawn/disputed heads.
            registry = CandidateRegistry(store.root / 'skill-candidates')
            alignment = align_analysis(analysis, knowledge)
            observed = registry.observe(analysis, alignment)
            projection = registry.project()
            item['skill_candidates'] = [record.model_dump() for record in observed]
            item['knowledge_projection'] = projection.model_dump()
            item['alignment'] = align_analysis(analysis, knowledge, candidate_projection=projection).model_dump()
            item['roles'] = compare_roles(analysis, knowledge).model_dump()
            item['interpretation_status'] = 'completed'
        except Exception:
            # Preserve P1, and never serialize provider or private source exception text.
            item.update(alignment=None, roles=None, interpretation_status='failed', reason='knowledge_interpretation_failed')
            if status == 'complete': item['status'] = 'partial'
        checkpoint('before_item_commit')
        store.append(run_id, 'item', item)
        items[index] = item
        store.append(run_id, 'progress', _result(store, run_id, saved, items, None, 'running'))
        checkpoint('after_item_commit')
    if stop and stop():
        result = _result(store, run_id, saved, items, None, 'stopped')
        store.append(run_id, 'progress', result)
        return result
    analyses = {i['analysis_sha256']: i['analysis'] for i in items.values()}
    operations = list(saved['request']['operations'])
    if saved['request'].get('research_sources'):
        # Each source duty remains an independent research seed, never an automatic
        # assertion that distinct JDs belong to the same occupation or work group.
        current = store.candidates.read()['candidates']
        for sha, analysis in analyses.items():
            for claim in analysis['claims']:
                if claim['kind'] != 'duty' or claim['core'] is not True:
                    continue
                candidate_id = 'source-work-' + digest([sha, claim['id']])[:24]
                if candidate_id not in current:
                    operations.append(dict(op='create', candidate_id=candidate_id, description=claim['text'],
                        research_question='源职责研究：与其他职责的关系尚未确认',
                        core_work=[dict(analysis_sha256=sha, claim_id=claim['id'])]))
    batch = dict(schema_version='m2-work-batch-1', batch_id='delivery-' + digest(run_id),
                 baseline=saved['request']['baseline'], operation_version='delivery-1',
                 analysis_sha256s=sorted(analyses), operations=operations)
    # A crash after candidate commit must retry the identical batch, not derive
    # fewer operations from the registry that now includes that commit.
    bound_batch = store.latest(run_id, 'candidate_batch')
    if bound_batch is None:
        store.append(run_id, 'candidate_batch', batch)
    else:
        batch = bound_batch
    checkpoint('before_candidate_commit')
    ensure_loaded()
    try:
        work = apply_batch(store.candidates, batch, analyses, knowledge)
    except (ValueError, OSError, sqlite3.Error):
        store.append(run_id, 'progress', _result(store, run_id, saved, items, None, 'candidate_failed'))
        raise
    checkpoint('after_candidate_commit')
    result = _result(store, run_id, saved, items, work, 'completed')
    store.append(run_id, 'result', result)
    checkpoint('after_result_commit')
    if output is not None: publish(result, output, run_id)
    return result

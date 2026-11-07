"""Version-bound local candidate maintenance over persisted, validated evidence."""
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field

from ..baseline.contract import validate_analysis
from ..foundation.inputs import digest
from ..knowledge.alignment import align_analysis
from ..knowledge.candidates import CandidateRegistry, CandidateVersion, _extract_observations
from ..knowledge.catalog import load_snapshot, LoadedSnapshot
from ..knowledge.models import Strict, StableId, Text, Sha256, validate_snapshot
from ..work_candidates.models import Binding, Link, Correct, Describe
from ..work_candidates.service import apply_batch, algorithm_version
from ..work_candidates.storage import CandidateStore
from .store import DeliveryStore


class WorkCommand(Strict):
    batch_id: StableId
    baseline: Binding
    analysis_sha256s: list[Sha256]
    operations: list[Annotated[Link | Correct | Describe, Field(discriminator='op')]] = Field(min_length=1, max_length=100)


class SkillCommand(Strict):
    request_id: StableId
    expected_version: int = Field(ge=1)
    action: Literal['mark_disputed', 'withdraw', 'revise']
    reason: Text
    description: Text | None = None
    competing_hypotheses: list[Text] = Field(default_factory=list)
    source_analysis_sha256: Sha256 | None = None


class _PreviewRegistry(CandidateRegistry):
    def _write(self, value):
        return value


def checkpoint(stage):
    """Fault-injection boundary for durable maintenance recovery."""


class Maintenance:
    def __init__(self, service):
        self.service = service

    def pending(self):
        if not (self.service.root / 'delivery.db').exists():
            return dict(items=[])
        with DeliveryStore(self.service.root, readonly=True) as store:
            result = []
            for (action_id,) in store.conn.execute("SELECT DISTINCT run_id FROM events WHERE kind='maintenance_prepare'"):
                if store.latest(action_id, 'maintenance_result') is not None or store.latest(action_id, 'maintenance_rejected') is not None:
                    continue
                prepared = store.latest(action_id, 'maintenance_prepare')
                request = prepared['request']
                result.append(dict(id=action_id, kind=prepared['kind'], candidate_id=request.get('candidate_id'),
                                   request_sha256=prepared['request_sha256'], request=request))
            return dict(items=result)

    def recover(self, action_id):
        with DeliveryStore(self.service.root, readonly=True) as store:
            prepared = store.latest(action_id, 'maintenance_prepare')
        if prepared is None:
            raise ValueError('unknown maintenance request')
        request = dict(prepared['request'])
        if prepared['kind'] == 'work':
            return self.update_work(request)
        candidate_id = request.pop('candidate_id')
        return self.update_skill(candidate_id, request)

    def _sources(self):
        sources = {}
        for root in (self.service.root, *self.service.history_roots):
            if not (root / 'delivery.db').exists():
                continue
            with DeliveryStore(root, readonly=True) as store:
                for row in store.conn.execute("SELECT body,sha FROM events WHERE kind='item' ORDER BY seq"):
                    item = store._checked(row)
                    analysis = item.get('analysis')
                    if analysis is None:
                        continue
                    validate_analysis(analysis)
                    sha = digest(analysis)
                    if sha != item.get('analysis_sha256'):
                        raise ValueError('saved analysis digest mismatch')
                    sources[sha] = analysis
        return sources

    def _work(self, store, revision=None):
        state = store.read(revision)
        sources = self._sources()
        for sha in state['analysis_sha256s']:
            sources[sha] = store.source('analysis', sha)
        return dict(state=state, versions=[r[0] for r in store.conn.execute('SELECT revision FROM batches ORDER BY revision')],
                    relation_sha256s={key: digest(value) for key, value in state['relations'].items()},
                    sources=[dict(analysis_sha256=sha, analysis=a) for sha, a in sorted(sources.items())])

    def work(self, revision=None):
        with CandidateStore(self.service.root / 'candidates.db', readonly=True) as store:
            return self._work(store, revision)

    @staticmethod
    def _guard(store, action_id):
        for (run_id,) in store.conn.execute('SELECT run_id FROM requests'):
            if store.read(run_id)['status'] not in {'completed', 'abandoned'}:
                raise RuntimeError('unfinished delivery run; resume or abandon before maintenance')
        for (pending,) in store.conn.execute("SELECT DISTINCT run_id FROM events WHERE kind='maintenance_prepare'"):
            if (pending != action_id and store.latest(pending, 'maintenance_result') is None
                    and store.latest(pending, 'maintenance_rejected') is None):
                raise RuntimeError('unfinished maintenance request; retry its original request first')

    @staticmethod
    def _previous(store, action_id, payload):
        prepared = store.latest(action_id, 'maintenance_prepare')
        if prepared is not None and prepared['request_sha256'] != digest(payload):
            raise RuntimeError('request ID already used for different content')
        if store.latest(action_id, 'maintenance_rejected') is not None:
            raise ValueError('original maintenance request rejected; correct it with a new request ID')
        return prepared, store.latest(action_id, 'maintenance_result')

    def update_work(self, payload):
        command = WorkCommand.model_validate(payload)
        if any(isinstance(op, Correct) and op.verification is not None for op in command.operations):
            raise ValueError('browser maintenance cannot supply formal review verification')
        action_id = 'maintenance-work-' + command.batch_id
        with DeliveryStore(self.service.root) as store:
            prepared, previous = self._previous(store, action_id, command.model_dump())
            if previous is not None:
                return previous
            self._guard(store, action_id)
            if prepared is None:
                state = store.candidates.read()
                if command.baseline.model_dump() != state['binding']:
                    raise RuntimeError('stale candidate baseline; refresh before editing')
                for op in command.operations:
                    if isinstance(op, Correct):
                        relation = state['relations'].get(op.relation_id)
                        if relation is None or digest(relation) != op.expected_sha256:
                            raise RuntimeError('stale relation; refresh before editing')
                    if isinstance(op, Describe):
                        candidate = state['candidates'].get(op.candidate_id)
                        if candidate is None or candidate['version'] != op.expected_version:
                            raise RuntimeError('stale candidate; refresh before editing')
                sources = self._sources()
                if any(sha not in sources for sha in command.analysis_sha256s):
                    raise ValueError('analysis must reference saved server evidence')
                knowledge = load_snapshot(self.service.knowledge)
                prepared = dict(request_sha256=digest(command.model_dump()), request=command.model_dump(), kind='work',
                    algorithm=algorithm_version(),
                    knowledge=knowledge.snapshot.model_dump(), knowledge_sha256=knowledge.sha256,
                    analyses={sha: sources[sha] for sha in command.analysis_sha256s})
                store.append(action_id, 'maintenance_prepare', prepared)
            knowledge = LoadedSnapshot(Path('.'), validate_snapshot(prepared['knowledge']), prepared['knowledge_sha256'])
            batch = dict(schema_version='m2-work-batch-1', operation_version='web-maintenance-1',
                         **command.model_dump())
            # Batch commit is already idempotent; save the input binding before any
            # independently committed work so a process exit can replay it exactly.
            try:
                committed = store.candidates.conn.execute('SELECT 1 FROM batches WHERE batch_id=?', (command.batch_id,)).fetchone()
                if not committed and prepared['algorithm'] != algorithm_version():
                    raise RuntimeError('maintenance recovery requires original algorithm dependencies')
                checkpoint('before_work_commit')
                result = apply_batch(store.candidates, batch, prepared['analyses'], knowledge, automatic_retrieval=False)
            except ValueError:
                store.append(action_id, 'maintenance_rejected', dict(reason='invalid_domain_operation'))
                raise
            checkpoint('after_work_commit')
            response = self._work(store.candidates, result['revision'])
            store.append(action_id, 'maintenance_result', response)
            return response

    def _registry(self):
        return CandidateRegistry(self.service.root / 'skill-candidates')

    def skills(self):
        return dict(items=[record.model_dump() for record in self._registry()._heads()])

    def skill(self, candidate_id, version=None):
        # StableId is also a path boundary; never trust a route segment as a path.
        from pydantic import TypeAdapter
        TypeAdapter(StableId).validate_python(candidate_id)
        registry = self._registry()
        candidate = registry.read(candidate_id, version)
        head = registry.read(candidate_id)
        eligible = []
        if candidate.version == head.version:
            bound = {o.observation_key for o in head.referenced_observations}
            knowledge = load_snapshot(self.service.knowledge)
            for sha, analysis in sorted(self._sources().items()):
                observations = _extract_observations(analysis, align_analysis(analysis, knowledge))
                if any(o.interpretation_key == head.interpretation_key and o.observation_key not in bound for o in observations):
                    eligible.append(dict(analysis_sha256=sha, analysis=analysis))
        return dict(candidate=candidate.model_dump(), versions=registry._versions(candidate_id),
                    projection=registry.project(persist=False).model_dump() if candidate.version == head.version else None,
                    projection_scope='current_head' if candidate.version == head.version else 'historical_candidate_only',
                    eligible_new_evidence=eligible)

    def update_skill(self, candidate_id, payload):
        command = SkillCommand.model_validate(payload)
        action_id = 'maintenance-skill-' + command.request_id
        request = dict(candidate_id=candidate_id, **command.model_dump())
        with DeliveryStore(self.service.root) as store:
            prepared, previous = self._previous(store, action_id, request)
            if previous is not None:
                return previous
            self._guard(store, action_id)
            registry = self._registry()
            current = self.skill(candidate_id)['candidate']
            if prepared is None:
                if current['version'] != command.expected_version:
                    raise RuntimeError('stale candidate version; refresh before editing')
                preview = _PreviewRegistry(registry.root)
                if command.action == 'withdraw':
                    updated = preview.withdraw(candidate_id, command.reason)
                elif command.action == 'mark_disputed':
                    updated = preview.mark_disputed(candidate_id, command.reason, command.competing_hypotheses)
                else:
                    if not command.description or not command.source_analysis_sha256:
                        raise ValueError('revision requires description and new evidence')
                    source = next((s['analysis'] for s in self.skill(candidate_id)['eligible_new_evidence']
                                   if s['analysis_sha256'] == command.source_analysis_sha256), None)
                    if source is None:
                        raise ValueError('revision requires matching new evidence not already bound')
                    updated = preview.revise(candidate_id, command.description, command.reason,
                        analysis=source, alignment=align_analysis(source, load_snapshot(self.service.knowledge)),
                        competing_hypotheses=command.competing_hypotheses or None)
                prepared = dict(request_sha256=digest(request), request=request, kind='skill', candidate=updated.model_dump(), algorithm=algorithm_version())
                store.append(action_id, 'maintenance_prepare', prepared)
            if prepared['algorithm'] != algorithm_version():
                raise RuntimeError('maintenance recovery requires original algorithm dependencies')
            updated = CandidateVersion.model_validate(prepared['candidate'])
            if current['version'] == updated.version:
                if current != updated.model_dump():
                    raise RuntimeError('maintenance recovery version mismatch')
            elif current['version'] == command.expected_version:
                registry._write(updated)
            else:
                raise RuntimeError('maintenance recovery requires original version')
            checkpoint('after_skill_commit')
            registry.project()
            response = self.skill(candidate_id, updated.version)
            store.append(action_id, 'maintenance_result', response)
            return response

"""Zero-network replay of manifest-bound P1 completions, keyed by exact request."""
from copy import deepcopy

from ..baseline.contract import validate_analysis
from ..foundation.inputs import check_public, digest
from ..understanding.processor import Completion
from ..understanding.storage import read_run


class RecordedProcessor:
    def __init__(self, paths):
        roots = [read_run(path) for path in paths]
        runs = []
        def collect(run):
            if run.get('schema_version') != 'm2-p1-run-1': raise ValueError('invalid nested P1 run')
            validate_analysis(run['analysis'])
            runs.append(run)
            for field in ('primary_run', 'audit_attempt'):
                if field in run: collect(run[field])
        for run in roots: collect(run)
        if not runs: raise ValueError('recorded runs required')
        descriptors = [{k: v for k, v in run['processor'].items()
                        if k not in {'audit_policy', 'previous_analysis_sha256', 'source_constraints'}} for run in runs]
        if any(d != descriptors[0] for d in descriptors):
            raise ValueError('recorded processor versions differ; separate runs required')
        self.descriptor = dict(descriptors[0], execution_mode='cached_recompile',
                               recorded_runs_sha256=digest(roots))
        check_public(self.descriptor)
        self.responses = {}
        for run in runs:
            key = digest(run['request'])
            value = dict(content=run['completion'], finish_reason=run['execution']['finish_reason'],
                         status='ok' if run['execution']['status'] in {'ok', 'partial', 'no_recognized_results', 'truncated'}
                                     else run['execution']['status'],
                         metadata=dict(deepcopy(run['execution']['metadata']), execution_mode='cached_recompile',
                                       source_run_sha256=digest(run), network_requests=0))
            if key in self.responses:
                old = deepcopy(self.responses[key])
                new = deepcopy(value)
                for candidate in (old, new): candidate['metadata'].pop('source_run_sha256')
                if old != new: raise ValueError('ambiguous recorded response; choose one source run')
                continue
            self.responses[key] = value

    async def complete(self, messages):
        value = self.responses.get(digest(messages))
        if value is None:
            return Completion(status='not_run', metadata=dict(execution_mode='cached_recompile',
                              reason='exact_recorded_request_unavailable', network_requests=0))
        return Completion(**deepcopy(value))

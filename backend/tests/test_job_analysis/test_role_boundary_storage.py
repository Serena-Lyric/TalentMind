"""Real SQLite/process boundaries; temporary synthetic fixtures clean in finally."""
from copy import deepcopy
import json
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

from test_foundation_inputs import area, jd, load
from test_role_boundary_claims import source, submission, multiple
from test_role_governance import no_network, catalog
from test_role_boundaries import taxonomy, V3


def event(report, **changes):
    member = report['members'][0]
    return dict(target_kind='assessment', target_id='assessment-a', result_version=member['result_version'],
        decision='reviewed_accepted', reviewer='synthetic-reviewer', basis='显式合成测试意见，不授予准入',
        evidence_refs=[member['body']['assessments'][0]['submitted_claim']['evidence'][0]],
        supersedes=None, formal_admitted=False) | changes


def test_persistent_reuse_versions_reviews_and_immutable_export(area):
    from app.job_analysis.role_classification.boundaries.runner import execute, replay, review_export
    from app.job_analysis.role_classification.boundaries.store import BoundaryStore
    batch, marks = multiple(area)
    state = area / 'state.db'
    with BoundaryStore(state) as store:
        first = execute(store, batch, marks, taxonomy(), output=area / 'out')
        assert not first['members'][0]['reused']
        old_event = event(first)
        review_id = store.record_review(first['members'][0]['result_id'], old_event)
        exported = review_export(store, first['run_id'])
        store.record_review(first['members'][0]['result_id'], event(first, decision='withdrawn', supersedes=review_id))
        assert len(replay(store, exported['run_id'])['members'][0]['reviews']) == 1
        assert replay(store, first['run_id']) == first
        for table in ('b34_versions', 'b34_inputs', 'b34_results', 'b34_reports', 'b34_reviews', 'b34_exports'):
            for action in ('UPDATE ' + table + ' SET ' + ('manifest=manifest' if table.endswith('versions') else 'sha256=sha256'), 'DELETE FROM ' + table):
                with pytest.raises(sqlite3.IntegrityError):
                    with store.conn:
                        store.conn.execute(action)
        row = store.conn.execute('SELECT * FROM b34_reports').fetchone()
        with pytest.raises(sqlite3.IntegrityError):
            with store.conn:
                store.conn.execute('INSERT OR REPLACE INTO b34_reports VALUES (?,?,?)', tuple(row))
    with BoundaryStore(state) as store:
        repeated = execute(store, batch, marks, taxonomy())
        assert repeated['members'][0]['reused']
        assert repeated['members'][0]['result_id'] == first['members'][0]['result_id']
        assert len(store.reviews(first['members'][0]['result_id'])) == 2
        changed = deepcopy(marks)
        changed['annotations'][0]['notes'] += ' changed'
        variants = [execute(store, batch, changed, taxonomy()), execute(store, batch, marks, taxonomy(), revision='rules-v2')]
        tax = taxonomy()
        tax['job_family'][-1]['scope'] += ' revision'
        variants.append(execute(store, batch, marks, tax))
        for result in variants:
            assert result['members'][0]['result_version'] != first['members'][0]['result_version']
            assert store.reviews(result['members'][0]['result_id']) == []
            with pytest.raises(ValueError):
                store.record_review(result['members'][0]['result_id'], old_event)
        assert first['manifest']['family_taxonomy']['revision'] == 'families-v3'
        assert first['input_sha256'] == batch.digest
        assert first['submission'] == marks


@pytest.mark.parametrize('bad', ['span', 'forbidden', 'source_bytes', 'source_type', 'second_annotation'])
def test_invalid_submission_is_atomic_across_the_entire_batch(area, bad):
    from app.job_analysis.role_classification.boundaries.runner import execute
    from app.job_analysis.role_classification.boundaries.store import BoundaryStore
    batch, marks = multiple(area)
    if bad == 'span':
        marks['annotations'][0]['assessments'][0]['position_targets'][1]['title']['start'] = 999
    elif bad == 'forbidden':
        marks['annotations'][0]['assessments'][0]['headcount'] = 2
    elif bad == 'source_bytes':
        batch = type(batch)(batch.namespace, batch.path, b'[]', batch.records)
    elif bad == 'source_type':
        batch = source(area, source='boss')
        marks = submission(batch.records[0])
    else:
        marks['annotations'].append(deepcopy(marks['annotations'][0]) | dict(jd_id='foreign'))
    with BoundaryStore(area / 'state.db') as store:
        with pytest.raises(ValueError):
            execute(store, batch, marks, taxonomy())
        for table in ('snapshots', 'b34_versions', 'b34_inputs', 'b34_results', 'b34_reports'):
            assert store.conn.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0] == 0


@pytest.mark.parametrize('bad', [dict(reviewer=' '), dict(basis=' '), dict(formal_admitted=True),
    dict(target_id='missing'), dict(target_kind='relation'), dict(decision='withdrawn'),
    dict(evidence_refs=[]), dict(headcount=2)])
def test_reviews_reject_unattributed_or_unbound_publication_claims(area, bad):
    from app.job_analysis.role_classification.boundaries.runner import execute
    from app.job_analysis.role_classification.boundaries.store import BoundaryStore
    batch = source(area)
    with BoundaryStore(area / 'state.db') as store:
        report = execute(store, batch, submission(batch.records[0]), taxonomy())
        with pytest.raises(ValueError):
            store.record_review(report['members'][0]['result_id'], event(report, **bad))
        assert store.reviews(report['members'][0]['result_id']) == []


@pytest.mark.parametrize('stage', ['after_result', 'before_commit', 'after_commit', 'after_output'])
def test_actual_hard_exit_recovers_committed_reports_only(area, stage):
    from app.job_analysis.role_classification.boundaries.runner import execute, replay
    from app.job_analysis.role_classification.boundaries.store import BoundaryStore
    batch, marks = multiple(area)
    for name, value in [('claims', marks), ('families', taxonomy())]:
        (area / (name + '.json')).write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
    script = '''
import json, os, socket, sys
from pathlib import Path
from app.job_analysis.foundation.inputs import read_snapshot
from app.job_analysis.role_classification.boundaries import runner
from app.job_analysis.role_classification.boundaries.store import BoundaryStore
def blocked(*args, **kwargs): raise AssertionError('network prohibited')
socket.socket.connect = socket.socket.connect_ex = blocked
root, stage = Path(sys.argv[1]), sys.argv[2]
runner.checkpoint = lambda point: os._exit(71) if point == stage else None
read = lambda name: json.loads((root / (name + '.json')).read_text(encoding='utf-8'))
with BoundaryStore(root / 'state.db') as store:
    runner.execute(store, read_snapshot(root / 'input.json', 'fixture'), read('claims'), read('families'), output=root / 'out')
'''
    done = subprocess.run([sys.executable, '-X', 'utf8', '-c', script, str(area), stage], capture_output=True)
    assert done.returncode == 71, done.stderr.decode()
    committed = stage in ('after_commit', 'after_output')
    with BoundaryStore(area / 'state.db') as store:
        rows = store.conn.execute('SELECT run_id FROM b34_reports').fetchall()
        assert len(rows) == int(committed)
        if committed:
            assert replay(store, rows[0][0])['submission'] == marks
        report = execute(store, batch, marks, taxonomy())
        assert report['members'][0]['reused'] == committed
        assert store.conn.execute('SELECT COUNT(*) FROM b34_results').fetchone()[0] == 1


def test_publication_failure_and_missing_configs_replay_without_reanalysis(area, monkeypatch):
    from app.job_analysis.role_classification.boundaries import runner
    from app.job_analysis.role_classification.boundaries.store import BoundaryStore
    batch, marks = multiple(area)
    def failure(*args):
        raise OSError('synthetic output fault')
    with BoundaryStore(area / 'state.db') as store:
        with monkeypatch.context() as m:
            m.setattr(runner, 'publish', failure)
            with pytest.raises(OSError):
                runner.execute(store, batch, marks, taxonomy(), output=area / 'out')
        identity = store.conn.execute('SELECT run_id FROM b34_reports').fetchone()[0]
        batch.path.unlink()
        report = runner.replay(store, identity)
        runner.publish(report, area / 'out', identity)
        assert json.loads((area / 'out' / (identity + '.json')).read_text(encoding='utf-8')) == report


def test_old_actual_v1_v2_and_all_upstream_rows_preserved_in_mixed_database(area):
    from app.job_analysis.foundation.store import AnalysisStore
    from app.job_analysis.role_classification.proposals.store import ProposalStore
    from app.job_analysis.role_classification.proposals.runner import execute as propose, replay as p_replay
    from app.job_analysis.role_classification.governance.store import CanonicalStore
    from app.job_analysis.role_classification.governance.runner import execute as govern, replay as g_replay
    from app.job_analysis.role_classification.boundaries.runner import execute, replay
    from app.job_analysis.role_classification.boundaries.store import BoundaryStore
    from app.job_analysis.role_classification.proposals.models import load_taxonomy
    from test_role_governance import source as b32_source, submission as b32_submission
    state = area / 'mixed.db'
    # Existing upstream integration tests also exercise actual execution; here seed A and old B31/B32 history.
    with ProposalStore(state):
        pass
    with CanonicalStore(state) as store:
        fixture = json.loads((Path(__file__).resolve().parents[1] / 'fixtures/role_classification/history.families-v1-v2.json').read_text(encoding='utf-8'))
        assert fixture['base_commit'] == '814c99168390f6d3ae476d814d9adddee36223df'
        with store.conn:
            for table, rows in fixture['tables'].items():
                for row in rows:
                    values = [v['utf8_bytes'].encode('utf-8') if isinstance(v, dict) else v for v in row]
                    store.conn.execute(f"INSERT INTO {table} VALUES ({','.join('?' for _ in values)})", values)
        old = {t: [tuple(r) for r in store.conn.execute(f'SELECT * FROM {t}')] for t in fixture['tables']}
        assert {json.loads(row[1])['manifest']['taxonomy']['revision'] for row in old['b31_reports']} == {'families-v1', 'families-v2'}
        batch = b32_source(area)
        v2 = load_taxonomy(V3.with_name('families.v2.json'))
        p = propose(store, batch, v2)
        g = govern(store, batch, b32_submission(batch.records[0]), catalog(), taxonomy=v2)
    with AnalysisStore(state) as store:
        store.ingest(load(area, [jd()]))
    with BoundaryStore(state) as store:
        tables = [r[0] for r in store.conn.execute("SELECT name FROM sqlite_master WHERE type='table'") if not r[0].startswith('b34_')]
        before = {t: [tuple(r) for r in store.conn.execute(f'SELECT * FROM {t}')] for t in tables}
        batch, marks = multiple(area)
        result = execute(store, batch, marks, taxonomy())
        for t, rows in before.items():
            assert [tuple(r) for r in store.conn.execute(f'SELECT * FROM {t} ORDER BY rowid LIMIT ?', (len(rows),))] == rows
        assert p_replay(store, p['run_id']) == p
        assert g_replay(store, g['run_id']) == g
        for table, fn in [('b31_reports', p_replay), ('b32_reports', g_replay), ('b32_exports', g_replay)]:
            for row in old[table]:
                assert fn(store, row[0]) == json.loads(row[-2])
        assert replay(store, result['run_id']) == result


def test_cli_actual_run_review_export_replay_and_path_protection(area, capsys):
    from app.job_analysis.role_classification.boundaries.__main__ import main
    batch, marks = multiple(area)
    claims = area / 'claims.json'
    families = area / 'families.json'
    claims.write_text(json.dumps(marks, ensure_ascii=False), encoding='utf-8')
    families.write_text(json.dumps(taxonomy(), ensure_ascii=False), encoding='utf-8')
    common = ['--state', str(area / 'state.db'), '--output', str(area / 'out')]
    args = ['run', *common, '--input', str(batch.path), '--dataset', 'fixture', '--submission', str(claims), '--family-taxonomy', str(families)]
    assert main(args) == 0
    identity = json.loads(capsys.readouterr().out)['run_id']
    report_path = area / 'out' / (identity + '.json')
    saved = report_path.read_bytes()
    report = json.loads(saved)
    ev = area / 'event.json'
    ev.write_text(json.dumps(event(report), ensure_ascii=False), encoding='utf-8')
    assert main(['review', '--state', str(area / 'state.db'), '--result', report['members'][0]['result_id'], '--event', str(ev)]) == 0
    capsys.readouterr()
    assert main(['export-reviews', *common, '--run', identity]) == 0
    export_id = json.loads(capsys.readouterr().out)['export_id']
    exported = (area / 'out' / (export_id + '.json')).read_bytes()
    families.unlink()
    for run_id, original in [(identity, saved), (export_id, exported)]:
        assert main(['replay', *common, '--run', run_id]) == 0
        capsys.readouterr()
        assert (area / 'out' / (run_id + '.json')).read_bytes() == original
    protected = area / 'out' / 'families.json'
    protected.write_text(json.dumps(taxonomy()), encoding='utf-8')
    args[-1] = str(protected)
    assert main(args) == 2


def test_actual_A_B1_B2_B22_B30_B31_B32_histories_and_running_A_untouched(area):
    from test_role_governance_storage import test_all_old_layers_rows_manifests_and_replays_remain_unchanged
    from app.job_analysis.role_classification.boundaries.runner import execute
    from app.job_analysis.role_classification.boundaries.store import BoundaryStore
    test_all_old_layers_rows_manifests_and_replays_remain_unchanged(area)
    with BoundaryStore(area / 'state.db') as store:
        tables = [r[0] for r in store.conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
                  if r[0] != 'snapshots' and not r[0].startswith('b34_')]
        before = {t: [tuple(r) for r in store.conn.execute(f'SELECT * FROM "{t}"')] for t in tables}
        batch = source(area)
        report = execute(store, batch, submission(batch.records[0]), taxonomy())
        store.record_review(report['members'][0]['result_id'], event(report))
        for table, rows in before.items():
            assert [tuple(r) for r in store.conn.execute(f'SELECT * FROM "{table}"')] == rows, table
        assert store.conn.execute("SELECT COUNT(*) FROM runs WHERE status='running'").fetchone()[0] == 1
        assert store.conn.execute('PRAGMA user_version').fetchone()[0] == 1


def test_observation_reuses_but_source_or_implementation_changes_invalidate(area, monkeypatch):
    from app.job_analysis.role_classification.boundaries.runner import execute
    from app.job_analysis.role_classification.boundaries.store import BoundaryStore
    batch = source(area, crawled_at='2026-10-16')
    marks = submission(batch.records[0])
    with BoundaryStore(area / 'state.db') as store:
        original = execute(store, batch, marks, taxonomy())
        observed = source(area, crawled_at='2026-10-17')
        later = execute(store, observed, marks, taxonomy())
        assert later['members'][0]['reused']
        assert later['members'][0]['observation'] == '2026-10-17'
        changed = source(area, raw_text='完整原文发生变化。')
        with pytest.raises(ValueError):
            execute(store, changed, marks, taxonomy())
        new_marks = submission(changed.records[0])
        fresh = execute(store, changed, new_marks, taxonomy())
        assert fresh['members'][0]['result_version'] != original['members'][0]['result_version']
        assert not fresh['members'][0]['reused']
        # Patch only the source-byte reader, simulating a changed installed implementation dependency.
        before = Path.read_bytes
        changed_path = Path(__import__('app.job_analysis.role_classification.boundaries.validation', fromlist=['x']).__file__)
        with monkeypatch.context() as m:
            m.setattr(Path, 'read_bytes', lambda p: before(p) + b'\n# new revision' if p == changed_path else before(p))
            revised = execute(store, changed, new_marks, taxonomy())
        assert revised['version_id'] != fresh['version_id'] and not revised['members'][0]['reused']


def test_shipped_synthetic_examples_cover_four_independent_claim_types(area, capsys):
    from app.job_analysis.role_classification.boundaries.__main__ import main
    fixtures = Path(__file__).resolve().parents[1] / 'fixtures/role_classification'
    common = ['--state', str(area / 'state.db'), '--output', str(area / 'out')]
    assert main(['run', *common, '--input', str(fixtures / 'boundaries.input.json'), '--dataset', 'synthetic-b34',
        '--submission', str(fixtures / 'boundaries.submission.json'), '--family-taxonomy', str(V3)]) == 0
    identity = json.loads(capsys.readouterr().out)['run_id']
    saved = (area / 'out' / (identity + '.json')).read_bytes()
    report = json.loads(saved)
    assert [m['body']['assessments'][0]['kind'] for m in report['members']] == [
        'family_identifiable_job_unknown', 'integrated_composite_candidate',
        'possible_multiple_positions', 'competing_canonical_candidates']
    assert [len(m['body']['position_target_proposals']) for m in report['members']] == [0, 0, 2, 0]
    assert main(['replay', *common, '--run', identity]) == 0
    assert (area / 'out' / (identity + '.json')).read_bytes() == saved


def test_actual_module_entrypoint_run_review_export_and_replay(area):
    fixtures = Path(__file__).resolve().parents[1] / 'fixtures/role_classification'
    common = ['--state', str(area / 'state.db'), '--output', str(area / 'out')]
    def cli(*args):
        result = subprocess.run([sys.executable, '-X', 'utf8', '-m',
            'app.job_analysis.role_classification.boundaries', *args], capture_output=True, text=True, encoding='utf-8')
        assert result.returncode == 0, result.stderr
        return json.loads(result.stdout)
    run_id = cli('run', *common, '--input', str(fixtures / 'boundaries.input.json'), '--dataset', 'synthetic-b34',
        '--submission', str(fixtures / 'boundaries.submission.json'), '--family-taxonomy', str(V3))['run_id']
    path = area / 'out' / (run_id + '.json')
    saved = path.read_bytes()
    report = json.loads(saved)
    ev = event(report, target_id='jd1-assessment-a')
    event_path = area / 'event.json'
    event_path.write_text(json.dumps(ev, ensure_ascii=False), encoding='utf-8')
    cli('review', '--state', str(area / 'state.db'), '--result', report['members'][0]['result_id'], '--event', str(event_path))
    export_id = cli('export-reviews', *common, '--run', run_id)['export_id']
    export_saved = (area / 'out' / (export_id + '.json')).read_bytes()
    for identity, original in [(run_id, saved), (export_id, export_saved)]:
        cli('replay', *common, '--run', identity)
        assert (area / 'out' / (identity + '.json')).read_bytes() == original
    assert len(json.loads(export_saved)['members'][0]['reviews']) == 1

"""Synthetic lifecycle, isolated SQLite, historical replay and real process failures."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

from test_foundation_inputs import area
from test_canonical_catalog import draft, source


def write(root, name, value):
    path = root / name
    path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
    return path


def start(root, store, **kwargs):
    from app.job_analysis.canonical_catalog.runner import execute
    return execute(store, write(root, 'draft.json', draft(root)), root, **kwargs)


def event(root, report, **changes):
    from app.job_analysis.foundation.inputs import digest
    candidate = report['catalog']['candidates'][0]
    return dict(schema_version='c35-review-1', snapshot_id=report['run_id'], candidate_id=candidate['id'],
        candidate_sha256=digest(candidate), decision='reviewed_accepted', reviewer='Synthetic Reviewer',
        basis='Synthetic individual definition review', source=source(root, 'review.md', f"Synthetic review of {candidate['id']} {digest(candidate)} {report['run_id']}"),
        confirmed_responsibilities=True, confirmed_boundaries=True, confirmed_family=True,
        mode='synthetic_only', supersedes=None) | changes


def reviewed(root, store, report, **changes):
    from app.job_analysis.canonical_catalog.runner import review
    return review(store, report['run_id'], write(root, 'event.json', event(root, report, **changes)), root)


def manifest(root, report, review_id, **changes):
    from app.job_analysis.foundation.inputs import digest
    c = report['catalog']['candidates'][0]
    ref = source(root, 'confirmation.md', f"Synthetic approve {c['id']} {digest(c)} {report['run_id']}")
    return dict(schema_version='c35-release-manifest-1', revision='release-v1', snapshot_id=report['run_id'],
        mode='synthetic_only', previous_release_id=None,
        approvals=[dict(candidate_id=c['id'], candidate_sha256=digest(c), review_id=review_id, confirmation_source=ref)]) | changes


def test_synthetic_full_cycle_and_no_jd_required(area):
    from app.job_analysis.canonical_catalog.store import CatalogStore
    from app.job_analysis.canonical_catalog.runner import export, replay
    with CatalogStore(area / 'state.db') as store:
        report = start(area, store)
        from app.job_analysis.foundation.inputs import digest
        assert report['candidate_versions'] == {c['id']: digest(c) for c in report['catalog']['candidates']}
        before = export(store, report['run_id'])
        assert before['states']['role-a'] == 'candidate'
        identity = reviewed(area, store, report)
        accepted = export(store, report['run_id'])
        assert accepted['states']['role-a'] == 'reviewed_accepted'
        release = export(store, report['run_id'], write(area, 'release.json', manifest(area, report, identity)), area)
        assert release['states']['role-a'] == 'admitted'
        assert release['synthetic_only'] is True and release['formal_jobs'] == []
        assert release['simulated_jobs'][0]['id'] == 'role-a'
        assert release['classification_complete'] is False and release['formal_statistics_eligible'] is False
        assert replay(store, before['run_id']) == before
        assert replay(store, release['run_id']) == release


def test_manual_strings_only_produce_release_proposal(area):
    from app.job_analysis.canonical_catalog.store import CatalogStore
    from app.job_analysis.canonical_catalog.runner import export
    with CatalogStore(area / 'state.db') as store:
        r = start(area, store)
        ev = reviewed(area, store, r, mode='manual_pending', reviewer='User Name')
        result = export(store, r['run_id'], write(area, 'release.json', manifest(area, r, ev, mode='release_proposal')), area)
        assert result['formal_jobs'] == [] and result['simulated_jobs'] == []
        assert result['states']['role-a'] == 'awaiting_external_approval'
        assert result['identity_verified'] is False
        assert result['proposed_jobs'][0]['id'] == 'role-a'


@pytest.mark.parametrize('change', ['version', 'hash', 'target', 'no_reviewer', 'missing_source', 'false_source',
    'core_unconfirmed', 'boundary_unconfirmed', 'family_unconfirmed', 'wrong_family', 'b32_event', 'unrelated_source'])
def test_bad_reviews_are_atomic_and_cannot_supply_approval(area, change):
    from app.job_analysis.canonical_catalog.store import CatalogStore
    from app.job_analysis.canonical_catalog.runner import review, export
    with CatalogStore(area / 'state.db') as store:
        r = start(area, store)
        ev = event(area, r)
        if change == 'version': ev['snapshot_id'] = 'snapshot-missing'
        if change == 'hash': ev['candidate_sha256'] = '0' * 64
        if change == 'target': ev['candidate_id'] = 'missing'
        if change == 'no_reviewer': ev['reviewer'] = ' '
        if change == 'missing_source': del ev['source']
        if change == 'false_source': ev['source']['quote'] = 'not present'
        if change == 'core_unconfirmed': ev['confirmed_responsibilities'] = False
        if change == 'boundary_unconfirmed': ev['confirmed_boundaries'] = False
        if change == 'family_unconfirmed': ev['confirmed_family'] = False
        if change == 'wrong_family': ev['family_id'] = 'data_ai'
        if change == 'b32_event': ev['schema_version'] = 'b32-review-1'
        if change == 'unrelated_source': ev['source'] = source(area, 'unrelated.md', 'Generic approval of product principles')
        with pytest.raises((ValueError, OSError)):
            review(store, r['run_id'], write(area, 'bad.json', ev), area)
        assert export(store, r['run_id'])['states']['role-a'] == 'candidate'


@pytest.mark.parametrize('change', ['missing_review', 'old_version', 'wrong_hash', 'duplicate', 'draft_source',
    'review_source', 'fabricated_source', 'mode_mismatch', 'unknown_previous'])
def test_release_manifest_gate(area, change):
    from app.job_analysis.canonical_catalog.store import CatalogStore
    from app.job_analysis.canonical_catalog.runner import export
    with CatalogStore(area / 'state.db') as store:
        r = start(area, store)
        ev = reviewed(area, store, r)
        m = manifest(area, r, ev)
        approval = m['approvals'][0]
        if change == 'missing_review': approval['review_id'] = 'review-missing'
        if change == 'old_version': m['snapshot_id'] = 'snapshot-old'
        if change == 'wrong_hash': approval['candidate_sha256'] = '0' * 64
        if change == 'duplicate': m['approvals'].append(deepcopy(approval))
        if change == 'draft_source': approval['confirmation_source'] = r['catalog']['candidates'][0]['definition_basis'][0]
        if change == 'review_source': approval['confirmation_source'] = event(area, r)['source']
        if change == 'fabricated_source': approval['confirmation_source']['sha256'] = '0' * 64
        if change == 'mode_mismatch': m['mode'] = 'release_proposal'
        if change == 'unknown_previous': m['previous_release_id'] = 'export-missing'
        with pytest.raises((ValueError, OSError)):
            export(store, r['run_id'], write(area, 'bad-release.json', m), area)


@pytest.mark.parametrize('decision', ['rejected', 'deferred'])
def test_later_event_requires_explicit_supersession_and_blocks_stale_approval(area, decision):
    from app.job_analysis.canonical_catalog.store import CatalogStore
    from app.job_analysis.canonical_catalog.runner import review, export
    with CatalogStore(area / 'state.db') as store:
        r = start(area, store)
        ev = reviewed(area, store, r)
        old_export = export(store, r['run_id'])
        with pytest.raises(ValueError):
            reviewed(area, store, r, decision=decision)
        reviewed(area, store, r, decision=decision, supersedes=ev)
        assert export(store, r['run_id'])['states']['role-a'] == decision
        with pytest.raises(ValueError):
            export(store, r['run_id'], write(area, 'stale.json', manifest(area, r, ev)), area)
        from app.job_analysis.canonical_catalog.runner import replay
        assert replay(store, old_export['run_id']) == old_export


@pytest.mark.parametrize('change', ['definition', 'family', 'alias', 'boundary', 'rules'])
def test_new_version_cannot_reuse_previous_review(area, change):
    from app.job_analysis.canonical_catalog.store import CatalogStore
    from app.job_analysis.canonical_catalog.runner import execute, review
    with CatalogStore(area / 'state.db') as store:
        r = start(area, store)
        ev = event(area, r)
        value = deepcopy(r['catalog'])
        value['revision'] = 'draft-v2'
        c = value['candidates'][0]
        if change == 'definition': c['deliverables'] = ['新的交付成果']
        if change == 'family': c['family_id'] = 'test_quality_engineering'
        if change == 'alias': c['proposed_aliases'] = ['另一别名']
        if change == 'boundary': c['neighbors'][0]['distinction'] = '修改后的区分边界'
        new = execute(store, write(area, 'v2.json', value), area, revision='rules-v2' if change == 'rules' else 'v1')
        with pytest.raises(ValueError):
            review(store, new['run_id'], write(area, 'old-event.json', ev), area)


def test_same_named_revision_cannot_overwrite_and_failed_round_rolls_back(area, monkeypatch):
    from app.job_analysis.canonical_catalog.store import CatalogStore
    from app.job_analysis.canonical_catalog import runner
    with CatalogStore(area / 'state.db') as store:
        r = start(area, store)
        value = deepcopy(r['catalog'])
        value['candidates'][0]['deliverables'] = ['changed']
        with pytest.raises(ValueError):
            runner.execute(store, write(area, 'mutated.json', value), area)
        value['revision'] = 'draft-v2'
        def fault(stage):
            if stage == 'before_commit': raise RuntimeError('synthetic interruption')
        monkeypatch.setattr(runner, 'checkpoint', fault)
        with pytest.raises(RuntimeError):
            runner.execute(store, write(area, 'v2.json', value), area)
        assert store.conn.execute('SELECT COUNT(*) FROM c35_revisions').fetchone()[0] == 1


def test_append_only_and_saved_source_tamper_detection(area):
    from app.job_analysis.canonical_catalog.store import CatalogStore
    from app.job_analysis.canonical_catalog import runner
    with CatalogStore(area / 'state.db') as store:
        r = start(area, store)
        for op in ['UPDATE c35_artifacts SET body=body', 'DELETE FROM c35_artifacts',
                   'INSERT OR REPLACE INTO c35_artifacts SELECT * FROM c35_artifacts']:
            with pytest.raises(sqlite3.IntegrityError):
                with store.conn: store.conn.execute(op)
        (area / 'basis.md').unlink()
        (area / 'draft.json').unlink()
        assert runner.replay(store, r['run_id']) == r


@pytest.mark.parametrize('stage', ['before_commit', 'after_commit', 'after_stage_output', 'after_output'])
def test_actual_process_exit_and_replay_recovery(area, stage):
    from app.job_analysis.canonical_catalog.store import CatalogStore
    from app.job_analysis.canonical_catalog.runner import replay, execute
    path = write(area, 'draft.json', draft(area))
    script = '''
import os, sys
from pathlib import Path
from app.job_analysis.canonical_catalog import runner
from app.job_analysis.foundation import runner as publication
from app.job_analysis.canonical_catalog.store import CatalogStore
root, stage = Path(sys.argv[1]), sys.argv[2]
hook = lambda point: os._exit(71) if point == stage else None
runner.checkpoint = publication.checkpoint = hook
with CatalogStore(root / 'state.db') as store:
    runner.execute(store, root / 'draft.json', root, output=root / 'out')
'''
    done = subprocess.run([sys.executable, '-X', 'utf8', '-c', script, str(area), stage], capture_output=True)
    assert done.returncode == 71, done.stderr.decode()
    with CatalogStore(area / 'state.db') as store:
        rows = store.conn.execute("SELECT id FROM c35_artifacts WHERE kind='snapshot'").fetchall()
        assert len(rows) == int(stage != 'before_commit')
        if rows: assert replay(store, rows[0][0])['catalog'] == draft(area)
        result = execute(store, path, area, output=area / 'out')
        assert (area / 'out' / (result['run_id'] + '.json')).exists()
        assert not list((area / 'out').glob('*.tmp'))


def test_output_failure_replays_and_protects_sources(area, monkeypatch):
    from app.job_analysis.canonical_catalog.store import CatalogStore
    from app.job_analysis.canonical_catalog import runner
    with CatalogStore(area / 'state.db') as store:
        def fail(*args): raise OSError('synthetic output failure')
        with monkeypatch.context() as m:
            m.setattr(runner, 'publish', fail)
            with pytest.raises(OSError): start(area, store, output=area / 'out')
        identity = store.conn.execute('SELECT id FROM c35_artifacts').fetchone()[0]
        assert runner.replay(store, identity)['formal_jobs'] == []
        with pytest.raises(ValueError): start(area, store, output=area)


def test_real_cli_run_review_export_replay(area):
    path = write(area, 'draft.json', draft(area))
    common = ['--state', str(area / 'state.db')]
    out = ['--output', str(area / 'out')]
    def cli(*args):
        done = subprocess.run([sys.executable, '-X', 'utf8', '-m', 'app.job_analysis.canonical_catalog', *args],
            capture_output=True, text=True, encoding='utf-8')
        assert done.returncode == 0, done.stderr
        return json.loads(done.stdout)['artifact_id']
    identity = cli('run', *common, *out, '--catalog', str(path), '--source-root', str(area))
    r = json.loads((area / 'out' / (identity + '.json')).read_text(encoding='utf-8'))
    ev = cli('review', *common, '--snapshot', identity, '--event', str(write(area, 'event.json', event(area, r))), '--source-root', str(area))
    ex = cli('export', *common, *out, '--snapshot', identity, '--manifest', str(write(area, 'release.json', manifest(area, r, ev))), '--source-root', str(area))
    for item in [identity, ex]:
        file = area / 'out' / (item + '.json')
        saved = file.read_bytes()
        cli('replay', *common, *out, '--artifact', item)
        assert saved == file.read_bytes()


def test_actual_upstream_mixed_histories_preserved(area):
    from test_role_boundary_storage import test_actual_A_B1_B2_B22_B30_B31_B32_histories_and_running_A_untouched
    from app.job_analysis.canonical_catalog.store import CatalogStore
    from app.job_analysis.canonical_catalog.runner import export
    test_actual_A_B1_B2_B22_B30_B31_B32_histories_and_running_A_untouched(area)
    with CatalogStore(area / 'state.db') as store:
        tables = [r[0] for r in store.conn.execute("SELECT name FROM sqlite_master WHERE type='table'") if not r[0].startswith('c35_')]
        before = {t: [tuple(r) for r in store.conn.execute(f'SELECT * FROM "{t}"')] for t in tables}
        report = start(area, store)
        reviewed(area, store, report)
        export(store, report['run_id'])
        for table, rows in before.items():
            assert [tuple(r) for r in store.conn.execute(f'SELECT * FROM "{table}"')] == rows
        assert store.conn.execute("SELECT COUNT(*) FROM runs WHERE status='running'").fetchone()[0] == 1


def test_actual_old_family_fixture_replays_unchanged(area):
    from test_role_boundary_storage import test_old_actual_v1_v2_and_all_upstream_rows_preserved_in_mixed_database
    from app.job_analysis.canonical_catalog.store import CatalogStore
    test_old_actual_v1_v2_and_all_upstream_rows_preserved_in_mixed_database(area)
    with CatalogStore(area / 'mixed.db') as store:
        before = {t: [tuple(r) for r in store.conn.execute(f'SELECT * FROM {t}')] for t in ['b31_reports', 'b32_reports', 'b32_exports', 'b34_reports']}
        start(area, store)
        for t, rows in before.items(): assert [tuple(r) for r in store.conn.execute(f'SELECT * FROM {t}')] == rows


def test_release_cannot_use_copied_review_as_independent_confirmation(area):
    from app.job_analysis.canonical_catalog.store import CatalogStore
    from app.job_analysis.canonical_catalog.runner import export
    with CatalogStore(area / 'state.db') as store:
        r = start(area, store)
        ev = reviewed(area, store, r)
        m = manifest(area, r, ev)
        copied = source(area, 'copied-review.md', (area / 'review.md').read_text(encoding='utf-8'))
        m['approvals'][0]['confirmation_source'] = copied
        with pytest.raises(ValueError):
            export(store, r['run_id'], write(area, 'release.json', m), area)


@pytest.mark.parametrize('mode', ['synthetic_only', 'manual_pending'])
def test_release_cannot_use_copied_review_event_json_as_confirmation(area, mode):
    from app.job_analysis.canonical_catalog.store import CatalogStore
    from app.job_analysis.canonical_catalog.runner import export
    with CatalogStore(area / 'state.db') as store:
        r = start(area, store)
        ev = reviewed(area, store, r, mode=mode)
        m = manifest(area, r, ev, mode='synthetic_only' if mode == 'synthetic_only' else 'release_proposal')
        copied = source(area, 'copied-event.json', (area / 'event.json').read_text(encoding='utf-8'))
        m['approvals'][0]['confirmation_source'] = copied
        with pytest.raises(ValueError):
            export(store, r['run_id'], write(area, 'release.json', m), area)


def test_release_revision_cannot_name_two_different_manifests(area):
    from app.job_analysis.canonical_catalog.store import CatalogStore
    from app.job_analysis.canonical_catalog.runner import export
    with CatalogStore(area / 'state.db') as store:
        r = start(area, store)
        ev = reviewed(area, store, r)
        m = manifest(area, r, ev)
        export(store, r['run_id'], write(area, 'release.json', m), area)
        m['approvals'][0]['confirmation_source'] = source(area, 'new-confirmation.md', m['approvals'][0]['confirmation_source']['quote'] + ' new')
        with pytest.raises(ValueError):
            export(store, r['run_id'], write(area, 'mutated-release.json', m), area)


@pytest.mark.parametrize('operation', ['review', 'export'])
def test_event_and_manifest_parse_the_exact_bytes_saved(area, monkeypatch, operation):
    from app.job_analysis.canonical_catalog.store import CatalogStore
    from app.job_analysis.canonical_catalog import runner
    with CatalogStore(area / 'state.db') as store:
        r = start(area, store)
        ev = reviewed(area, store, r)
        if operation == 'review':
            value = event(area, r, decision='deferred', supersedes=ev)
        else:
            value = manifest(area, r, ev)
        path = write(area, 'race.json', value)
        original = runner.raw_source
        def switch_after_read(file):
            raw = original(file)
            if Path(file) == path:
                changed = deepcopy(value)
                if operation == 'review': changed['reviewer'] = 'Other Reviewer'
                else: changed['revision'] = 'other-release'
                write(area, 'race.json', changed)
            return raw
        monkeypatch.setattr(runner, 'raw_source', switch_after_read)
        if operation == 'review':
            identity = runner.review(store, r['run_id'], path, area)
            saved = runner.replay(store, identity)
            assert saved['event'] == value
        else:
            saved = runner.export(store, r['run_id'], path, area)
            assert saved['release_manifest'] == value


def test_new_definition_release_requires_new_review_and_preserves_old_export(area):
    from app.job_analysis.canonical_catalog.store import CatalogStore
    from app.job_analysis.canonical_catalog import runner
    with CatalogStore(area / 'state.db') as store:
        r = start(area, store)
        ev = reviewed(area, store, r)
        old = runner.export(store, r['run_id'], write(area, 'release.json', manifest(area, r, ev)), area)
        value = deepcopy(r['catalog'])
        value['revision'] = 'draft-v2'
        value['candidates'][0]['deliverables'] = ['新定义的技术成果']
        second = runner.execute(store, write(area, 'v2.json', value), area)
        with pytest.raises(ValueError):
            runner.export(store, second['run_id'], write(area, 'bad.json', manifest(area, r, ev)), area)
        fresh_review = reviewed(area, store, second)
        m = manifest(area, second, fresh_review, revision='release-v2', previous_release_id=old['run_id'])
        new = runner.export(store, second['run_id'], write(area, 'new.json', m), area)
        assert new['simulated_jobs'][0]['deliverables'] != old['simulated_jobs'][0]['deliverables']
        assert runner.replay(store, old['run_id']) == old


def test_release_cannot_silently_drop_an_existing_job(area):
    from app.job_analysis.canonical_catalog.store import CatalogStore
    from app.job_analysis.canonical_catalog import runner
    with CatalogStore(area / 'state.db') as store:
        r = start(area, store)
        ev = reviewed(area, store, r)
        m = manifest(area, r, ev)
        old = runner.export(store, r['run_id'], write(area, 'release.json', m), area)
        # Review the other candidate independently; no default name merge across families.
        swapped = deepcopy(r)
        swapped['catalog']['candidates'].reverse()
        other_review = reviewed(area, store, swapped)
        new = manifest(area, swapped, other_review, revision='release-v2', previous_release_id=old['run_id'])
        with pytest.raises(ValueError):
            runner.export(store, r['run_id'], write(area, 'dropped.json', new), area)

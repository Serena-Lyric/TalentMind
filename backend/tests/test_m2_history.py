"""Old product results are readable without starting/migrating the retired engine."""
import hashlib
import json
import sqlite3

import pytest

from app.job_analysis.foundation.inputs import canonical, digest


@pytest.fixture
def old_store(tmp_path):
    root = tmp_path / 'history'
    root.mkdir()
    run_id = 'a' * 32
    inputs = canonical([{'id': 7, 'source': 'synthetic', 'raw_text': 'Python'}])
    folder = root / 'runs' / run_id
    folder.mkdir(parents=True)
    (folder / 'input.json').write_text(inputs, encoding='utf-8')
    with sqlite3.connect(root / 'workflow.sqlite3') as db:
        db.execute('CREATE TABLE product_runs(id TEXT, input_json TEXT, input_sha256 TEXT, selection TEXT, provenance TEXT, versions TEXT, parent_id TEXT, status TEXT, created_at TEXT, finished_at TEXT, reason TEXT)')
        db.execute('CREATE TABLE product_items(run_id TEXT, ordinal INTEGER, body TEXT)')
        db.execute('CREATE TABLE product_reports(run_id TEXT, body TEXT, sha256 TEXT)')
        db.execute('CREATE TABLE product_reviews(id INTEGER, run_id TEXT, body TEXT, sha256 TEXT)')
        db.execute('INSERT INTO product_runs VALUES(?,?,?,?,?,?,?,?,?,?,?)', (run_id, inputs, hashlib.sha256(inputs.encode()).hexdigest(), '{}', '{}', '{"revision":"historic"}', None, 'interrupted', '2026-10-21', None, 'stopped'))
        report = {'run_id': run_id, 'items': [], 'versions': {'revision': 'historic'}}
        db.execute('INSERT INTO product_reports VALUES(?,?,?)', (run_id, canonical(report), digest(report)))
    db.close()
    try:
        yield root, run_id
    finally:
        # Unique fixture directory only; verify no surviving fixture DB.
        import shutil
        shutil.rmtree(root)
        assert not root.exists()


def test_history_never_creates_store(tmp_path):
    from app.job_analysis.product.workflow import History
    root = tmp_path / 'missing'
    assert History(root).list_runs() == []
    assert not root.exists()


def test_history_is_readonly_and_preserves_original_status_and_versions(old_store):
    from app.job_analysis.product.workflow import History
    root, run_id = old_store
    before = (root / 'workflow.sqlite3').read_bytes()
    history = History(root)
    assert history.list_runs()[0]['status'] == 'interrupted'
    result = history.get(run_id)
    assert result['versions']['revision'] == 'historic'
    assert result['execution_available'] is False
    assert result['disposition'] == 'historical_read_only_select_inputs_for_new_delivery'
    assert history.report(run_id)['versions']['revision'] == 'historic'
    assert history.review_export(run_id)['run']['versions']['revision'] == 'historic'
    assert history._inputs(run_id)[0]['id'] == 7
    with history.db() as db, pytest.raises(sqlite3.OperationalError, match='readonly'):
        db.execute('DELETE FROM product_runs')
    assert (root / 'workflow.sqlite3').read_bytes() == before
    assert not hasattr(history, 'start')
    assert not hasattr(history, 'replay')


def test_history_detects_tampered_sources_and_reports(old_store):
    from app.job_analysis.product.workflow import History
    root, run_id = old_store
    history = History(root)
    (root / 'runs' / run_id / 'input.json').write_text('[]', encoding='utf-8')
    with pytest.raises(ValueError, match='integrity'):
        history._inputs(run_id)
    with sqlite3.connect(root / 'workflow.sqlite3') as db:
        db.execute("UPDATE product_reports SET body='{}'")
    db.close()
    with pytest.raises(ValueError, match='integrity'):
        history.report(run_id)
    with pytest.raises(ValueError):
        history.get('../escape')


def test_saved_graph_is_read_without_generation_and_checks_every_artifact(old_store):
    from app.job_analysis.product.workflow import History
    from app.graph.product_bundle import read_bundle, graph_info
    root, run_id = old_store
    history = History(root)
    report = dict(history.report(run_id), input_sha256=history._row(run_id)['input_sha256'], items=[{'input': history._inputs(run_id)[0]}])
    with sqlite3.connect(root / 'workflow.sqlite3') as db:
        db.execute('UPDATE product_reports SET body=?,sha256=?', (canonical(report), digest(report)))
    db.close()
    folder = root / 'graphs' / run_id
    folder.mkdir(parents=True)
    artifacts = {}
    for name in ('facts.json', 'sources.json', 'layout.json', 'derived.json'):
        raw = b'{}'
        (folder / name).write_bytes(raw)
        artifacts[name] = hashlib.sha256(raw).hexdigest()
    binding = dict(run_id=run_id, report_sha256=digest(report), input_sha256=report['input_sha256'], versions=report['versions'])
    implementation = {'old': 'fixed'}
    manifest = dict(m2_product=binding, implementation=implementation, data_version=digest(dict(m2=binding, projection=implementation)), artifacts=artifacts)
    (folder / 'manifest.json').write_text(canonical(manifest) + '\n', encoding='utf-8')
    assert read_bundle(history, run_id) == manifest
    assert graph_info(history, run_id)['manifest'] == manifest
    (folder / 'facts.json').write_bytes(b'{"changed":true}')
    with pytest.raises(ValueError, match='hash'):
        read_bundle(history, run_id)
    with pytest.raises(ValueError):
        read_bundle(history, run_id, '../workflow.sqlite3')

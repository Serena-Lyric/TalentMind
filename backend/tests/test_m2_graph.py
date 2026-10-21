"""M2 reports project into private M3 bundles without rerunning analysis."""
import shutil

import pytest

from app.job_analysis.product import source
from app.job_analysis.product.workflow import Workflow


@pytest.fixture
def completed(tmp_path, monkeypatch):
    rows = [dict(id=1, source='boss', job_title='后端工程师',
                 raw_text='岗位职责：负责软件开发。\n任职要求：必须掌握 Python。'),
            dict(id=2, source='boss', job_title='空正文', raw_text=None)]
    monkeypatch.setattr(source, 'read_mysql', lambda _: (rows, {'kind': 'synthetic'}))
    engine = Workflow(tmp_path / 'product')
    run = engine.create(source.Selection(limit=2))
    engine.start(run['run_id'])
    engine.join(20)
    assert not engine.busy
    try:
        yield engine, run['run_id']
    finally:
        engine.join(20)
        shutil.rmtree(engine.root)
        assert not engine.root.exists()


def test_graph_reuses_exact_report_and_frozen_input(completed, monkeypatch):
    from app.graph.product_bundle import build_bundle, read_bundle
    engine, run_id = completed
    report = engine.report(run_id)
    monkeypatch.setattr(engine, '_execute_stage', lambda *args: pytest.fail('analysis rerun'))
    manifest = build_bundle(engine, run_id)
    assert manifest['m2_product']['run_id'] == run_id
    assert manifest['m2_product']['versions'] == report['versions']
    assert manifest['input_sha256'] == report['input_sha256']
    assert manifest['counts']['input'] == 2
    assert manifest['counts']['eligible_jd'] == 1
    assert manifest['formal_statistics_eligible'] is False
    graph = read_bundle(engine, run_id, 'facts.json')
    assert any(n['type'] == 'job' for n in graph['nodes'])
    assert all(e['type'] == 'HAS_SKILL_STATEMENT' and not e['formal_statistics_eligible'] for e in graph['edges'])
    assert all(e['semantic_review'] == 'unreviewed' for e in graph['edges'])
    sources = read_bundle(engine, run_id, 'sources.json')
    assert len(sources['records']) == 2 and not sources['records'][1]['eligible']
    assert sources['records'][0]['m2_reference']['b22']['run_id'] == report['items'][0]['stages']['b22']['run_id']
    assert build_bundle(engine, run_id) == manifest
    assert engine.report(run_id) == report
    monkeypatch.setattr('app.graph.product_bundle.implementation', lambda: {'new_generator': 'later'})
    assert read_bundle(engine, run_id) == manifest
    assert build_bundle(engine, run_id) == manifest


def test_graph_rejects_tampered_input_or_artifact(completed):
    from app.graph.product_bundle import build_bundle, read_bundle
    engine, run_id = completed
    build_bundle(engine, run_id)
    path = engine.root / 'graphs' / run_id / 'facts.json'
    path.write_text('{}', encoding='utf-8')
    with pytest.raises(ValueError, match='hash'):
        read_bundle(engine, run_id, 'facts.json')
    with pytest.raises(ValueError):
        read_bundle(engine, run_id, '../../workflow.sqlite3')
    with pytest.raises(ValueError):
        build_bundle(engine, '../other')
    path = engine.root / 'runs' / run_id / 'input.json'
    path.write_text('[]', encoding='utf-8')
    with pytest.raises(ValueError, match='input'):
        build_bundle(engine, run_id)


def test_graph_requires_published_report(tmp_path):
    from app.graph.product_bundle import build_bundle
    engine = Workflow(tmp_path / 'queued')
    try:
        run = engine._freeze([dict(id=1, source='boss', job_title='工程师', raw_text='Python')], {}, {}, 'v1')
        with pytest.raises(ValueError, match='published'):
            build_bundle(engine, run['run_id'])
    finally:
        shutil.rmtree(engine.root)

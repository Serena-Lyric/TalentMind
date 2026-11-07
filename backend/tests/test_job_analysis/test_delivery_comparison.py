from copy import deepcopy


def run(name, text='Python 或 Java', knowledge='k1'):
    return {'run_id': name, 'request_sha256': name, 'status': 'completed', 'knowledge': {'sha256': knowledge}, 'items': [{'namespace': 'mysql-jd_pool', 'jd_id': '7', 'input': {'raw_text': text}, 'input_version': text, 'analysis_sha256': 'a1', 'analysis': {'claims': [{'text': text, 'requirement': {'combination': 'any'}}]}, 'alignment': {'version': knowledge}, 'roles': {}, 'work': None}], 'work': None}


def test_comparison_preserves_input_and_knowledge_differences_without_market_claim():
    from app.job_analysis.delivery.comparison import compare_runs
    a, b = run('old'), run('new', knowledge='k2')
    before = deepcopy(a)
    result = compare_runs(a, b)
    assert a == before
    assert result['before_run'] == 'old'
    assert result['after_run'] == 'new'
    assert result['market_change_verified'] is False
    item = result['items'][0]
    assert item['source_comparable'] is True
    layers = {layer['kind']: layer for layer in item['layers']}
    assert layers['input']['changed'] is False
    assert layers['knowledge']['changed'] is True
    assert layers['analysis']['before']['claims'][0]['requirement']['combination'] == 'any'


def test_unrelated_sources_and_missing_results_never_become_changes_or_zero():
    from app.job_analysis.delivery.comparison import compare_runs
    a, b = run('old'), run('new')
    b['items'][0]['jd_id'] = '8'
    result = compare_runs(a, b)
    assert len(result['items']) == 2
    assert all(not item['source_comparable'] for item in result['items'])
    assert all(layer['changed'] is None for item in result['items'] for layer in item['layers'])
    b['items'][0]['jd_id'] = '7'
    b['items'][0]['analysis'] = None
    layers = {layer['kind']: layer for layer in compare_runs(a, b)['items'][0]['layers']}
    assert layers['analysis']['changed'] is None
    assert layers['analysis']['available'] is False


def test_research_requires_same_registry_and_compares_content_not_counter():
    from app.job_analysis.delivery.comparison import compare_runs
    a, b = run('old'), run('new')
    a['work'] = {'binding': {'registry_id': 'one', 'revision': 1}, 'candidates': {'c': {'description': 'same'}}}
    b['work'] = {'binding': {'registry_id': 'two', 'revision': 1}, 'candidates': {'c': {'description': 'same'}}}
    assert compare_runs(a, b)['research']['changed'] is None
    b['work']['binding'] = {'registry_id': 'one', 'revision': 2}
    result = compare_runs(a, b)['research']
    assert result['available'] is True
    assert result['changed'] is False
    assert result['after_binding']['revision'] == 2

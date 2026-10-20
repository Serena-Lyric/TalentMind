"""Synthetic structural regressions; never a human real-JD benchmark."""
import json
from pathlib import Path
import tempfile

import pytest

from app.job_analysis.foundation.inputs import InputRecord
from app.job_analysis.semantics.rules import SkillSemanticAnalyzer
from app.job_analysis.semantics.validation import validate


@pytest.fixture
def tmp_path():
    with tempfile.TemporaryDirectory(prefix='talentmind-real-quality-test-') as area:
        yield Path(area)


def analyze(text):
    record = InputRecord.from_row('quality-fixture', dict(id=1, source='synthetic', job_title='工程师', raw_text=text))
    analyzer = SkillSemanticAnalyzer()
    return validate(analyzer.analyze(record), record, analyzer)


@pytest.mark.parametrize('text,state', [
    ('公司: 合成企业\n职位描述:\n岗位职责：1.负责开发软件接口。 任职要求：1、熟悉Python语言。', 'required'),
    ('职位描述： 岗位职责 1.开发软件接口。 职位要求 1.熟练使用Python。', 'required'),
    ('【任职条件】 1、熟悉Python。 【加分项】 1、熟悉Java。', 'required'),
    ('任职要求：(1)熟悉Python。 (2)不要求Java。', 'required'),
    ('加分项： 1、熟悉Python。', 'preferred'),
])
def test_inline_numbered_sections_keep_exact_unicode_offsets(text, state):
    result = analyze('😀\n' + text)
    statement = next(s for s in result['statements'] if s['skills'][0]['name'] == 'python')
    assert statement['state'] == state
    for evidence in (statement['evidence'], statement['context'], statement['skills'][0]['evidence']):
        assert ('😀\n' + text)[evidence['start']:evidence['end']] == evidence['quote']


def test_numbering_and_commas_keep_preference_negation_and_degrees_separate():
    result = analyze('任职要求：1、熟悉Python语言，精通Java。 2、不要求Go。 加分项：1、熟悉SQL。')
    assert [(s['skills'][0]['name'], s['state'], s['degree']) for s in result['statements']] == [
        ('python', 'required', 'familiar'), ('java', 'required', 'expert'),
        ('go', 'not_required', None), ('sql', 'preferred', 'familiar')]


def test_unparsed_sibling_cannot_certify_independent_scope():
    result = analyze('任职要求：1.熟悉Java语言，熟练掌握Spring框架及未知扩展组件。')
    assert [(s['skills'][0]['name'], s['state']) for s in result['statements']] == [
        ('java', 'uncertain'), ('spring', 'uncertain')]
    assert result['coverage'] == 'incomplete'


@pytest.mark.parametrize('text', [
    '任职要求：熟悉Python，熟悉Java二选一。',
    '任职要求：不要求熟悉Python，熟悉Java。',
    '任职要求：1.熟悉Python 2.熟悉Java（以上满足一项即可）。',
    '任职要求：1.熟悉Python 2.熟悉Java 3.以上技能均为加分。',
])
def test_review_shared_negation_choice_and_numbered_tail_scope(text):
    assert all(s['state'] != 'required' for s in analyze(text)['statements'])


@pytest.mark.parametrize('text,want', [
    ('公司：合成企业。岗位职责：负责开发软件接口。', 'in_scope'),
    ('岗位职责：负责后端服务的开发进度管理。', 'needs_review'),
    ('岗位职责：负责前端应用的开发工具采购。', 'needs_review'),
    ('岗位职责：负责前端应用的设计与开发进度管理。', 'needs_review'),
])
def test_review_activity_boundaries_and_inline_metadata(text, want):
    from app.job_analysis.screening.rules import screen
    record = InputRecord.from_row('quality-fixture', dict(id=1, source='synthetic', job_title='开发工程师', raw_text=text))
    assert screen(record, dict(activities=['software_development']))['scope_status'] == want


@pytest.mark.parametrize('text', [
    '任职要求：1、如果参与项目，则熟悉Python。',
    '任职要求：1、不熟悉Python也可以。',
    '公司介绍：1、熟悉Python。',
    '任职要求：1、熟悉Python或Java等至少一种语言。',
    '任职要求：1、熟悉Python，可能不需要Java。',
    '任职要求：1、熟悉Python，不要求Java或Go中的某些能力。',
    '任职要求：1、熟悉Python及未知工具FixtureTool。',
])
def test_unparsed_scope_and_groups_never_promote_to_required(text):
    assert all(s['state'] != 'required' for s in analyze(text)['statements'])


def test_holdout_export_selects_disjoint_id_window(tmp_path):
    from app.integration.real_jd_export import export_sql
    source = tmp_path / 'source.sql'
    source.write_text("CREATE TABLE `jd_pool` (\n `id` bigint,\n `source` text,\n `job_title` text,\n `raw_text` text\n);\nINSERT INTO `jd_pool` VALUES " +
        ','.join(f"({i},'boss','fixture','body')" for i in range(1, 7)) + ';\n', encoding='utf-8')
    export_sql(source, tmp_path / 'baseline', 2)
    result = export_sql(source, tmp_path / 'holdout', 2, offset=2)
    rows = json.loads((tmp_path / 'holdout/input.json').read_text(encoding='utf-8'))
    assert [r['id'] for r in rows] == [3, 4]
    assert result['offset'] == 2
    with pytest.raises(ValueError):
        export_sql(source, tmp_path / 'negative', 2, offset=-1)


@pytest.mark.parametrize('text', [
    '技能标签: 爬虫开发 互联网电商 软件/IT服务\n学历：本科',
    '岗位要求：熟练软件开发流程，热爱编程，有良好的代码风格。',
    '任职要求：详细设计经验 4）程序员：开发经验1年以上。',
])
def test_b1_metadata_and_cross_phrase_matches_are_not_work_activity(text):
    from app.job_analysis.screening.rules import screen
    record = InputRecord.from_row('quality-fixture', dict(id=1, source='synthetic', job_title='开发工程师', raw_text=text))
    assert screen(record, dict(activities=['software_development']))['scope_status'] == 'needs_review'


def test_b1_real_activity_survives_metadata_exclusion():
    from app.job_analysis.screening.rules import screen
    record = InputRecord.from_row('quality-fixture', dict(id=1, source='synthetic', job_title='开发工程师',
        raw_text='技能标签: Python\n岗位职责：负责开发软件接口。'))
    assert screen(record, dict(activities=['software_development']))['scope_status'] == 'in_scope'


@pytest.mark.parametrize('text', [
    '岗位职责：负责Java应用程序的设计与开发，包括需求分析与系统设计。',
    '岗位职责：负责公司后端业务系统的开发、迭代与功能优化。',
])
def test_b1_explicit_object_before_work_predicate_is_also_activity(text):
    from app.job_analysis.screening.rules import screen
    record = InputRecord.from_row('quality-fixture', dict(id=1, source='synthetic', job_title='开发工程师', raw_text=text))
    assert screen(record, dict(activities=['software_development']))['scope_status'] == 'in_scope'


def test_quality_comparison_requires_same_frozen_input_and_has_no_gold(tmp_path):
    from app.graph.real_pipeline import run_pipeline
    from app.graph.real_quality import compare, review_items
    source = tmp_path / 'input.json'
    source.write_text(json.dumps([dict(id=1, source='synthetic', job_title='软件工程师',
        raw_text='负责开发软件接口。\n任职要求：1、熟悉Python。')]), encoding='utf-8')
    first, second = tmp_path / 'first', tmp_path / 'second'
    run_pipeline(source, 'quality-test', first)
    run_pipeline(source, 'quality-test', second)
    report = compare(first, second)
    assert report['metrics']['status'] == 'not_evaluated_no_human_signoff'
    assert report['metrics']['precision'] is report['metrics']['recall'] is None
    items = review_items(second)
    assert items and all(x['human_state'] is None and x['review_status'] == 'pending_human_review' for x in items)
    source.write_text(json.dumps([dict(id=2, source='synthetic', job_title='软件工程师', raw_text='负责开发软件接口。')]), encoding='utf-8')
    third = tmp_path / 'third'
    run_pipeline(source, 'quality-test', third)
    with pytest.raises(ValueError, match='frozen input'):
        compare(first, third)


def test_review_card_excerpt_omits_company_and_personal_metadata(tmp_path):
    from app.graph.real_pipeline import run_pipeline
    from app.graph.real_quality import review_items
    source = tmp_path / 'input.json'
    source.write_text(json.dumps([dict(id=1, source='boss', job_title='后端工程师',
        raw_text='后端工程师 20K 本科 私有机构甲 北京\n薪资：20K\n地点：北京')]), encoding='utf-8')
    bundle = tmp_path / 'bundle'
    run_pipeline(source, 'quality-review', bundle)
    items = review_items(bundle)
    assert len(items) == 1 and items[0]['platform'] == 'boss'
    assert '私有机构甲' not in json.dumps(items, ensure_ascii=False)
    assert items[0]['evidence']['quote'] == '后端'


@pytest.mark.parametrize('heading', ['任职要求', '加分项'])
def test_review_retains_section_context_and_each_skill_target(tmp_path, heading):
    from app.graph.real_pipeline import run_pipeline
    from app.graph.real_quality import review_items
    source = tmp_path / 'input.json'
    source.write_text(json.dumps([dict(id=1, source='synthetic', job_title='软件工程师',
        raw_text=f'负责开发软件接口。\n{heading}：Python优先，Java必备。')]), encoding='utf-8')
    bundle = tmp_path / 'bundle'
    run_pipeline(source, 'quality-review', bundle)
    items = [i for i in review_items(bundle) if i['kind'] == 'skill_statement']
    assert len(items) == 2 and len({i['sample_id'] for i in items}) == 2
    assert {i['target']['name'] for i in items} == {'python', 'java'}
    assert all(heading in i['context']['quote'] for i in items)


def test_diagnostic_experience_metadata_is_not_a_recovered_body():
    from app.graph.real_quality import input_kind
    assert input_kind(dict(payload=dict(raw_text='后端工程师 20K 本科', experience='3年'))) == 'list_or_unstructured_only_no_activity_inference'

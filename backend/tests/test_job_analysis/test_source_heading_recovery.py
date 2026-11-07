"""Plain section labels cannot disappear when a valid P1 quote is shortened."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from app.job_analysis.baseline.contract import validate_analysis
from app.job_analysis.foundation.inputs import InputRecord
from app.job_analysis.knowledge.work_semantics import source_work
from app.job_analysis.work_candidates.retrieval import compare_work
from app.job_analysis.work_candidates.storage import CandidateStore
from test_knowledge_alignment import evidence
from test_role_research_summary import build
from test_work_candidates import apply, batch, cleanup_p3_files, create, work


def cited(text, quote='开发订单接口', core=None):
    analysis = work('heading-history', text)
    analysis['claims'][0]['core'] = core
    analysis['claims'][0]['evidence'] = [evidence(InputRecord.from_row(analysis['namespace'], analysis['input_row']), quote)]
    validate_analysis(analysis)
    return analysis


@pytest.mark.parametrize('heading', ['协助职责', '【协助职责】'])
@pytest.mark.parametrize('full_quote', [False, True])
def test_plain_auxiliary_heading_survives_full_and_short_quote_through_batch(tmp_path, heading, full_quote):
    raw = heading + '\n开发订单接口。\n要求：Python。'
    b = cited(raw, heading + '\n开发订单接口' if full_quote else '开发订单接口')
    original = deepcopy(b)
    a = work('anchor', '开发订单接口')
    view = source_work(b['claims'][0], b)
    comparison = compare_work(b['claims'][0], a['claims'][0], b, a)
    assert view['importance'] == 'auxiliary'
    assert comparison['state'] == 'unresolved'
    assert comparison['reason_codes'] == ['responsibility_importance_differs']
    supports = build(b)['local_supports']
    assert supports and {item['importance'] for item in supports} == {'auxiliary'}
    with CandidateStore(tmp_path / 'state.db', create=True) as store:
        previous = apply(store, batch(store, 'anchor', [a], [create(a)]), [a])
        command = batch(store, 'incoming', [b])
        result = apply(store, command, [b])
        assert not any(item['jd_id'] == 'heading-history' for item in result['relations'].values())
        assert store.read(1) == previous
        assert apply(store, command, [b]) == result
    assert b == original


@pytest.mark.parametrize('heading', ['协助职责', '【协助职责】', '协助职责：'])
@pytest.mark.parametrize('full_quote', [False, True])
def test_structural_heading_is_not_an_extra_unknown_task_for_auxiliary_match(tmp_path, heading, full_quote):
    b = cited(heading + '\n开发订单接口。', heading + '\n开发订单接口' if full_quote else '开发订单接口')
    a = work('aux-anchor', '协助开发订单接口')
    original = deepcopy(b)
    view = source_work(b['claims'][0], b)
    assert view['importance'] == 'auxiliary'
    assert not view['source_explanation']['gaps']
    assert view['matched_source_units'][0]['governing_evidence']
    assert compare_work(b['claims'][0], a['claims'][0], b, a)['state'] == 'supported'
    with CandidateStore(tmp_path / 'state.db', create=True) as store:
        previous = apply(store, batch(store, 'anchor', [a], [create(a)]), [a])
        result = apply(store, batch(store, 'incoming', [b]), [b])
        relation = next(item for item in result['relations'].values() if item['jd_id'] == 'heading-history')
        assert relation['discovery']['kind'] == 'automatic_bounded_semantic'
        assert store.read(1) == previous
    assert b == original


@pytest.mark.parametrize('quote', ['编写', '软件', '代码'])
def test_partial_known_work_is_a_citation_restriction_not_unknown_vocabulary(quote):
    analysis = cited('编写软件采购合同及代码', quote, True)
    current = source_work(analysis['claims'][0], analysis)
    assert not current['source_explanation']['frames']
    assert current['source_explanation']['context_restricts_quote'] is True
    assert any(gap['reason'] == 'uncited_action_or_object' for gap in current['source_explanation']['gaps'])
    legacy = source_work(analysis['claims'][0], analysis, recover_plain_headings=False)
    assert legacy['source_explanation']['context_restricts_quote'] is False
    assert not any(gap['reason'] == 'uncited_action_or_object' for gap in legacy['source_explanation']['gaps'])


@pytest.mark.parametrize('heading', ['辅助任务', '配合职责', '[协助职责]', '（协助职责）',
                                    '二、【协助职责】', '1. 辅助职责', '【协助职责：】'])
def test_bounded_heading_forms_keep_exact_source_offsets(heading):
    analysis = cited(heading + '\r\n开发订单接口。')
    result = source_work(analysis['claims'][0], analysis)
    assert result['importance'] == 'auxiliary'
    task = next(unit for unit in result['matched_source_units'] if unit['view']['frames'])
    assert task['governing_evidence']
    row = analysis['input_row']
    for item in [task['evidence'], *task['governing_evidence']]:
        assert row[item['field']][item['start']:item['end']] == item['quote']


@pytest.mark.parametrize('aux,main', [('协助职责', '主要职责'), ('【协助职责】', '【主要职责】'),
                                   ('协助职责：', '主要职责'), ('辅助任务', '岗位职责：')])
def test_new_plain_primary_heading_resets_previous_auxiliary_scope(aux, main):
    analysis = cited(aux + '\n维护网络。\n' + main + '\n开发订单接口。', core=True)
    result = source_work(analysis['claims'][0], analysis)
    assert result['importance'] == 'core'
    assert not result['matched_source_units'][0]['governing_evidence']
    anchor = work('anchor', '开发订单接口')
    assert compare_work(analysis['claims'][0], anchor['claims'][0], analysis, anchor)['state'] == 'supported'


@pytest.mark.parametrize('prefix', ['协助开发其他接口。', '讨论协助职责相关事项', '【协助开发其他接口】'])
def test_ordinary_narrative_is_not_promoted_to_governing_heading(prefix):
    analysis = cited(prefix + '\n开发订单接口。', core=True)
    assert source_work(analysis['claims'][0], analysis)['importance'] == 'core'


def test_later_auxiliary_heading_does_not_change_prior_quote():
    analysis = cited('开发订单接口。\n【协助职责】\n维护网络。', core=True)
    result = source_work(analysis['claims'][0], analysis)
    assert result['importance'] == 'core'
    assert not result['matched_source_units'][0]['governing_evidence']


@pytest.mark.parametrize('heading,scope', [('无需承担：', 'negated'), ('如果项目需要：', 'conditional'), ('客户负责：', 'other_actor')])
def test_existing_colon_scope_controls_remain_restrictive(heading, scope):
    analysis = cited(heading + '\n开发订单接口。')
    assert source_work(analysis['claims'][0], analysis)['scope'] == scope


HISTORY = json.loads((Path(__file__).resolve().parents[1] / 'fixtures/knowledge/source_work_headings_v2.json').read_text(encoding='utf-8'))


@pytest.mark.parametrize('case', HISTORY['cases'], ids=lambda case: case['text'].replace('\n', ' / '))
def test_legacy_title_mode_is_deep_equal_to_fixed_pre_fix_source_result(case):
    analysis = cited(case['text'], case['quote'], case['core'])
    assert source_work(analysis['claims'][0], analysis, recover_plain_headings=False) == case['expected']

"""Closed source constraints supplement open model understanding, without DEV identifiers."""
from copy import deepcopy

import pytest

from test_understanding import claim,draft,quote,requirement,run
from test_understanding_audit import audit,patch_for,prior


def test_habit_is_a_disposition_not_an_engineering_execution_method():
    value=prior('要求：良好文档整理习惯','良好文档整理习惯','文档整理习惯')
    patch=patch_for(value)
    patch['requirements'][0]['requirement'].update(state='required',category='engineering_practice')
    result=audit(value,patch)
    assert result['analysis']['claims'][1]['requirement']['category']=='soft_skill'
    assert result['execution']['metadata']['semantic_policy_adjustments']


def test_open_tool_examples_without_a_quantifier_are_not_implicitly_any_of():
    value=prior('要求：日常使用 Atlas、Orion 等编辑工具者优先','日常使用 Atlas、Orion 等编辑工具者优先','Atlas')
    patch=patch_for(value)
    patch['requirements'][0]['requirement'].update(state='preferred',members=['Atlas','Orion'],
         combination='any_of',open_set=True,scope_evidence=[quote('日常使用 Atlas、Orion 等编辑工具者优先')])
    result=audit(value,patch)
    req=result['analysis']['claims'][1]['requirement']
    assert (req['combination'],req['open_set'],req['state'])==('unresolved',True,'preferred')


@pytest.mark.parametrize('separator',['。','；','，'])
def test_choice_quantifier_in_an_unrelated_clause_does_not_override_open_examples(separator):
    text=f'日常使用 Atlas、Orion 等工具{separator}英语或中文流利'
    value=prior(text,text,'Atlas');patch=patch_for(value)
    patch['requirements'][0]['requirement'].update(state='preferred',members=['Atlas','Orion'],
        combination='any_of',open_set=True,scope_evidence=[quote(text)])
    result=audit(value,patch)
    assert result['analysis']['claims'][1]['requirement']['combination']=='unresolved'


def test_reverse_negated_choice_quantifier_does_not_prove_any_of():
    text='任一 Atlas、Orion 工具都不要求'
    value=prior(text,text,'Atlas');patch=patch_for(value)
    patch['requirements'][0]['requirement'].update(state='required',members=['Atlas','Orion'],
        combination='any_of',open_set=True,scope_evidence=[quote(text)])
    result=audit(value,patch)
    assert result['analysis']['claims'][1]['requirement']['combination']=='unresolved'


@pytest.mark.parametrize('text',[
    '不要求全部掌握 Atlas、Orion 等工具',
    '并非全部 Atlas、Orion 等工具都必须掌握',
    '无需每项掌握 Atlas、Orion 等工具',
    '不要求全部掌握 Atlas、Orion',
])
def test_negative_all_quantifier_does_not_prove_an_all_of_requirement(text):
    value=prior(text,text,'Atlas');patch=patch_for(value)
    patch['requirements'][0]['requirement'].update(state='required',members=['Atlas','Orion'],
        combination='all_of',open_set='等' in text,scope_evidence=[quote(text)])
    result=audit(value,patch)
    assert result['analysis']['claims'][1]['requirement']['combination']=='unresolved'


def test_explicit_any_and_conventional_education_alternatives_are_preserved():
    for text,members,target in [
        ('要求：Atlas 或 Orion 等工具至少一种',['Atlas','Orion'],'capability'),
        ('要求：应用数学、统计学等相关专业',['应用数学','统计学'],'education'),
    ]:
        value=prior(text,text,members[0]);patch=patch_for(value)
        patch['requirements'][0]['requirement'].update(state='required',target=target,
            category=None if target=='education' else 'technical_skill',members=members,
            combination='any_of',open_set=True,scope_evidence=[quote(text)])
        assert audit(value,patch)['analysis']['claims'][1]['requirement']['combination']=='any_of'


def test_ellipsis_list_keeps_choice_when_members_expand_a_shared_suffix():
    text='有完整的数据产品或 BI 项目从 0 到 1 的成功交付经验'
    value=prior(text,text,'数据产品');patch=patch_for(value)
    members=['完整的数据产品项目从 0 到 1 的成功交付经验','完整的 BI 项目从 0 到 1 的成功交付经验']
    patch['requirements'][0]['requirement'].update(state='required',target='experience',category=None,
        members=members,combination='any_of',scope_evidence=[quote(text)])
    assert audit(value,patch)['analysis']['claims'][1]['requirement']['combination']=='any_of'


def test_compatibility_characters_do_not_erase_an_explicit_choice_quantifier():
    text='要求：Atlas、Orion ⾄少⼀种'
    value=prior(text,text,'Atlas');patch=patch_for(value)
    patch['requirements'][0]['requirement'].update(state='required',members=['Atlas','Orion'],
        combination='any_of',scope_evidence=[quote(text)])
    assert audit(value,patch)['analysis']['claims'][1]['requirement']['combination']=='any_of'


def test_nominal_platform_filter_does_not_become_candidate_domain_experience():
    text='任职要求：熟悉数据建模。其他信息 行业要求：工业制造'
    value=prior(text,text,'工业制造');patch=patch_for(value)
    patch['requirements'][0]['requirement'].update(state='mentioned',target='domain',category=None,
        scope_evidence=[quote('行业要求：工业制造')])
    result=audit(value,patch);req=result['analysis']['claims'][1]['requirement']
    assert (req['state'],req['target'])==('uncertain','unresolved')


def test_explicit_domain_tenure_is_not_erased_by_a_platform_header():
    text='其他信息 行业要求：需要工业制造行业经验至少四年'
    value=prior(text,text,'工业制造');patch=patch_for(value)
    patch['requirements'][0]['requirement'].update(state='required',target='experience',category=None,
        scope_evidence=[quote(text)])
    assert audit(value,patch)['analysis']['claims'][1]['requirement']['state']=='required'


def test_explicit_domain_preference_is_not_treated_as_an_unqualified_filter_label():
    text='其他信息 行业要求：工业制造领域优先'
    value=prior(text,text,'工业制造');patch=patch_for(value)
    patch['requirements'][0]['requirement'].update(state='preferred',target='domain',category=None,scope_evidence=[quote('行业要求：工业制造领域优先')])
    assert audit(value,patch)['analysis']['claims'][1]['requirement']['state']=='preferred'


def test_filter_location_is_based_on_the_field_not_on_a_wide_citation_start():
    text='其他信息 行业要求：工业制造'
    value=prior(text,text,'工业制造');patch=patch_for(value)
    patch['requirements'][0]['requirement'].update(state='mentioned',target='domain',category=None,scope_evidence=[quote(text)])
    assert audit(value,patch)['analysis']['claims'][1]['requirement']['state']=='uncertain'


def test_one_filter_member_is_not_replaced_by_an_adjacent_filter_value():
    text='其他信息 语言要求：不限 行业要求：工业制造'
    value=prior(text,text,'工业制造');patch=patch_for(value)
    patch['requirements'][0]['requirement'].update(state='mentioned',target='domain',category=None,scope_evidence=[quote(text)])
    result=audit(value,patch)
    assert result['analysis']['claims'][1]['requirement']['state']=='uncertain'
    assert result['analysis']['claims'][1]['text']=='行业要求：工业制造'


def test_named_human_language_is_not_blindly_replaced_with_unknown_filter_semantics():
    text='其他信息 语言要求：英语'
    value=prior(text,text,'英语');patch=patch_for(value)
    patch['requirements'][0]['requirement'].update(state='required',category='professional_skill',scope_evidence=[quote('语言要求：英语')])
    assert audit(value,patch)['analysis']['claims'][1]['requirement']['state']=='required'


def test_fragmented_nominal_and_capability_mix_is_preserved_as_one_unresolved_expression():
    text='要求：有良好的调度框架及问题定位能力'
    row=dict(id='mixed',source='synthetic',job_title='测试',raw_text=text)
    data=draft();data['claims']=[claim('d1','duty',text)]
    for cid,word in [('r1','调度框架'),('r2','问题定位能力')]:
        req=requirement([word]);req.update(combination='single',scope_evidence=[quote(text)])
        data['claims'].append(claim(cid,'requirement',word,req))
    old=run(data,row=row);patch=patch_for(old);result=audit(old,patch)
    reqs=[c for c in result['analysis']['claims'] if c['kind']=='requirement']
    assert len(reqs)==1
    assert reqs[0]['requirement']['state']=='required'
    assert reqs[0]['requirement']['target']=='capability'
    assert reqs[0]['requirement']['degree']=='良好'
    assert reqs[0]['requirement']['combination']=='unresolved'
    assert '调度框架及问题定位能力' in reqs[0]['text']
    assert old['analysis']['claims'][1]['requirement']['state']=='required'


def test_explicitly_separate_or_all_required_competencies_are_not_downgraded():
    for text in ['要求：掌握调度框架并具备问题定位能力','要求：两项缺一不可，有良好的调度框架及问题定位能力']:
        value=prior(text,text,'调度框架');patch=patch_for(value)
        patch['requirements'][0]['requirement'].update(state='required',scope_evidence=[quote(text)])
        assert audit(value,patch)['analysis']['claims'][1]['requirement']['state']=='required'

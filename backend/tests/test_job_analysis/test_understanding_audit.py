"""Synthetic source-role proofs exercise guards; actual DEV effect is evaluated separately."""
import asyncio
from copy import deepcopy
import json

import pytest

from test_understanding import claim, draft, quote, requirement, run


def prior(text, duty, member="Redis", extra_members=(), duty_occurrence=None, member_occurrence=None):
    row = dict(id="audit-one", source="synthetic", job_title="合成职责", raw_text=text)
    req = requirement([member])
    req.update(state="mentioned", combination="single", scope_evidence=[quote(member)])
    data = draft()
    data["claims"] = [claim("d1", "duty", duty), claim("r1", "requirement", member, req)]
    data['claims'][0]['evidence'][0]['occurrence']=duty_occurrence
    data['claims'][1]['evidence'][0]['occurrence']=member_occurrence
    data['claims'][1]['requirement']['scope_evidence'][0]['occurrence']=member_occurrence
    for index, extra in enumerate(extra_members,2):
        extra_req=deepcopy(req)
        extra_req.update(members=[extra],scope_evidence=[quote(extra)])
        data["claims"].append(claim(f"r{index}","requirement",extra,extra_req))
    return run(data, row=row)


def patch_for(value):
    def locator(e):
        return quote(e["quote"], e["field"])
    edits=[]
    for original in value["analysis"]["claims"]:
        if original["kind"]!="requirement":continue
        c=deepcopy(original)
        c["requirement"]["scope_evidence"]=[locator(e) for e in c["requirement"]["scope_evidence"]]
        edits.append(dict(claim_id=c["id"],text=c["text"],reason=c["reason"],requirement=c["requirement"],
                          degree_binding=None,condition_binding=None))
    return dict(requirements=edits,relations=[])


def audit(value, patch):
    from app.job_analysis.understanding.audit import audit as execute
    from app.job_analysis.understanding.processor import Completion

    class Processor:
        descriptor = dict(provider="synthetic", model="fixture", model_revision="audit-1")

        async def complete(self, messages):
            body = json.loads(messages[1]["content"])
            assert set(body) == {"input", "claims", "relations"}
            assert not ({"namespace", "jd_id", "human_labels", "input_row"} & set(body["input"]))
            return Completion(content=json.dumps(patch, ensure_ascii=False), finish_reason="stop")

    return asyncio.run(execute(value, Processor()))


def relation(kind, means, work, cue=None, bridge=None):
    return dict(duty_id="d1", requirement_id="r1", reason="根据所引局部上下文判断",
                evidence=[quote(work)], proof=dict(kind=kind, means=quote(means), work=quote(work),
                                                  cue=quote(cue) if cue else None,
                                                  bridge=quote(bridge) if bridge else None))


def test_same_named_activity_is_inferred_not_employer_explicit_usage():
    value = prior("职责：维护缓存。要求：熟悉 Redis 缓存。", "维护缓存")
    patch = patch_for(value)
    patch["relations"] = [relation("same_activity", "Redis", "维护缓存")]
    result = audit(value, patch)
    assert result["analysis"]["relations"][0]["basis"] == "inferred"
    assert "有限推测" in result["analysis"]["relations"][0]["reason"]
    assert result["lineage"]["policy"] == "semantic-audit-1"
    assert json.loads(result["completion"]) == patch
    assert result["request"][0]["content"].startswith("你是中文JD的定向语义复核器")


@pytest.mark.parametrize("text,cue,bridge", [
    ("使用 Redis 完成任务存储", "使用", None),
    ("使用 Redis。该工具用于任务存储", "使用", "用于"),
    ("Redis 用于任务存储", "用于", None),
    ("熟练使用 Redis 完成任务存储", "熟练使用", None),
    ("不仅能熟练使用 Redis 完成任务存储", "熟练使用", None),
    ("不但熟练使用 Redis 完成任务存储", "熟练使用", None),
    ("不只熟练使用 Redis 完成任务存储", "熟练使用", None),
    ("使用 Redis，但只用于任务存储", "使用", None),
    ("使用 Redis，并用于任务存储", "使用", None),
    ("使用 Redis，主要用来完成任务存储", "使用", None),
])
def test_real_instrumental_usage_stays_explicit_including_named_continuation(text, cue, bridge):
    value = prior(text, "任务存储")
    patch = patch_for(value)
    patch["relations"] = [relation("instrumental_use", "Redis", "任务存储", cue, bridge)]
    result = audit(value, patch)
    assert result["analysis"]["relations"][0]["basis"] == "explicit"
    assert result["analysis"]["claims"][1]["requirement"]["state"] == "mentioned"


@pytest.mark.parametrize("text,cue,bridge", [
    ("跟进 Redis。任务存储另行处理", "跟进", None),
    ("不使用 Redis 完成任务存储", "使用", None),
    ("使用 Redis。摄影用于任务存储", "使用", "用于"),
    ("使用 Java；Redis 与任务存储仅同页出现", "使用", None),
])
def test_unsupported_explicit_proof_cannot_pass_just_because_quotes_exist(text, cue, bridge):
    value = prior(text, "任务存储")
    patch = patch_for(value)
    patch["relations"] = [relation("instrumental_use", "Redis", "任务存储", cue, bridge)]
    result = audit(value, patch)
    assert result["analysis"]["relations"] == []
    assert result["analysis"]["coverage"]["relations"]["status"] == "partial"


def test_cooccurrence_does_not_create_an_inferred_or_explicit_relationship():
    value = prior("职责：智能体开发。摄影兴趣优先。", "智能体开发", "摄影")
    value["analysis"]["relations"]=[dict(duty_id="d1",requirement_id="r1",basis="unknown",
        evidence=[deepcopy(value["analysis"]["claims"][0]["evidence"][0]),
                  deepcopy(value["analysis"]["claims"][1]["evidence"][0])],
        reason="既有稀疏未知关系")]
    patch = patch_for(value)
    patch["relations"] = [relation("cooccurrence", "摄影", "智能体开发")]
    result = audit(value, patch)
    assert result["analysis"]["relations"][0]["basis"] == "unknown"


@pytest.mark.parametrize("kind", ["predicate", "shared_modifier", "anaphora"])
def test_qualification_cannot_cross_other_subject_clause_with_a_broad_quote(kind):
    value = prior("熟悉 Java；Python 不要求精通", "Python 不要求精通", "Python")
    patch = patch_for(value)
    edit = patch["requirements"][0]
    edit["requirement"].update(state="required", degree="熟悉", degree_polarity="affirmed",
                               scope_evidence=[quote("熟悉 Java；Python 不要求精通")])
    edit["degree_binding"] = dict(kind=kind, target=quote("Python"), qualifier=quote("熟悉"))
    result = audit(value, patch)
    assert result["analysis"]["claims"][1]["requirement"] == value["analysis"]["claims"][1]["requirement"]
    assert result["analysis"]["coverage"]["requirements"]["status"] == "partial"


@pytest.mark.parametrize("text,target,degree,kind", [
    ("Python 熟练", "Python", "熟练", "predicate"),
    ("强烈的技术热情和钻研精神", "钻研精神", "强烈", "shared_modifier"),
    ("Python 能独立写。要求能调试", "Python", "能调试", "anaphora"),
])
def test_real_local_shared_and_anaphoric_qualification_is_preserved(text,target,degree,kind):
    value = prior(text, text, target, extra_members=["技术热情"] if kind=="shared_modifier" else [])
    patch = patch_for(value)
    edit = patch["requirements"][0]
    edit["requirement"].update(state="required", degree=degree, degree_polarity="affirmed",
                               scope_evidence=[quote(text)])
    edit["degree_binding"] = dict(kind=kind,target=quote(target),qualifier=quote(degree))
    result = audit(value, patch)
    assert result["analysis"]["claims"][1]["requirement"]["degree"] == degree


def test_editor_cannot_rename_or_modify_duty_or_accept_unknown_claim_ids():
    value = prior("使用 Redis 完成任务存储", "任务存储")
    original = deepcopy(value)
    patch = patch_for(value)
    patch["requirements"][0]["claim_id"] = "d1"
    result = audit(value, patch)
    assert result["analysis"]["claims"][0]["text"] == "任务存储"
    assert result["analysis"]["coverage"]["requirements"]["status"] == "partial"
    assert value == original


def test_one_member_binding_cannot_qualify_an_entire_multi_subject_group():
    value = prior("熟悉 Java；Python 不要求精通", "Python 不要求精通", "Python")
    patch = patch_for(value)
    edit = patch["requirements"][0]
    edit["requirement"].update(members=["Java", "Python"], combination="all_of", state="required",
                               degree="熟悉", degree_polarity="affirmed",
                               scope_evidence=[quote("熟悉 Java；Python 不要求精通")])
    edit["degree_binding"] = dict(kind="predicate",target=quote("Java"),qualifier=quote("熟悉"))
    assert audit(value,patch)["analysis"]["claims"][1]["requirement"] == value["analysis"]["claims"][1]["requirement"]


@pytest.mark.parametrize("text", ["使用 Redis 维护缓存，使用 Java 实现任务存储", "使用 Redis 做缓存，但不用于任务存储"])
def test_switch_of_instrument_or_negated_purpose_after_comma_is_not_direct_usage(text):
    value=prior(text,"任务存储")
    patch=patch_for(value)
    patch["relations"]=[relation("instrumental_use","Redis","任务存储","使用")]
    # Disambiguate the first occurrence of 使用 in the first synthetic sentence.
    patch["relations"][0]["proof"]["cue"]["occurrence"]=0
    result=audit(value,patch)
    assert result["analysis"]["relations"]==[]
    assert result["analysis"]["coverage"]["relations"]["status"]=="partial"


@pytest.mark.parametrize("text", [
    "使用 Redis 维护缓存，Java 开发任务存储",
    "使用 Redis 维护缓存，任务存储另行处理",
])
def test_work_after_a_comma_cannot_borrow_the_previous_clause_instrument(text):
    value=prior(text,"任务存储")
    patch=patch_for(value)
    patch["relations"]=[relation("instrumental_use","Redis","任务存储","使用")]
    result=audit(value,patch)
    assert result["analysis"]["relations"]==[]
    assert result["analysis"]["coverage"]["relations"]["status"]=="partial"


@pytest.mark.parametrize("text", [
    "使用 Redis 维护缓存而不用它做任务存储",
    "使用 Redis 维护缓存，并不会用于任务存储",
    "使用 Redis 维护缓存，未用于任务存储",
    "使用 Redis 维护缓存而不是用来做任务存储",
    "使用 Redis 维护缓存而不是用于任务存储",
    "使用 Redis 维护缓存而不得将其用于任务存储",
    "使用 Redis 维护缓存而不会直接用于任务存储",
    "使用 Redis 维护缓存而不应当用于任务存储",
    "使用 Redis 维护缓存却不适用于任务存储",
])
def test_negative_purpose_after_the_instrument_cannot_become_explicit(text):
    value=prior(text,"任务存储")
    patch=patch_for(value)
    patch["relations"]=[relation("instrumental_use","Redis","任务存储","使用")]
    result=audit(value,patch)
    assert result["analysis"]["relations"]==[]
    assert result["analysis"]["coverage"]["relations"]["status"]=="partial"


@pytest.mark.parametrize("kind",["cooccurrence","unknown"])
def test_audit_cannot_create_a_new_unknown_relation_endpoint(kind):
    value=prior("维护缓存。熟悉 Redis","维护缓存")
    patch=patch_for(value)
    patch["relations"]=[relation(kind,"Redis","维护缓存")]
    result=audit(value,patch)
    assert result["analysis"]["relations"]==[]
    assert result["analysis"]["coverage"]["relations"]["status"]=="partial"
    assert any(i["kind"]=="relation_proof_rejected" for i in result["execution"]["metadata"]["audit_issues"])


def test_audit_cannot_create_a_dense_same_activity_matrix():
    text="维护缓存。开发接口。熟悉 Redis。掌握 Python。"
    row=dict(id="matrix",source="synthetic",job_title="测试",raw_text=text)
    data=draft();data["claims"]=[]
    for claim_id,kind,value in (
        ("d1","duty","维护缓存"),("d2","duty","开发接口"),
        ("r1","requirement","Redis"),("r2","requirement","Python"),
    ):
        req=requirement([value]) if kind=="requirement" else None
        if req:
            req.update(combination="single",scope_evidence=[quote(text)])
        data["claims"].append(claim(claim_id,kind,value,req))
    value=run(data,row=row)
    patch=patch_for(value)
    patch["relations"]=[]
    for duty_id,work in (("d1","维护缓存"),("d2","开发接口")):
        for requirement_id,means in (("r1","Redis"),("r2","Python")):
            item=relation("same_activity",means,work)
            item.update(duty_id=duty_id,requirement_id=requirement_id)
            patch["relations"].append(item)
    result=audit(value,patch)
    assert result["analysis"]["relations"]==[]
    assert result["analysis"]["coverage"]["relations"]["status"]=="partial"
    assert any(i["kind"]=="relation_proof_rejected" for i in result["execution"]["metadata"]["audit_issues"])


@pytest.mark.parametrize("text,polarity", [("不要求精通 Python","affirmed"),("精通 Python","negated")])
def test_degree_binding_cannot_invert_a_literal_negative_or_positive(text,polarity):
    value=prior(text,text,"Python")
    patch=patch_for(value)
    e=patch["requirements"][0]
    e["requirement"].update(state="required",degree="精通",degree_polarity=polarity,scope_evidence=[quote(text)])
    e["degree_binding"]=dict(kind="predicate",target=quote("Python"),qualifier=quote("精通"))
    result=audit(value,patch)
    assert result["analysis"]["coverage"]["requirements"]["status"]=="partial"
    assert result["analysis"]["claims"][1]["requirement"] == value["analysis"]["claims"][1]["requirement"]


def test_duplicate_edits_are_all_rejected_instead_of_arbitrarily_accepting_first():
    value=prior("使用 Redis 完成任务存储","任务存储")
    patch=patch_for(value)
    patch["requirements"][0]["requirement"]["state"]="required"
    patch["requirements"].append(deepcopy(patch["requirements"][0]))
    result=audit(value,patch)
    assert result["analysis"]["coverage"]["requirements"]["status"]=="partial"
    assert result["analysis"]["claims"][1]["requirement"] == value["analysis"]["claims"][1]["requirement"]


def test_requirement_edit_uses_outer_reason_when_nested_reason_is_omitted():
    value=prior("维护缓存。熟悉 Redis","维护缓存","Redis")
    patch=patch_for(value)
    patch["requirements"][0]["requirement"].pop("reason")
    patch["requirements"][0]["reason"]="外层修订理由"
    result=audit(value,patch)
    assert result["analysis"]["claims"][1]["requirement"]["reason"]=="外层修订理由"
    assert result["analysis"]["coverage"]["requirements"]["status"]=="complete"


@pytest.mark.parametrize("text,kind,degree,target", [
    ("熟悉 Java 并了解 Python","predicate","熟悉","Python"),
    ("强烈的技术热情和较弱的钻研精神","shared_modifier","强烈","钻研精神"),
])
def test_qualifier_cannot_jump_another_predicate_or_competing_coordinate_modifier(text,kind,degree,target):
    value=prior(text,text,target,extra_members=["技术热情"] if kind=="shared_modifier" else [])
    patch=patch_for(value)
    e=patch["requirements"][0]
    e["requirement"].update(state="required",degree=degree,degree_polarity="affirmed",scope_evidence=[quote(text)])
    e["degree_binding"]=dict(kind=kind,target=quote(target),qualifier=quote(degree))
    result=audit(value,patch)
    assert result["analysis"]["claims"][1]["requirement"] == value["analysis"]["claims"][1]["requirement"]
    assert result['analysis']['coverage']['requirements']['status']=="partial"


def test_processor_exception_retains_actual_audit_request_and_prompt():
    from app.job_analysis.understanding.audit import audit as execute
    value=prior("使用 Redis 完成任务存储","任务存储")
    captured={}
    class Broken:
        descriptor=dict(provider="synthetic",model="fixture",model_revision="1")
        async def complete(self,messages):
            captured['request']=deepcopy(messages)
            raise RuntimeError("private provider detail")
    result=asyncio.run(execute(value,Broken()))
    assert result['execution']['status']=="processor_error"
    assert result['request']==captured['request']
    assert "private provider detail" not in str(result)


def test_relation_audit_must_account_for_each_existing_endpoint():
    value=prior("使用 Redis 完成任务存储","任务存储")
    value["analysis"]["relations"]=[dict(duty_id="d1",requirement_id="r1",basis="explicit",
        evidence=[deepcopy(value["analysis"]["claims"][0]["evidence"][0])],reason="已有待复核关系")]
    patch=patch_for(value)
    result=audit(value,patch)
    assert result["analysis"]["relations"]==[]
    assert result["analysis"]["coverage"]["relations"]["status"]=="partial"
    assert any(i["kind"]=="relation_audit_omitted" for i in result["execution"]["metadata"]["audit_issues"])


def test_ambiguous_short_qualifier_is_resolved_only_inside_declared_target_scope():
    value=prior("熟悉 Java。熟悉 Python","熟悉 Python","Python")
    patch=patch_for(value);e=patch['requirements'][0]
    e['requirement'].update(state='required',degree='熟悉',degree_polarity='affirmed',scope_evidence=[quote('熟悉 Python')])
    e['degree_binding']=dict(kind='predicate',target=quote('Python'),qualifier=quote('熟悉'))
    result=audit(value,patch)
    assert result['analysis']['claims'][1]['requirement']['degree']=='熟悉'
    assert result['execution']['metadata']['resolved_bindings'][0]['qualifier']['start']==8


def test_context_only_proof_reversed_fields_are_bound_by_actual_claim_scopes_not_upgraded():
    value=prior("跟进 Redis 缓存技术。熟悉 Redis 架构","跟进 Redis 缓存技术","Redis 架构")
    patch=patch_for(value)
    patch['relations']=[relation('shared_context','Redis 缓存技术','Redis 架构')]
    result=audit(value,patch)
    assert result['analysis']['relations'][0]['basis']=='inferred'
    assert 'Redis 缓存技术' in result['analysis']['relations'][0]['reason']


def test_bad_qualification_edit_keeps_original_fact_but_is_not_verified_complete():
    value=prior('熟悉 Java；Python 不要求精通','Python 不要求精通','Python')
    patch=patch_for(value);e=patch['requirements'][0]
    e['requirement'].update(state='required',degree='熟悉',degree_polarity='affirmed',scope_evidence=[quote('熟悉 Java；Python 不要求精通')])
    e['degree_binding']=dict(kind='predicate',target=quote('Python'),qualifier=quote('熟悉'))
    result=audit(value,patch)
    assert result['analysis']['claims'][1]['requirement']==value['analysis']['claims'][1]['requirement']
    assert result['analysis']['coverage']['requirements']['status']=='partial'


@pytest.mark.parametrize('component',['condition','negated_degree'])
def test_editor_cannot_erase_existing_condition_or_negated_degree(component):
    text='仅限内部项目：Python 不要求精通'
    value=prior(text,text,'Python')
    req=value['analysis']['claims'][1]['requirement']
    req['scope_evidence']=deepcopy(value['analysis']['claims'][0]['evidence'])
    if component=='condition':req['condition']='仅限内部项目'
    else:req.update(state='not_required',degree='精通',degree_polarity='negated')
    patch=patch_for(value);e=patch['requirements'][0]
    if component=='condition':e['requirement']['condition']=None
    else:e['requirement'].update(degree=None,degree_polarity=None)
    result=audit(value,patch)
    assert result['analysis']['claims'][1]['requirement']==req
    assert result['analysis']['coverage']['requirements']['status']=='partial'


def test_unicode_compatibility_quote_maps_back_to_real_source_codepoints():
    text='🧪熟悉ﬁle工具，具备办公开发能⼒'
    value=prior(text,text,'ﬁle工具')
    patch=patch_for(value);e=patch['requirements'][0]
    e['requirement'].update(state='required',members=['file工具'],degree='熟悉',degree_polarity='affirmed',
                            scope_evidence=[quote('熟悉file工具，具备办公开发能力')])
    e['degree_binding']=dict(kind='predicate',target=quote('file工具'),qualifier=quote('熟悉'))
    result=audit(value,patch)
    req=result['analysis']['claims'][1]['requirement']
    assert req['members']==['file工具']
    assert req['scope_evidence'][0]['quote']=='熟悉ﬁle工具，具备办公开发能⼒'
    ev=req['scope_evidence'][0]
    assert text[ev['start']:ev['end']]==ev['quote']


def test_local_usage_and_existing_duty_align_by_specific_action_object_not_fabricated_quote():
    text='设计、开发和维护检索系统。熟练使用 Alpha 进行检索开发'
    value=prior(text,'设计、开发和维护检索系统','Alpha')
    patch=patch_for(value)
    rel=relation('instrumental_use','Alpha','进行检索开发','使用')
    rel['evidence']=[quote('负责开发检索系统')]
    rel['proof']['alignment']=dict(duty_scope=quote('设计、开发和维护检索系统'),action='开发',object='检索系统')
    patch['relations']=[rel]
    result=audit(value,patch)
    assert result['analysis']['relations'][0]['basis']=='explicit'
    assert all(e['quote'] in text for e in result['analysis']['relations'][0]['evidence'])
    assert '不扩展聚合项其他动作' in result['analysis']['relations'][0]['reason']


def test_usage_cue_ambiguity_is_resolved_by_actual_instrument_and_local_purpose():
    text='使用 Java 处理日志。使用 Redis 完成任务存储'
    value=prior(text,'任务存储')
    patch=patch_for(value)
    patch['relations']=[relation('instrumental_use','Redis','任务存储','使用')]
    result=audit(value,patch)
    assert result['analysis']['relations'][0]['basis']=='explicit'
    assert any(e['start']==13 and e['quote']=='使用' for e in result['analysis']['relations'][0]['evidence'])


def test_actual_method_usage_is_not_lost_when_editor_calls_it_contextual():
    value=prior('运用排查方法，定位系统问题','定位系统问题','排查方法')
    patch=patch_for(value)
    patch['requirements'][0]['requirement']['state']='uncertain'
    patch['relations']=[relation('same_activity','排查方法','定位系统问题')]
    result=audit(value,patch)
    assert result['analysis']['relations'][0]['basis']=='explicit'
    assert result['analysis']['claims'][1]['requirement']['state']=='uncertain'


@pytest.mark.parametrize('text,cue',[
    ('Redis 缓存旁是 Java，Java 用于任务存储','用于'),
    ('未使用 Redis 完成任务存储','使用'),
    ('没有使用 Redis 完成任务存储','使用'),
])
def test_changed_subject_before_purpose_or_negative_usage_cannot_be_promoted(text,cue):
    value=prior(text,'任务存储')
    patch=patch_for(value)
    patch['relations']=[relation('instrumental_use','Redis','任务存储',cue)]
    result=audit(value,patch)
    assert result['analysis']['relations']==[]


def test_compatibility_lookup_does_not_accept_half_of_an_expanded_codepoint():
    value=prior('熟悉 ﬁle 工具','熟悉 ﬁle 工具','ﬁle')
    patch=patch_for(value);e=patch['requirements'][0]
    e['requirement'].update(state='required',degree='熟悉',degree_polarity='affirmed',scope_evidence=[quote('熟悉 file 工具')])
    e['degree_binding']=dict(kind='predicate',target=quote('f'),qualifier=quote('熟悉'))
    result=audit(value,patch)
    assert result['analysis']['claims'][1]['requirement']['degree'] is None
    assert result['analysis']['coverage']['requirements']['status']=='partial'


def test_compound_capability_nouns_keep_only_the_local_corresponding_work_scope():
    text='职责：方案评审。要求：具备方案评审和测试的能力'
    value=prior(text,'方案评审','方案评审和测试的能力',duty_occurrence=0)
    patch=patch_for(value)
    patch['requirements'][0]['requirement'].update(members=['方案评审能力','测试能力'],combination='all_of')
    patch['relations']=[relation('same_activity','方案评审和测试的能力','方案评审')]
    result=audit(value,patch)
    assert result['analysis']['relations'][0]['basis']=='inferred'
    assert '手段范围仅为「方案评审」' in result['analysis']['relations'][0]['reason']


def test_unrecognized_negative_operator_is_not_treated_as_affirmative_degree():
    value=prior('不强求精通 Python','不强求精通 Python','Python')
    patch=patch_for(value);e=patch['requirements'][0]
    e['requirement'].update(state='required',degree='精通',degree_polarity='affirmed',scope_evidence=[quote('不强求精通 Python')])
    e['degree_binding']=dict(kind='predicate',target=quote('Python'),qualifier=quote('精通'))
    result=audit(value,patch)
    assert result['analysis']['claims'][1]['requirement']['degree'] is None
    assert result['analysis']['coverage']['requirements']['status']=='partial'


def test_one_subject_can_keep_negative_expert_and_positive_basic_threshold_in_same_clause():
    value=prior('Python 不要求精通但需了解','Python 不要求精通但需了解','Python')
    patch=patch_for(value);e=patch['requirements'][0]
    e['requirement'].update(state='required',degree='了解',degree_polarity='affirmed',scope_evidence=[quote('Python 不要求精通但需了解')])
    e['degree_binding']=dict(kind='predicate',target=quote('Python'),qualifier=quote('了解'))
    assert audit(value,patch)['analysis']['claims'][1]['requirement']['degree']=='了解'


def test_method_role_can_be_narrowed_from_a_complete_ability_phrase_without_creating_a_requirement():
    text='熟练运用排查方法，快速定位系统问题'
    value=prior(text,'快速定位系统问题','熟练运用排查方法')
    patch=patch_for(value)
    patch['requirements'][0]['requirement']['state']='uncertain'
    patch['relations']=[relation('same_activity','熟练运用排查方法','快速定位系统问题')]
    result=audit(value,patch)
    assert result['analysis']['relations'][0]['basis']=='explicit'
    assert '手段范围仅为「排查方法」' in result['analysis']['relations'][0]['reason']
    assert result['analysis']['claims'][1]['requirement']['state']=='uncertain'


@pytest.mark.parametrize('text,member,fragment',[
    ('熟悉 Scala；Java 不要求精通','Java','a'),
    ('熟悉 C++；C 不要求精通','C','C'),
])
def test_partial_spelling_cannot_borrow_degree_from_another_named_subject(text,member,fragment):
    value=prior(text,text,member,member_occurrence=1 if member=='C' else None)
    patch=patch_for(value);e=patch['requirements'][0]
    e['requirement'].update(state='required',degree='熟悉',degree_polarity='affirmed',scope_evidence=[quote(text)])
    e['degree_binding']=dict(kind='predicate',target=quote(fragment,occurrence=0),qualifier=quote('熟悉'))
    result=audit(value,patch)
    assert result['analysis']['claims'][1]['requirement']['degree'] is None
    assert result['analysis']['coverage']['requirements']['status']=='partial'


def test_unanchored_context_proof_cannot_create_a_new_inferred_relation():
    value=prior('维护缓存。熟悉 Redis 架构','维护缓存','Redis 架构')
    patch=patch_for(value);rel=relation('shared_context','Redis 架构','维护缓存')
    rel['proof'].update(means=None,work=None)
    patch['relations']=[rel]
    result=audit(value,patch)
    assert result['analysis']['relations']==[]
    assert result['analysis']['coverage']['relations']['status']=='partial'
    assert any(i['kind']=='relation_proof_rejected' for i in result['execution']['metadata']['audit_issues'])


def test_existing_unanchored_context_relation_is_kept_only_as_bounded_unknown():
    value=prior('维护缓存。熟悉 Redis 架构','维护缓存','Redis 架构')
    value['analysis']['relations']=[dict(duty_id='d1',requirement_id='r1',basis='inferred',
        evidence=[deepcopy(value['analysis']['claims'][0]['evidence'][0]),
                  deepcopy(value['analysis']['claims'][1]['evidence'][0])],
        reason='既有上下文假设')]
    patch=patch_for(value);rel=relation('shared_context','Redis 架构','维护缓存')
    rel['proof'].update(means=None,work=None)
    patch['relations']=[rel]
    result=audit(value,patch)
    assert result['analysis']['relations'][0]['basis']=='unknown'
    assert result['analysis']['coverage']['relations']['status']=='partial'
    assert '关系锚点缺失' in result['analysis']['relations'][0]['reason']
    assert all(e['quote'] in value['analysis']['input_row']['raw_text']
               for e in result['analysis']['relations'][0]['evidence'])


def test_cross_sentence_context_with_anchored_activity_keeps_a_bounded_inference():
    text='排查系统问题。要求掌握根因分析方法'
    value=prior(text,'排查系统问题','根因分析方法')
    patch=patch_for(value)
    patch['relations']=[relation('shared_context','根因分析方法','排查系统问题')]
    result=audit(value,patch)
    assert result['analysis']['relations'][0]['basis']=='inferred'
    assert '有限推测' in result['analysis']['relations'][0]['reason']


def test_missing_instrumental_anchors_are_not_treated_as_a_successful_explicit_proof():
    value=prior('使用 Redis 完成任务存储','任务存储')
    patch=patch_for(value);rel=relation('instrumental_use','Redis','任务存储','使用')
    rel['proof'].update(means=None,work=None)
    patch['relations']=[rel]
    result=audit(value,patch)
    assert result['analysis']['relations']==[]
    assert result['analysis']['coverage']['relations']['status']=='partial'


def test_short_entity_name_does_not_prove_a_longer_distinct_requirement_is_used():
    value=prior('使用 Java 完成任务存储；要求 JavaScript','使用 Java 完成任务存储','JavaScript')
    patch=patch_for(value)
    patch['relations']=[relation('instrumental_use','Java','任务存储','使用')]
    result=audit(value,patch)
    assert result['analysis']['relations']==[]
    assert result['analysis']['coverage']['relations']['status']=='partial'


def test_audit_cannot_silently_erase_an_existing_grounded_positive_degree():
    text='要求精通 Python'
    value=prior(text,text,'Python')
    # Establish an actual, previously grounded threshold rather than just text.
    from test_understanding import run
    data=draft();req=requirement(['Python'])
    req.update(combination='single',degree='精通',degree_polarity='affirmed',scope_evidence=[quote(text)])
    data['claims']=[claim('d1','duty',text),claim('r1','requirement','Python',req)]
    value=run(data,row=value['analysis']['input_row'])
    patch=patch_for(value)
    patch['requirements'][0]['requirement'].update(degree=None,degree_polarity=None)
    result=audit(value,patch)
    assert result['analysis']['claims'][1]['requirement']['degree']=='精通'
    assert result['analysis']['coverage']['requirements']['status']=='partial'


def test_alignment_cannot_join_the_action_and_object_from_different_duty_clauses():
    value=prior('维护缓存组件，开发支付模块。使用 Java 开发缓存组件','维护缓存组件，开发支付模块','Java')
    patch=patch_for(value)
    rel=relation('instrumental_use','Java','开发缓存组件','使用')
    rel['proof']['alignment']=dict(duty_scope=quote('开发支付模块'),action='开发',object='缓存组件')
    patch['relations']=[rel]
    assert audit(value,patch)['analysis']['relations']==[]


def test_paraphrased_alignment_can_reanchor_only_one_actual_local_duty_clause():
    value=prior('设计、开发和维护高效、稳定的检索系统，提升效率。使用 Alpha 进行检索开发',
                '设计、开发和维护高效、稳定的检索系统，提升效率','Alpha')
    patch=patch_for(value)
    rel=relation('instrumental_use','Alpha','进行检索开发','使用')
    rel['proof']['alignment']=dict(duty_scope=quote('开发高效、稳定的检索系统'),action='开发',object='检索系统')
    patch['relations']=[rel]
    result=audit(value,patch)
    assert result['analysis']['relations'][0]['basis']=='explicit'
    assert all(e['quote'] in value['analysis']['input_row']['raw_text'] for e in result['analysis']['relations'][0]['evidence'])


@pytest.mark.parametrize('scope',['负责 Java 开发','开发 JavaScript 模块'])
def test_alignment_object_cannot_borrow_a_short_name_from_a_different_technical_entity(scope):
    value=prior('开发 JavaScript 模块。使用 Alpha 开发 Java 组件','开发 JavaScript 模块','Alpha')
    patch=patch_for(value)
    rel=relation('instrumental_use','Alpha','开发 Java 组件','使用')
    rel['proof']['alignment']=dict(duty_scope=quote(scope),action='开发',object='Java组件')
    patch['relations']=[rel]
    assert audit(value,patch)['analysis']['relations']==[]

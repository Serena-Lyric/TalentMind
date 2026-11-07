"""F1 source-fact restrictions survive response acceptance and historical reads."""
from copy import deepcopy
import json

import pytest

from app.job_analysis.baseline.contract import validate_analysis
from app.job_analysis.foundation.inputs import InputRecord, digest
from app.job_analysis.knowledge.attribution import read_attribution
from app.job_analysis.knowledge.storage import save_result
from app.job_analysis.knowledge.work_comparison import (
    WorkComparisonResult, add_work_response, start_work_comparison,
)
from app.job_analysis.knowledge.work_semantics import source_work
from test_knowledge_alignment import evidence
from test_knowledge_context import execute
from test_knowledge_local_semantics import binding
from test_knowledge_roles import analysis_with_duties
from test_knowledge_work_comparison import first, second
from test_work_candidates import cleanup_p3_files, work


def source(text, quote=None):
    value = analysis_with_duties([text], core_values=[None])
    if quote is not None:
        row = InputRecord.from_row(value['namespace'], value['input_row'])
        value['claims'][0]['evidence'] = [evidence(row, quote)]
    validate_analysis(value)
    return value


def accept(value, *, version=None):
    context = execute(value)
    result = start_work_comparison(context, **({'version': version} if version is not None else {}))
    # Explicitly synthetic agreements; no model or external runtime is called.
    return add_work_response(result, 'd1', 'ref-software-development', 'resp-software-develop',
        first(), second(), binding(), 'qwen3-instruct', 1, 1)


def roundtrip(result, path):
    payload = result.model_dump()
    save_result(path, payload)
    assert read_attribution(path).model_dump() == payload
    raw = json.loads((path / 'value.json').read_text(encoding='utf-8'))
    assert WorkComparisonResult.model_validate(raw).model_dump() == payload
    return raw


@pytest.mark.parametrize('text,quote', [
    ('编写软件采购合同及代码', '编写软件'),
    ('编写接口采购合同及接口', '编写接口'),
    ('编写软件采购合同及代码', '编写'),
    ('编写软件采购合同及代码', '软件'),
    ('编写软件采购合同及代码', '代码'),
])
def test_new_work_rejects_uncited_object_despite_two_positive_responses(tmp_path, text, quote):
    value = source(text, quote)
    before = deepcopy(value)
    interpretation = source_work(value['claims'][0], value)['source_explanation']
    assert interpretation['frames'] == []
    assert interpretation['context_restricts_quote'] is True
    assert 'uncited_action_or_object' in {g['reason'] for g in interpretation['gaps']}
    result = accept(value)
    saved = roundtrip(result, tmp_path / 'accepted')
    assert saved['task_assessments'][0]['state'] == 'unresolved'
    assert saved['task_assessments'][0]['reason_code'] == 'source_guard_uncited_action_or_object'
    assert saved['work_candidates'] == []
    assert value == before
    forged = deepcopy(saved)
    forged['task_assessments'][0].update(state='machine_supported',
        reason_code='two_source_views_support_task_aspect')
    save_result(tmp_path / 'forged', forged)
    with pytest.raises(ValueError, match='work state exceeds'):
        read_attribution(tmp_path / 'forged')


@pytest.mark.parametrize('text,quote,state', [
    ('编写软件采购合同', '编写软件', 'unresolved'),
    ('编写软件代码', None, 'machine_supported'),
    ('编写软件采购合同及代码', None, 'machine_supported'),
    ('配合开发团队完成功能实现', None, 'machine_supported'),
    ('将系统能力进行Agent化封装', None, 'machine_supported'),
])
def test_new_work_preserves_complete_and_model_only_work(tmp_path, text, quote, state):
    value = source(text, quote)
    result = accept(value)
    roundtrip(result, tmp_path / 'control')
    assert result.task_assessments[0].state == state
    assert bool(result.work_candidates) == (state == 'machine_supported')


@pytest.mark.parametrize('version', [4, 5])
@pytest.mark.parametrize('text,state', [
    ('不承担课程教学，仅开发软件', 'machine_supported'),
    ('如果项目批准：\n开发软件', 'unresolved'),
    ('客户负责：\n开发软件', 'unresolved'),
    ('过去职责：\n开发软件', 'unresolved'),
])
def test_local_affirmation_survives_other_scope_without_relaxing_controls(tmp_path, version, text, state):
    result = accept(source(text), version=version)
    roundtrip(result, tmp_path / 'scopes')
    assert result.task_assessments[0].state == state
    assert bool(result.work_candidates) == (state == 'machine_supported')


@pytest.mark.parametrize('quote', [None, '开发软件'])
def test_new_work_recovers_noncolon_condition_without_turning_work_into_heading(tmp_path, quote):
    restricted = accept(source('能力允许的话可以延伸\n开发软件', quote))
    roundtrip(restricted, tmp_path / 'condition')
    assert restricted.task_assessments[0].state == 'unresolved'
    assert not restricted.work_candidates
    # A complete conditional task line is not a heading for another task.
    separate = accept(source('如果项目批准则维护网络\n开发软件', quote))
    roundtrip(separate, tmp_path / 'separate')
    assert separate.task_assessments[0].state == 'machine_supported'


@pytest.mark.parametrize('text,quote,input_sha', [
    ('编写软件采购合同及代码', '编写软件', 'b32fcc57536f8014fe7bf129c84c80d0cc2459d20af1b87542890b245d61f615'),
    ('编写接口采购合同及接口', '编写接口', 'e35039f7de58b529b41cce84b89a574f86caab52c98139eb0823b3d2b64f8aa6'),
    ('编写软件采购合同及代码', '编写', 'a9123f5e77ee1f00adc68f813372f8cdebbce93c23a5a9287e74e8cc4d0aa357'),
    ('编写软件采购合同及代码', '软件', 'ef5cbd09d0921b5cc812b61def7071ae158bf56db4ba4a122c4318c1cd543902'),
    ('编写软件采购合同及代码', '代码', '6f06fe977dc44a1fc99aa6f71a4bec925d450bbe225fa6832bf757b5f292d431'),
    ('协助职责\n开发订单接口。', '开发订单接口', '02c60036e5314ee9fcdcc9b98105dba6fbd44aa2c24d8c4cd0bf9c55fe3a96c6'),
    ('【协助职责】\n开发订单接口。', '开发订单接口', 'da70ff1348cfe170c834fd7ce38c8897dec4daa8a5d28a5c161771440803093d'),
])
def test_published_v4_input_and_error_remain_historical(tmp_path, text, quote, input_sha):
    result = accept(source(text, quote), version=4)
    assert digest(result.task_assessments[0].input_json) == input_sha
    # Preserve the recorded historical error, never silently upgrade/recompute it.
    assert result.task_assessments[0].state == 'machine_supported'
    assert result.work_candidates[0].importance == 'unknown'
    roundtrip(result, tmp_path / 'historical')


@pytest.mark.parametrize('heading', ['协助职责', '【协助职责】'])
def test_new_work_saves_auxiliary_importance_without_rewriting_v4(tmp_path, heading):
    value = work(text=heading + '\n开发订单接口。')
    value['claims'][0]['core'] = None
    value['claims'][0]['evidence'] = [evidence(InputRecord.from_row(value['namespace'], value['input_row']), '开发订单接口')]
    validate_analysis(value)
    old = accept(value, version=4)
    current = accept(value)
    assert old.work_candidates[0].importance == 'unknown'
    assert current.work_candidates[0].importance == 'auxiliary'
    assert heading in current.task_assessments[0].primary.prompt
    roundtrip(old, tmp_path / 'old')
    roundtrip(current, tmp_path / 'current')
    from app.job_analysis.knowledge.research_summary import build_research_summary
    assert build_research_summary(old)['method_version'] == 'bounded-work-semantics-2'
    assert build_research_summary(current)['method_version'] == 'bounded-work-semantics-3'


def test_public_work_entry_applies_new_source_guard(tmp_path):
    from types import SimpleNamespace
    from app.job_analysis.knowledge.attribution import attribute_roles
    from app.job_analysis.knowledge.catalog import load_snapshot
    from app.job_analysis.knowledge.role_policy import load_policy
    from app.job_analysis.knowledge.work_context_models import ModelBinding
    from test_knowledge_context import ROOT

    class Ranker:
        binding = {'id': 'synthetic'}

        def rank(self, pairs):
            return [(0.5, False) for _ in pairs]

    class SyntheticResponses:
        manifest = SimpleNamespace(binding=ModelBinding.model_validate(binding()), prompt_format='qwen3-instruct')

        def complete_json(self, prompt, schema):
            return second() if 'relation' in schema['properties'] else first()

    result = attribute_roles(source('编写软件采购合同及代码', '编写软件'),
        load_snapshot(ROOT / 'catalog/role-references.v3'),
        load_policy(ROOT / 'policies/role-attribution.v2.json'), method='work',
        local_model=SyntheticResponses(), task_retriever=Ranker(), pairs_per_role=1000)
    item = next(a for a in result.task_assessments if a.role_id == 'ref-software-development'
                and a.reference_id == 'resp-software-develop')
    assert item.state == 'unresolved'
    assert item.reason_code == 'source_guard_uncited_action_or_object'
    assert result.work_candidates == []
    roundtrip(result, tmp_path / 'public')

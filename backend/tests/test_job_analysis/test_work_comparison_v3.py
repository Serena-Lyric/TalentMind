"""New source guards do not reinterpret old responses or hide unchecked work."""
import pytest

from app.job_analysis.knowledge.work_comparison import start_work_comparison, add_work_response
from app.job_analysis.knowledge.task_comparison import select_tasks
from test_knowledge_context import execute
from test_knowledge_roles import analysis_with_duties
from test_knowledge_local_semantics import binding
from test_knowledge_work_comparison import first, second


def result(text):
    return start_work_comparison(execute(analysis_with_duties([text])), version=3)


@pytest.mark.parametrize("text,role,ref", [
    ("优化系统资源调度", "p0-ref-network-operations", "resp-network-optimize"),
    ("定位系统问题根因并修复", "p0-ref-network-operations", "resp-network-fault"),
    ("沉淀技术规范", "ref-software-development", "resp-software-develop"),
    ("构建标注测试集并设计评分口径", "ref-software-development", "resp-software-develop"),
    ("清洗知识文档并验证检索效果", "ref-software-development", "resp-software-develop"),
    ("开发后端接口", "ref-business-intelligence", "resp-bi-tools"),
    ("编写软件模块设计文档", "ref-software-development", "resp-software-develop"),
    ("管理和维护BI平台", "ref-business-intelligence", "resp-bi-tools"),
])
def test_two_model_agreements_cannot_supply_missing_source_domain_or_responsibility(text, role, ref):
    out = add_work_response(result(text), "d1", role, ref, first(), second(), binding(), "qwen3-instruct", 1, 1)
    assert out.task_assessments[0].state == "unresolved"
    assert out.task_assessments[0].reason_code.startswith("source_guard_")
    assert not out.work_candidates


@pytest.mark.parametrize("text", ["实现订单服务接口", "协助开发软件模块", "设计并实现高效算法",
    "将系统能力进行Agent化封装", "负责BI产品的开发工作", "开发和维护算法服务",
    "设计、开发和维护稳定的爬虫系统", "完成通信模块的方案设计、编码实现、单元测试"])
def test_source_guard_keeps_actual_software_aspects(text):
    out = add_work_response(result(text), "d1", "ref-software-development", "resp-software-develop",
                            first(), second(), binding(), "qwen3-instruct", 1, 1)
    assert out.task_assessments[0].state == "machine_supported"


def test_new_selection_covers_distinct_claims_before_repeated_references():
    base = start_work_comparison(execute(analysis_with_duties(["开发软件", "维护BI平台", "编写代码"])), version=3)
    class Ranker:
        binding = {"id": "synthetic"}
        def rank(self, pairs): return [(0.9 if "开发软件" in source else 0.1, False) for source, _ in pairs]
    choice = select_tasks(base, Ranker(), 5, definition_examples=True, diverse_claims=True)
    by_id = {p.id: p for p in choice.proposals}
    selected = [by_id[i] for i in choice.selected_pair_ids if by_id[i].role_id == "ref-software-development"]
    assert len({p.claim_id for p in selected[:3]}) == 3
    assert choice.method == "claim-diverse-task-budget-1"
    assert len(choice.unchecked_pair_ids) + len(choice.selected_pair_ids) == len(choice.proposals)


def test_coding_cannot_borrow_previous_design_predicate_in_a_list():
    out = add_work_response(result("完成通信模块的方案设计、编码实现、单元集成测试"),
        "d1", "p0-ref-programming", "resp-write-program", first(), second(), binding(), "qwen3-instruct", 1, 1)
    assert out.task_assessments[0].state == "machine_supported"


def test_business_report_is_not_misclassified_as_a_required_bi_system():
    out = add_work_response(result("设计并交付业务数据报表和可视化看板"),
        "d1", "ref-business-intelligence", "resp-bi-report", first(), second(), binding(), "qwen3-instruct", 1, 1)
    assert out.task_assessments[0].state == "machine_supported"


def test_business_report_does_not_supply_bi_system_creation():
    out = add_work_response(result("制作业务分析报告"),
        "d1", "ref-business-intelligence", "resp-bi-tools", first(), second(), binding(), "qwen3-instruct", 1, 1)
    assert out.task_assessments[0].state == "unresolved"
    assert out.task_assessments[0].reason_code == "source_guard_functional_domain_unestablished"


def test_old_work_result_cannot_claim_new_expanded_budget():
    from app.job_analysis.knowledge.work_comparison import WorkComparisonResult
    old = start_work_comparison(execute(analysis_with_duties(['开发软件'])), version=2).model_dump()
    old['task_selection']['pairs_per_role'] = 4
    with pytest.raises(ValueError, match='historical role budget'):
        WorkComparisonResult.model_validate(old)

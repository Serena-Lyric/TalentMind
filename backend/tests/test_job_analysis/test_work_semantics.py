"""Bounded semantic frames must preserve responsibility and functional objects."""
import pytest

from app.job_analysis.knowledge.work_semantics import compare_work, explain_work


@pytest.mark.parametrize("left,right", [
    ("使用Java开发订单API", "采用Go实现订单服务接口"),
    ("编写软件模块代码", "实现应用程序"),
    ("维护商业智能平台", "管理BI系统"),
    ("编制经营指标报告", "制作业务数据报表"),
    ("生成销售报告", "制作销售报表"),
    ("开发和维护算法服务", "实现并管理算法服务"),
])
def test_same_responsibility_with_different_expression_or_stack(left, right):
    assert compare_work(left, right)["state"] == "supported"


@pytest.mark.parametrize("left,right", [
    ("讲授Java软件开发课程", "使用Java开发软件"),
    ("不负责开发软件", "开发软件"),
    ("必要时开发软件", "开发软件"),
    ("整理资料供开发团队完成软件开发", "开发软件"),
    ("编写需求规格说明书", "编写应用程序"),
    ("优化资源调度和软件性能", "优化网络性能"),
    ("构建标注测试集并设计评分口径", "构建软件系统"),
    ("清洗知识文档并验证检索效果", "开发软件系统"),
    ("编写软件模块设计文档", "编写软件模块代码"),
    ("协助开发软件", "开发软件"),
    ("如有需要开发订单接口", "开发订单接口"),
    ("为开发人员整理订单接口需求", "开发订单接口"),
    ("开发订单接口", "开发测试框架"),
    ("设计用户界面", "设计后端接口"),
    ("开发订单接口", "实现推荐算法"),
    ("封装业务系统能力为Skills", "开发业务系统"),
    ("构建标准化Skills", "开发产品接口"),
    ("执行Skills开发规范与接口规范", "开发软件接口"),
    ("客户负责：\n开发软件", "开发软件"),
    ("无需承担以下工作：\n开发软件", "开发软件"),
])
def test_related_words_do_not_establish_same_responsibility(left, right):
    assert compare_work(left, right)["state"] != "supported"


def test_action_and_object_cannot_be_taken_from_different_work():
    result = compare_work("评审软件代码；编写技术规范", "编写软件代码")
    assert result["state"] != "supported"


def test_unknown_words_are_visible_not_fabricated():
    result = explain_work("负责霁风处理")
    assert result["frames"] == []
    assert result["gaps"]


def test_matched_frames_keep_original_text_and_machine_status():
    text = "采用Go实现订单服务接口"
    result = explain_work({"text": text, "core": True})
    assert result["version"] == "bounded-work-semantics-2"
    assert result["semantic_review"] == "machine_unreviewed"
    assert all(text[f["start"]:f["end"]] == f["quote"] for f in result["frames"])


def test_unknown_core_and_unrecognized_extra_work_do_not_prove_whole_claim_equivalence():
    result = compare_work("开发软件；维护神秘装置", "开发软件")
    assert result["state"] == "unresolved"
    assert result["matched_aspects"]


def test_negated_other_work_does_not_erase_explicit_current_work():
    result = compare_work("不承担课程教学，仅开发软件", "开发软件")
    assert result["state"] == "supported"


def test_different_aspects_are_not_explicit_counterevidence():
    assert compare_work("开发订单接口", "维护网络配置")["state"] == "unresolved"


@pytest.mark.parametrize("tail", ["主持部门会议", "处理霁风事项", "协调跨组项目"])
def test_unknown_coordinated_tail_is_not_swallowed_by_a_supported_prefix(tail):
    result = compare_work("开发订单接口并" + tail, "开发订单接口")
    assert result["state"] == "unresolved"
    assert result["left"]["gaps"]
    assert result["matched_aspects"]


def test_concurrency_noun_is_not_a_coordinated_unknown_duty():
    assert not explain_work("优化软件接口并发性能")["gaps"]


@pytest.mark.parametrize("suffix", ["和组织招聘活动", "，招聘工程师"])
def test_unknown_conjunct_or_comma_tail_remains_uncovered(suffix):
    result = compare_work("开发订单接口" + suffix, "开发订单接口")
    assert result["state"] == "unresolved"
    assert result["left"]["gaps"]

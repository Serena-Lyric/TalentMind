"""Finite synthetic grammar checks, not real JD accuracy."""
import copy
import json
import socket
from pathlib import Path

import pytest

from test_foundation_inputs import area, load
from app.job_analysis.foundation.inputs import InputRecord

CATALOG = Path(__file__).resolve().parents[2] / "app/job_analysis/role_classification/proposals/families.v1.json"

CASES = [
    ("软件研发", "software_engineering", "开发后端接口并交付服务"),
    ("测试与质量工程", "test_quality_engineering", "设计测试用例并交付测试报告"),
    ("数据与人工智能", "data_ai", "训练机器学习模型并交付预测模型"),
    ("基础设施与运维", "infrastructure_operations", "维护云基础设施并保障系统可用性"),
    ("网络与信息安全", "network_information_security", "排查网络安全漏洞并交付修复方案"),
    ("嵌入式与系统软件", "embedded_system_software", "开发嵌入式驱动并交付固件"),
    ("技术服务与交付", "technical_services_delivery", "实施客户系统并交付集成方案"),
]


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("external/service network prohibited")
    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked)


def config():
    from app.job_analysis.role_classification.proposals.models import load_taxonomy
    return load_taxonomy(CATALOG)


def record(text, title="工程师", **changes):
    return InputRecord.from_row("fixture", dict(id=1, source="synthetic", job_title=title,
        duties=text, raw_text=text) | changes)


def suggest(item):
    from app.job_analysis.role_classification.proposals.rules import suggest
    return suggest(item, config())


@pytest.mark.parametrize("label,family,work", CASES)
def test_explicit_delivery_proposes_family_with_exact_original_core_evidence(label, family, work):
    item = record("核心职责：" + work + "。")
    body = suggest(item)
    assert [c["family_id"] for c in body["candidates"]] == [family]
    assert body["primary_family_hint"] == family
    assert body["resolution"] == "proposed"
    assert body["review_status"] == "pending_review"
    assert body["classification_complete"] is body["formal_statistics_eligible"] is False
    assert body["canonical_job"]["state"] == "unknown"
    assert body["technology_tracks"] == [] and body["seniority"]["state"] == "unknown"
    core = body["candidates"][0]["clues"][0]
    assert core["kind"] == "core"
    ref = core["evidence"]
    assert (ref["namespace"], ref["jd_id"], ref["fingerprint"]) == ("fixture", "1", item.fingerprint)
    assert item.payload[ref["field"]][ref["start"]:ref["end"]] == ref["quote"]
    assert ref["quote"] == "核心职责：" + work


@pytest.mark.parametrize("text", [
    "核心职责：销售转化并维护客户关系。",
    "负责向客户演示我司开发的软件产品。",
    "核心职责：部署产品演示环境并进行操作培训。",
    "负责普通客服咨询和商务维护。",
    "技术支持、解决方案、Python、部署、演示。",
    "公司介绍：负责开发后端接口并交付服务。",
    "不负责开发后端接口并交付服务。",
    "曾经负责开发后端接口并交付服务。",
    "培训内容：负责开发后端接口并交付服务。",
    "示例：负责实施客户系统并交付集成方案。",
    "任职要求：负责开发后端接口并交付服务。",
    "如果需要则负责实施客户系统并交付集成方案。",
    "客户负责开发后端接口并交付服务。",
    "负责演示我们研发的软件，促进销售转化。",
    "公司介绍\n负责开发后端接口并交付服务。",
    "历史项目\n负责实施客户系统并交付集成方案。",
])
def test_title_technical_words_company_negation_history_and_demonstrations_do_not_create_candidates(text):
    body = suggest(record(text, title="技术支持 / 软件工程师 / 解决方案工程师"))
    assert body["candidates"] == []
    assert body["primary_family_hint"] is None
    assert body["resolution"] in ("unknown", "unresolved")


@pytest.mark.parametrize("work", [
    "诊断客户系统复杂故障并交付修复方案",
    "设计客户系统技术架构并交付技术方案",
    "部署客户生产系统并完成系统验收",
])
def test_delivery_is_admitted_by_actual_technical_action_object_and_outcome(work):
    body = suggest(record("主要职责：" + work))
    assert [c["family_id"] for c in body["candidates"]] == ["technical_services_delivery"]


def test_title_alone_never_supplies_a_family_and_generic_title_does_not_conflict():
    assert suggest(record("负责客户沟通", title="软件工程师"))["candidates"] == []
    assert suggest(record("核心职责：开发后端接口并交付服务", title="工程师"))["resolution"] == "proposed"


def test_title_conflict_keeps_both_original_fields_and_no_primary():
    body = suggest(record("核心职责：设计测试用例并交付测试报告", title="软件工程师"))
    assert body["resolution"] == "unresolved" and body["primary_family_hint"] is None
    assert "title_duties_conflict" in body["reasons"]
    assert body["title_clues"][0]["evidence"]["field"] == "job_title"
    assert body["candidates"][0]["clues"][0]["evidence"]["field"] == "duties"


def test_explicit_auxiliary_never_outvotes_core_by_repetition():
    aux = "协助设计测试用例并交付测试报告。"
    body = suggest(record("核心职责：开发后端接口并交付服务。" + aux * 8))
    assert body["primary_family_hint"] == "software_engineering"
    assert {c["family_id"] for c in body["candidates"]} == {"software_engineering", "test_quality_engineering"}
    quality = next(c for c in body["candidates"] if c["family_id"] == "test_quality_engineering")
    assert all(c["kind"] == "auxiliary" for c in quality["clues"])


@pytest.mark.parametrize("text", [
    "负责开发后端接口并交付服务。负责设计测试用例并交付测试报告。",
    "核心职责：开发后端接口并交付服务。核心职责：设计测试用例并交付测试报告。",
    "协助开发后端接口并交付服务。",
    "核心职责：开发后端接口并交付服务。负责设计测试用例并交付测试报告。",
])
def test_no_primary_with_unspecified_or_competing_responsibilities(text):
    body = suggest(record(text))
    assert body["resolution"] == "unresolved"
    assert body["primary_family_hint"] is None


@pytest.mark.parametrize("title,text,reason", [
    ("全栈工程师", "核心职责：开发后端接口并交付服务", "compound_role_unresolved"),
    ("工程师", "招聘两个岗位：\n核心职责：开发后端接口并交付服务", "possible_multiple_positions"),
    ("工程师", "核心职责：开发后端接口并交付服务。其他职责待商定", "unsupported_duty_context"),
])
def test_compound_multiple_positions_and_unknown_context_block_single_primary(title, text, reason):
    body = suggest(record(text, title))
    assert body["resolution"] == "unresolved" and body["primary_family_hint"] is None
    assert reason in body["reasons"]
    assert "vacancy_count" not in body and body["canonical_job"]["value"] is None


def test_duties_raw_text_disagreement_and_raw_section_boundaries():
    body = suggest(record("核心职责：开发后端接口并交付服务",
        raw_text="岗位职责：核心职责：设计测试用例并交付测试报告"))
    assert {c["family_id"] for c in body["candidates"]} == {"software_engineering", "test_quality_engineering"}
    assert body["resolution"] == "unresolved"
    body = suggest(record("", raw_text="公司介绍：负责开发后端接口并交付服务。\n岗位职责：核心职责：实施客户系统并交付集成方案\n任职要求：熟悉Python"))
    assert [c["family_id"] for c in body["candidates"]] == ["technical_services_delivery"]
    assert body["candidates"][0]["clues"][0]["evidence"]["field"] == "raw_text"


@pytest.mark.parametrize("mutate", [
    lambda c: c["job_family"].append(c["job_family"][0]),
    lambda c: c["job_family"].pop(),
    lambda c: c["job_family"][0].update(id="unknown"),
    lambda c: c["job_family"][0].update(label="自定类别"),
    lambda c: c["job_family"][0].update(scope=" "),
    lambda c: c.update(revision=" "),
    lambda c: c.update(canonical_job=["backend"]),
    lambda c: c.update(extra=True),
])
def test_invalid_or_unconfirmed_catalog_values_rejected(mutate):
    from app.job_analysis.role_classification.proposals.models import FamilyTaxonomy
    value = config()
    mutate(value)
    with pytest.raises(ValueError):
        FamilyTaxonomy.model_validate(value)


def test_old_empty_and_synthetic_taxonomy_are_still_parsed_independently():
    from app.job_analysis.role_classification.models import Taxonomy
    from test_role_classification import taxonomy
    assert Taxonomy.model_validate(taxonomy()).mode == "synthetic_example"
    empty = taxonomy(mode="empty", job_family=[], canonical_job=[], technology_tracks=[], seniority=[])
    assert Taxonomy.model_validate(empty).job_family == []


@pytest.mark.parametrize("change", [
    dict(jd_id="2"), dict(namespace="other"), dict(fingerprint="0" * 64),
    dict(start=999), dict(end=999), dict(quote="假的"), dict(field="source"),
])
def test_proposal_boundary_rejects_foreign_or_fabricated_evidence(change):
    from app.job_analysis.role_classification.proposals.models import validate_proposal
    item = record("核心职责：开发后端接口并交付服务")
    body = suggest(item)
    body["candidates"][0]["clues"][0]["evidence"].update(change)
    with pytest.raises(ValueError):
        validate_proposal(item, body, config())


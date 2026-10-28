"""P0 trust-boundary checks use synthetic inputs, never a semantic oracle."""
from copy import deepcopy
import json
from pathlib import Path

import pytest


def example():
    return json.loads((Path(__file__).parents[2] / "app/job_analysis/baseline/examples/analysis.json").read_text(encoding="utf-8"))


def validate(data):
    from app.job_analysis.baseline.contract import validate_analysis
    return validate_analysis(data)


def test_open_alternative_and_usage_link_do_not_require_each_tool():
    data = validate(example())
    req = data.claims[1].requirement
    assert (req.state, req.combination, req.open_set) == ("required", "any_of", True)
    assert data.claims[2].requirement.state == "mentioned"
    assert data.relations[0].basis == "explicit"
    assert data.role_judgments == []  # Empty formal role catalog is legal.


@pytest.mark.parametrize("mutation", ["foreign_identity", "wrong_quote", "utf16_offset", "changed_input", "missing_reference", "degree_scope"])
def test_bad_evidence_and_dependency_binding_are_rejected(mutation):
    data = example()
    evidence = data["claims"][0]["evidence"][0]
    if mutation == "foreign_identity":
        evidence["jd_id"] = "other"
    elif mutation == "wrong_quote":
        evidence["quote"] = "不存在"
    elif mutation == "utf16_offset":
        evidence["start"] += 1
    elif mutation == "changed_input":
        data["input_row"]["requirements"] = "新增要求"
    elif mutation == "missing_reference":
        data["relations"][0]["duty_id"] = "missing"
    else:
        data["claims"][1]["requirement"]["degree"] = "熟练"
    with pytest.raises(ValueError):
        validate(data)


def test_inference_and_unknown_remain_distinct_and_sparse():
    data = example()
    data["relations"][0]["basis"] = "inferred"
    data["relations"][0]["reason"] = "上下文支持，尚无直接使用表述"
    assert validate(data).relations[0].basis == "inferred"
    data["relations"][0].update(basis="unknown", evidence=[], reason="无法确定联系")
    assert validate(data).relations[0].basis == "unknown"
    data["relations"] = []
    assert validate(data).relations == []


def test_failure_cannot_masquerade_as_complete_but_retains_partial_claims():
    data = example()
    data["coverage"]["classification"] = {"status": "failed", "reason": "timeout"}
    with pytest.raises(ValueError):
        validate(data)
    data["outcome"] = "partial"
    assert len(validate(data).claims) == 3


def test_knowledge_status_and_exact_definition_version_are_bound():
    data = example()
    data["knowledge"] = [{"id": "role-x", "revision": "1", "sha256": "0" * 64, "status": "candidate"}]
    data["role_judgments"] = [{"reference_id": "role-x", "reference_revision": "1", "knowledge_status": "formal", "judgment": "unresolved", "covered_duty_ids": [], "uncovered_duty_ids": ["d1"], "conflicts": [], "reason": "定义未覆盖不等于冲突"}]
    with pytest.raises(ValueError):
        validate(data)
    data["role_judgments"][0]["knowledge_status"] = "candidate"
    assert validate(data).role_judgments[0].judgment == "unresolved"
    data["role_judgments"][0]["reference_revision"] = "2"
    with pytest.raises(ValueError):
        validate(data)


def role_example(judgment="unresolved", conflicts=None):
    data = example()
    data["knowledge"] = [{"id": "synthetic-teaching-only", "revision": "1", "sha256": "0" * 64, "status": "candidate"}]
    data["role_judgments"] = [{"reference_id": "synthetic-teaching-only", "reference_revision": "1", "knowledge_status": "candidate", "judgment": judgment, "covered_duty_ids": [], "uncovered_duty_ids": ["d1"], "conflicts": [] if conflicts is None else conflicts, "reason": "仅对给定参照比较，不排除整个目录"}]
    return data


def explicit_role_conflict():
    return {"duty_id": "d1", "boundary_locator": "definition.boundaries[0]", "boundary_quote": "此合成参照仅包含课程讲授，明确排除系统状态存储与恢复的开发工作。", "reason": "本条JD承担系统状态存储与恢复开发，与参照明示边界冲突"}


def test_uncovered_duties_alone_cannot_exclude_a_role():
    data = role_example("not_supported")
    with pytest.raises(ValueError, match="explicit boundary conflict"):
        validate(data)
    data["role_judgments"][0]["judgment"] = "unresolved"
    assert validate(data).role_judgments[0].uncovered_duty_ids == ["d1"]


def test_role_exclusion_retains_traceable_boundary_and_jd_duty():
    result = validate(role_example("not_supported", [explicit_role_conflict()]))
    judgment = result.role_judgments[0]
    conflict = judgment.conflicts[0]
    assert (judgment.reference_id, judgment.reference_revision) == ("synthetic-teaching-only", "1")
    assert conflict.duty_id == result.claims[0].id
    assert conflict.boundary_locator == "definition.boundaries[0]"
    assert conflict.boundary_quote.startswith("此合成参照仅包含课程讲授")


@pytest.mark.parametrize("field,value", [("duty_id", "missing"), ("duty_id", "r1"), ("boundary_locator", " "), ("boundary_quote", ""), ("reason", " ")])
def test_role_exclusion_rejects_missing_or_unbound_conflict_details(field, value):
    conflict = explicit_role_conflict()
    conflict[field] = value
    with pytest.raises(ValueError):
        validate(role_example("not_supported", [conflict]))


def test_free_text_coverage_gap_is_not_traceable_exclusion_evidence():
    with pytest.raises(ValueError):
        validate(role_example("not_supported", ["岗位定义未覆盖此职责"]))


def test_unsupported_nested_logic_can_be_retained_without_forced_tree():
    data = example()
    data["claims"][1]["requirement"].update(combination="unresolved", state="uncertain", reason="嵌套作用域待确认")
    assert validate(data).claims[1].requirement.state == "uncertain"


def test_duplicate_claim_ids_and_missing_coverage_are_rejected():
    data = example()
    data["claims"].append(deepcopy(data["claims"][0]))
    with pytest.raises(ValueError):
        validate(data)
    data = example()
    del data["coverage"]["duties"]
    with pytest.raises(ValueError):
        validate(data)


def test_unknown_term_and_candidate_alignment_do_not_become_formal_knowledge():
    data = example()
    data["alignments"] = [{"claim_id": "r1", "member": "其他语言", "concept_id": None, "knowledge_id": None, "status": "unknown", "reason": "保留原文，尚无同义确认"}]
    assert validate(data).alignments[0].status == "unknown"
    data["alignments"][0]["status"] = "formal"
    with pytest.raises(ValueError):
        validate(data)


def test_role_reference_requires_source_and_cannot_self_promote():
    from app.job_analysis.baseline.contract import RoleReference
    path = Path(__file__).parents[2] / "app/job_analysis/baseline/role-references.v1.json"
    roles = json.loads(path.read_text(encoding="utf-8"))["items"]
    for role in roles:
        assert RoleReference.model_validate(role).status == "candidate"
        role["status"] = "formal"
        with pytest.raises(ValueError):
            RoleReference.model_validate(role)

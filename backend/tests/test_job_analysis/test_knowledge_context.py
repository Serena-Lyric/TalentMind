"""Contextual P2 explanations; synthetic behavior checks, not human role truth."""
from copy import deepcopy
from pathlib import Path

import pytest

from app.job_analysis.foundation.inputs import InputRecord, digest
from app.job_analysis.knowledge.attribution import attribute_roles, read_attribution
from app.job_analysis.knowledge.catalog import load_snapshot
from app.job_analysis.knowledge.role_policy import load_policy, bind_policy
from app.job_analysis.knowledge.storage import save_result
from test_knowledge_alignment import evidence
from test_knowledge_roles import analysis_with_duties

ROOT = Path(__file__).resolve().parents[2] / "app/job_analysis/knowledge"


def execute(value, *, empty=False):
    knowledge = load_snapshot(ROOT / "catalog/role-references.v3")
    policy = load_policy(ROOT / "policies/role-attribution.v2.json")
    if empty:
        # Empty-catalog tests below use a bound in-memory snapshot, not disk mutation.
        from app.job_analysis.knowledge.catalog import LoadedSnapshot
        from app.job_analysis.foundation.inputs import canonical
        from app.job_analysis.knowledge.models import validate_snapshot
        import hashlib
        data = knowledge.snapshot.model_dump()
        data["roles"] = []
        raw = canonical(data).encode()
        sha = hashlib.sha256(raw).hexdigest()
        knowledge = LoadedSnapshot(knowledge.path, validate_snapshot(data), sha, raw)
        rules = policy.policy.model_dump()
        rules["roles"] = []
        rules["knowledge_sha256"] = sha
        policy = bind_policy(rules)
    return attribute_roles(value, knowledge, policy, method="context")


def comparison(result, role_id="ref-software-development"):
    return next(r for r in result.comparisons if r.role_id == role_id)


def test_source_backed_paraphrase_is_not_required_to_repeat_pattern_tokens():
    value = analysis_with_duties(["负责开发软件服务"])
    value["claims"][0]["text"] = "把业务规则实现为可运行的系统功能"
    before = deepcopy(value)
    result = execute(value)
    assert comparison(result).supports
    assert result.primary_role_id == "ref-software-development"
    assert result.source_analysis.model_dump() == before
    assert not comparison(result).deliveries  # No fabricated explicit output.


def test_unknown_importance_on_explained_work_does_not_veto_known_core():
    result = execute(analysis_with_duties(
        ["负责开发软件服务", "分析用户需求"], core_values=[True, None]))
    assert comparison(result).judgment == "core_candidate"
    assert result.primary_role_id == "ref-software-development"
    assert result.source_claims[1].core is None


def test_unknown_unexplained_work_blocks_primary_but_retains_local_core():
    result = execute(analysis_with_duties(
        ["负责开发软件服务", "负责制定课程计划"], core_values=[True, None]))
    assert comparison(result).judgment == "core_candidate"
    assert result.primary_role_id is None
    assert result.axes.canonical_job.status == "unresolved"
    assert result.axes.canonical_job.candidates
    assert any(w.claim_id == "d2" for w in result.unaccounted_work)


@pytest.mark.parametrize("text", ["负责开发不同业务的应用程序", "负责修改未来版本的软件系统", "不断开发软件服务"])
def test_affirmative_words_containing_negation_characters_are_not_negated(text):
    assert comparison(execute(analysis_with_duties([text]))).supports


@pytest.mark.parametrize("text", [
    "不负责开发软件系统", "尚未开展软件系统开发", "如果客户需要，开发软件系统",
    "客户负责开发软件系统", "曾经开发软件系统", "讲解开发软件系统的方法",
])
def test_scope_blocks_other_conditional_historical_and_instructional_work(text):
    result = execute(analysis_with_duties([text]))
    assert not comparison(result).supports
    assert result.primary_role_id is None
    assert all(u.scope != "affirmed" for u in result.work_units)


def test_later_condition_does_not_retroactively_cancel_independent_work():
    result = execute(analysis_with_duties(["负责开发软件服务，如果有空则讲解课程"]))
    assert comparison(result).supports
    assert result.primary_role_id == "ref-software-development"
    assert any(u.scope == "conditional" for u in result.work_units)


def test_catalog_gap_preserves_auditable_work_and_marks_unconfigured_axes():
    result = execute(analysis_with_duties(["负责制定课程计划"]), empty=True)
    assert result.retrieval.status == "empty_catalog"
    assert len(result.work_units) == 1
    assert result.work_units[0].evidence.quote == "负责制定课程计划"
    assert result.work_units[0].reference_status == "unexplained"
    assert result.axis_assessments["seniority"].status == "not_evaluated"
    assert result.axis_assessments["seniority"].reason_code == "no_versioned_reference"
    assert result.identity_action == "none"


def test_goal_link_requires_same_source_context_and_retains_distinct_claims():
    value = analysis_with_duties(["负责开发软件服务，以满足订单处理需求"])
    row = InputRecord.from_row(value["namespace"], value["input_row"])
    value["claims"].insert(1, dict(id="g1", kind="goal", text="满足订单处理需求", core=None,
        requirement=None, evidence=[evidence(row, "满足订单处理需求")], reason="合成目标"))
    result = execute(value)
    assert any(link.work_claim_id == "d1" and link.context_claim_id == "g1"
               and link.basis == "source_context" for link in result.work_links)
    assert not comparison(result).deliveries
    assert result.source_claims[1].kind == "goal"


def test_unrelated_goal_cannot_lend_an_output_to_work():
    value = analysis_with_duties(["负责开发软件服务", "开展课程教学以满足学员需求"])
    row = InputRecord.from_row(value["namespace"], value["input_row"])
    value["claims"].insert(2, dict(id="g1", kind="goal", text="满足学员需求", core=None,
        requirement=None, evidence=[evidence(row, "满足学员需求")], reason="合成目标"))
    result = execute(value)
    assert not any(link.work_claim_id == "d1" for link in result.work_links)


def test_context_history_is_read_without_reexecuting_algorithm(tmp_path):
    result = execute(analysis_with_duties(["负责开发软件服务"]))
    payload = result.model_dump()
    save_result(tmp_path / "result", payload)
    assert read_attribution(tmp_path / "result").model_dump() == payload
    broken = deepcopy(payload)
    broken["work_units"][0]["evidence"]["quote"] = "伪造原文"
    save_result(tmp_path / "bad", broken)
    with pytest.raises(ValueError):
        read_attribution(tmp_path / "bad")


def test_context_cli_reexplain_preserves_old_value_and_lineage(tmp_path):
    from test_knowledge_cli import run_cli, write_analysis
    source = tmp_path / "p1.json"
    write_analysis(source, analysis_with_duties(["负责开发软件服务"]))
    old, new = tmp_path / "old", tmp_path / "new"
    common = ("--snapshot", ROOT / "catalog/role-references.v3", "--policy", ROOT / "policies/role-attribution.v2.json")
    assert run_cli("attribute", "--analysis", source, *common, "--output", old).returncode == 0
    payload = read_attribution(old).model_dump()
    run = run_cli("reexplain", "--previous", old, *common, "--method", "context", "--output", new)
    assert run.returncode == 0, run.stdout + run.stderr
    result = read_attribution(new)
    assert result.reinterprets_sha256 == digest(payload)
    assert result.source_analysis_sha256 == payload["source_analysis_sha256"]
    assert read_attribution(old).model_dump() == payload


@pytest.mark.parametrize("text", ["由客户开发软件系统", "让客户开发软件系统", "交给供应商开发软件系统", "负责开发软件系统相关课程"])
def test_delegated_or_course_work_does_not_become_software_ownership(text):
    assert not comparison(execute(analysis_with_duties([text]))).supports


@pytest.mark.parametrize("prefix", [
    "不负责", "客户负责", "曾经", "如果项目批准，同时", "客户负责分析用户需求，同时", "曾经分析用户需求，同时",
])
def test_cropped_p1_quote_cannot_hide_source_scope(prefix):
    local = "负责使用Python开发软件服务并交付应用"
    value = analysis_with_duties([prefix + local])
    row = InputRecord.from_row(value["namespace"], value["input_row"])
    value["claims"][0]["text"] = local
    value["claims"][0]["evidence"] = [evidence(row, local)]
    result = execute(value)
    assert not comparison(result).supports
    assert not comparison(result).deliveries
    assert not result.axes.technology_tracks.values
    assert result.primary_role_id is None


def test_second_coordinated_work_cannot_hide_behind_a_supported_prefix():
    result = execute(analysis_with_duties(["负责开发软件服务并制定课程计划"]))
    assert comparison(result).supports
    assert result.primary_role_id is None
    assert any("课程计划" in u.evidence.quote for u in result.unaccounted_work)


@pytest.mark.parametrize("text", ["负责开发软件服务并负责课程管理", "负责开发软件服务和编制财务计划"])
def test_unrecognized_second_work_is_not_filled_by_a_known_first_work(text):
    result = execute(analysis_with_duties([text]))
    assert result.primary_role_id is None
    assert result.unaccounted_work


@pytest.mark.parametrize("prefix", ["熟悉数据分析", "负责讲解软件系统开发方法"])
def test_independent_explicit_responsibility_does_not_inherit_prior_nonwork(prefix):
    result = execute(analysis_with_duties([prefix + "，本人负责开发软件服务"]))
    assert comparison(result).supports


def test_context_historical_technology_binding_is_not_weaker_than_v1(tmp_path):
    result = execute(analysis_with_duties(["使用Python开发软件服务"], requirement="Go"))
    payload = result.model_dump()
    c = payload["axes"]["technology_tracks"]["candidates"][0]
    req = next(c for c in payload["source_analysis"]["claims"] if c["kind"] == "requirement")
    row = InputRecord.from_row(payload["source_analysis"]["namespace"], payload["source_analysis"]["input_row"])
    c.update(value="Go", claim_ids=[req["id"]], evidence=[evidence(row, "Go")])
    payload["axes"]["technology_tracks"]["values"] = ["Go"]
    save_result(tmp_path / "bad", payload)
    with pytest.raises(ValueError):
        read_attribution(tmp_path / "bad")


@pytest.mark.parametrize("raw,local", [("无需本人负责开发软件系统", "本人负责开发软件系统"),
                                      ("不要求本岗位负责开发软件系统", "本岗位负责开发软件系统")])
def test_explicit_self_does_not_remove_a_governing_negation(raw, local):
    value = analysis_with_duties([raw])
    row = InputRecord.from_row(value["namespace"], value["input_row"])
    value["claims"][0].update(text=local, evidence=[evidence(row, local)])
    out = execute(value)
    assert not comparison(out).supports
    assert out.primary_role_id is None


def test_list_number_is_not_a_standalone_work_hypothesis():
    out = execute(analysis_with_duties(["1.负责开发软件服务"]))
    assert all(u.evidence.quote.strip() != "1" for u in out.work_units)
    assert any("开发软件服务" in u.evidence.quote for u in out.work_units)

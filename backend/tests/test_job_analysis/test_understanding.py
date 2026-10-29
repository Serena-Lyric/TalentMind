"""Synthetic processor outputs test engineering boundaries, not Chinese accuracy."""
import asyncio
from copy import deepcopy
import json

import pytest

ROW = {"id": "one", "source": "synthetic", "job_title": "开发", "raw_text":
       "🧪职责：使用 Redis 保存状态。\r\n要求：Python 或 Java 至少一种。摄影优先。"}


def quote(text, field="raw_text", occurrence=None):
    return dict(field=field, quote=text, occurrence=occurrence)


def claim(cid, kind, text, req=None):
    return dict(id=cid, kind=kind, text=text, evidence=[quote(text)],
                requirement=req, core=None, reason="原文陈述，未推断工作占比")


def requirement(members, **overrides):
    return dict(state="required", target="capability", category="technical_skill",
                members=members, combination="any_of", open_set=False, degree=None,
                degree_polarity=None, condition=None, reason="任选作用于组合",
                scope_evidence=[quote("Python 或 Java 至少一种")], **overrides)


def draft():
    return dict(coverage={d: dict(status="complete", reason="通读本输入，机器未审核")
                         for d in ("goals", "objects", "duties", "requirements", "relations")},
                claims=[claim("d1", "duty", "使用 Redis 保存状态"),
                        claim("r1", "requirement", "Python 或 Java 至少一种", requirement(["Python", "Java"]))],
                relations=[])


def run(data, *, row=None, finish="stop", status="ok"):
    from app.job_analysis.understanding import analyze
    from app.job_analysis.understanding.processor import Completion

    class Processor:
        descriptor = {"provider": "synthetic", "model": "fixture", "model_revision": "handwritten-1"}

        async def complete(self, messages):
            assert "human_labels" not in messages[-1]["content"]
            assert '"scope_evidence"' in messages[0]["content"]
            assert '"$defs"' in messages[0]["content"]
            schema = json.loads(messages[0]["content"].rsplit("\n", 1)[1])
            allowed = schema["$defs"]["Locator"]["properties"]["field"]["enum"]
            assert set(allowed) == {k for k, v in (row or ROW).items()
                                    if k in {"job_title", "raw_text", "duties", "requirements", "experience"} and v}
            return Completion(content=data if isinstance(data, str) else json.dumps(data, ensure_ascii=False),
                              finish_reason=finish, status=status, metadata={})

    return asyncio.run(analyze("synthetic", row or deepcopy(ROW), "v1", Processor()))


def test_actual_entry_binds_codepoint_evidence_and_keeps_classification_not_run():
    result = run(draft())
    analysis = result["analysis"]
    assert result["execution"]["status"] == "ok"
    assert analysis["outcome"] == "partial"
    assert analysis["coverage"]["classification"]["status"] == "not_run"
    assert analysis["semantic_review"] == "machine_unreviewed"
    ev = analysis["claims"][0]["evidence"][0]
    assert (ev["start"], ev["end"]) == (4, 17)
    assert analysis["claims"][1]["requirement"]["members"] == ["Python", "Java"]
    assert analysis["claims"][1]["requirement"]["combination"] == "any_of"
    assert analysis["role_judgments"] == []


def test_bad_evidence_does_not_discard_other_valid_claims():
    data = draft()
    data["claims"][1]["evidence"] = [quote("并不存在")]
    result = run(data)
    assert [c["id"] for c in result["analysis"]["claims"]] == ["d1"]
    assert result["execution"]["status"] == "partial"
    assert result["analysis"]["coverage"]["requirements"]["status"] == "partial"
    assert result["execution"]["issues"]


def test_ambiguous_quote_rejected_until_occurrence_is_explicit():
    row = deepcopy(ROW)
    row["raw_text"] += "使用 Redis 保存状态"
    result = run(draft(), row=row)
    assert [c["id"] for c in result["analysis"]["claims"]] == ["r1"]
    data = draft()
    data["claims"][0]["evidence"][0]["occurrence"] = 0
    assert len(run(data, row=row)["analysis"]["claims"]) == 2


@pytest.mark.parametrize("content,finish,status,want", [
    ("", "stop", "ok", "empty"),
    ('{"claims":[{"id":"d1"}', "length", "ok", "truncated"),
    ('{"claims": [}', "stop", "ok", "invalid_json"),
    ('{"claims": [], "claims": []}', "stop", "ok", "invalid_json"),
    ('{"claims": []}', "stop", "ok", "invalid_structure"),
    ("", None, "timeout", "timeout"),
    ("", None, "http_error", "http_error"),
])
def test_failures_have_distinct_status_and_no_fabricated_complete(content, finish, status, want):
    result = run(content, finish=finish, status=status)
    assert result["execution"]["status"] == want
    assert result["analysis"]["outcome"] == "failed"
    assert result["analysis"]["claims"] == []


def test_complete_json_at_length_limit_keeps_facts_but_not_complete_coverage():
    result = run(draft(), finish="length")
    assert result["execution"]["status"] == "truncated"
    assert len(result["analysis"]["claims"]) == 2
    assert all(v["status"] == "partial" for k, v in result["analysis"]["coverage"].items()
               if k != "classification")


def test_no_recognized_facts_is_not_execution_failure_or_not_required():
    data = draft()
    data["claims"] = []
    result = run(data)
    assert result["execution"]["status"] == "no_recognized_results"
    assert result["analysis"]["coverage"]["requirements"]["status"] == "complete"


def test_invalid_relation_cannot_attach_to_unrelated_or_rejected_claim():
    data = draft()
    data["relations"] = [dict(duty_id="d1", requirement_id="missing", basis="explicit",
                              evidence=[quote("使用 Redis 保存状态")], reason="原文使用联系")]
    result = run(data)
    assert result["analysis"]["relations"] == []
    assert len(result["analysis"]["claims"]) == 2
    assert result["analysis"]["coverage"]["relations"]["status"] == "partial"


def test_identical_field_copies_merge_with_all_evidence_and_remap_relations():
    row = deepcopy(ROW)
    row["duties"] = "使用 Redis 保存状态"
    data = draft()
    other = deepcopy(data["claims"][0])
    other.update(id="d2", evidence=[quote("使用 Redis 保存状态", "duties")])
    data["claims"].append(other)
    result = run(data, row=row)
    assert len(result["analysis"]["claims"]) == 2
    assert len(result["analysis"]["claims"][0]["evidence"]) == 2


def test_scope_degree_and_experience_are_not_rewritten():
    row = deepcopy(ROW)
    row["raw_text"] = "不要求精通但需了解 Python；Python 项目经验优先。"
    data = draft()
    req = requirement(["Python"])
    req.update(combination="single", degree="了解", degree_polarity="affirmed",
               scope_evidence=[quote("不要求精通但需了解 Python")])
    negative = deepcopy(req)
    negative.update(state="not_required", degree="精通", degree_polarity="negated")
    experience = deepcopy(req)
    experience.update(state="preferred", target="experience", category=None, degree=None,
                      degree_polarity=None, scope_evidence=[quote("Python 项目经验优先")])
    data["claims"] = [claim("r1", "requirement", "不要求精通但需了解 Python", req),
                      claim("r2", "requirement", "不要求精通但需了解 Python", negative),
                      claim("r3", "requirement", "Python 项目经验优先", experience)]
    result = run(data, row=row)
    requirements = [c["requirement"] for c in result["analysis"]["claims"]]
    assert [(r["state"], r["target"], r["degree"]) for r in requirements] == [
        ("required", "capability", "了解"), ("not_required", "capability", "精通"),
        ("preferred", "experience", None)]


def test_unrecognized_item_keys_and_coverage_claims_are_not_silently_accepted():
    data = draft()
    data["claims"][0]["human_reviewed"] = True
    data["coverage"]["requirements"]["status"] = "not_run"
    result = run(data)
    assert result["analysis"]["claims"] == []
    assert result["execution"]["status"] == "partial"


def test_processor_exception_is_saved_as_failure_without_exception_text():
    from app.job_analysis.understanding import analyze

    class Broken:
        descriptor = dict(provider="synthetic", model="fixture", model_revision="1")

        async def complete(self, messages):
            raise RuntimeError("sensitive provider context")

    result = asyncio.run(analyze("synthetic", ROW, "v1", Broken()))
    assert result["execution"]["status"] == "processor_error"
    assert result["analysis"]["outcome"] == "failed"
    assert "sensitive provider context" not in str(result)


@pytest.mark.parametrize("bad_kind", [[], {}])
def test_malformed_kind_does_not_abort_other_valid_claims(bad_kind):
    data = draft()
    data["claims"].append({"id": "bad", "kind": bad_kind})
    result = run(data)
    assert len(result["analysis"]["claims"]) == 2
    assert result["execution"]["status"] == "partial"


@pytest.mark.parametrize("coverage,want", [("failed", "failed"), ("not_run", "not_run")])
def test_no_executed_dimension_does_not_report_partial_success(coverage, want):
    data = draft()
    data["claims"] = []
    for value in data["coverage"].values():
        value["status"] = coverage
    result = run(data)
    assert result["execution"]["status"] == want
    assert result["analysis"]["outcome"] == want


def test_absent_semantic_field_can_reanchor_only_to_unique_literal_raw_quote_with_audit():
    data = draft()
    data["claims"][1]["evidence"][0]["field"] = "requirements"
    data["claims"][1]["requirement"]["scope_evidence"][0]["field"] = "requirements"
    result = run(data)
    assert len(result["analysis"]["claims"]) == 2
    assert result["analysis"]["claims"][1]["evidence"][0]["field"] == "raw_text"
    assert result["execution"]["grounding_adjustments"]
    row = deepcopy(ROW)
    row["requirements"] = "另一个明确字段，并无上述表达"
    assert len(run(data, row=row)["analysis"]["claims"]) == 1
    row.pop("requirements")
    row["raw_text"] += "Python 或 Java 至少一种"
    assert len(run(data, row=row)["analysis"]["claims"]) == 1


def test_long_lived_processor_records_loaded_code_version_not_later_disk_edits(monkeypatch):
    from app.job_analysis.understanding import core
    before = run(draft())["analysis"]["analyzer"]
    monkeypatch.setattr(core.Path, "read_bytes", lambda self: b"later on-disk edit, not loaded code")
    after = run(draft())["analysis"]["analyzer"]
    assert before == after

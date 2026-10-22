"""Hand-specified synthetic counterexamples; these are not an accuracy benchmark."""
import json
import sqlite3
from pathlib import Path
import subprocess
import sys

import pytest

from test_foundation_inputs import area, load


def row(text, **changes):
    return dict(id=1, source="synthetic", job_title="工程师", raw_text=text) | changes


def analyze(text, **fields):
    from app.job_analysis.foundation.inputs import InputRecord
    from app.job_analysis.semantics.rules import SkillSemanticAnalyzer
    from app.job_analysis.semantics.validation import validate
    record = InputRecord.from_row("fixture", row(text, **fields))
    analyzer = SkillSemanticAnalyzer()
    return validate(analyzer.analyze(record), record, analyzer)


def states(result, skill="python"):
    return [item["state"] for item in result["effective"] if item["skill"] == skill]


@pytest.mark.parametrize("text,want", [
    ("必须掌握 Python。", "required"),
    ("任职要求：\n熟悉Python。", "required"),
    ("需要了解 Python 基础。", "required"),
    ("Python 经验优先。", "preferred"),
    ("加分项：\n熟悉 Python。", "preferred"),
    ("技术栈：Python。", "mentioned"),
    ("工作职责：\n使用 Python 开发服务。", "mentioned"),
    ("不要求 Python。", "not_required"),
    ("无需掌握 Python。", "not_required"),
    ("可能要求 Python，具体待定。", "uncertain"),
    ("Python。", "mentioned"),
])
def test_five_states_need_clause_context_not_presence(text, want):
    result = analyze(text)
    assert states(result) == [want]
    assert result["statements"][0]["evidence"]["quote"]
    assert result["semantic_validation"] == "deterministic_rules_only"


@pytest.mark.parametrize("text", [
    "工作职责：\n使用 Python。", "技术栈：Python、Java。",
    "不要求精通 Python。", "并非必须掌握 Python。",
    "公司产品要求精通 Python，非本岗位要求。",
    "如果参加数据项目，则需要掌握 Python。",
    "任职要求：\n不熟悉 Python 也可以。",
    "任职要求：\n学习 Python 的机会。",
    "任职要求：\nJava 或 Python。",
])
def test_high_impact_non_required_never_becomes_independent_required(text):
    assert "required" not in states(analyze(text))


def test_any_of_required_is_group_requirement_only():
    result = analyze("Java 或 Python 至少掌握一种。")
    group = result["statements"][0]
    assert group["relation"] == "any_of" and group["state"] == "required"
    assert [s["name"] for s in group["skills"]] == ["java", "python"]
    assert states(result, "java") == states(result) == ["mentioned"]
    assert all(e["reason"] == "group_membership_only" for e in result["effective"])


def test_all_of_and_independent_statement_do_not_erase_each_other():
    result = analyze("必须同时掌握 Java 和 Python。必须掌握 Python。")
    assert result["statements"][0]["relation"] == "all_of"
    assert result["statements"][0]["state"] == "required"
    assert states(result) == ["required"]
    assert len(result["effective"][1]["group_ids"]) == 1


def test_distinct_degrees_not_false_conflict():
    result = analyze("不要求精通 Python，但需了解 Python 基础。")
    assert [(s["state"], s["degree"]) for s in result["statements"]] == [
        ("not_required", "expert"), ("required", "basic")]
    assert all(not e["conflict"] for e in result["effective"])
    assert result["statements"][0]["degree_evidence"]["quote"] == "精通"


@pytest.mark.parametrize("first,second", [
    ("必须掌握 Python。", "不要求掌握 Python。"),
    ("不要求掌握 Python。", "必须掌握 Python。"),
])
def test_true_conflict_keeps_both_evidences_and_never_chooses_order(first, second):
    result = analyze(first + second)
    assert states(result) == ["uncertain"]
    assert result["effective"][0]["conflict"] is True
    assert result["effective"][0]["statement_ids"] == ["s1", "s2"]
    assert len(result["statements"]) == 2


def test_object_and_condition_cannot_create_unqualified_required_or_false_conflict():
    result = analyze("前端岗位要求掌握 Python。后端岗位不要求掌握 Python。")
    assert not any(e["conflict"] for e in result["effective"])
    assert "required" not in states(result)
    assert result["coverage"] == "incomplete"


@pytest.mark.parametrize("text", [
    "必须掌握 (Java 或 Python) 和 SQL。", "Java、Python 等至少两种。",
    "无需 Python 或 Java 中的某些能力。", "不但熟悉 Python，而且精通 Java。",
])
def test_complex_logic_retains_uncertainty_and_original(text):
    result = analyze(text)
    assert result["coverage"] == "incomplete"
    assert all(s["relation"] is None and s["state"] == "uncertain" for s in result["statements"])
    assert result["issues"]


def test_alias_overlap_repetition_and_unicode_positions():
    text = "任职要求：\n熟悉python3。熟悉python3。"
    result = analyze(text)
    assert [s["skills"][0]["name"] for s in result["statements"]] == ["python", "python"]
    assert len({s["evidence"]["start"] for s in result["statements"]}) == 2
    for statement in result["statements"]:
        for evidence in [statement["evidence"], statement["context"], statement["skills"][0]["evidence"]]:
            assert text[evidence["start"]:evidence["end"]] == evidence["quote"]


def test_years_do_not_become_degree_and_unparsed_text_blocks_complete():
    result = analyze("必须掌握 Python。另需五年工作经验。", experience="5年")
    assert result["statements"][0]["degree"] is None
    assert result["coverage"] == "incomplete"


def test_unrelated_conditional_does_not_poison_separate_requirement():
    result = analyze(
        "岗位职责：负责开发软件。\n"
        "任职要求：熟悉 Python。\n"
        "如果参加其他项目，则需要掌握 Docker。"
    )

    assert states(result) == ["required"]
    assert result["statements"][0]["condition"] is None


def test_inline_requirement_heading_changes_section_after_duty_sentence():
    result = analyze("岗位职责：负责后端接口开发。任职要求：熟悉 Python。")

    assert states(result) == ["required"]
    assert result["statements"][0]["section"] == "requirements"


@pytest.mark.parametrize("text", [
    "任职要求：\n本科及以上学历。\n熟练掌握 Python，并能独立完成接口开发。",
    "职位描述 1.负责后端接口开发。 职位要求 1.本科及以上学历。 2.熟练掌握 Python。",
    "任职要求：\n针对有项目经验的候选人，需要了解业务流程。\n熟练掌握 Python。",
])
def test_unparsed_experience_lines_do_not_erase_following_requirement_section(text):
    result = analyze(text)

    assert states(result) == ["required"]
    assert result["statements"][0]["section"] == "requirements"


@pytest.mark.parametrize("text,skill,want", [
    ("任职要求：\n熟练掌握 Python，并能独立完成接口开发。", "python", "required"),
    ("加分项：\n熟悉 Docker，具备容器化交付经验。", "docker", "preferred"),
])
def test_explicit_capability_with_trailing_context_keeps_requirement_state(text, skill, want):
    result = analyze(text)

    assert states(result, skill) == [want]
    assert result["statements"][0]["evidence"]["quote"] in text


@pytest.mark.parametrize("text", [
    "任职要求：\n熟悉 Python 或其他技术。",
    "任职要求：\n熟悉 Python（非必备）。",
    "任职要求：\n熟悉 Python，属于可选要求。",
    "任职要求：\n熟悉 Python，非硬性条件。",
])
def test_open_choice_or_limiting_tail_does_not_promote_single_skill(text):
    result = analyze(text)

    assert states(result) == ["uncertain"]
    assert result["statements"][0]["reason"] != "section_capability_extended"
    assert result["coverage"] == "incomplete"


@pytest.mark.parametrize("text", [
    "任职要求：\n熟悉 Python 或自研脚本语言。",
    "任职要求：\n熟悉 Python 或未登记内部框架。",
])
def test_known_skill_with_unregistered_alternative_stays_uncertain(text):
    result = analyze(text)

    assert states(result) == ["uncertain"]
    assert result["statements"][0]["reason"] == "unresolved_alternative"
    assert result["coverage"] == "incomplete"


def test_enumeration_delimiter_without_unparsed_alternative_keeps_required():
    result = analyze("任职要求：\n熟悉 Python、业务流程。")

    assert states(result) == ["required"]
    assert result["statements"][0]["reason"] == "section_capability_extended"


def test_job_title_lists_skill_as_mention_only():
    result = analyze("暂无描述", job_title="Python 工程师")

    assert states(result) == ["mentioned"]
    assert result["statements"][0]["reason"] == "title_reference_only"
    assert result["statements"][0]["evidence"]["field"] == "job_title"


def test_compatibility_variant_at_least_one_keeps_any_of_semantics():
    result = analyze("任职要求：\n熟练掌握 Java、Python、TypeScript ⾄少⼀种")

    statement = result["statements"][0]
    assert statement["state"] == "required"
    assert statement["relation"] == "any_of"
    assert {skill["name"] for skill in statement["skills"]} == {"java", "python", "typescript"}


def test_structured_clause_wins_over_identical_raw_text_copy():
    text = "工作职责：使用 Python 开发服务。"
    result = analyze(text, duties=text)

    assert states(result) == ["mentioned"]
    assert [statement["evidence"]["field"] for statement in result["statements"]] == ["duties"]


def test_unknown_skill_no_result_is_not_execution_failure_or_uncertain_skill():
    result = analyze("要求掌握 UnlistedFixtureLang。")
    assert result["outcome"] == "no_recognized_skills"
    assert result["effective"] == result["statements"] == []
    assert result["coverage"] == "incomplete" and result["issues"]


@pytest.mark.parametrize("tamper", ["foreign", "offset", "semantic", "group", "coverage"])
def test_boundary_rejects_forged_evidence_and_semantics(tamper):
    from app.job_analysis.foundation.inputs import InputRecord
    from app.job_analysis.semantics.rules import SkillSemanticAnalyzer
    from app.job_analysis.semantics.validation import validate
    record = InputRecord.from_row("fixture", row("技术栈：Python。"))
    analyzer = SkillSemanticAnalyzer()
    value = analyzer.analyze(record)
    if tamper == "foreign":
        value["statements"][0]["evidence"]["jd_id"] = "other"
    elif tamper == "offset":
        value["statements"][0]["evidence"]["start"] += 1
    elif tamper == "semantic":
        value["statements"][0]["state"] = "required"
    elif tamper == "group":
        value["statements"][0]["relation"] = "any_of"
    else:
        value["coverage"] = "incomplete" if value["coverage"] == "complete" else "complete"
    with pytest.raises(ValueError):
        validate(value, record, analyzer)


def execute(area, rows=None, **options):
    from app.job_analysis.semantics.runner import execute as run
    from app.job_analysis.semantics.store import SemanticStore
    with SemanticStore(area / "state.sqlite3") as store:
        return run(store, load(area, rows or [row("必须掌握 Python。")]), **options)


def test_run_reuses_complete_but_input_and_rule_changes_append_history(area):
    from app.job_analysis.semantics.runner import replay
    from app.job_analysis.semantics.store import SemanticStore
    first = execute(area)
    second = execute(area)
    assert first["members"][0]["attempt_id"] == second["members"][0]["attempt_id"]
    changed = execute(area, [row("Python 经验优先。")])
    versioned = execute(area, rules_revision="v2")
    assert len({x["members"][0]["attempt_id"] for x in (first, changed, versioned)}) == 3
    with SemanticStore(area / "state.sqlite3") as store:
        assert replay(store, first["run_id"]) == first
        assert store.conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert store.conn.execute("SELECT count(*) FROM facts").fetchone()[0] == 0
    assert first["formal_statistics_eligible"] is False


def test_failed_call_and_no_skill_result_are_separate_durable_outcomes(area):
    from app.job_analysis.semantics.rules import SkillSemanticAnalyzer
    class Broken(SkillSemanticAnalyzer):
        def analyze(self, record):
            raise RuntimeError("never-persist-this")
    failed = execute(area, analyzer=Broken())
    empty = execute(area, [row("尚无技能要求说明。")])
    assert failed["members"][0]["status"] == "failed"
    assert failed["members"][0]["body"] is None
    assert "never-persist-this" not in json.dumps(failed)
    assert empty["members"][0]["status"] == "partial"
    assert empty["members"][0]["body"]["outcome"] == "no_recognized_skills"


def test_history_replace_update_delete_are_blocked(area):
    from app.job_analysis.semantics.store import SemanticStore
    execute(area)
    with SemanticStore(area / "state.sqlite3") as store:
        for table in ("b2_versions", "b2_attempts", "b2_reports", "b2_observations"):
            saved = store.conn.execute(f"SELECT * FROM {table} LIMIT 1").fetchone()
            for sql, args in [
                (f"DELETE FROM {table}", ()),
                (f"INSERT OR REPLACE INTO {table} VALUES ({','.join('?' for _ in saved)})", tuple(saved)),
            ]:
                with pytest.raises(sqlite3.IntegrityError):
                    store.conn.execute(sql, args)


@pytest.mark.parametrize("text", ["必须掌握 S 和 Python。", "必须掌握 S。", "Java 或 Java 至少掌握一种。"])
def test_literal_unknown_tokens_and_repeated_members_cannot_fabricate_groups(text):
    result = analyze(text)
    assert all(s["relation"] is None for s in result["statements"])
    assert not any(s["state"] == "required" for s in result["statements"])
    assert result["coverage"] == "incomplete"


@pytest.mark.parametrize("text,degree", [
    ("任职要求：\n基础了解 Python。", "basic"),
    ("任职要求：\n熟悉 Python。", "familiar"),
    ("任职要求：\n熟练掌握 Python。", "proficient"),
    ("必须精通 Python。", "expert"),
])
def test_degree_is_statement_bound_with_original_wording(text, degree):
    result = analyze(text)
    assert result["statements"][0]["degree"] == degree
    assert result["statements"][0]["degree_evidence"]["quote"] in text


@pytest.mark.parametrize("text", [
    "加分项：\nJava 或 Python 至少掌握一种。",
    "技术栈：Python。", "工作职责：\n使用 Python 开发服务。",
    "不要求精通Python，但需了解Python基础。",
    "必须掌握 Python。Python 经验优先。",
])
def test_statement_resolution_does_not_promote_other_evidence(text):
    result = analyze(text)
    if text.startswith("加分项"):
        assert result["statements"][0]["state"] == "preferred"
        assert states(result) == ["mentioned"]
    elif text.startswith("必须掌握"):
        assert states(result) == ["required", "preferred"]
        assert not any(e["conflict"] for e in result["effective"])
    elif text.startswith("不要求"):
        assert [(e["degree"], e["state"]) for e in result["effective"]] == [("expert", "not_required"), ("basic", "required")]
    else:
        assert states(result) == ["mentioned"]


def test_absent_skill_not_negative_and_unknown_clause_not_hidden():
    result = analyze("必须掌握 Java。要求掌握 UnlistedFixtureLang。")
    assert states(result) == []
    assert result["coverage"] == "incomplete"
    assert states(result, "java") == ["required"]
    assert result["issues"][0]["evidence"]["quote"] == "要求掌握 UnlistedFixtureLang"


def test_same_jd_is_independent_of_other_jobs_and_partial_is_reusable(area):
    first = execute(area, [row("可能要求Python，待定。")])
    second = execute(area, [row("必须精通 Python。", id=2)])
    assert first["members"][0] == second["members"][0]
    assert second["audit"] == dict(jd_records=2, completed=1, partial=1, failed=0, no_recognized_skills=0)


def test_observation_and_full_payload_invalidation_and_historical_resume(area):
    from app.job_analysis.semantics.runner import execute as run, resume, replay
    from app.job_analysis.semantics.rules import SkillSemanticAnalyzer
    from app.job_analysis.semantics.store import SemanticStore
    with SemanticStore(area / "state.sqlite3") as store:
        first = run(store, load(area, [row("必须掌握Python。", crawled_at="2026-10-15")]))
        observed = run(store, load(area, [row("必须掌握Python。", crawled_at="2026-10-16")]))
        assert first["members"][0] == observed["members"][0]
        assert [r[0] for r in store.conn.execute("SELECT crawled_at FROM b2_observations ORDER BY rowid")] == ["2026-10-15", "2026-10-16"]
        changed = run(store, load(area, [row("必须掌握Python。", custom="changed")]))
        assert changed["members"][0]["snapshot_id"] != first["members"][0]["snapshot_id"]
        assert resume(store, first["run_id"]) == replay(store, first["run_id"]) == first
        analyzer = SkillSemanticAnalyzer()
        analyzer.aliases["python"] = "fixture-change"
        with pytest.raises(ValueError, match="dependencies"):
            resume(store, first["run_id"], analyzer=analyzer)


def test_actual_rule_source_change_invalidates_without_label_change(area, monkeypatch):
    from app.job_analysis.semantics.rules import SkillSemanticAnalyzer
    from app.job_analysis.semantics.store import SemanticStore
    from app.job_analysis.semantics.runner import execute as run, replay, resume
    first = execute(area)
    original = Path.read_bytes
    def changed_bytes(path):
        content = original(path)
        return content + b"\n# synthetic rule change\n" if path.name == "rules.py" else content
    monkeypatch.setattr(Path, "read_bytes", changed_bytes)
    with SemanticStore(area / "state.sqlite3") as store:
        newer = run(store, load(area, [row("必须掌握 Python。")]))
        assert newer["version_id"] != first["version_id"]
        assert newer["members"][0]["attempt_id"] != first["members"][0]["attempt_id"]
        assert replay(store, first["run_id"]) == first
        with pytest.raises(ValueError, match="dependencies"):
            resume(store, first["run_id"], analyzer=SkillSemanticAnalyzer())


def test_a_b1_b2_shared_store_preserves_legacy_history_and_both_replays(area):
    from app.job_analysis.foundation.runner import execute as run_a
    from app.job_analysis.foundation.aggregate import replay as replay_a
    from app.job_analysis.foundation.store import AnalysisStore
    from app.job_analysis.screening.runner import execute as run_b1, replay as replay_b1
    from app.job_analysis.screening.store import ScreeningStore
    from app.job_analysis.semantics.runner import execute as run_b2
    from app.job_analysis.semantics.store import SemanticStore
    from test_foundation_runner import FakeAnalyzer
    from test_foundation_validation import claim, response
    batch = load(area, [row("必须掌握 Python。", duties="负责开发软件服务。")])
    analyzer = FakeAnalyzer(response([claim(requirement="legacy_required", evidence=dict(
        namespace="fixture", jd_id="1", field="raw_text", quote="Python"))]))
    with AnalysisStore(area / "state.sqlite3") as store:
        a = run_a(store, batch, analyzer)
        old_facts = store.conn.execute("SELECT body FROM facts ORDER BY id").fetchall()
    scope = json.loads((Path(__file__).resolve().parents[2] / "app/job_analysis/screening/software-related.offline.json").read_text(encoding="utf-8"))
    with ScreeningStore(area / "state.sqlite3") as store:
        b1 = run_b1(store, batch.path, "fixture", scope=scope)
        old_decisions = [tuple(r) for r in store.conn.execute("SELECT * FROM b1_decisions")]
    with SemanticStore(area / "state.sqlite3") as store:
        b2 = run_b2(store, batch)
        assert b2["members"][0]["body"]["statements"][0]["state"] == "required"
        assert [r[0] for r in store.conn.execute("SELECT body FROM facts ORDER BY id")] == [r[0] for r in old_facts]
        assert [tuple(r) for r in store.conn.execute("SELECT * FROM b1_decisions")] == old_decisions
        assert store.conn.execute("PRAGMA user_version").fetchone()[0] == 1
        assert replay_a(store, a["aggregate_id"])["members"] == a["members"]
        assert replay_b1(store, b1["run_id"]) == b1
    with AnalysisStore(area / "state.sqlite3") as store:
        again = run_a(store, batch, analyzer)
        assert again["members"] == a["members"]
        fact = again["members"][0]["facts"][0]
        assert fact["requirement"] == "legacy_required" and fact["semantic_status"] == "unreviewed"
    with ScreeningStore(area / "state.sqlite3") as store:
        assert run_b1(store, batch.path, "fixture", scope=scope)["members"][0]["decision_id"] == b1["members"][0]["decision_id"]


@pytest.mark.parametrize("phase", ["after_prepare", "after_start", "after_analyze", "before_commit", "after_commit", "after_report", "after_stage_output", "after_output"])
def test_real_process_exit_resumes_without_duplicate_results(area, phase):
    from app.job_analysis.semantics.store import SemanticStore
    from app.job_analysis.semantics.runner import resume, replay
    batch = load(area, [row("必须掌握Python。"), row("Java或Python至少掌握一种。", id=2)])
    program = r'''
import os, sys
from pathlib import Path
from app.job_analysis.foundation.inputs import read_snapshot
from app.job_analysis.semantics.store import SemanticStore
import app.job_analysis.semantics.runner as runner
import app.job_analysis.foundation.runner as foundation
area, phase = Path(sys.argv[1]), sys.argv[2]
def crash(stage):
    if stage == phase:
        os._exit(71)
runner.checkpoint = foundation.checkpoint = crash
with SemanticStore(area / 'state.sqlite3') as store:
    runner.execute(store, read_snapshot(area / 'input.json', 'fixture'), output=area / 'out')
'''
    child = subprocess.run([sys.executable, "-X", "utf8", "-c", program, str(area), phase], capture_output=True, timeout=30)
    assert child.returncode == 71, child.stderr.decode("utf-8", errors="replace")
    with SemanticStore(area / "state.sqlite3") as store:
        identity = store.conn.execute("SELECT id FROM b2_runs").fetchone()[0]
        result = resume(store, identity, output=area / "out")
        assert result["audit"]["completed"] == 2
        assert store.conn.execute("SELECT count(*) FROM b2_attempts WHERE status='running'").fetchone()[0] == 0
        assert store.conn.execute("SELECT count(*) FROM b2_attempts WHERE status='completed'").fetchone()[0] == 2
        assert replay(store, identity) == result
        assert json.loads((area / "out" / (identity + ".json")).read_text(encoding="utf-8")) == result
        assert not list((area / "out").glob("*.tmp"))


def test_publication_failure_can_resume_and_output_cannot_overwrite_input(area, monkeypatch):
    import app.job_analysis.semantics.runner as runner
    from app.job_analysis.semantics.store import SemanticStore
    batch = load(area, [row("必须掌握Python。")])
    original = runner.publish
    def fail(*args):
        raise OSError("synthetic publication failure")
    with SemanticStore(area / "state.sqlite3") as store:
        monkeypatch.setattr(runner, "publish", fail)
        with pytest.raises(OSError):
            runner.execute(store, batch, output=area / "out")
        identity = store.conn.execute("SELECT id FROM b2_runs").fetchone()[0]
        assert store.conn.execute("SELECT status FROM b2_runs").fetchone()[0] == "publication_failed"
        monkeypatch.setattr(runner, "publish", original)
        runner.resume(store, identity, output=area / "out")
        assert store.conn.execute("SELECT count(*) FROM b2_attempts").fetchone()[0] == 1
        with pytest.raises(ValueError):
            runner.execute(store, batch, output=batch.path)
        with pytest.raises(ValueError):
            runner.execute(store, batch, output=store.path)
        assert batch.path.read_bytes() == batch.raw_bytes


def test_cli_real_run_resume_replay_and_malformed_input(area):
    path = load(area, [row("不要求精通Python，但需了解Python基础。")]).path
    command = [sys.executable, "-X", "utf8", "-m", "app.job_analysis.semantics"]
    common = ["--state", str(area / "state.sqlite3"), "--output", str(area / "out")]
    child = subprocess.run(command + ["run", "--input", str(path), "--dataset", "fixture"] + common, capture_output=True, timeout=30)
    assert child.returncode == 0, child.stderr
    identity = json.loads(child.stdout)["run_id"]
    for action in ("resume", "replay"):
        child = subprocess.run(command + [action, "--run", identity] + common, capture_output=True, timeout=30)
        assert child.returncode == 0, child.stderr
    path.write_text("[{", encoding="utf-8")
    child = subprocess.run(command + ["run", "--input", str(path), "--dataset", "fixture"] + common, capture_output=True, timeout=30)
    assert child.returncode == 2 and not child.stdout


def test_unparsed_multi_skill_clause_does_not_distribute_degree_to_every_skill():
    result = analyze("使用 Python，并要求精通 Java。")
    assert result["coverage"] == "incomplete"
    assert all(s["degree"] is None and s["degree_evidence"] is None for s in result["statements"])
    assert "精通" in result["statements"][0]["evidence"]["quote"]


@pytest.mark.parametrize("heading", ["加分项", "【加分项】", "优先条件", "加分项："])
def test_heading_without_colon_cannot_inherit_required_section(heading):
    result = analyze("任职要求：\n熟悉 Java。\n" + heading + "\n熟悉 Python。")
    assert states(result, "java") == ["required"]
    assert states(result) == ["preferred"]


@pytest.mark.parametrize("qualifier", ["仅适用于实习生。", "仅限参与项目的人员。", "限于导师岗位。", "条件见附件。",
    "以下要求仅对实习生生效。", "当参与数据项目时。", "不必满足以下条件。"])
def test_unparsed_subject_context_cannot_disappear_on_later_lines(qualifier):
    result = analyze(qualifier + "\n必须掌握 Python。\n必须掌握 Java。")
    assert "required" not in states(result)
    assert "required" not in states(result, "java")
    assert result["coverage"] == "incomplete"


@pytest.mark.parametrize("fragment", ["必须精通 Java：", "SQL：", "其他条件："])
def test_unknown_heading_preserves_unparsed_content_instead_of_complete_omission(fragment):
    result = analyze("任职要求：\n熟悉 Python。\n" + fragment)
    assert result["coverage"] == "incomplete" and result["issues"]
    if "Java" in fragment:
        assert states(result, "java") == ["uncertain"]
    elif "SQL" in fragment:
        assert states(result, "sql") == ["uncertain"]


def test_conditional_context_is_not_lost_at_field_boundary():
    result = analyze("仅适用于实习生。", requirements="必须掌握 Python。")
    assert states(result) == ["uncertain"]
    assert result["statements"][0]["condition"]


@pytest.mark.parametrize("text", [
    "必须掌握 Python。Python 经验优先。", "Python 经验优先。必须掌握 Python。",
])
def test_capability_and_experience_are_distinct_objects_in_sqlite(area, text):
    from app.job_analysis.semantics.store import SemanticStore
    result = execute(area, [row(text)])
    member = result["members"][0]
    assert member["status"] == "completed"
    with SemanticStore(area / "state.sqlite3") as store:
        body = json.loads(store.conn.execute("SELECT body FROM b2_attempts WHERE id=?", (member["attempt_id"],)).fetchone()[0])
    assert body == member["body"]
    assert not any(e["conflict"] for e in body["effective"])
    assert {(s["requirement_object"], s["state"], s["degree"]) for s in body["statements"]} == {
        ("capability", "required", None), ("experience", "preferred", None)}
    assert {(e["requirement_object"], e["state"]) for e in body["effective"]} == {
        ("capability", "required"), ("experience", "preferred")}
    assert all(not e["conflict"] and len(e["statement_ids"]) == 1 for e in body["effective"])


def test_requirement_object_does_not_replace_capability_degree(area):
    result = execute(area, [row("必须精通 Python。Python 经验优先。")])
    body = result["members"][0]["body"]
    assert {(e["requirement_object"], e["degree"], e["state"]) for e in body["effective"]} == {
        ("capability", "expert", "required"), ("experience", None, "preferred")}
    assert body["statements"][0]["degree_evidence"]["quote"] == "精通"


@pytest.mark.parametrize("text", [
    "必须掌握 Python。不要求掌握 Python。", "不要求掌握 Python。必须掌握 Python。",
])
def test_mutually_exclusive_capability_requirements_still_conflict_in_sqlite(area, text):
    from app.job_analysis.semantics.store import SemanticStore
    result = execute(area, [row(text)])
    with SemanticStore(area / "state.sqlite3") as store:
        body = json.loads(store.conn.execute("SELECT body FROM b2_attempts").fetchone()[0])
    assert body == result["members"][0]["body"]
    assert len(body["effective"]) == 1
    effective = body["effective"][0]
    assert effective["state"] == "uncertain" and effective["conflict"]
    assert effective["requirement_object"] == "capability"
    assert effective["statement_ids"] == ["s1", "s2"]
    assert {s["state"] for s in body["statements"]} == {"required", "not_required"}
    assert {s["evidence"]["quote"] for s in body["statements"]} == {"必须掌握 Python", "不要求掌握 Python"}


def test_unparsed_project_experience_is_not_a_false_capability_conflict(area):
    result = execute(area, [row("任职要求：\n熟悉 Java；有 Java 项目经验者优先。")])
    body = result["members"][0]["body"]
    assert body["coverage"] == "incomplete"
    assert body["statements"][1]["state"] == "uncertain"
    assert body["statements"][1]["requirement_object"] == "unresolved"
    assert not any(e["conflict"] for e in body["effective"])


def test_duplicate_group_references_are_unique_but_original_members_remain(area):
    result = execute(area, [row("必须掌握 Java 和 Java 和 Python。")])
    body = result["members"][0]["body"]
    assert [s["name"] for s in body["statements"][0]["skills"]] == ["java", "java", "python"]
    assert [e["group_ids"] for e in body["effective"]] == [["s1"], ["s1"]]
    assert all(e["state"] == "mentioned" and not e["statement_ids"] for e in body["effective"])


def test_b2_schema_upgrade_invalidates_old_conflict_without_rewriting_history(area):
    from app.job_analysis.foundation.inputs import canonical
    from app.job_analysis.foundation.store import now
    from app.job_analysis.semantics.store import SemanticStore
    from app.job_analysis.semantics.runner import execute as run, build_report, replay, resume
    history = json.loads((Path(__file__).resolve().parents[1] / "fixtures/semantics/b2-1-capability-experience-history.json").read_text(encoding="utf-8"))
    batch = load(area, [history["input"]])
    with SemanticStore(area / "state.sqlite3") as store:
        # Load the captured original output as immutable history; no old grammar is emulated.
        identity = store.prepare(batch, history["manifest"])
        snapshot = store.conn.execute("SELECT snapshot_id FROM b2_members WHERE run_id=?", (identity,)).fetchone()[0]
        version = store.conn.execute("SELECT version_id FROM b2_runs WHERE id=?", (identity,)).fetchone()[0]
        with store.conn:
            old_attempt = store.conn.execute("INSERT INTO b2_attempts(run_id,snapshot_id,version_id,status,started_at,finished_at,body) VALUES (?,?,?,'completed',?,?,?)",
                (identity, snapshot, version, now(), now(), canonical(history["body"]))).lastrowid
            store.conn.execute("UPDATE b2_members SET attempt_id=? WHERE run_id=?", (old_attempt, identity))
        build_report(store, identity)
        original = replay(store, identity)
        newer = run(store, batch)
        assert newer["version_id"] != version
        assert newer["members"][0]["snapshot_id"] == snapshot
        assert newer["members"][0]["attempt_id"] != old_attempt
        assert states(newer["members"][0]["body"]) == ["required", "preferred"]
        assert replay(store, identity) == original
        assert original["members"][0]["body"]["schema_version"] == "b2-1"
        assert original["members"][0]["body"]["effective"][0]["conflict"]
        with pytest.raises(ValueError, match="dependencies"):
            resume(store, identity)
        reused = run(store, batch)
        assert reused["members"][0]["attempt_id"] == newer["members"][0]["attempt_id"]

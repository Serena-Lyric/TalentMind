"""B1 business paths use synthetic inputs and a real temporary SQLite store."""
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from test_foundation_inputs import area


SCOPE = {
    "scope_id": "software-related-offline",
    "version": "2026-10-15-v1",
    "mode": "offline_experiment",
    "description": "软件开发及相关技术岗位；离线试验，不是最终职业目录",
    "activities": ["software_development", "software_testing", "data", "it_operations"],
}


def jd(**changes):
    return dict(id=1, source="synthetic", source_detail="fixture-b1",
                job_title="软件开发工程师", raw_text="岗位职责：负责开发软件服务。",
                duties="", crawled_at="2026-10-15") | changes


def run(area, rows=None, **options):
    from app.job_analysis.screening.runner import execute
    from app.job_analysis.screening.store import ScreeningStore
    path = area / "input.json"
    path.write_text(json.dumps(rows if rows is not None else [jd()], ensure_ascii=False), encoding="utf-8")
    with ScreeningStore(area / "state.sqlite3") as store:
        return execute(store, path, "fixture-b1", scope=options.pop("scope", SCOPE), **options)


@pytest.mark.parametrize("row,validity,scope,reason", [
    (jd(), "valid", "in_scope", "technical_activity"),
    (jd(job_title="开发实习生", raw_text="负责开发软件，只要求 Python。"), "valid", "in_scope", "technical_activity"),
    (jd(job_title="行政助理", raw_text="负责整理行政报表，使用 Excel。"), "valid", "out_of_scope", "nontechnical_activity"),
    (jd(job_title="销售专员", raw_text="负责开发软件接口。"), "valid", "needs_review", "title_activity_conflict"),
    (jd(raw_text="负责客户销售及签约。"), "valid", "needs_review", "title_activity_conflict"),
    (jd(job_title="助理", raw_text="欢迎了解，具体工作待定。"), "undetermined", "needs_review", "insufficient_evidence"),
    (jd(raw_text="公司简介：我们是一家软件公司。五险一金。"), "invalid", None, "no_job_content"),
    (jd(raw_text="非招聘信息，仅供产品宣传，欢迎购买。"), "invalid", None, "non_recruitment"),
    (jd(raw_text="无需开发软件，只负责客户销售。"), "valid", "needs_review", "ambiguous_activity"),
    (jd(job_title="测试工程师", raw_text="负责执行软件测试。"), "valid", "in_scope", "technical_activity"),
    (jd(job_title="数据分析师", raw_text="负责构建数据模型并分析业务数据。"), "valid", "in_scope", "technical_activity"),
    (jd(job_title="运维工程师", raw_text="负责维护服务器及部署应用。"), "valid", "in_scope", "technical_activity"),
    (jd(job_title="行政助理", raw_text="熟练使用 Excel。"), "valid", "needs_review", "insufficient_evidence"),
    (jd(raw_text="暂无描述", duties="负责开发软件服务。"), "valid", "in_scope", "technical_activity"),
])
def test_layered_decisions_through_persistence(area, row, validity, scope, reason):
    result = run(area, [row])
    member = result["members"][0]
    assert (member["validity"], member["scope_status"]) == (validity, scope)
    assert reason in member["reason_codes"]
    assert member["execution_status"] == "completed"
    assert member["namespace"] == "fixture-b1" and member["jd_id"] == "1"
    assert member["snapshot_id"] and member["fingerprint"] and member["decision_id"]
    assert member["source"] == "synthetic" and member["source_detail"] == "fixture-b1"
    for evidence in member["evidence"]:
        text = row[evidence["field"]]
        assert text[evidence["start"]:evidence["end"]] == evidence["quote"]
    assert member["evidence"]
    assert member["decided_at"] and result["formal_statistics_eligible"] is False
    if scope == "needs_review":
        assert member["review_reasons"]


def test_audit_accounts_for_all_applicable_states_and_bad_rows(area):
    result = run(area, [jd(), jd(id=2, job_title="销售", raw_text="负责客户销售。"),
        jd(id=3, raw_text="暂无描述"), jd(id=4, raw_text="待定"), {"id": 5, "source": "synthetic"}])
    audit = result["audit"]
    assert audit["input_total"] == 5 and audit["member_total"] == 5
    assert audit["validity_counts"] == {"valid": 2, "invalid": 1, "undetermined": 1, "not_evaluated": 1}
    assert audit["scope_counts"] == {"in_scope": 1, "out_of_scope": 1, "needs_review": 1, "not_applicable": 2}
    assert audit["input_failed"] == 1 and audit["screening_failed"] == 0
    assert audit["reason_counts"]["input_record_invalid"] == 1
    error = next(m for m in result["members"] if m["execution_status"] == "input_failed")
    assert error["jd_id"] == "5" and error["scope_status"] is None
    assert error["input_position"] == 5


def test_reuse_invalidation_and_observation_are_independent(area, monkeypatch):
    import app.job_analysis.screening.runner as runner
    real = runner.screen
    calls = []
    def counting(*args):
        calls.append(args[0].jd_id)
        return real(*args)
    monkeypatch.setattr(runner, "screen", counting)
    first = run(area, [jd(), jd(id=2)])
    second = run(area, [jd(crawled_at="2026-10-16")])
    assert calls == ["1", "2"]
    assert [m["decision_id"] for m in first["members"]] == [m["decision_id"] for m in second["members"]]
    assert second["audit"]["input_total"] == 1 and second["audit"]["member_total"] == 2
    assert second["audit"]["reused"] == 2
    from app.job_analysis.screening.store import ScreeningStore
    with ScreeningStore(area / "state.sqlite3") as store:
        assert store.conn.execute("SELECT count(*) FROM b1_observations WHERE crawled_at='2026-10-16'").fetchone()[0] == 1
        assert store.conn.execute("SELECT count(*) FROM heads").fetchone()[0] == 0


@pytest.mark.parametrize("change", [dict(job_title="高级研发工程师"), dict(duties="负责维护服务器。"),
    dict(raw_text="x" * 2500 + "负责开发软件。"), dict(requirements="掌握 Python"), dict(custom={"a": 2})])
def test_complete_input_change_creates_history(area, change):
    first = run(area)
    second = run(area, [jd() | change])
    assert first["members"][0]["decision_id"] != second["members"][0]["decision_id"]
    assert first["members"][0]["snapshot_id"] != second["members"][0]["snapshot_id"]
    from app.job_analysis.screening.runner import replay
    from app.job_analysis.screening.store import ScreeningStore
    with ScreeningStore(area / "state.sqlite3") as store:
        assert replay(store, first["run_id"]) == first


def test_scope_content_revision_and_rule_revision_create_new_decisions(area):
    first = run(area)
    changed = run(area, scope=SCOPE | {"activities": ["data"]})
    assert changed["members"][0]["scope_status"] == "needs_review"
    revision = run(area, scope=SCOPE | {"version": "v2"})
    rules = run(area, rules_revision="v2")
    ids = {r["members"][0]["decision_id"] for r in (first, changed, revision, rules)}
    assert len(ids) == 4
    assert first["scope_definition"] == SCOPE


def test_screening_error_is_separate_and_retryable(area, monkeypatch):
    import app.job_analysis.screening.runner as runner
    real = runner.screen
    def broken(*_):
        raise RuntimeError("secret=never-persist")
    monkeypatch.setattr(runner, "screen", broken)
    failed = run(area)
    member = failed["members"][0]
    assert member["execution_status"] == "failed"
    assert member["validity"] == "not_evaluated" and member["scope_status"] is None
    assert failed["audit"]["screening_failed"] == 1
    assert "never-persist" not in json.dumps(failed)
    monkeypatch.setattr(runner, "screen", real)
    recovered = run(area)
    assert recovered["members"][0]["scope_status"] == "in_scope"
    assert recovered["members"][0]["decision_id"] != member["decision_id"]


@pytest.mark.parametrize("phase", ["after_prepare", "after_start", "after_screen", "before_commit",
    "after_commit", "after_report", "after_output"])
def test_interrupt_resume_preserves_members_and_unique_results(area, monkeypatch, phase):
    import app.job_analysis.screening.runner as runner
    from app.job_analysis.screening.store import ScreeningStore
    path = area / "input.json"
    path.write_text(json.dumps([jd(), jd(id=2)]), encoding="utf-8")
    def crash(stage):
        if stage == phase:
            raise KeyboardInterrupt()
    monkeypatch.setattr(runner, "checkpoint", crash)
    with ScreeningStore(area / "state.sqlite3") as store:
        with pytest.raises(KeyboardInterrupt):
            runner.execute(store, path, "fixture-b1", scope=SCOPE, output=area / "out")
        identity = store.conn.execute("SELECT id FROM b1_runs").fetchone()[0]
    monkeypatch.setattr(runner, "checkpoint", lambda _: None)
    with ScreeningStore(area / "state.sqlite3") as store:
        result = runner.resume(store, identity, output=area / "out")
        assert result["audit"]["member_total"] == 2
        assert store.conn.execute("SELECT count(*) FROM b1_decisions WHERE status='completed'").fetchone()[0] == 2
        assert store.conn.execute("SELECT count(*) FROM b1_decisions WHERE status='running'").fetchone()[0] == 0
        assert json.loads((area / "out" / (identity + ".json")).read_text(encoding="utf-8")) == result
        for table in ("b1_decisions", "b1_versions", "b1_reports"):
            row = store.conn.execute(f"SELECT * FROM {table} LIMIT 1").fetchone()
            with pytest.raises(sqlite3.IntegrityError):
                store.conn.execute(f"INSERT OR REPLACE INTO {table} VALUES ({','.join('?' for _ in row)})", tuple(row))


def cli(area, path, command="run", *extra):
    scope_path = area / "scope.json"
    scope_path.write_text(json.dumps(SCOPE), encoding="utf-8")
    args = ["--input", str(path), "--dataset", "fixture-b1", "--scope", str(scope_path)] if command == "run" else []
    return subprocess.run([sys.executable, "-m", "app.job_analysis.screening", command,
        "--state", str(area / "state.sqlite3"), "--output", str(area / "out"), *args, *extra],
        capture_output=True, text=True, encoding="utf-8")


def test_jsonl_keeps_bad_lines_duplicate_ids_and_later_valid_members(area):
    path = area / "input.jsonl"
    path.write_text(json.dumps(jd()) + "\n{bad\n" + json.dumps(jd(id=2)) + "\n" + json.dumps(jd()), encoding="utf-8")
    process = cli(area, path)
    assert process.returncode == 2, process.stderr
    info = json.loads(process.stdout)
    result = json.loads(Path(info["output"]).read_text(encoding="utf-8"))
    assert result["audit"]["input_total"] == 4
    assert result["audit"]["input_failed"] == 2
    assert result["audit"]["validity_counts"]["valid"] == 2
    assert sorted(m["input_position"] for m in result["members"]) == [1, 2, 3, 4]
    replay = cli(area, path, "replay", "--run", info["run_id"])
    assert replay.returncode == 2


@pytest.mark.parametrize("text", ["{bad", "[]", "{}", '[{"id":1,"id":2}]'])
def test_bad_container_is_audited_without_successful_empty_run(area, text):
    path = area / "input.json"
    path.write_text(text, encoding="utf-8")
    result = cli(area, path)
    assert result.returncode == 2
    artifact = json.loads(Path(json.loads(result.stdout)["output"]).read_text(encoding="utf-8"))
    assert artifact["audit"]["input_failed"] == 1
    assert artifact["audit"]["scope_counts"]["out_of_scope"] == 0


def test_b1_and_a_share_store_without_changing_a_facts_or_replay(area):
    from app.job_analysis.foundation.aggregate import replay
    from app.job_analysis.foundation.inputs import read_snapshot
    from app.job_analysis.foundation.runner import execute
    from app.job_analysis.foundation.store import AnalysisStore
    from app.job_analysis.foundation.__main__ import LiteralDemoAnalyzer
    path = area / "a.json"
    path.write_text(json.dumps([jd(raw_text="负责开发软件，使用 Python。")]), encoding="utf-8")
    with AnalysisStore(area / "state.sqlite3") as store:
        first = execute(store, read_snapshot(path, "fixture-a"), LiteralDemoAnalyzer())
    run(area)
    run(area, rules_revision="v2")
    with AnalysisStore(area / "state.sqlite3") as store:
        assert replay(store, first["aggregate_id"])["business"] == first["business"]
        second = execute(store, read_snapshot(path, "fixture-a"), LiteralDemoAnalyzer())
        assert second["members"][0]["attempt_id"] == first["members"][0]["attempt_id"]
        assert store.conn.execute("PRAGMA user_version").fetchone()[0] == 1
        assert store.conn.execute("SELECT count(*) FROM attempts").fetchone()[0] == 1


@pytest.mark.parametrize("row", [
    jd(raw_text="公司简介：我们负责开发软件。"),
    jd(raw_text="公司简介：我们负责开发软件，欢迎购买。"),
    jd(raw_text="教程示例：负责开发软件，不是招聘。"),
    jd(raw_text="本文介绍如何开发软件。"),
    jd(raw_text="任职要求：非招聘信息，欢迎购买。"),
])
def test_company_marketing_and_tutorials_are_not_confirmed_jobs(area, row):
    member = run(area, [row])["members"][0]
    assert member["validity"] != "valid"
    assert member["scope_status"] != "in_scope"


def test_english_short_jd_and_title_conflict(area):
    result = run(area, [jd(job_title="Software Intern", raw_text="Build software. Python."),
        jd(id=2, job_title="Sales Assistant", raw_text="Develop software services.")])
    assert [m["scope_status"] for m in result["members"]] == ["in_scope", "needs_review"]


@pytest.mark.parametrize("phase", ["after_prepare", "after_start", "after_screen", "before_commit",
    "after_commit", "after_report", "after_stage_output", "after_output"])
def test_hard_exit_and_resume_use_committed_state(area, phase):
    path = area / "input.json"
    path.write_text(json.dumps([jd(), jd(id=2)]), encoding="utf-8")
    script = """
import json, os, sys
from pathlib import Path
import app.job_analysis.screening.runner as runner
import app.job_analysis.foundation.runner as foundation
from app.job_analysis.screening.store import ScreeningStore
area, phase, config = Path(sys.argv[1]), sys.argv[2], json.loads(sys.argv[3])
def crash(stage):
    if stage == phase:
        os._exit(71)
runner.checkpoint = crash
foundation.checkpoint = crash
with ScreeningStore(area / 'state.sqlite3') as store:
    runner.execute(store, area / 'input.json', 'fixture-b1', scope=config, output=area / 'out')
"""
    child = subprocess.run([sys.executable, "-c", script, str(area), phase, json.dumps(SCOPE)],
                           capture_output=True, text=True)
    assert child.returncode == 71, child.stderr
    from app.job_analysis.screening.runner import resume
    from app.job_analysis.screening.store import ScreeningStore
    with ScreeningStore(area / "state.sqlite3") as store:
        identity = store.conn.execute("SELECT id FROM b1_runs").fetchone()[0]
        result = resume(store, identity, output=area / "out")
        assert result["audit"]["member_total"] == 2
        assert result["audit"]["validity_counts"]["valid"] == 2
        assert store.conn.execute("SELECT count(*) FROM b1_decisions WHERE status='completed'").fetchone()[0] == 2
        assert store.conn.execute("SELECT count(*) FROM b1_decisions WHERE status='running'").fetchone()[0] == 0
        assert list((area / "out").glob("*.tmp")) == []


def test_publication_failure_recovers_without_screening_again(area, monkeypatch):
    import app.job_analysis.foundation.runner as foundation
    import app.job_analysis.screening.runner as runner
    from app.job_analysis.screening.store import ScreeningStore
    replace = foundation.os.replace
    def broken(*_):
        raise OSError("synthetic")
    monkeypatch.setattr(foundation.os, "replace", broken)
    with pytest.raises(OSError):
        run(area, output=area / "out")
    monkeypatch.setattr(foundation.os, "replace", replace)
    monkeypatch.setattr(runner, "screen", broken)
    with ScreeningStore(area / "state.sqlite3") as store:
        row = store.conn.execute("SELECT id,status FROM b1_runs").fetchone()
        assert row["status"] == "publication_failed"
        result = runner.resume(store, row["id"], output=area / "out")
        assert result["audit"]["screening_failed"] == 0
        assert store.conn.execute("SELECT count(*) FROM b1_decisions").fetchone()[0] == 1


def test_old_run_keeps_original_members_after_new_input(area, monkeypatch):
    import app.job_analysis.screening.runner as runner
    from app.job_analysis.screening.store import ScreeningStore
    def crash(stage):
        if stage == "after_prepare":
            raise KeyboardInterrupt()
    monkeypatch.setattr(runner, "checkpoint", crash)
    with pytest.raises(KeyboardInterrupt):
        run(area)
    with ScreeningStore(area / "state.sqlite3") as store:
        identity = store.conn.execute("SELECT id FROM b1_runs").fetchone()[0]
    monkeypatch.setattr(runner, "checkpoint", lambda _: None)
    run(area, [jd(raw_text="负责维护服务器。"), jd(id=2)])
    with ScreeningStore(area / "state.sqlite3") as store:
        result = runner.resume(store, identity)
        assert result["audit"]["member_total"] == 1
        evidence = result["members"][0]["evidence"]
        assert any(e["quote"] == "开发软件" for e in evidence)


def test_cli_explicit_success_scope_and_protected_destinations(area):
    path = area / "input.json"
    path.write_text(json.dumps([jd()]), encoding="utf-8")
    process = cli(area, path)
    assert process.returncode == 0, process.stderr
    result = json.loads(Path(json.loads(process.stdout)["output"]).read_text(encoding="utf-8"))
    assert result["scope_definition"] == SCOPE
    from app.job_analysis.screening.store import ScreeningStore
    root = Path(__file__).resolve().parents[3]
    with pytest.raises(ValueError):
        ScreeningStore(root / "exchange/m2/b1.sqlite3")
    assert not (root / "exchange/m2/b1.sqlite3").exists()


def test_incremental_absent_member_has_real_original_file_reference(area):
    first = run(area, [jd(), jd(id=2)])
    second = run(area, [jd()])
    absent = next(m for m in second["members"] if m["jd_id"] == "2")
    assert absent["input_position"] is None
    assert absent["input_snapshot"]["run_id"] == first["run_id"]
    assert absent["input_snapshot"]["position"] == 2


def test_prohibited_fields_are_errors_and_never_persisted(area):
    result = run(area, [jd(), jd(id=2, api_key="secret-b1-test")])
    assert result["audit"]["input_failed"] == 1
    assert result["raw_input_retained"] is False
    assert b"secret-b1-test" not in (area / "state.sqlite3").read_bytes()


def test_invalid_evidence_becomes_execution_error(area, monkeypatch):
    import app.job_analysis.screening.runner as runner
    original = runner.screen
    def wrong(*args):
        body = original(*args)
        body["evidence"][0]["quote"] = "not in this JD"
        return body
    monkeypatch.setattr(runner, "screen", wrong)
    result = run(area)
    assert result["members"][0]["execution_error"] == "screening_result_invalid"
    assert result["members"][0]["scope_status"] is None


@pytest.mark.parametrize("row", [
    jd(job_title="助理", raw_text="岗位职责：不开发软件，不编写代码，只进行文书工作。"),
    jd(job_title="客户顾问", raw_text="向客户介绍公司开发的软件产品。"),
    jd(job_title="技术支持", raw_text="岗位职责：负责客户服务。任职要求：熟悉我们开发的软件产品。"),
])
def test_negation_and_company_product_attributes_need_review(area, row):
    member = run(area, [row])["members"][0]
    assert member["scope_status"] == "needs_review"
    assert "ambiguous_activity" in member["reason_codes"]


def test_truncated_jsonl_cannot_persist_unchecked_credentials(area):
    path = area / "input.jsonl"
    path.write_text(json.dumps(jd()) + '\n{"api_key":"synthetic-probe-credential"', encoding="utf-8")
    process = cli(area, path)
    assert process.returncode == 2
    result = json.loads(Path(json.loads(process.stdout)["output"]).read_text(encoding="utf-8"))
    assert result["audit"]["input_failed"] == 1
    assert result["raw_input_retained"] is False
    assert b"synthetic-probe-credential" not in (area / "state.sqlite3").read_bytes()

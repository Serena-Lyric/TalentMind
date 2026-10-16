"""Finite synthetic grammar checks, not real JD accuracy."""
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

def batch(area, **changes):
    return load(area, [dict(id=1, source="synthetic", job_title="工程师",
        duties="核心职责：开发后端接口并交付服务", raw_text="核心职责：开发后端接口并交付服务") | changes])


def run(store, source, **kwargs):
    from app.job_analysis.role_classification.proposals.runner import execute
    return execute(store, source, kwargs.pop("taxonomy", config()), **kwargs)


def test_reuse_observation_content_identity_rules_and_catalog_changes_append(area, monkeypatch):
    from app.job_analysis.role_classification.proposals import runner
    from app.job_analysis.role_classification.proposals.store import ProposalStore
    with ProposalStore(area / "state.db") as store:
        source = batch(area)
        first = run(store, source)
        reused = run(store, batch(area, crawled_at="2026-10-17"))
        assert reused["members"][0]["result_id"] == first["members"][0]["result_id"]
        assert reused["members"][0]["observation"] == "2026-10-17"
        assert reused["members"][0]["input_position"] == 1
        assert reused["members"][0]["reused"] is True
        for changed in (dict(raw_text="不同正文"), dict(id=2), dict(requirements="Python")):
            result = run(store, batch(area, **changed))
            assert result["members"][0]["result_id"] != first["members"][0]["result_id"]
        cat = json.loads(CATALOG.with_name("families.v2.json").read_text(encoding="utf-8"))
        revised = run(store, source, taxonomy=cat)
        assert revised["version_id"] != first["version_id"]
        cat["job_family"][0]["scope"] += " 版本边界说明"
        assert run(store, source, taxonomy=cat)["version_id"] != revised["version_id"]
        assert run(store, source, revision="v2")["version_id"] != first["version_id"]
        manifest = runner.version_manifest
        monkeypatch.setattr(runner, "version_manifest", lambda t, r: manifest(t, r) | dict(changed_source="simulation"))
        assert run(store, source)["members"][0]["result_id"] != first["members"][0]["result_id"]
        assert runner.replay(store, first["run_id"]) == first


def test_manifest_hashes_rules_catalog_validation_and_transitive_sources():
    from app.job_analysis.role_classification.proposals.runner import version_manifest
    value = version_manifest(config(), "v1")
    assert value["taxonomy"] == config()
    hashes = value["source_sha256"]
    for name in ("role_classification/proposals/rules.py", "role_classification/proposals/models.py",
                 "role_classification/validation.py", "role_classification/models.py",
                 "foundation/inputs.py", "foundation/models.py", "foundation/store.py", "foundation/runner.py",
                 "semantics/models.py"):
        assert len(hashes[name]) == 64


def test_new_proposal_does_not_mutate_any_existing_layer_or_b30_manifest(area):
    from app.job_analysis.foundation.store import AnalysisStore
    from app.job_analysis.foundation.__main__ import LiteralDemoAnalyzer
    from app.job_analysis.foundation.runner import execute as a
    from app.job_analysis.screening.store import ScreeningStore
    from app.job_analysis.screening.runner import execute as b1
    from app.job_analysis.semantics.store import SemanticStore
    from app.job_analysis.semantics.runner import execute as b2
    from app.job_analysis.governance.store import GovernanceStore
    from app.job_analysis.governance.runner import execute as b22
    from app.job_analysis.role_classification.store import RoleStore
    from app.job_analysis.role_classification.runner import execute as b30, replay as replay30, version_manifest
    from app.job_analysis.role_classification.proposals.store import ProposalStore
    from test_role_classification import taxonomy, annotation
    state, source = area / "state.db", batch(area)
    old_manifest = version_manifest(taxonomy(), "v1")
    with AnalysisStore(state) as store:
        a(store, source, LiteralDemoAnalyzer())
        with store.conn:
            store.conn.execute("UPDATE runs SET status='running'")
    with ScreeningStore(state) as store:
        scope = json.loads((CATALOG.parents[2] / "screening/software-related.offline.json").read_text(encoding="utf-8"))
        b1(store, source.path, source.namespace, scope=scope)
    with SemanticStore(state) as store:
        old_b2 = b2(store, source)
    with GovernanceStore(state) as store:
        b22(store, old_b2["run_id"])
    with RoleStore(state) as store:
        old = b30(store, source, [annotation(source.records[0])], taxonomy())
        tables = [r[0] for r in store.conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        before = {t: [tuple(r) for r in store.conn.execute(f'SELECT * FROM "{t}"')] for t in tables}
    with ProposalStore(state) as store:
        new = run(store, source)
        assert new["members"][0]["body"]["candidates"][0]["family_id"] == "software_engineering"
        for table, rows in before.items():
            assert [tuple(r) for r in store.conn.execute(f'SELECT * FROM "{table}"')] == rows, table
        assert replay30(store, old["run_id"]) == old
        assert version_manifest(taxonomy(), "v1") == old_manifest
        assert store.conn.execute("PRAGMA user_version").fetchone()[0] == 1


@pytest.mark.parametrize("kind", ["bytes", "records", "namespace", "duplicate"])
def test_forged_batch_is_rejected_atomically(area, kind):
    from dataclasses import replace
    from app.job_analysis.role_classification.proposals.store import ProposalStore
    source = batch(area)
    source = (replace(source, raw_bytes=b"[]") if kind == "bytes" else
              replace(source, records=(record("伪造"),)) if kind == "records" else
              replace(source, namespace="other") if kind == "namespace" else
              replace(source, records=source.records * 2))
    with ProposalStore(area / "state.db") as store:
        with pytest.raises(ValueError):
            run(store, source)
        for table in ("snapshots", "b31_inputs", "b31_results", "b31_reports", "b31_versions"):
            assert store.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0

def test_actual_source_bytes_change_appends_b31_but_does_not_change_b30_manifest(area, monkeypatch):
    import shutil
    from app.job_analysis.role_classification.proposals import runner
    from app.job_analysis.role_classification.proposals.store import ProposalStore
    from app.job_analysis.role_classification.runner import version_manifest as b30_manifest
    from test_role_classification import taxonomy
    root = Path(runner.__file__).resolve().parents[2]
    copied = area / "copied_job_analysis"
    files = runner.version_manifest(config(), "v1")["source_sha256"]
    for relative in files:
        target = copied / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / relative, target)
    before_b30 = b30_manifest(taxonomy(), "v1")
    monkeypatch.setattr(runner, "__file__", str(copied / "role_classification/proposals/runner.py"))
    source = batch(area)
    with ProposalStore(area / "state.db") as store:
        first = run(store, source)
        path = copied / "role_classification/proposals/rules.py"
        path.write_text(path.read_text(encoding="utf-8") + "\n# Simulated source revision\n", encoding="utf-8")
        next_run = run(store, source)
        assert next_run["version_id"] != first["version_id"]
        assert next_run["members"][0]["result_id"] != first["members"][0]["result_id"]
        assert runner.replay(store, first["run_id"]) == first
    assert b30_manifest(taxonomy(), "v1") == before_b30


def test_open_does_not_recover_running_a_and_rejects_legacy_state(area):
    import sqlite3
    from contextlib import closing
    from app.job_analysis.foundation.store import AnalysisStore
    from app.job_analysis.role_classification.proposals.store import ProposalStore
    path = area / "state.db"
    source = batch(area)
    with AnalysisStore(path) as store:
        run_id = store.ingest(source)
        with store.conn:
            store.conn.execute("UPDATE runs SET status='running' WHERE id=?", (run_id,))
        before = [tuple(r) for r in store.conn.execute("SELECT * FROM runs")]
    with ProposalStore(path) as store:
        run(store, source)
        assert [tuple(r) for r in store.conn.execute("SELECT * FROM runs")] == before
    legacy = area / "legacy.db"
    with closing(sqlite3.connect(legacy)) as conn:
        conn.execute("CREATE TABLE legacy (body TEXT)")
        conn.commit()
    before_bytes = legacy.read_bytes()
    with pytest.raises(ValueError):
        ProposalStore(legacy)
    assert legacy.read_bytes() == before_bytes


@pytest.mark.parametrize("stage", ["after_result", "before_commit", "after_commit"])
def test_interruption_rolls_back_or_replays_exact_saved_report(area, monkeypatch, stage):
    from app.job_analysis.role_classification.proposals import runner
    from app.job_analysis.role_classification.proposals.store import ProposalStore
    def fail(point):
        if point == stage:
            raise RuntimeError("interrupted")
    with ProposalStore(area / "state.db") as store:
        monkeypatch.setattr(runner, "checkpoint", fail)
        with pytest.raises(RuntimeError):
            run(store, batch(area))
        count = int(stage == "after_commit")
        for table in ("b31_inputs", "b31_results", "b31_versions", "b31_reports", "snapshots"):
            assert store.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == count
        monkeypatch.setattr(runner, "checkpoint", lambda _: None)
        again = run(store, batch(area))
        assert again["members"][0]["reused"] is bool(count)


def test_immutable_tables_and_publication_recovery_without_current_rules(area, monkeypatch):
    import sqlite3
    from app.job_analysis.role_classification.proposals import runner
    from app.job_analysis.role_classification.proposals.store import ProposalStore
    from app.job_analysis.foundation.runner import publish
    with ProposalStore(area / "state.db") as store:
        def fail(*args):
            raise OSError("output interrupted")
        monkeypatch.setattr(runner, "publish", fail)
        with pytest.raises(OSError):
            run(store, batch(area), output=area / "out")
        run_id = store.conn.execute("SELECT run_id FROM b31_reports").fetchone()[0]
        monkeypatch.setattr(runner, "suggest", lambda *args: (_ for _ in ()).throw(AssertionError("must not reinterpret")))
        saved = runner.replay(store, run_id)
        artifact = publish(saved, area / "out", run_id)
        assert json.loads(artifact.read_text(encoding="utf-8")) == saved
        artifact.write_text("different", encoding="utf-8")
        with pytest.raises(ValueError):
            publish(saved, area / "out", run_id)
        for table in ("b31_inputs", "b31_results", "b31_versions", "b31_reports"):
            for sql in (f"DELETE FROM {table}", f"UPDATE {table} SET rowid=rowid", f"INSERT OR REPLACE INTO {table} SELECT * FROM {table}"):
                with pytest.raises(sqlite3.IntegrityError):
                    with store.conn:
                        store.conn.execute(sql)


def test_cli_run_replay_and_output_protection(area):
    from app.job_analysis.role_classification.proposals.__main__ import main
    from app.job_analysis.role_classification.proposals.store import ProposalStore
    source = batch(area)
    cat = area / "families.json"
    cat.write_text(json.dumps(config()), encoding="utf-8")
    state, out = area / "state.db", area / "out"
    args = ["run", "--input", str(source.path), "--dataset", "fixture", "--taxonomy", str(cat),
            "--state", str(state), "--output", str(out)]
    assert main(args) == 0
    original = json.loads(next(out.glob("*.json")).read_text(encoding="utf-8"))
    source.path.unlink()
    cat.unlink()
    assert main(["replay", "--run", original["run_id"], "--state", str(state), "--output", str(area / "replay")]) == 0
    assert json.loads(next((area / "replay").glob("*.json")).read_text(encoding="utf-8")) == original
    source = batch(area)
    cat.write_text(json.dumps(config()), encoding="utf-8")
    assert main(args[:-1] + [str(area)]) == 2
    assert main(["replay", "--run", original["run_id"], "--state", str(state), "--output", str(area)]) == 2
    with ProposalStore(state) as store:
        assert store.conn.execute("SELECT COUNT(*) FROM b31_reports").fetchone()[0] == 1


@pytest.mark.parametrize("stage", ["after_result", "before_commit", "after_commit", "after_stage_output", "after_output"])
def test_real_process_exit_preserves_transaction_and_output_replay(area, stage):
    import subprocess
    import sys
    from app.job_analysis.role_classification.proposals.store import ProposalStore
    from app.job_analysis.role_classification.proposals.runner import replay
    from app.job_analysis.foundation.runner import publish
    source = batch(area)
    script = """
import os, socket, sys
def blocked(*args, **kwargs): raise AssertionError("network forbidden")
socket.socket.connect = socket.socket.connect_ex = blocked
from app.job_analysis.foundation.inputs import read_snapshot
from app.job_analysis.role_classification.proposals import runner
from app.job_analysis.role_classification.proposals.models import load_taxonomy
from app.job_analysis.foundation import runner as publication
from app.job_analysis.role_classification.proposals.store import ProposalStore
def stop(point):
    if point == sys.argv[2]: os._exit(73)
runner.checkpoint = publication.checkpoint = stop
with ProposalStore(sys.argv[3]) as store:
    runner.execute(store, read_snapshot(sys.argv[1], "fixture"), load_taxonomy(sys.argv[5]), output=sys.argv[4])
"""
    state, out = area / "state.db", area / "out"
    proc = subprocess.run([sys.executable, "-c", script, str(source.path), stage, str(state), str(out), str(CATALOG)], capture_output=True)
    assert proc.returncode == 73, proc.stderr
    with ProposalStore(state) as store:
        rows = store.conn.execute("SELECT run_id FROM b31_reports").fetchall()
        assert len(rows) == int(stage not in ("after_result", "before_commit"))
        if rows:
            saved = replay(store, rows[0][0])
            publish(saved, out, saved["run_id"])
            assert json.loads(next(out.glob("*.json")).read_text(encoding="utf-8")) == saved
            assert not list(out.glob("*.tmp"))
        else:
            assert store.conn.execute("SELECT COUNT(*) FROM b31_results").fetchone()[0] == 0

@pytest.mark.parametrize("heading", ["公司介绍：", "历史项目：", "培训内容：", "示例：", "公司介绍\n", "历史项目\n"])
@pytest.mark.parametrize("duties_first", [True, False])
def test_extracted_duties_cannot_override_explicit_non_current_source_context(heading, duties_first):
    clause = "核心职责：开发后端接口并交付服务"
    item = record(clause if duties_first else heading + clause,
                  raw_text=heading + clause if duties_first else clause)
    body = suggest(item)
    assert body["candidates"] == []
    assert body["primary_family_hint"] is None
    assert body["resolution"] == "unresolved"
    assert "cross_field_context_conflict" in body["reasons"]
    assert body["source_payload"] == item.payload


def test_auxiliary_title_match_cannot_hide_title_core_responsibility_conflict():
    body = suggest(record("核心职责：开发后端接口并交付服务。协助设计测试用例并交付测试报告", title="测试工程师"))
    assert body["resolution"] == "unresolved"
    assert body["primary_family_hint"] is None
    assert "title_duties_conflict" in body["reasons"]
    assert {c["family_id"] for c in body["candidates"]} == {"software_engineering", "test_quality_engineering"}


def test_supported_current_work_with_same_company_background_keeps_candidates_but_no_primary():
    clause = "核心职责：开发后端接口并交付服务"
    body = suggest(record(clause, raw_text="公司介绍：" + clause + "\n岗位职责：" + clause))
    assert [c["family_id"] for c in body["candidates"]] == ["software_engineering"]
    assert body["resolution"] == "unresolved"
    assert body["primary_family_hint"] is None
    assert all(c["evidence"]["field"] == "raw_text" for c in body["candidates"][0]["clues"])


def test_late_foreign_evidence_failure_rolls_back_whole_new_run(area, monkeypatch):
    from app.job_analysis.role_classification.proposals import runner
    from app.job_analysis.role_classification.proposals.store import ProposalStore
    source = load(area, [dict(id=i, source="synthetic", job_title="工程师",
        raw_text="核心职责：开发后端接口并交付服务") for i in (1, 2)])
    original = runner.suggest
    def forged(item, taxonomy):
        body = original(item, taxonomy)
        if item.jd_id == "2":
            body["candidates"][0]["clues"][0]["evidence"]["jd_id"] = "1"
        return body
    monkeypatch.setattr(runner, "suggest", forged)
    with ProposalStore(area / "state.db") as store:
        with pytest.raises(ValueError):
            run(store, source)
        for table in ("b31_results", "b31_reports", "b31_inputs", "snapshots"):
            assert store.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0

"""Synthetic governance counterexamples; no model, service or production data."""
import copy
import json
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

from test_foundation_inputs import area, load


def record(text, **changes):
    from app.job_analysis.foundation.inputs import InputRecord
    return InputRecord.from_row("fixture", dict(id=1, source="synthetic", job_title="工程师", raw_text=text) | changes)


def govern(text, **changes):
    from app.job_analysis.governance.catalog import Catalog
    from app.job_analysis.governance.extract import analyze
    from app.job_analysis.semantics.rules import SkillSemanticAnalyzer
    item = record(text, **changes)
    original = SkillSemanticAnalyzer().analyze(item)
    before = copy.deepcopy(original)
    result = analyze(item, original, Catalog())
    assert original == before
    assert result["original_semantics"] == before
    assert not result["formal_statistics_eligible"]
    assert result["analysis_complete"] is False
    return result


@pytest.mark.parametrize("raw,canonical,version", [
    ("JS", "javascript", None), ("JavaScript", "javascript", None),
    ("SQL", "sql", None), ("MySQL", "mysql", None),
    ("Spring", "spring", None), ("Spring Boot", "spring boot", None),
    ("Vue", "vue", None), ("Vue 3", "vue", "3"),
    ("python3", "python", "3"), ("Python 3.12", "python", "3.12"),
    ("OAuth2", "oauth", "2"), ("Sass", "sass", None),
])
def test_strict_names_preserve_technology_and_versions(raw, canonical, version):
    from app.job_analysis.governance.catalog import Catalog
    found = Catalog().resolve(raw)
    assert found["canonical"] == canonical
    assert found["version"] == version
    assert found["raw_name"] == raw


def test_unverified_aliases_are_audited_not_silently_accepted():
    from app.job_analysis.governance.catalog import Catalog
    catalog = Catalog()
    for raw in ("cv", "ci", "optimization", "es6", "angularjs"):
        result = catalog.resolve(raw)
        assert result["canonical"] is None
        assert result["status"] == "needs_review"
        assert result["baseline_matches"]
    collisions = {i["term"] for i in catalog.audit if i["reason"] == "multiple_targets"}
    assert {"sass", "js", "ts", "k8s", "oop", "敏捷开发"} <= collisions
    assert any(i["term"] == "python3" and i["reason"] == "version_alias" for i in catalog.audit)
    assert any(i["term"] == "cv" and i["reason"] == "unreviewed_alias" for i in catalog.audit)


def test_alias_conflicts_never_depend_on_order_and_duplicate_entries_survive_audit():
    from app.job_analysis.governance.catalog import Catalog
    seed = [dict(canonical="alpha", aliases=["shared", "shared"], category="编程语言"),
            dict(canonical="beta", aliases=["shared"], category="编程语言")]
    original = copy.deepcopy(seed)
    first, second = Catalog(seed), Catalog(list(reversed(seed)))
    assert first.resolve("shared") == second.resolve("shared")
    assert first.resolve("shared")["canonical"] is None
    assert any(i["reason"] == "duplicate_entry" for i in first.audit)
    assert seed == original


def test_related_and_hierarchical_edges_never_normalize_or_imply_substitution():
    from app.job_analysis.governance.catalog import Catalog
    catalog = Catalog()
    assert {r["relation"] for r in catalog.policy["relations"]} >= {"synonym", "related_to", "narrower_than", "version_of"}
    assert catalog.resolve("SQL")["key"] != catalog.resolve("MySQL")["key"]
    assert catalog.resolve("Spring")["key"] != catalog.resolve("Spring Boot")["key"]
    assert catalog.resolve("Vue")["key"] != catalog.resolve("Vue 3")["key"]


@pytest.mark.parametrize("text,category", [
    ("必须掌握 Java。", "technical_skill"),
    ("必须掌握 系统设计。", "professional_skill"),
    ("必须掌握 单元测试。", "engineering_practice"),
    ("必须具备 团队协作。", "soft_skill"),
])
def test_four_skill_categories_have_evidence(text, category):
    result = govern(text)
    fact = result["skills"][0]
    assert fact["category"] == category and fact["classification_basis"]
    assert fact["evidence"]["quote"] in text
    assert fact["statement_ids"] == ["s1"]


def test_versions_original_five_states_degrees_and_groups_remain_intact():
    result = govern("Java 或 Python 至少掌握一种。不要求精通 Python，但需了解 Python 基础。必须掌握 Vue 3。")
    before = result["original_semantics"]
    assert before["statements"][0]["relation"] == "any_of"
    assert [s["state"] for s in before["statements"]][1:3] == ["not_required", "required"]
    assert [s["degree"] for s in before["statements"]][1:3] == ["expert", "basic"]
    vue = next(s for s in result["skills"] if s["raw_name"] == "Vue 3")
    assert vue["canonical"] == "vue" and vue["version"] == "3"
    assert vue["evidence"]["quote"] == "Vue 3" and vue["statement_ids"]


def test_skills_and_non_skills_are_linked_without_turning_years_into_degree():
    result = govern("三年以上 Java 开发经验。本科及以上学历。具备金融行业经验。持有 PMP 证书。")
    assert [s["canonical"] for s in result["skills"]] == ["java"]
    facts = {n["kind"]: n for n in result["non_skills"]}
    assert set(facts) == {"work_years", "education", "domain_experience", "credential"}
    assert facts["work_years"]["value"] == {"minimum": 3, "unit": "year", "scope": "skill_specific"}
    assert facts["work_years"]["skill_ids"] == [result["skills"][0]["id"]]
    assert all(s["degree"] is None for s in result["original_semantics"]["statements"])
    assert all(n["evidence"]["quote"] in result["source_payload"][n["evidence"]["field"]] for n in facts.values())


def test_requirement_object_experience_does_not_become_jd_work_years():
    result = govern("必须掌握 Python。Python 经验优先。")
    assert result["non_skills"] == []
    assert [s["requirement_object"] for s in result["original_semantics"]["statements"]] == ["capability", "experience"]


@pytest.mark.parametrize("text", [
    "公司名称：AcmeLabs。福利：五险一金。", "欢迎加入 UnicornCorp 公司。", "薪资：20K-30K。",
    "熟悉 AcmeLabs 公司产品。", "我们正在招聘 UnlistedLang 团队经理。",
    "本科及以上学历。持有 PMP 证书。具备金融行业经验。",
])
def test_arbitrary_words_company_benefits_and_conditions_are_not_skill_candidates(text):
    result = govern(text)
    assert result["candidates"] == []
    assert result["skills"] == []


def test_unknown_candidate_grades_keep_evidence_context_comparison_and_no_admission():
    from app.job_analysis.governance.candidates import validate_admission
    result = govern("必须掌握 UnlistedLang。技术栈：OtherRuntime。熟悉 cv。")
    candidates = {c["raw_name"]: c for c in result["candidates"]}
    assert set(candidates) == {"UnlistedLang", "OtherRuntime", "cv"}
    assert candidates["UnlistedLang"]["tier"] == "strong_context"
    assert candidates["OtherRuntime"]["tier"] == candidates["cv"]["tier"] == "disputed"
    for c in candidates.values():
        assert c["governance_status"] == "pending_review"
        assert c["statement"]["evidence"]["quote"]
        assert c["context"]["quote"] and c["review_reasons"]
        assert c["formal_admitted"] is False
        decision = validate_admission(c)
        assert decision["allowed"] is False and "automatic_admission_disabled" in decision["reasons"]


def test_review_decision_needs_attribution_and_does_not_grant_dictionary_membership():
    from app.job_analysis.governance.candidates import review_event, validate_admission
    candidate = govern("必须掌握 UnlistedLang。")["candidates"][0]
    with pytest.raises(ValueError):
        review_event(candidate, decision="reviewed_accepted", reviewer="", basis="", evidence_refs=[])
    event = review_event(candidate, decision="reviewed_accepted", reviewer="fixture-human",
                         basis="synthetic review interface test only", evidence_refs=["fixture:manual-check"])
    assert event["formal_admitted"] is False
    assert validate_admission(candidate, event)["allowed"] is False


def stage_b2(area, texts):
    from app.job_analysis.semantics.runner import execute
    from app.job_analysis.semantics.store import SemanticStore
    batch = load(area, [dict(id=i, source=f"synthetic-{i}", job_title="工程师", raw_text=t, dup_group="same-job", cross_source=1)
                        for i, t in enumerate(texts, 1)])
    with SemanticStore(area / "state.sqlite3") as store:
        result = execute(store, batch)
    return batch, result


def test_governance_reuses_appends_replays_and_does_not_infer_independent_sources(area):
    from app.job_analysis.governance.catalog import Catalog
    from app.job_analysis.governance.runner import execute, replay
    from app.job_analysis.governance.store import GovernanceStore
    batch, old = stage_b2(area, ["必须掌握 UnlistedLang。"] * 2)
    original_bytes = batch.path.read_bytes()
    with GovernanceStore(area / "state.sqlite3") as store:
        old_rows = [tuple(r) for r in store.conn.execute("SELECT * FROM b2_attempts")]
        first = execute(store, old["run_id"], output=area / "out")
        again = execute(store, old["run_id"])
        assert [m["result_id"] for m in first["members"]] == [m["result_id"] for m in again["members"]]
        for member in first["members"]:
            c = member["body"]["candidates"][0]
            assert c["independent_validation"] == "not_established"
            assert not c["formal_admitted"]
        catalog = Catalog(); catalog.policy["version"] = "fixture-v2"
        changed = execute(store, old["run_id"], catalog=catalog)
        assert changed["version_id"] != first["version_id"]
        assert changed["members"][0]["result_id"] != first["members"][0]["result_id"]
        assert replay(store, first["run_id"]) == first
        assert [tuple(r) for r in store.conn.execute("SELECT * FROM b2_attempts")] == old_rows
        assert json.loads((area / "out" / (first["run_id"] + ".json")).read_text(encoding="utf-8")) == first
        for table in ("b22_results", "b22_reports", "b22_versions"):
            with pytest.raises(sqlite3.IntegrityError):
                store.conn.execute(f"DELETE FROM {table}")
            store.conn.rollback()
    assert batch.path.read_bytes() == original_bytes


def test_a_b1_b2_facts_and_legacy_history_are_unchanged_after_governance(area):
    from test_semantics import test_a_b1_b2_shared_store_preserves_legacy_history_and_both_replays
    from app.job_analysis.governance.runner import execute
    from app.job_analysis.governance.store import GovernanceStore
    test_a_b1_b2_shared_store_preserves_legacy_history_and_both_replays(area)
    with GovernanceStore(area / "state.sqlite3") as store:
        tables = [r[0] for r in store.conn.execute("SELECT name FROM sqlite_master WHERE type='table'") if not r[0].startswith('b22_')]
        before = {t: [tuple(r) for r in store.conn.execute(f'SELECT * FROM "{t}"')] for t in tables}
        b2_id = store.conn.execute("SELECT run_id FROM b2_reports LIMIT 1").fetchone()[0]
        result = execute(store, b2_id)
        assert result["members"][0]["body"]["skills"][0]["canonical"] == "python"
        assert {t: [tuple(r) for r in store.conn.execute(f'SELECT * FROM "{t}"')] for t in tables} == before
        assert store.conn.execute("PRAGMA user_version").fetchone()[0] == 1


def test_governance_cli_run_and_replay_use_only_saved_b2(area):
    _, old = stage_b2(area, ["必须掌握 Vue 3。"])
    root = Path(__file__).resolve().parents[2]
    args = [sys.executable, "-m", "app.job_analysis.governance"]
    common = ["--state", str(area / "state.sqlite3"), "--output", str(area / "out")]
    run = subprocess.run(args + ["run", "--b2-run", old["run_id"]] + common, cwd=root, capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    identity = json.loads(run.stdout)["run_id"]
    again = subprocess.run(args + ["replay", "--run", identity] + common, cwd=root, capture_output=True, text=True)
    assert again.returncode == 0, again.stderr


def test_unclassified_domain_mentions_are_review_items_instead_of_assumed_skills():
    result = govern("技术栈：金融。")
    assert result["skills"] == []
    assert result["review_mentions"][0]["raw_name"] == "金融"
    assert result["review_mentions"][0]["category"] is None


def test_version_wildcard_is_not_collapsed_into_exact_major_version():
    from app.job_analysis.governance.catalog import Catalog
    catalog = Catalog()
    assert catalog.resolve("Vue 3.x")["version"] == "3.x"
    assert catalog.resolve("Vue 3.x")["key"] != catalog.resolve("Vue 3")["key"]
    assert govern("必须掌握 Vue 3.x。")["skills"][0]["raw_name"] == "Vue 3.x"


@pytest.mark.parametrize("text", ["不要求三年以上工作经验。", "如果参与项目，要求三年以上工作经验。"])
def test_non_skill_constraints_do_not_drop_negation_or_condition(text):
    facts = govern(text)["non_skills"]
    assert facts[0]["constraint_state"] == "needs_review"
    assert facts[0]["context"]["quote"] == text


def test_review_history_is_append_only_exportable_and_never_changes_candidate(area):
    from app.job_analysis.governance.candidates import review_event
    from app.job_analysis.governance.runner import execute, replay
    from app.job_analysis.governance.store import GovernanceStore
    _, old = stage_b2(area, ["必须掌握 UnlistedLang。"])
    with GovernanceStore(area / "state.sqlite3") as store:
        report = execute(store, old["run_id"])
        member = report["members"][0]; candidate = member["body"]["candidates"][0]
        event = review_event(candidate, decision="deferred", reviewer="fixture-human", basis="needs documentation", evidence_refs=["fixture:one"])
        store.record_review(member["result_id"], event)
        assert store.reviews(member["result_id"]) == [event]
        assert replay(store, report["run_id"]) == report
        with pytest.raises(sqlite3.IntegrityError):
            store.conn.execute("DELETE FROM b22_reviews")
        store.conn.rollback()
        wrong = event | {"candidate_version": "wrong-version"}
        with pytest.raises(ValueError):
            store.record_review(member["result_id"], wrong)


def test_overlay_transaction_rolls_back_on_failure_and_publish_failure_is_replayable(area, monkeypatch):
    from app.job_analysis.governance import runner
    from app.job_analysis.governance.store import GovernanceStore
    _, old = stage_b2(area, ["必须掌握 Python。"])
    with GovernanceStore(area / "state.sqlite3") as store:
        original = runner.analyze
        def fail(*args):
            raise ValueError("synthetic failure")
        monkeypatch.setattr(runner, "analyze", fail)
        with pytest.raises(ValueError):
            runner.execute(store, old["run_id"])
        assert store.conn.execute("SELECT count(*) FROM b22_versions").fetchone()[0] == 0
        assert store.conn.execute("SELECT count(*) FROM b22_results").fetchone()[0] == 0
        monkeypatch.setattr(runner, "analyze", original)
        def fail_publish(*args):
            raise OSError("synthetic disk error")
        monkeypatch.setattr(runner, "publish", fail_publish)
        with pytest.raises(OSError):
            runner.execute(store, old["run_id"], output=area / "out")
        identity = store.conn.execute("SELECT run_id FROM b22_reports").fetchone()[0]
        assert runner.replay(store, identity)["members"][0]["body"]["skills"][0]["canonical"] == "python"


def test_old_b2_1_document_remains_unmodified_and_can_receive_new_overlay(area):
    from test_semantics import test_b2_schema_upgrade_invalidates_old_conflict_without_rewriting_history
    from app.job_analysis.governance.runner import execute
    from app.job_analysis.governance.store import GovernanceStore
    test_b2_schema_upgrade_invalidates_old_conflict_without_rewriting_history(area)
    with GovernanceStore(area / "state.sqlite3") as store:
        identity, body = store.conn.execute("SELECT run_id,body FROM b2_reports ORDER BY rowid LIMIT 1").fetchone()
        source = json.loads(body)
        result = execute(store, identity)
        assert result["members"][0]["body"]["original_semantics"] == source["members"][0]["body"]
        assert result["members"][0]["body"]["original_semantics"]["schema_version"] == "b2-1"
        assert store.conn.execute("SELECT body FROM b2_reports WHERE run_id=?", (identity,)).fetchone()[0] == body


def test_upstream_execution_failure_stays_failure_not_zero_skill_success(area):
    from app.job_analysis.semantics.rules import SkillSemanticAnalyzer
    from app.job_analysis.semantics.runner import execute as b2
    from app.job_analysis.semantics.store import SemanticStore
    from app.job_analysis.governance.runner import execute
    from app.job_analysis.governance.store import GovernanceStore
    class Broken(SkillSemanticAnalyzer):
        def analyze(self, record):
            raise RuntimeError("synthetic failure")
    batch = load(area, [dict(id=1, source="synthetic", job_title="工程师", raw_text="必须掌握 Python。")])
    with SemanticStore(area / "state.sqlite3") as store:
        original = b2(store, batch, analyzer=Broken())
    with GovernanceStore(area / "state.sqlite3") as store:
        report = execute(store, original["run_id"])
        assert report["audit"]["upstream_failed"] == 1
        assert report["members"][0]["body"] is None
        assert report["members"][0]["status"] == "upstream_failed"


@pytest.mark.parametrize("raw", ["Python 3.12rc1", "Vue 3.5-beta", "Python 3.12+", "python3.12rc1", "Docker 24.0-beta", "Vue >=3", "Vue 3.5 - 4.0"])
def test_unsupported_versions_are_preserved_whole_without_known_prefix_normalization(raw):
    result = govern("必须掌握 " + raw + "。")
    assert result["skills"] == []
    review = result["candidates"] + result["review_mentions"]
    assert len(review) == 1 and review[0]["raw_name"] == raw
    assert review[0]["evidence"]["quote"] == raw
    assert review[0].get("comparison", review[0])["canonical"] is None


@pytest.mark.parametrize("number", ["十一", "二十", "100", "3.5", "3-5"])
def test_unsupported_year_numbers_do_not_match_their_tail(number):
    result = govern(number + "年以上工作经验。")
    assert result["non_skills"] == []
    assert result["unresolved_fragments"][0]["evidence"]["quote"] == number + "年以上工作经验"


@pytest.mark.parametrize("name", ["Scrum", "Agile", "Kanban"])
def test_engineering_practices_are_not_inferred_technical_from_legacy_devops(name):
    result = govern("必须掌握 " + name + "。")
    assert result["skills"][0]["category"] == "engineering_practice"


@pytest.mark.parametrize("changes", [dict(reviewer=" "), dict(basis="\t"), dict(evidence_refs=[""])])
def test_store_cannot_bypass_review_attribution_validation(area, changes):
    from app.job_analysis.governance.candidates import review_event
    from app.job_analysis.governance.runner import execute
    from app.job_analysis.governance.store import GovernanceStore
    _, old = stage_b2(area, ["必须掌握 UnlistedLang。"])
    with GovernanceStore(area / "state.sqlite3") as store:
        member = execute(store, old["run_id"])["members"][0]
        event = review_event(member["body"]["candidates"][0], decision="reviewed_accepted", reviewer="fixture-human",
                             basis="fixture only", evidence_refs=["fixture:check"])
        with pytest.raises(ValueError):
            store.record_review(member["result_id"], event | changes)
        assert store.reviews(member["result_id"]) == []

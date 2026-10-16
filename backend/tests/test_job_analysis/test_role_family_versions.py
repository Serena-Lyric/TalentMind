"""Synthetic version boundaries, not a standard-job list or semantic benchmark."""
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

from test_foundation_inputs import area, load
from test_role_proposals import CATALOG, config, record, no_network
from test_role_governance import catalog, source, submission, candidate
from test_role_governance_storage import event

HARDWARE = "hardware_integrated_circuits"
V2 = CATALOG.with_name("families.v2.json")
HISTORY = Path(__file__).resolve().parents[1] / "fixtures/role_classification/history.families-v1.json"


def eight():
    value = config()
    value["revision"] = "families-v2"
    value["job_family"].append(dict(id=HARDWARE, label="硬件与集成电路",
        scope="以硬件电路、FPGA、芯片或数字 IC 工程交付为核心；跨界主次不明待审。"))
    return value


def test_v1_content_preserved_and_shipped_v2_has_exactly_eight_stable_pairs():
    from app.job_analysis.role_classification.proposals.models import load_taxonomy
    # Git may check out LF or CRLF; the delivery also checks raw pre/post bytes.
    original = CATALOG.read_bytes().replace(b"\r\n", b"\n")
    assert hashlib.sha256(original).hexdigest() == "10194ea96ec0b3a82759ccabef1e7fe9fc82382db6789cde83964c9383ed9519"
    assert V2.is_file(), "versioned eight-family file is missing"
    new = load_taxonomy(V2)
    assert new["revision"] == "families-v2"
    assert [(f["id"], f["label"]) for f in new["job_family"]] == [
        ("software_engineering", "软件研发"), ("test_quality_engineering", "测试与质量工程"),
        ("data_ai", "数据与人工智能"), ("infrastructure_operations", "基础设施与运维"),
        ("network_information_security", "网络与信息安全"), ("embedded_system_software", "嵌入式与系统软件"),
        ("technical_services_delivery", "技术服务与交付"), (HARDWARE, "硬件与集成电路")]
    assert new["canonical_job"] == new["technology_tracks"] == new["seniority"] == []


@pytest.mark.parametrize("bad", ["missing", "duplicate", "label", "id", "v1", "unregistered", "seven-as-v2", "alias", "formal"])
def test_revision_registry_rejects_missing_duplicate_and_relabelled_taxonomies(bad):
    from app.job_analysis.role_classification.proposals.models import FamilyTaxonomy
    value = eight()
    if bad == "missing":
        value["job_family"].pop(0)
    elif bad == "duplicate":
        value["job_family"][-1] = value["job_family"][0]
    elif bad == "label":
        value["job_family"][-1]["label"] = "嵌入式与系统软件"
    elif bad == "id":
        value["job_family"][-1]["id"] = "fpga"
    elif bad in ("v1", "unregistered"):
        value["revision"] = "families-v1" if bad == "v1" else "families-v999"
    elif bad == "seven-as-v2":
        value["job_family"].pop()
    elif bad == "alias":
        value["job_family"][-1]["aliases"] = ["embedded_system_software"]
    else:
        value["canonical_job"] = ["FPGA工程师"]
    with pytest.raises(ValueError):
        FamilyTaxonomy.model_validate(value)


@pytest.mark.parametrize("work", ["设计硬件电路并交付电路原理图", "开发FPGA逻辑并交付验证结果", "设计数字IC并交付RTL"])
def test_hardware_delivery_v2_pending_hint_and_v1_no_hardware(work):
    from app.job_analysis.role_classification.proposals.rules import suggest
    item = record("核心职责：" + work)
    new = suggest(item, eight())
    assert [c["family_id"] for c in new["candidates"]] == [HARDWARE]
    assert new["primary_family_hint"] == HARDWARE and new["resolution"] == "proposed"
    assert new["canonical_job"] == dict(state="unknown", value=None)
    assert new["review_status"] == "pending_review"
    assert new["classification_complete"] is new["formal_statistics_eligible"] is False
    ref = new["candidates"][0]["clues"][0]["evidence"]
    assert item.payload[ref["field"]][ref["start"]:ref["end"]] == ref["quote"] == "核心职责：" + work
    assert suggest(item, config())["candidates"] == []


@pytest.mark.parametrize("text", [
    "FPGA / SoC / 数字IC / Verilog", "负责销售FPGA产品并进行操作培训",
    "公司介绍：核心职责：开发FPGA逻辑并交付验证结果", "历史项目：核心职责：设计数字IC并交付RTL",
    "培训内容：核心职责：设计硬件电路并交付电路原理图", "不负责开发FPGA逻辑并交付验证结果",
    "曾经负责设计数字IC并交付RTL", "核心职责：向客户演示芯片产品",
])
def test_hardware_title_stack_history_training_sales_are_not_duty_candidates(text):
    from app.job_analysis.role_classification.proposals.rules import suggest
    body = suggest(record(text, "FPGA工程师 / 硬件工程师"), eight())
    assert body["candidates"] == [] and body["primary_family_hint"] is None


@pytest.mark.parametrize("text,title,want", [
    ("核心职责：开发FPGA逻辑并交付验证结果。核心职责：开发嵌入式驱动并交付固件", "SoC工程师", {HARDWARE, "embedded_system_software"}),
    ("负责开发FPGA逻辑并交付验证结果", "SoC工程师", {HARDWARE}),
    ("核心职责：开发FPGA逻辑并交付验证结果", "嵌入式工程师", {HARDWARE}),
    ("核心职责：开发嵌入式驱动并交付固件", "FPGA工程师", {"embedded_system_software"}),
])
def test_cross_boundary_unclear_responsibility_and_title_conflict_stay_unresolved(text, title, want):
    from app.job_analysis.role_classification.proposals.rules import suggest
    body = suggest(record(text, title), eight())
    assert {c["family_id"] for c in body["candidates"]} == want
    assert body["resolution"] == "unresolved" and body["primary_family_hint"] is None
    assert "vacancy_count" not in body and body["technology_tracks"] == []


def test_explicit_eighth_candidate_passes_only_with_validated_v2_and_stays_pending(area):
    from app.job_analysis.role_classification.governance.validation import validate_submission
    batch = source(area)
    marks = submission(batch.records[0], [candidate(batch.records[0], family_candidates=[HARDWARE])])
    body = validate_submission(batch, marks, catalog(), taxonomy=eight())[0]
    assert body["candidates"][0]["family_candidates"] == [HARDWARE]
    assert body["primary_job"]["state"] == "unresolved"
    assert body["formal_jobs"] == []
    assert body["formal_admitted"] is body["classification_complete"] is body["formal_statistics_eligible"] is False
    for value in (None, config()):
        with pytest.raises(ValueError):
            validate_submission(batch, marks, catalog(), taxonomy=value)


def restore_history(store):
    fixture = json.loads(HISTORY.read_text(encoding="utf-8"))
    assert fixture["base_commit"] == "bbe5309c44189b1b0d811363320b9df6f37574c9"
    with store.conn:
        for table, rows in fixture["tables"].items():
            for row in rows:
                values = [v["utf8_bytes"].encode("utf-8") if isinstance(v, dict) else v for v in row]
                store.conn.execute(f"INSERT INTO {table} VALUES ({','.join('?' for _ in values)})", values)
    return {t: [tuple(r) for r in store.conn.execute(f"SELECT * FROM {t}")] for t in fixture["tables"]}


def test_pre_upgrade_reports_reviews_and_exports_replay_exactly_in_mixed_version_database(area):
    from app.job_analysis.role_classification.proposals.store import ProposalStore
    from app.job_analysis.role_classification.proposals.runner import execute as propose, replay as p_replay
    from app.job_analysis.role_classification.governance.store import CanonicalStore
    from app.job_analysis.role_classification.governance.runner import execute, replay
    state = area / "history.db"
    with ProposalStore(state):
        pass
    with CanonicalStore(state) as store:
        before = restore_history(store)
        from app.job_analysis.foundation.inputs import read_snapshot
        historical_input = area / "historical-input.json"
        historical_input.write_bytes(before["b32_inputs"][0][3])
        historical_batch = read_snapshot(historical_input, "fixture")
        old_governance = json.loads(before["b32_reports"][0][1])
        old_proposal = json.loads(before["b31_reports"][0][1])
        fresh_governance = execute(store, historical_batch, old_governance["submission"], catalog())
        fresh_proposal = propose(store, historical_batch, config())
        for fresh, old in ((fresh_governance, old_governance), (fresh_proposal, old_proposal)):
            assert fresh["members"][0]["body"] == old["members"][0]["body"]
            assert fresh["version_id"] != old["version_id"]
            assert fresh["members"][0]["result_id"] != old["members"][0]["result_id"]
        old_review = json.loads(before["b32_reviews"][0][2])["event"]
        with pytest.raises(ValueError):
            store.record_review(fresh_governance["members"][0]["result_id"], old_review)
        batch = source(area)
        default = execute(store, batch, submission(batch.records[0]), catalog())
        old_config = execute(store, batch, submission(batch.records[0]), catalog(), taxonomy=config())
        assert old_config["version_id"] == default["version_id"]
        assert old_config["members"][0]["reused"]
        store.record_review(default["members"][0]["result_id"], event(default))
        upgraded = execute(store, batch, submission(batch.records[0]), catalog(), taxonomy=eight())
        assert upgraded["manifest"]["family_taxonomy"] == eight()
        assert upgraded["version_id"] != default["version_id"]
        assert store.reviews(upgraded["members"][0]["result_id"]) == []
        with pytest.raises(ValueError):
            store.record_review(upgraded["members"][0]["result_id"], event(default))
        changed = eight()
        changed["job_family"][-1]["scope"] += " 新范围文字"
        assert execute(store, batch, submission(batch.records[0]), catalog(), taxonomy=changed)["version_id"] != upgraded["version_id"]
        propose(store, batch, config())
        propose(store, batch, eight())
        for table, rows in before.items():
            assert [tuple(r) for r in store.conn.execute(f"SELECT * FROM {table} ORDER BY rowid LIMIT ?", (len(rows),))] == rows
        for table, fn in (("b31_reports", p_replay), ("b32_reports", replay), ("b32_exports", replay)):
            original = json.loads(before[table][0][-2])
            assert fn(store, before[table][0][0]) == original
        for table in ("b31_reports", "b32_reports", "b32_reviews", "b32_exports"):
            with pytest.raises(sqlite3.IntegrityError):
                with store.conn:
                    store.conn.execute(f"DELETE FROM {table}")


@pytest.mark.parametrize("bad", ["evidence", "revision"])
def test_v2_bad_second_annotation_or_taxonomy_rolls_back_whole_run(area, bad):
    from app.job_analysis.role_classification.governance.runner import execute
    from app.job_analysis.role_classification.governance.store import CanonicalStore
    batch = source(area)
    marks, tax = submission(batch.records[0]), eight()
    if bad == "evidence":
        marks["annotations"][0]["candidates"].append(candidate(batch.records[0], "second"))
        marks["annotations"][0]["candidates"][-1]["evidence"][0]["start"] = 999
    else:
        tax["revision"] = "families-v1"
    with CanonicalStore(area / "state.db") as store:
        with pytest.raises(ValueError):
            execute(store, batch, marks, catalog(), taxonomy=tax)
        for table in ("snapshots", "b32_versions", "b32_inputs", "b32_results", "b32_reports"):
            assert store.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0


def test_v2_cli_run_replay_and_explicit_taxonomy_output_protection(area, capsys):
    from app.job_analysis.role_classification.governance.__main__ import main
    batch = source(area)
    marks = submission(batch.records[0], [candidate(batch.records[0], family_candidates=[HARDWARE])])
    claims, jobs, families = [area / f"{name}.json" for name in ("claims", "jobs", "families")]
    for path, value in ((claims, marks), (jobs, catalog()), (families, eight())):
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    args = ["--state", str(area / "state.db"), "--output", str(area / "out")]
    run_args = ["run", *args, "--input", str(batch.path), "--dataset", "fixture", "--submission", str(claims), "--catalog", str(jobs), "--family-taxonomy", str(families)]
    assert main(run_args) == 0
    identity = json.loads(capsys.readouterr().out)["run_id"]
    saved = (area / "out" / (identity + ".json")).read_bytes()
    families.unlink()
    assert main(["replay", *args, "--run", identity]) == 0
    assert (area / "out" / (identity + ".json")).read_bytes() == saved
    protected = area / "out" / "families.json"
    protected.write_text(json.dumps(eight(), ensure_ascii=False), encoding="utf-8")
    run_args[-1] = str(protected)
    assert main(run_args) == 2


@pytest.mark.parametrize("stage", ["after_result", "before_commit", "after_commit", "after_output"])
@pytest.mark.parametrize("layer", ["b31", "b32"])
def test_v2_actual_process_exit_recovers_only_committed_history(area, stage, layer):
    from app.job_analysis.role_classification.governance.store import CanonicalStore
    from app.job_analysis.role_classification.governance.runner import execute, replay
    batch = source(area)
    marks = submission(batch.records[0], [candidate(batch.records[0], family_candidates=[HARDWARE])])
    for name, value in (("claims", marks), ("families", eight())):
        (area / (name + ".json")).write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    script = '''
import json, os, socket, sys
from pathlib import Path
from app.job_analysis.foundation.inputs import read_snapshot
if sys.argv[3] == 'b32':
    from app.job_analysis.role_classification.governance import runner
    from app.job_analysis.role_classification.governance.store import CanonicalStore as Store
else:
    from app.job_analysis.role_classification.proposals import runner
    from app.job_analysis.role_classification.proposals.store import ProposalStore as Store
def blocked(*args, **kwargs):
    raise AssertionError("network prohibited")
socket.socket.connect = socket.socket.connect_ex = blocked
root, stage = Path(sys.argv[1]), sys.argv[2]
runner.checkpoint = lambda point: os._exit(71) if point == stage else None
read = lambda name: json.loads((root/(name+'.json')).read_text(encoding='utf-8'))
with Store(root/'state.db') as store:
    batch = read_snapshot(root/'input.json','fixture')
    if sys.argv[3] == 'b32':
        runner.execute(store, batch, read('claims'), dict(schema_version='b32-catalog-1', revision='empty-v1', formal_jobs=[]), taxonomy=read('families'), output=root/'out')
    else:
        runner.execute(store, batch, read('families'), output=root/'out')
'''
    done = subprocess.run([sys.executable, "-X", "utf8", "-c", script, str(area), stage, layer], capture_output=True)
    assert done.returncode == 71, done.stderr.decode()
    if layer == "b31":
        from app.job_analysis.role_classification.proposals.store import ProposalStore as CanonicalStore
        from app.job_analysis.role_classification.proposals.runner import execute, replay
    with CanonicalStore(area / "state.db") as store:
        reports = store.conn.execute(f"SELECT run_id FROM {layer}_reports").fetchall()
        committed = stage in ("after_commit", "after_output")
        assert len(reports) == int(committed)
        if committed:
            key = "family_taxonomy" if layer == "b32" else "taxonomy"
            assert replay(store, reports[0][0])["manifest"][key] == eight()
        result = (execute(store, batch, marks, catalog(), taxonomy=eight()) if layer == "b32" else execute(store, batch, eight()))
        assert result["members"][0]["reused"] == committed
        assert store.conn.execute(f"SELECT COUNT(*) FROM {layer}_results").fetchone()[0] == 1


def test_v2_shipped_synthetic_examples_run_both_clis_and_replay(area, capsys):
    from app.job_analysis.foundation.inputs import read_snapshot
    from app.job_analysis.role_classification.proposals.__main__ import main as proposals_cli
    from app.job_analysis.role_classification.governance.__main__ import main as governance_cli
    fixtures = HISTORY.parent
    source_path = fixtures / "families-v2.input.json"
    marks_path = fixtures / "families-v2.submission.json"
    jobs = CATALOG.parent.parent / "governance/catalog.empty.v1.json"
    common = ["--state", str(area / "state.db"), "--output", str(area / "out")]
    inputs = ["--input", str(source_path), "--dataset", "synthetic-b33"]
    assert proposals_cli(["run", *common, *inputs, "--taxonomy", str(V2)]) == 0
    p_id = json.loads(capsys.readouterr().out)["run_id"]
    p_saved = (area / "out" / (p_id + ".json")).read_bytes()
    p = json.loads(p_saved)
    assert p["members"][0]["body"]["primary_family_hint"] == HARDWARE
    assert p["members"][1]["body"]["resolution"] == "unresolved"
    assert p["members"][2]["body"]["candidates"] == []
    assert proposals_cli(["replay", *common, "--run", p_id]) == 0
    capsys.readouterr()
    assert (area / "out" / (p_id + ".json")).read_bytes() == p_saved
    assert governance_cli(["run", *common, *inputs, "--submission", str(marks_path), "--catalog", str(jobs), "--family-taxonomy", str(V2)]) == 0
    g_id = json.loads(capsys.readouterr().out)["run_id"]
    g_saved = (area / "out" / (g_id + ".json")).read_bytes()
    g = json.loads(g_saved)
    assert g["members"][0]["body"]["primary_job"] == dict(state="unresolved", value=None, candidates=["hardware-example"])
    assert g["members"][0]["body"]["relations"][0]["mapping_active"] is False
    assert g["members"][1]["body"]["primary_job"]["candidates"] == ["cross-hardware", "cross-embedded"]
    assert governance_cli(["replay", *common, "--run", g_id]) == 0
    assert (area / "out" / (g_id + ".json")).read_bytes() == g_saved
    assert g["input_sha256"] == hashlib.sha256(source_path.read_bytes()).hexdigest()
    batch = read_snapshot(source_path, "synthetic-b33")
    from app.job_analysis.role_classification.proposals.models import validate_proposal
    # A genuine v2 hardware proposal cannot be reinterpreted using the seven-family validator.
    with pytest.raises(ValueError):
        validate_proposal(batch.records[0], p["members"][0]["body"], config())

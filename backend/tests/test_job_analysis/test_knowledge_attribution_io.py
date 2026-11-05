"""Versioned P2-2 CLI and historical contract; no model, database or network."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from app.job_analysis.foundation.inputs import digest
from app.job_analysis.knowledge.storage import read_result
from test_knowledge_cli import run_cli, write_analysis
from test_knowledge_roles import analysis_with_duties

BACKEND = Path(__file__).resolve().parents[2]
KNOWLEDGE = BACKEND / "app/job_analysis/knowledge/catalog/role-references.v2"
POLICY = BACKEND / "app/job_analysis/knowledge/policies/role-attribution.v1.json"


def test_cli_attribute_read_and_reexplain_append_only(tmp_path):
    source = tmp_path / "analysis.json"
    write_analysis(source, analysis_with_duties(["使用Python开发软件服务并交付应用"]))
    first = tmp_path / "first"
    invocation = ("attribute", "--analysis", source, "--snapshot", KNOWLEDGE, "--policy", POLICY, "--output", first)
    generated = run_cli(*invocation)
    assert generated.returncode == 0, generated.stdout + generated.stderr
    summary = json.loads(generated.stdout)
    assert summary["axes"]["canonical_job"] == "single"
    assert "软件" not in generated.stdout
    before = (first / "value.json").read_bytes()
    assert run_cli(*invocation).returncode == 1
    assert (first / "value.json").read_bytes() == before
    historic = run_cli("read-attribution", "--result", first)
    assert historic.returncode == 0
    assert json.loads(historic.stdout)["source_analysis_sha256"] == summary["source_analysis_sha256"]

    value = json.loads(POLICY.read_text(encoding="utf-8"))
    value["revision"] = "controlled-new-delivery-definition"
    for rule in value["roles"]:
        rule["deliveries"] = ["受控新交付物"]
    changed = tmp_path / "policy.json"
    changed.write_text(json.dumps(value), encoding="utf-8")
    second = tmp_path / "second"
    reinterpreted = run_cli("reexplain", "--previous", first, "--snapshot", KNOWLEDGE,
                           "--policy", changed, "--output", second)
    assert reinterpreted.returncode == 0, reinterpreted.stdout + reinterpreted.stderr
    a, b = read_result(first), read_result(second)
    assert a["source_analysis_sha256"] == b["source_analysis_sha256"]
    assert a["policy_sha256"] != b["policy_sha256"]
    assert b["reinterprets_sha256"] == digest(a)
    assert b["change_kind"] == "interpretation_only"
    assert b["axes"]["canonical_job"]["status"] == "unresolved"
    assert read_result(first) == a
    assert run_cli("read-attribution", "--result", first).returncode == 0


def test_cli_corrupt_output_and_public_output_rejected(tmp_path):
    source = tmp_path / "analysis.json"
    write_analysis(source, analysis_with_duties(["开发软件服务并交付应用"]))
    output = tmp_path / "result"
    assert run_cli("attribute", "--analysis", source, "--snapshot", KNOWLEDGE, "--policy", POLICY,
                   "--output", output).returncode == 0
    (output / "value.json").write_text("{}", encoding="utf-8")
    failed = run_cli("read-attribution", "--result", output)
    assert failed.returncode == 1
    assert "Traceback" not in failed.stderr
    public = BACKEND / "tests" / "forbidden-attribution-output"
    assert not public.exists()
    failed = run_cli("attribute", "--analysis", source, "--snapshot", KNOWLEDGE,
                     "--policy", POLICY, "--output", public)
    assert failed.returncode == 1
    assert not public.exists()


def test_policy_and_projection_wrong_binding_rejected():
    from app.job_analysis.knowledge.attribution import attribute_roles
    from app.job_analysis.knowledge.catalog import load_snapshot
    from app.job_analysis.knowledge.role_policy import load_policy, bind_policy

    value = load_policy(POLICY).policy.model_dump()
    value["knowledge_sha256"] = "a" * 64
    with pytest.raises(ValueError, match="binding"):
        attribute_roles(analysis_with_duties(["开发软件服务并交付应用"]), load_snapshot(KNOWLEDGE), bind_policy(value))


def test_historical_reader_rejects_self_consistent_manifest_with_foreign_support(tmp_path):
    from app.job_analysis.knowledge.attribution import attribute_roles, read_attribution
    from app.job_analysis.knowledge.catalog import load_snapshot
    from app.job_analysis.knowledge.role_policy import load_policy
    from app.job_analysis.knowledge.storage import save_result

    result = attribute_roles(analysis_with_duties(["开发软件服务并交付应用"]),
                             load_snapshot(KNOWLEDGE), load_policy(POLICY))
    value = result.model_dump()
    supported = next(r for r in value["comparisons"] if r["role_id"] == "ref-software-development")
    supported["supports"][0]["jd_evidence"]["quote"] = "不是实际原文"
    save_result(tmp_path / "bad", value)
    with pytest.raises(ValueError):
        read_attribution(tmp_path / "bad")


def test_different_knowledge_versions_preserve_input_and_history(tmp_path):
    from app.job_analysis.knowledge.attribution import attribute_roles, read_attribution
    from app.job_analysis.knowledge.catalog import load_snapshot
    from app.job_analysis.knowledge.role_policy import load_policy, bind_policy
    from app.job_analysis.knowledge.storage import save_result
    from test_knowledge_catalog import write_snapshot

    source = analysis_with_duties(["开发软件服务并交付应用"])
    old = load_snapshot(KNOWLEDGE)
    policy = load_policy(POLICY)
    a = attribute_roles(source, old, policy)
    save_result(tmp_path / "old", a.model_dump())
    value = old.snapshot.model_dump()
    value["revision"] = "changed-reference"
    value["roles"] = [r for r in value["roles"] if r["id"] != "ref-software-development"]
    write_snapshot(tmp_path / "knowledge", value)
    new = load_snapshot(tmp_path / "knowledge")
    rules = policy.policy.model_dump()
    rules["knowledge_sha256"] = new.sha256
    rules["roles"] = [r for r in rules["roles"] if r["role_id"] != "ref-software-development"]
    b = attribute_roles(source, new, bind_policy(rules))
    assert a.source_analysis_sha256 == b.source_analysis_sha256
    assert a.knowledge_sha256 != b.knowledge_sha256
    assert a.axes.canonical_job.values and not b.axes.canonical_job.values
    assert read_attribution(tmp_path / "old") == a


def test_immutable_catalog_bytes_survive_git_checkout_attributes():
    import subprocess
    paths = [KNOWLEDGE / "knowledge.json", KNOWLEDGE.parent / "backend-foundations.v1/knowledge.json"]
    root = BACKEND.parent
    result = subprocess.run(["git", "check-attr", "eol", "--", *[p.relative_to(root).as_posix() for p in paths]],
                            cwd=root, capture_output=True, text=True, check=True)
    assert all(line.endswith(": lf") for line in result.stdout.strip().splitlines())
    for path in paths:
        assert b"\r\n" not in path.read_bytes()
        manifest = json.loads((path.parent / "manifest.json").read_text())
        assert hashlib.sha256(path.read_bytes()).hexdigest() == manifest["sha256"]


@pytest.mark.parametrize("mutation", ["axis", "support", "definition"])
def test_historical_contract_rejects_inconsistent_decisions_and_definition(mutation):
    from app.job_analysis.knowledge.attribution import attribute_roles
    from app.job_analysis.knowledge.attribution_models import AttributionResult
    from app.job_analysis.knowledge.catalog import load_snapshot
    from app.job_analysis.knowledge.role_policy import load_policy
    result = attribute_roles(analysis_with_duties(["开发软件服务并交付应用"]),
                             load_snapshot(KNOWLEDGE), load_policy(POLICY))
    value = result.model_dump()
    comparison = next(r for r in value["comparisons"] if r["role_id"] == "ref-software-development")
    if mutation == "axis":
        value["axes"]["canonical_job"].update(status="unresolved", values=[])
    elif mutation == "support":
        comparison.update(supports=[], deliveries=[])
    else:
        comparison["definition"]["name"] = "被改写的岗位定义"
    with pytest.raises(ValueError):
        AttributionResult.model_validate(value)


@pytest.mark.parametrize("mutation", ["foreign_claim_kind", "inflate_core"])
def test_historical_support_cannot_outgrow_its_p1_claim(mutation):
    from app.job_analysis.knowledge.attribution import attribute_roles
    from app.job_analysis.knowledge.attribution_models import AttributionResult
    from app.job_analysis.knowledge.catalog import load_snapshot
    from app.job_analysis.knowledge.role_policy import load_policy
    source = analysis_with_duties(["开发软件服务并交付应用"], core_values=[None])
    result = attribute_roles(source, load_snapshot(KNOWLEDGE), load_policy(POLICY))
    value = result.model_dump()
    comparison = next(r for r in value["comparisons"] if r["role_id"] == "ref-software-development")
    if mutation == "foreign_claim_kind":
        comparison["supports"][0]["claim_id"] = source["claims"][-1]["id"]
    else:
        comparison["supports"][0]["importance"] = "core"
        comparison["judgment"] = "core_candidate"
        value["primary_role_id"] = "ref-software-development"
        value["axes"]["canonical_job"].update(status="single", values=["ref-software-development"])
    with pytest.raises(ValueError):
        AttributionResult.model_validate(value)

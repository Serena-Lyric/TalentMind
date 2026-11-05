"""CLI round trip for the public P2-1 knowledge workflow."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
from uuid import uuid4

from test_knowledge_alignment import analysis_with


BACKEND = Path(__file__).resolve().parents[2]
SHIPPED_CATALOG = BACKEND / "app/job_analysis/knowledge/catalog/backend-foundations.v1"


def run_cli(*arguments):
    return subprocess.run(
        [sys.executable, "-m", "app.job_analysis.knowledge", *map(str, arguments)],
        cwd=BACKEND,
        capture_output=True,
        text=True,
    )


def write_analysis(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def test_cli_validate_align_compare_govern_and_profile_roundtrip(tmp_path):
    analysis = analysis_with(["Flink SQL"], jd_id="cli-one")
    source = tmp_path / "analysis.json"
    write_analysis(source, analysis)

    validated = run_cli("validate", "--snapshot", SHIPPED_CATALOG)
    assert validated.returncode == 0
    assert json.loads(validated.stdout)["revision"] == "backend-foundations-1"

    alignment_dir = tmp_path / "alignment"
    aligned = run_cli("align", "--analysis", source, "--snapshot", SHIPPED_CATALOG,
                      "--output", alignment_dir)
    assert aligned.returncode == 0
    aligned_summary = json.loads(aligned.stdout)
    assert aligned_summary["unknown"] == 1
    assert "Flink SQL" not in aligned.stdout

    comparison_dir = tmp_path / "comparison"
    compared = run_cli("compare", "--analysis", source, "--snapshot", SHIPPED_CATALOG,
                       "--output", comparison_dir)
    assert compared.returncode == 0
    assert json.loads(compared.stdout)["checked_roles"] == 3

    registry = tmp_path / "registry"
    governed = run_cli("govern", "--analysis", source, "--alignment", alignment_dir,
                        "--registry", registry)
    assert governed.returncode == 0
    assert json.loads(governed.stdout)["observations"] == 1

    profile_dir = tmp_path / "profile"
    profiled = run_cli(
        "profile", "--role-id", "p0-ref-programming",
        "--comparisons", comparison_dir, "--alignments", alignment_dir,
        "--output", profile_dir,
    )
    assert profiled.returncode == 0
    assert json.loads(profiled.stdout)["members"] == 0


def test_cli_refuses_overwrite_and_public_repository_output(tmp_path):
    source = tmp_path / "analysis.json"
    write_analysis(source, analysis_with(["Python"]))
    output = tmp_path / "alignment"
    first = run_cli("align", "--analysis", source, "--snapshot", SHIPPED_CATALOG, "--output", output)
    second = run_cli("align", "--analysis", source, "--snapshot", SHIPPED_CATALOG, "--output", output)
    assert first.returncode == 0
    assert second.returncode == 1
    assert json.loads(second.stdout)["status"] == "rejected"

    public_dir = BACKEND / "app" / ("__knowledge_cli_" + uuid4().hex)
    try:
        rejected = run_cli("align", "--analysis", source, "--snapshot", SHIPPED_CATALOG,
                           "--output", public_dir)
        assert rejected.returncode == 1
        assert not public_dir.exists()
    finally:
        if public_dir.exists():
            shutil.rmtree(public_dir)

    public_registry = BACKEND / "app" / ("__knowledge_registry_" + uuid4().hex)
    try:
        rejected_registry = run_cli(
            "govern", "--analysis", source, "--alignment", output,
            "--registry", public_registry,
        )
        assert rejected_registry.returncode == 1
        assert not public_registry.exists()
    finally:
        if public_registry.exists():
            shutil.rmtree(public_registry)


def test_cli_align_verifies_a_saved_p1_run_directory(tmp_path):
    from test_understanding import draft, run
    from app.job_analysis.understanding.storage import save_run

    result = run(draft())
    run_path = tmp_path / "p1-run"
    save_run(run_path, result)
    output = tmp_path / "alignment"
    completed = run_cli("align", "--analysis", run_path, "--snapshot", SHIPPED_CATALOG,
                        "--output", output)
    assert completed.returncode == 0
    assert json.loads(completed.stdout)["requirements"] == 1
    assert "Redis" not in completed.stdout

    (run_path / "run.json").write_text('{"tampered":true}', encoding="utf-8")
    rejected = run_cli("align", "--analysis", run_path, "--snapshot", SHIPPED_CATALOG,
                       "--output", tmp_path / "tampered-output")
    assert rejected.returncode == 1
    assert not (tmp_path / "tampered-output").exists()


def test_cli_govern_projects_verified_candidate_for_limited_alignment(tmp_path):
    from app.job_analysis.knowledge.storage import read_result

    first_analysis = analysis_with(["Flink SQL"], jd_id="cli-projection-one",
                                   row_extra={"source_identity": "cli-employer-a"})
    second_analysis = analysis_with(
        ["Flink SQL"],
        row_extra={"source_identity": "cli-employer-b"},
        raw_text="任职要求：掌握 Flink SQL。",
        source="Zhaopin",
        jd_id="cli-projection-two",
    )
    first_path = tmp_path / "first.json"
    second_path = tmp_path / "second.json"
    write_analysis(first_path, first_analysis)
    write_analysis(second_path, second_analysis)
    first_alignment = tmp_path / "first-alignment"
    second_alignment = tmp_path / "second-alignment"
    for source, output in ((first_path, first_alignment), (second_path, second_alignment)):
        completed = run_cli("align", "--analysis", source, "--snapshot", SHIPPED_CATALOG,
                            "--output", output)
        assert completed.returncode == 0
    registry = tmp_path / "registry"
    for source, alignment in ((first_path, first_alignment), (second_path, second_alignment)):
        governed = run_cli("govern", "--analysis", source, "--alignment", alignment,
                           "--registry", registry)
        assert governed.returncode == 0
    summary = json.loads(governed.stdout)
    assert summary["projection_concepts"] == 1
    projection = registry / "projections" / summary["projection_sha256"]
    output = tmp_path / "limited-alignment"
    completed = run_cli(
        "align", "--analysis", first_path, "--snapshot", SHIPPED_CATALOG,
        "--candidate-projection", projection, "--output", output,
    )
    assert completed.returncode == 0
    value = read_result(output)
    decision = value["requirements"][0]["alignments"][0]
    assert decision["concept_source"] == "candidate"
    assert decision["knowledge_status"] == "candidate"
    assert value["candidate_projection_sha256"] == summary["projection_sha256"]


def test_cli_compare_accepts_concept_only_snapshot(tmp_path):
    from test_knowledge_catalog import catalog_value, write_snapshot

    value = catalog_value()
    value["roles"] = []
    snapshot = tmp_path / "concept-only"
    write_snapshot(snapshot, value)
    source = tmp_path / "analysis.json"
    write_analysis(source, analysis_with(["别名一"]))
    completed = run_cli("compare", "--analysis", source, "--snapshot", snapshot,
                        "--output", tmp_path / "comparison")
    assert completed.returncode == 0
    assert json.loads(completed.stdout)["checked_roles"] == 0

def test_cli_impact_reads_candidate_projection_versions(tmp_path):
    from test_knowledge_versions import _candidate_projection_pair

    registry, empty, projected, source = _candidate_projection_pair(tmp_path)
    source_path = tmp_path / "source.json"
    write_analysis(source_path, source)
    alignment = tmp_path / "old-alignment"
    completed = run_cli(
        "align", "--analysis", source_path, "--snapshot", SHIPPED_CATALOG,
        "--candidate-projection", registry.root / "projections" / empty.sha256, "--output", alignment,
    )
    assert completed.returncode == 0
    output = tmp_path / "impact"
    completed = run_cli(
        "impact", "--old", SHIPPED_CATALOG, "--new", SHIPPED_CATALOG,
        "--old-candidate-projection", registry.root / "projections" / empty.sha256,
        "--new-candidate-projection", registry.root / "projections" / projected.sha256,
        "--alignments", alignment, "--output", output,
    )
    assert completed.returncode == 0
    assert json.loads(completed.stdout)["candidate_projection_changed"] is True

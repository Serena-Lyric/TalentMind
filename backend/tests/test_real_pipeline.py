"""Real pipeline contract tests use synthetic inputs, never production services."""
import json
from pathlib import Path

import pytest


def test_pipeline_keeps_identity_states_and_source_evidence(tmp_path):
    from app.graph.real_pipeline import run_pipeline, verify_bundle
    rows = [
        dict(id=1, source="synthetic", job_title="软件开发工程师", raw_text="负责开发软件接口。\n任职要求：必须掌握 Python。\n不要求 Java。\nPython 或 Go 至少掌握一种。"),
        dict(id=2, source="synthetic", job_title="行政助理", raw_text="负责整理行政报表，使用 Excel。"),
        dict(id=3, source="synthetic", job_title="软件开发工程师", raw_text="负责开发软件接口。\n任职要求：必须掌握 Python。\n不要求 Python。\n熟悉 ZorbTool。"),
    ]
    source = tmp_path / "input.json"
    source.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    output = tmp_path / "bundle"
    manifest = run_pipeline(source, "synthetic-e2e", output)
    verify_bundle(output)
    graph = json.loads((output / "facts.json").read_text(encoding="utf-8"))
    sources = json.loads((output / "sources.json").read_text(encoding="utf-8"))
    assert manifest["counts"]["input"] == 3
    assert manifest["counts"]["eligible_jd"] == 2
    assert len([n for n in graph["nodes"] if n["type"] == "job"]) == 2
    assert not any(n["type"] == "industry" for n in graph["nodes"])
    assert {e["state"] for e in graph["edges"]} >= {"required", "not_required"}
    assert any(e["relation"] == "any_of" for e in graph["edges"])
    assert any(e["conflict"] for e in graph["edges"])
    assert all(e["semantic_validation"] == "deterministic_rules_only" for e in graph["edges"])
    assert all(e["type"] == "HAS_SKILL_STATEMENT" for e in graph["edges"])
    assert manifest["formal_statistics_eligible"] is False
    assert len(sources["records"]) == 3
    assert any(r["governance"] and r["governance"]["candidates"] for r in sources["records"])
    for edge in graph["edges"]:
        record = sources["records"][edge["source_record"]]
        ev = edge["evidence"]
        assert record["payload"][ev["field"]][ev["start"]:ev["end"]] == ev["quote"]
    assert not any(e["type"] == "RELATED_TO" for e in graph["edges"])
    with pytest.raises(ValueError, match="exist"):
        run_pipeline(source, "synthetic-e2e", output)
    (output / "facts.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="hash"):
        verify_bundle(output)


def test_pipeline_empty_scope_still_publishes_rejections(tmp_path):
    from app.graph.real_pipeline import run_pipeline, verify_bundle
    source = tmp_path / "input.json"
    source.write_text(json.dumps([dict(id=1, source="synthetic", job_title="行政助理", raw_text="负责整理行政报表，使用 Excel。")]), encoding="utf-8")
    manifest = run_pipeline(source, "synthetic-empty", tmp_path / "bundle")
    assert manifest["counts"]["eligible_jd"] == 0
    assert manifest["counts"]["fact_edges"] == 0
    verify_bundle(tmp_path / "bundle")


def test_empty_real_body_is_audited_without_dropping_other_records(tmp_path):
    from app.graph.real_pipeline import run_pipeline, verify_bundle
    source = tmp_path / "input.json"
    source.write_text(json.dumps([dict(id=1, source="synthetic", job_title="岗位", raw_text=""),
        dict(id=2, source="synthetic", job_title="软件工程师", raw_text="负责开发软件接口。\n任职要求：必须掌握 Python。")]), encoding="utf-8")
    output = tmp_path / "bundle"
    manifest = run_pipeline(source, "synthetic-invalid", output)
    assert manifest["counts"]["input"] == 2
    assert manifest["m2_audits"]["screening"]["input_failed"] == 1
    sources = json.loads((output / "sources.json").read_text(encoding="utf-8"))
    assert len(sources["records"]) == 2
    assert sources["records"][0]["payload"]["raw_text"] == ""
    assert sources["records"][0]["eligible"] is False
    verify_bundle(output)
    import hashlib
    # Rewriting a source and its file hash must still fail against the frozen M1/M2 inputs.
    sources["records"][0]["payload"]["raw_text"] = "replacement"
    from app.job_analysis.foundation.inputs import digest
    sources["records"][0]["fingerprint"] = digest(sources["records"][0]["payload"])
    changed = json.dumps(sources).encode()
    (output / "sources.json").write_bytes(changed)
    manifest["artifacts"]["sources.json"] = hashlib.sha256(changed).hexdigest()
    (output / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="source"):
        verify_bundle(output)


def test_export_requires_new_private_destination(tmp_path):
    from app.integration.real_jd_export import validate_destination
    with pytest.raises(ValueError):
        validate_destination(Path(__file__).resolve())
    with pytest.raises(ValueError):
        validate_destination(tmp_path)


def test_sql_export_parses_extended_values_and_preserves_original_text(tmp_path):
    from app.integration.real_jd_export import export_sql
    source = tmp_path / "source.sql"
    source.write_text("CREATE TABLE `jd_pool` (\n `id` bigint,\n `source` varchar(32),\n `source_detail` text,\n `job_title` text,\n `raw_text` text\n);\nINSERT INTO `jd_pool` VALUES (1,'boss','url','NULL','a, b (x)\\nquote \\' ok'),(2,'zhaopin',NULL,'岗位','正文');\n", encoding="utf-8")
    export_sql(source, tmp_path / "export", 40)
    rows = json.loads((tmp_path / "export/input.json").read_text(encoding="utf-8"))
    assert rows[0]["job_title"] == "NULL"
    assert rows[0]["raw_text"] == "a, b (x)\nquote ' ok"
    assert rows[1]["source_detail"] is None


def test_group_conflict_does_not_spread_to_another_member():
    from app.graph.real_pipeline import project
    from app.job_analysis.semantics.models import resolve
    statements = [dict(id="s1", skills=[dict(name="python")], state="required", relation=None),
        dict(id="s2", skills=[dict(name="python")], state="not_required", relation=None),
        dict(id="s3", skills=[dict(name="python"),dict(name="go")], state="required", relation="any_of")]
    for s in statements:
        s.update(requirement_object="capability",degree=None,target="candidate",condition=None)
    overlay = dict(original_semantics=dict(statements=statements,effective=resolve(statements)),
        skills=[dict(id="k1",canonical="python",statement_ids=["s3"],evidence={}),dict(id="k2",canonical="go",statement_ids=["s3"],evidence={})])
    sources = dict(records=[dict(eligible=True,screening={},governance=overlay,namespace="test",jd_id="1",payload=dict(source="synthetic",job_title="test"))])
    graph,_ = project(sources)
    assert next(e for e in graph["edges"] if e["target"]=="skill:python")["conflict"] is True
    assert next(e for e in graph["edges"] if e["target"]=="skill:go")["conflict"] is False


def test_project_keeps_legacy_node_shape_when_source_has_no_identity_metadata():
    from app.graph.real_pipeline import project
    overlay = dict(
        original_semantics=dict(statements=[], effective=[]),
        skills=[],
    )
    sources = dict(records=[dict(
        eligible=True, screening={}, governance=overlay,
        namespace="legacy", jd_id="1",
        payload=dict(source="synthetic", job_title="Python", raw_text="Python"),
    )])
    graph, _ = project(sources)
    job = next(node for node in graph["nodes"] if node["type"] == "job")
    assert "identity_status" not in job
    assert "content_eligible" not in job
    assert "identity_evidence" not in job


def test_verify_recomputes_derived_and_layout_instead_of_trusting_rehashed_file(tmp_path):
    import hashlib
    from app.graph.real_pipeline import run_pipeline, verify_bundle
    source = tmp_path / "input.json"
    source.write_text(json.dumps([dict(id=1,source="synthetic",job_title="软件工程师",raw_text="负责开发软件接口。\n任职要求：必须掌握 Python。")]),encoding="utf-8")
    output = tmp_path / "bundle"
    manifest = run_pipeline(source,"synthetic-verify",output)
    changed = json.dumps(dict(edges=[dict(source="missing",target="other",score=1)] )).encode()
    (output / "derived.json").write_bytes(changed)
    manifest["artifacts"]["derived.json"] = hashlib.sha256(changed).hexdigest()
    (output / "manifest.json").write_text(json.dumps(manifest),encoding="utf-8")
    with pytest.raises(ValueError,match="derived"):
        verify_bundle(output)

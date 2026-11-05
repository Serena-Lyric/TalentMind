"""P2-1 knowledge snapshots bind source, license, evidence and manifest integrity."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest


BACKEND = Path(__file__).resolve().parents[2]
SHIPPED_CATALOG = BACKEND / "app/job_analysis/knowledge/catalog/backend-foundations.v1"


def source(source_id="src-fixture"):
    return {
        "id": source_id,
        "title": "Fixture source",
        "uri": "https://example.invalid/source",
        "document_version": "fixture-v1",
        "retrieved_on": "2026-11-04",
        "license_id": "CC-BY-4.0",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "use_constraint": "short citation only",
        "sha256": "a" * 64,
    }


def evidence(source_id="src-fixture", quote="Fixture evidence"):
    return {"source_id": source_id, "locator": "fixture section", "quote": quote}


def concept(concept_id="concept-one", name="概念一", alias="别名一"):
    return {
        "id": concept_id,
        "name": name,
        "definition": "仅供工程测试的概念定义",
        "category": "technical_skill",
        "maturity": "candidate",
        "aliases": [{"term": alias, "evidence": [evidence()]}],
        "evidence": [evidence()],
        "approval_source": None,
    }


def role(role_id="role-fixture", maturity="candidate"):
    return {
        "id": role_id,
        "name": "测试岗位",
        "definition_version": "role-fixture-1",
        "maturity": maturity,
        "goals": ["交付测试软件"],
        "responsibilities": [{
            "id": "resp-one",
            "text": "编写测试程序",
            "anchors": [["编写"], ["程序"]],
            "evidence": [evidence()],
        }],
        "boundaries": [],
        "known_scope": ["仅用于测试"],
        "unresolved_boundaries": ["真实岗位边界待审"],
        "evidence": [evidence()],
        "approval_source": None,
    }


def catalog_value():
    return {
        "schema_version": "m2-knowledge-1",
        "id": "fixture-knowledge",
        "revision": "fixture-1",
        "purpose": "测试知识快照",
        "created_on": "2026-11-04",
        "sources": [source()],
        "concepts": [concept()],
        "relations": [],
        "roles": [role()],
    }


def write_snapshot(root, value):
    root.mkdir()
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    (root / "knowledge.json").write_bytes(raw)
    manifest = {
        "schema_version": "m2-knowledge-manifest-1",
        "sha256": hashlib.sha256(raw).hexdigest(),
    }
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def test_shipped_catalog_binds_sources_licenses_and_exact_excerpts():
    from app.job_analysis.knowledge.catalog import load_snapshot

    loaded = load_snapshot(SHIPPED_CATALOG)
    assert loaded.snapshot.revision == "backend-foundations-1"
    assert {s.id for s in loaded.snapshot.sources} >= {
        "src-python-docs",
        "src-mdn-javascript",
        "src-mdn-typescript",
        "src-kubernetes",
        "src-role-programming",
        "src-role-network",
    }
    assert all(source.license_id and source.license_url for source in loaded.snapshot.sources)
    assert all(evidence.quote for concept in loaded.snapshot.concepts
               for evidence in [*concept.evidence, *[a for alias in concept.aliases for a in alias.evidence]])
    assert loaded.sha256 == json.loads((SHIPPED_CATALOG / "manifest.json").read_text(encoding="utf-8"))["sha256"]


def test_shipped_catalog_separates_exact_alias_from_related_languages():
    from app.job_analysis.knowledge.catalog import load_snapshot

    loaded = load_snapshot(SHIPPED_CATALOG)
    concepts = {item.id: item for item in loaded.snapshot.concepts}
    javascript = concepts["concept-javascript"]
    typescript = concepts["concept-typescript"]
    assert {javascript.name, *[alias.term for alias in javascript.aliases]} >= {"JavaScript", "JS"}
    assert typescript.id != javascript.id
    assert any(relation.source_id == "concept-typescript"
               and relation.target_id == "concept-javascript"
               and relation.kind == "narrower_than"
               for relation in loaded.snapshot.relations)


def test_ambiguous_alias_is_rejected_instead_of_silently_merged():
    from app.job_analysis.knowledge.models import validate_snapshot

    value = catalog_value()
    value["concepts"].append(concept("concept-two", "概念二", "别名二"))
    value["concepts"][1]["aliases"][0]["term"] = "别名一"
    with pytest.raises(ValueError, match="ambiguous"):
        validate_snapshot(value)


def test_formal_entry_requires_per_item_approval_evidence():
    from app.job_analysis.knowledge.models import validate_snapshot

    value = catalog_value()
    value["concepts"][0]["maturity"] = "formal"
    with pytest.raises(ValueError, match="approval"):
        validate_snapshot(value)


def test_manifest_digest_detects_changed_snapshot_bytes(tmp_path):
    from app.job_analysis.knowledge.catalog import load_snapshot

    root = tmp_path / "snapshot"
    write_snapshot(root, catalog_value())
    assert load_snapshot(root).snapshot.id == "fixture-knowledge"
    path = root / "knowledge.json"
    path.write_bytes(path.read_bytes().replace("Fixture source".encode(), "Changed source".encode()))
    with pytest.raises(ValueError, match="digest"):
        load_snapshot(root)


def test_evidence_must_bind_existing_source_and_roles_need_core_content():
    from app.job_analysis.knowledge.models import validate_snapshot

    value = deepcopy(catalog_value())
    value["concepts"][0]["evidence"][0]["source_id"] = "missing"
    with pytest.raises(ValueError, match="source"):
        validate_snapshot(value)

    value = catalog_value()
    value["roles"][0]["responsibilities"] = []
    with pytest.raises(ValueError):
        validate_snapshot(value)


def test_concept_only_snapshot_loads_and_compares_without_role_candidates(tmp_path):
    from app.job_analysis.knowledge.alignment import align_analysis
    from app.job_analysis.knowledge.catalog import load_snapshot
    from app.job_analysis.knowledge.roles import compare_roles
    from test_knowledge_alignment import analysis_with

    value = catalog_value()
    value["roles"] = []
    root = tmp_path / "concept-only"
    write_snapshot(root, value)
    knowledge = load_snapshot(root)
    aligned = align_analysis(analysis_with(["别名一"]), knowledge)
    compared = compare_roles(analysis_with(["整理资料"]), knowledge)
    assert aligned.alignments[0].concept_id == "concept-one"
    assert compared.checked_role_ids == []
    assert compared.comparisons == []
    assert compared.comparison_status == "no_role_candidates"

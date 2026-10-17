"""Issue #20: full graph projection, entirely in memory and without service imports."""
import copy
import json
from pathlib import Path
from urllib.parse import unquote

import pytest

from app.integration.rebuild_m2_graph import build_graph_data


def job(number=1, required=(), bonus=(), scenarios=(), **extra):
    return dict(id=number, m2_job_id=f"j-{number:02}", job_name=f"Job {number}",
                required_skills=list(required), bonus_skills=list(bonus),
                scenarios=list(scenarios), **extra)


def of_type(graph, kind):
    return [item for item in graph["edges"] if item["type"] == kind]


@pytest.mark.parametrize("names", [
    ["C++", "C#"], ["C", "C++", "C#"], [".NET", "NET"],
    ["A/B", "A-B", "A B"], ["C%2B%2B", "C++"],
    ["Vue 2", "Vue 3", "vue"], ["++", "#", "unknown"],
])
def test_skill_names_do_not_collapse(names):
    graph = build_graph_data([job(required=names)], [])
    skills = [item for item in graph["nodes"] if item["type"] == "skill"]
    assert len(skills) == len(names)
    assert {unquote(item["id"].split(":", 1)[1]) for item in skills} == {
        item["name"] for item in skills}


def test_exact_canonical_case_variants_merge_with_original_occurrences():
    graph = build_graph_data([job(required=["Python", "python", "PYTHON"])], [])
    edge, = of_type(graph, "REQUIRES")
    assert edge["target"] == "skill:python"
    assert edge["source_names"] == ["PYTHON", "Python", "python"]
    assert edge["source_states"] == ["legacy_required"] * 3
    assert edge["has_duplicates"] is True
    skill, = [item for item in graph["nodes"] if item["type"] == "skill"]
    assert skill["job_count"] == 1


def test_all_shared_skill_pairs_including_first_and_twelfth_are_present():
    graph = build_graph_data([job(i, required=["python"]) for i in range(1, 13)], [])
    edges = of_type(graph, "RELATED_TO")
    assert len(edges) == 66
    assert any(e["source"] == "job:j-01" and e["target"] == "job:j-12" for e in edges)
    assert all(e["similar"] == 1 for e in edges)


@pytest.mark.parametrize("shared,total,expected", [(7, 20, True), (6, 20, False), (0, 0, False)])
def test_jaccard_threshold_uses_complete_sets(shared, total, expected):
    common = [f"shared-{i}" for i in range(shared)]
    graph = build_graph_data([job(1, common), job(2, common + [f"extra-{i}" for i in range(total-shared)])], [])
    edges = of_type(graph, "RELATED_TO")
    assert bool(edges) is expected
    if expected:
        assert edges[0]["similar"] == .35


def test_conflicting_historical_requirements_are_not_resolved_by_last_or_strongest():
    graph = build_graph_data([job(required=["Python", "Python"], bonus=["python"])], [])
    edge, = of_type(graph, "REQUIRES")
    assert edge["is_required"] is None
    assert edge["weight"] is None
    assert edge["status_conflict"] is True
    assert edge["needs_review"] is True
    assert list(zip(edge["source_names"], edge["source_states"])) == [
        ("Python", "legacy_required"), ("Python", "legacy_required"), ("python", "legacy_bonus")]
    assert graph["audit"]["requirement_conflicts"] == [{"source": edge["source"], "target": edge["target"]}]


def test_unverified_and_competing_canonical_claims_preserve_distinct_names():
    rows = [job(required=["C++", "cpp", "C#", "unknown-v2", "unknown-v3"])]
    details = [{"jd_id": 1, "skills": [
        {"name": "cpp", "canonical_name": "c++", "is_required": True},
        {"name": "cpp", "canonical_name": "c#", "is_required": False},
        {"name": "unknown-v2", "canonical_name": "unknown"},
        {"name": "unknown-v3", "canonical_name": "unknown"},
    ]}]
    graph = build_graph_data(rows, details)
    assert len(of_type(graph, "REQUIRES")) == 5
    assert len(graph["audit"]["unverified_canonical_claims"]) == 4
    reversed_graph = build_graph_data(rows, [{"jd_id": 1, "skills": list(reversed(details[0]["skills"]))}])
    assert graph["nodes"] == reversed_graph["nodes"]
    assert graph["audit"]["unverified_canonical_claims"] == reversed_graph["audit"]["unverified_canonical_claims"]
    assert [(e["target"], e["is_required"], e["status_conflict"]) for e in of_type(graph, "REQUIRES")] == [
        (e["target"], e["is_required"], e["status_conflict"]) for e in of_type(reversed_graph, "REQUIRES")]


def test_industry_keys_do_not_silently_merge_and_mapping_is_explicit():
    graph = build_graph_data([job(scenarios=["A/B", "A-B", "A B", "A/B"])], [])
    industries = [n for n in graph["nodes"] if n["type"] == "industry"]
    assert len(industries) == 3
    assert len(of_type(graph, "APPLIES_TO")) == 3
    collisions = graph["audit"]["legacy_id_collisions"]
    assert any(item["legacy_id"] == "industry:a-b" and len(item["new_ids"]) == 3 for item in collisions)


def test_duplicate_job_keys_raise_instead_of_silently_overwriting():
    with pytest.raises(ValueError, match="job.*ID"):
        build_graph_data([job(1) | {"m2_job_id": "a_b"},
                          job(2) | {"m2_job_id": "a-b"}], [])


def test_projection_replays_and_does_not_mutate_inputs_or_exchange_bytes():
    path = Path(__file__).resolve().parents[2] / "exchange/m3/graph.json"
    before_bytes = path.read_bytes()
    rows = [job(2, ["C++", "C#"], ["c++"], ["A/B"]), job(1, ["C++"])]
    details = [{"jd_id": 2, "skills": json.dumps([{"name": "C++", "canonical_name": "c++"}])}]
    before = copy.deepcopy((rows, details))
    graph = build_graph_data(rows, details)
    assert graph == build_graph_data(rows, details) == build_graph_data(list(reversed(rows)), details)
    assert (rows, details) == before
    assert path.read_bytes() == before_bytes
    ids = [item["id"] for item in graph["nodes"]]
    assert len(ids) == len(set(ids))
    keys = [(e["source"], e["target"], e["type"]) for e in graph["edges"]]
    assert len(keys) == len(set(keys))
    assert all(s in ids and t in ids for s, t, _ in keys)
    assert len(graph["audit"]["entity_mappings"]) > 0


def test_json_fields_and_list_fields_have_same_projection():
    row = job(required=["C++"], bonus=["C#"], scenarios=["金融"])
    encoded = {key: json.dumps(value) if isinstance(value, list) else value for key, value in row.items()}
    assert build_graph_data([row], []) == build_graph_data([encoded], [])


def test_source_indices_reference_original_fields_including_blank_entries():
    graph = build_graph_data([job(required=["", "Python", " "])], [])
    edge, = of_type(graph, "REQUIRES")
    assert edge["source_fields"] == ["required_skills"]
    assert edge["source_indices"] == [1]


def test_detail_boolean_disagreement_is_preserved_as_legacy_conflict():
    detail = {"name": "python", "canonical_name": "python", "is_required": False, "evidence": "legacy bonus"}
    graph = build_graph_data([job(required=["Python"])], [{"jd_id": 1, "skills": [detail]}])
    edge, = of_type(graph, "REQUIRES")
    assert edge["status_conflict"] is True
    assert edge["is_required"] is None and edge["weight"] is None
    assert edge["source_states"] == ["legacy_required", "legacy_bonus"]
    assert edge["source_fields"] == ["required_skills", "skill_details"]
    assert graph["audit"]["skill_details"][0]["detail"] == detail


def test_detail_provenance_keeps_original_row_and_field_indices_before_sorting():
    details = [{"jd_id": 1, "skills": [
        {"name": "python", "evidence": "zzz", "is_required": False},
        {"name": "java", "evidence": "aaa", "is_required": False},
    ]}, {"jd_id": 1, "skills": [{"name": "python", "is_required": True}]}]
    graph = build_graph_data([job(required=["python", "java"])], details)
    for entry in graph["audit"]["skill_details"]:
        assert entry["detail"] == details[entry["source_row_index"]]["skills"][entry["source_index"]]
    for edge in of_type(graph, "REQUIRES"):
        for name, field, row_index, index in zip(edge["source_names"], edge["source_fields"], edge["source_row_indices"], edge["source_indices"]):
            if field == "skill_details":
                assert details[row_index]["skills"][index]["name"] == name


def test_legacy_mapping_reproduces_job_specific_historical_alias_targets():
    rows = [job(1, ["cpp", "tool"]), job(2, ["tool"])]
    details = [{"jd_id": 1, "skills": [{"name": "cpp", "canonical_name": "c++"},
                                         {"name": "tool", "canonical_name": "python"}]},
               {"jd_id": 2, "skills": [{"name": "tool", "canonical_name": "java"}]}]
    graph = build_graph_data(rows, details)
    mappings = graph["audit"]["entity_mappings"]
    assert any(m["source_name"] == "cpp" and m["legacy_id"] == "skill:c" and m["new_id"] == "skill:cpp" for m in mappings)
    assert {(m["job_id"], m["legacy_id"], m["new_id"]) for m in mappings if m["source_name"] == "tool"} == {
        ("job:j-01", "skill:python", "skill:tool"), ("job:j-02", "skill:java", "skill:tool")}

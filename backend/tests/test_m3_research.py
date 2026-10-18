"""Research safety and mathematical counterexamples; all fixtures are synthetic."""
import hashlib
import json
from pathlib import Path

import pytest


def test_projection_keeps_conflict_null_and_source_indices():
    from app.graph.research.experiment import project_snapshot
    snapshot = {"nodes": [
        {"id": "job:j-1", "type": "job", "name": "one",
         "required_skills": ["", "C++", "Python"], "bonus_skills": ["Python", "C#"]},
    ], "edges": []}
    projection = project_snapshot(snapshot)
    edges = [e for e in projection["edges"] if e["type"] == "REQUIRES"]
    assert {e["target"] for e in edges} == {"skill:c%2B%2B", "skill:c%23", "skill:python"}
    conflict = next(e for e in edges if e["target"] == "skill:python")
    assert conflict["is_required"] is conflict["weight"] is None
    assert conflict["status_conflict"] is True
    assert set(conflict["source_states"]) == {"legacy_required", "legacy_bonus"}
    assert next(e for e in edges if e["target"] == "skill:c%2B%2B")["source_indices"] == [1]


def test_pair_scores_match_all_pairs_and_do_not_invent_requirements():
    from app.graph.research.algorithms import pair_scores
    sets = {"a": {"common", "rare"}, "b": {"common"}, "c": {"other"}, "empty": set()}
    rows = pair_scores(sets)
    assert len(rows) == 1
    row = rows[0]
    assert (row["source"], row["target"], row["jaccard"]) == ("a", "b", .5)
    assert 0 < row["idf_jaccard"] < .5
    assert row["shared"] == ["common"]
    assert "is_required" not in row


def test_paths_exclude_derived_edges_and_return_no_path_honestly():
    from app.graph.research.algorithms import local_path
    graph = {"nodes": [{"id": x, "type": "job" if x in "abc" else "skill"} for x in ["a", "b", "c", "s"]],
             "edges": [{"source": "a", "target": "s", "type": "REQUIRES"},
                       {"source": "b", "target": "s", "type": "REQUIRES"},
                       {"source": "a", "target": "c", "type": "RELATED_TO"}]}
    assert local_path(graph, "a", "b", 2)["node_ids"] == ["a", "s", "b"]
    assert local_path(graph, "a", "c", 3) is None
    assert local_path(graph, "a", "b", 1) is None
    assert local_path(graph, "a", "missing", 3) is None


@pytest.mark.parametrize("method", ["louvain", "leiden"])
def test_communities_cover_isolates_and_repeat_without_fixed_count(method):
    pytest.importorskip("networkx")
    if method == "leiden":
        pytest.importorskip("leidenalg")
    from app.graph.research.algorithms import community_run
    nodes = ["a", "b", "c", "d", "e"]
    edges = [{"source": "a", "target": "b", "score": 1.0}, {"source": "c", "target": "d", "score": 1.0}]
    one = community_run(nodes, edges, method, 1.0, 7)
    two = community_run(list(reversed(nodes)), list(reversed(edges)), method, 1.0, 7)
    assert one == two
    assert sorted(x for group in one["members"] for x in group) == nodes
    assert one["disconnected_communities"] == 0
    assert one["sizes"] == [2, 2, 1]
    empty = community_run(nodes, [], method, 1.0, 7)
    assert empty["modularity"] is None
    assert empty["sizes"] == [1] * 5


def test_ari_is_label_invariant_and_detects_different_partitions():
    from app.graph.research.algorithms import adjusted_rand
    assert adjusted_rand([["a", "b"], ["c", "d"]], [["d", "c"], ["b", "a"]]) == 1.0
    assert adjusted_rand([["a", "b"], ["c", "d"]], [["a", "c"], ["b", "d"]]) == pytest.approx(-.5)


def test_write_artifacts_refuses_existing_or_protected_directory(tmp_path):
    from app.graph.research.experiment import write_artifacts
    target = tmp_path / "new"
    try:
        write_artifacts(target, {"deterministic": {"x": 1}})
        assert json.loads((target / "results.json").read_text(encoding="utf-8"))["deterministic"] == {"x": 1}
        before = (target / "results.json").read_bytes()
        with pytest.raises((ValueError, FileExistsError)):
            write_artifacts(target, {"x": 2})
        assert (target / "results.json").read_bytes() == before
        root = Path(__file__).resolve().parents[2]
        with pytest.raises(ValueError, match="protected"):
            write_artifacts(root / "exchange/m3/new-research", {})
    finally:
        for path in target.glob("*"):
            path.unlink()
        if target.exists():
            target.rmdir()


def test_verified_snapshot_has_expected_hash_and_no_dangling_endpoints():
    from app.graph.research.experiment import read_snapshot
    path = Path(__file__).resolve().parents[2] / "exchange/m3/graph.json"
    before = path.read_bytes()
    snapshot = read_snapshot(path)
    assert len(snapshot["nodes"]) == 7845
    assert len(snapshot["edges"]) == 11412
    # Git stores LF; Windows core.autocrlf gives a different original-byte hash.
    assert hashlib.sha256(before.replace(b"\r\n", b"\n")).hexdigest() == "e8e3fe6aab4ffd359a16c8c62ee8edd4684504266fafe1534d36599cd7af742f"
    assert path.read_bytes() == before


@pytest.mark.parametrize("damage", ["dangling", "duplicate", "wrong_type"])
def test_rejects_invalid_graph_before_algorithms(tmp_path, damage):
    from app.graph.research.experiment import read_snapshot
    node = {"id": "a", "type": "job"}
    graph = {"nodes": [node], "edges": []}
    if damage == "dangling":
        graph["edges"] = [{"source": "a", "target": "missing", "type": "REQUIRES"}]
    elif damage == "duplicate":
        graph["nodes"].append(node)
    else:
        graph["nodes"][0]["type"] = "decorative_particle"
    path = tmp_path / "synthetic.json"
    try:
        path.write_text(json.dumps(graph), encoding="utf-8")
        with pytest.raises(ValueError):
            read_snapshot(path)
    finally:
        path.unlink(missing_ok=True)


def test_candidates_include_first_and_twelfth_and_match_independent_math():
    import math
    from itertools import combinations
    from app.graph.research.algorithms import pair_scores
    sets = {f"j{i:02}": {"common", f"unique{i}", "even" if i % 2 == 0 else "odd"} for i in range(12)}
    rows = pair_scores(sets)
    assert len(rows) == 66
    expected_pairs = set(combinations(sorted(sets), 2))
    assert {(r["source"], r["target"]) for r in rows} == expected_pairs
    for row in rows:
        a, b = sets[row["source"]], sets[row["target"]]
        assert row["jaccard"] == len(a & b) / len(a | b)
        weights = {s: 1 + math.log(13 / (1 + sum(s in v for v in sets.values()))) for s in a | b}
        assert row["idf_jaccard"] == pytest.approx(sum(weights[s] for s in a & b) / sum(weights.values()))


def test_research_import_does_not_load_service_dependencies():
    import subprocess
    import sys
    code = '''
import builtins, sys
original = builtins.__import__
def guarded(name, *args, **kwargs):
    if name.startswith(("app.db", "app.config", "sqlalchemy", "neo4j", "redis")):
        raise AssertionError("service import: " + name)
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
from app.graph.research.experiment import project_snapshot
assert project_snapshot({"nodes": [], "edges": []})["nodes"] == []
'''
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr


def test_missing_algorithm_dependency_fails_without_output(tmp_path):
    import subprocess
    import sys
    output = tmp_path / "must-not-exist"
    code = '''
import builtins, sys
original = builtins.__import__
def guarded(name, *args, **kwargs):
    if name == "networkx":
        raise ModuleNotFoundError("synthetic missing research dependency")
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
from app.graph.research.experiment import main
sys.argv = ["research", "--snapshot", "missing-source.json", "--output", sys.argv[1]]
main()
'''
    result = subprocess.run([sys.executable, "-c", code, str(output)], capture_output=True, text=True, timeout=30)
    assert result.returncode != 0
    assert "synthetic missing research dependency" in result.stderr
    assert not output.exists()


def test_empty_snapshot_and_missing_source_are_honest_cli_results(tmp_path):
    pytest.importorskip("networkx")
    pytest.importorskip("leidenalg")
    import subprocess
    import sys
    source = tmp_path / "synthetic-empty.json"
    output = tmp_path / "new-result"
    crlf_output = tmp_path / "crlf-result"
    command = [sys.executable, "-X", "utf8", "-m", "app.graph.research", "--snapshot", str(source), "--output", str(output)]
    try:
        missing = subprocess.run(command, capture_output=True, text=True, timeout=30)
        assert missing.returncode != 0
        assert "FileNotFoundError" in missing.stderr
        assert not output.exists()
        source.write_bytes(b'{"nodes": [], "edges": []}\n')
        empty = subprocess.run(command, capture_output=True, text=True, timeout=30)
        assert empty.returncode == 0, empty.stderr
        full_result = json.loads((output / "results.json").read_text(encoding="utf-8"))
        result = full_result["deterministic"]
        from app.graph.research.experiment import digest
        assert digest(result) == full_result["deterministic_sha256"]
        assert all(digest(g) == sha for sha, g in result["community_members"].items())
        assert all(digest([result["community_members"][g] for g in refs]) == sha for sha, refs in result["partitions"].items())
        assert result["candidate_pairs"] == 0
        assert result["partitions"]
        assert all(r["modularity"] is None and r["sizes"] == [] for r in result["community_runs"])
        source.write_bytes(source.read_bytes().replace(b"\n", b"\r\n"))
        crlf = subprocess.run(command[:-1] + [str(crlf_output)], capture_output=True, text=True, timeout=30)
        assert crlf.returncode == 0, crlf.stderr
        other = json.loads((crlf_output / "results.json").read_text(encoding="utf-8"))
        assert full_result["deterministic_sha256"] != other["deterministic_sha256"]
        assert full_result["portable_lf_sha256"] == other["portable_lf_sha256"]
    finally:
        source.unlink(missing_ok=True)
        for folder in (output, crlf_output):
            (folder / "results.json").unlink(missing_ok=True)
            if folder.exists():
                folder.rmdir()


def test_structural_counts_and_digest_survive_json_roundtrip():
    from app.graph.research.algorithms import structural_summary
    from app.graph.research.experiment import digest
    graph = {"nodes": [{"id": "j", "type": "job"}, {"id": "s", "type": "skill"}],
             "edges": [{"source": "j", "target": "s", "type": "REQUIRES"}]}
    summary = structural_summary(graph)
    assert summary["skill_degree_histogram"] == {"1": 1}
    assert summary == json.loads(json.dumps(summary))
    assert digest(summary) == digest(json.loads(json.dumps(summary)))

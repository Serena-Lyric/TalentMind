"""M3 图谱模块测试：graph.json 契约校验（D26/D31）。

注意：测试输出写入临时目录（monkeypatch OUTPUT_PATH），避免覆盖正式 exchange/m3/graph.json。
"""
import json

import pytest

from app.graph import builder

# 使用 mock 数据源（M2 产出为旧版未约束技能，无法通过归一校验；mock 回退用于测试）
builder.DATA_SOURCE_PRIORITY = ["mock"]


@pytest.fixture(autouse=True)
def _tmp_output(tmp_path, monkeypatch):
    """所有测试的 graph.json 输出重定向到临时目录，防止污染正式产出。"""
    monkeypatch.setattr(builder, "OUTPUT_PATH", tmp_path / "graph.json")


def _load_graph():
    with open(builder.OUTPUT_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def test_build_graph_success():
    result = builder.build_graph()
    assert result["code"] == 0  # D29 统一响应
    assert result["data"]["node_count"] > 0
    assert result["data"]["edge_count"] > 0


def test_graph_structure():
    builder.build_graph()
    data = _load_graph()
    assert {"nodes", "edges", "metadata"} <= set(data.keys())
    assert data["nodes"] and data["edges"]


def test_job_node_id_aligns_job_name():
    """D26：job 节点 id 对齐 job_name，不再用序号。"""
    builder.build_graph()
    data = _load_graph()
    for node in data["nodes"]:
        if node["type"] == "job":
            assert node["id"] == node["name"], node


def test_skill_node_id_is_canonical_and_unique():
    """D26/D31：skill 节点 id 为 canonical 且去重。"""
    builder.build_graph()
    data = _load_graph()
    skill_ids = [n["id"] for n in data["nodes"] if n["type"] == "skill"]
    assert len(skill_ids) == len(set(skill_ids))
    for sid in skill_ids:
        assert sid == sid.lower(), f"skill id 非 canonical: {sid!r}"


def test_edge_types():
    builder.build_graph()
    data = _load_graph()
    types = {e["type"] for e in data["edges"]}
    assert types <= {"REQUIRES", "RELATED_TO"}, types


def test_exported_at_dynamic():
    builder.build_graph()
    data = _load_graph()
    assert data["metadata"]["exported_at"] != "2026-08-03T10:00:00"
    assert "T" in data["metadata"]["exported_at"]


def test_normalize_skills_skips_unknown():
    jobs = [
        {"job_name": "测试岗", "required_skills": ["Python", "cobol"],
         "bonus_skills": ["k8s"]},
    ]
    out = builder._normalize_skills(jobs)
    assert out[0]["required_skills"] == ["python"]
    assert out[0]["bonus_skills"] == ["kubernetes"]
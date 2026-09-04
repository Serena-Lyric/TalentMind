# -*- coding: utf-8 -*-
"""学习路径生成纯函数单测（D37：不写库；不依赖 DB/网络）。2026-09-04：分层路径（基础→核心→专项→加分）。"""
from app.routers.learning import build_learning_path, _phase_for

JOB = dict(job_id="1", job_title="后端工程师", job_name_en="Backend Engineer", category="现有")


def _build(required=(), bonus=(), resume=(), evidence=None):
    return build_learning_path(**JOB, required=list(required), bonus=list(bonus),
                               resume_skills=list(resume), evidence_map=evidence or {})


def _names(stage):
    return [s["name"] for s in stage["skills"]]


def test_layered_path_base_core_bonus():
    data = _build(
        required=["python", "shell", "linux", "mysql", "docker"],
        bonus=["kubernetes"],
        resume=["Python"],
        evidence={"docker": "JD #1: 负责容器化部署"},
    )
    assert data["overview"]["missing_required"] == 4
    assert data["overview"]["missing_bonus"] == 1
    assert [s["phase"] for s in data["stages"]] == ["base", "core", "bonus"]
    assert [s["title"] for s in data["stages"]] == ["基础与工具", "核心框架与平台", "加分拓展"]
    assert _names(data["stages"][0]) == ["shell", "linux", "mysql"]  # 基础工具/数据库
    assert _names(data["stages"][1]) == ["docker"]                    # 平台/容器
    assert _names(data["stages"][2]) == ["kubernetes"]                # 加分
    assert data["mastered_skills"] == ["python"]
    # 缺口技能仍带建议与证据
    docker = [s for s in data["missing_skills"] if s["name"] == "docker"][0]
    assert "岗位依据" in docker["suggestion"]
    assert docker["evidence"].startswith("JD #1")


def test_unknown_required_goes_advanced():
    data = _build(required=["系统集成部署运维", "python"], bonus=[], resume=[])
    assert [s["phase"] for s in data["stages"]] == ["base", "advanced"]
    assert _names(data["stages"][0]) == ["python"]
    assert _names(data["stages"][1]) == ["系统集成部署运维"]
    assert data["stages"][1]["skills"][0]["category"] == "其他"


def test_phase_for_mapping():
    cases = [
        ({"name": "python", "category": "编程语言", "priority": "high"}, "base"),
        ({"name": "mysql", "category": "数据库", "priority": "high"}, "base"),
        ({"name": "linux", "category": "DevOps/运维", "priority": "high"}, "base"),   # 通用工具
        ({"name": "docker", "category": "DevOps/运维", "priority": "high"}, "core"),
        ({"name": "spring boot", "category": "后端框架", "priority": "high"}, "core"),
        ({"name": "tensorflow", "category": "AI/机器学习", "priority": "high"}, "advanced"),
        ({"name": "知识图谱", "category": "专业领域", "priority": "high"}, "advanced"),
        ({"name": "需求分析", "category": "其他", "priority": "high"}, "advanced"),
        ({"name": "kubernetes", "category": "DevOps/运维", "priority": "medium"}, "bonus"),
    ]
    for item, expected in cases:
        assert _phase_for(item) == expected, (item, _phase_for(item))


def test_at_standard_when_no_gap():
    data = _build(required=["python"], bonus=["docker"], resume=["Python", "docker"])
    assert data["overview"]["at_standard"] is True
    assert data["stages"] == []
    assert data["missing_skills"] == []
    assert data["mastered_skills"] == ["python", "docker"]


def test_core_bonus_skill_rows_keep_contract():
    data = _build(required=["python", "docker"], bonus=["kubernetes"], resume=["docker"])
    assert [s["name"] for s in data["core_skills"]] == ["python", "docker"]
    assert data["core_skills"][0]["status"] == "not_started"
    assert data["core_skills"][1]["status"] == "completed"
    assert data["bonus_skills"][0]["priority"] == "medium"
    assert data["source"].startswith("job_definition")
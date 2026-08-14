"""exchange 交接文件 schema 校验测试（2026-08-14）。

覆盖：结构校验、snake_case、坏样例拦截、M2/M3 现有产出可校验（软警告不阻断）。
"""
import json
from pathlib import Path

import pytest

from app.integration.validate_exchange import (
    SKILL_DICT_PATH,
    validate_exchange,
    validate_m2,
    validate_m3,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_m2_job_definition_structure_ok():
    r = validate_exchange(REPO_ROOT / "exchange" / "m2" / "job_definition.json", "job_definition")
    assert r["ok"] is True, r["errors"]


def test_m2_job_skill_structure_ok():
    r = validate_exchange(REPO_ROOT / "exchange" / "m2" / "job_skill.json", "job_skill")
    assert r["ok"] is True, r["errors"]


def test_m3_graph_ok():
    r = validate_m3()
    assert r["ok"] is True, r["errors"]


def test_skill_dict_seed_ok():
    r = validate_exchange(SKILL_DICT_PATH, "skill_dict")
    assert r["ok"] is True, r["errors"]


def test_missing_required_field_rejected(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps([{"core_duties": "x"}]), encoding="utf-8")
    r = validate_exchange(bad, "job_definition")
    assert r["ok"] is False
    assert any("job_name" in e for e in r["errors"])


def test_camel_case_field_rejected(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps([{"job_name": "A", "coreDuties": "x"}]), encoding="utf-8")
    r = validate_exchange(bad, "job_definition")
    assert r["ok"] is False
    assert any("snake_case" in e for e in r["errors"])


def test_m2_validate_all_reports_warnings_not_blocking():
    r = validate_m2()
    # 结构全部通过；关联/技能对齐以警告呈现（等 M2 二次开发修复后转硬校验）
    assert r["job_definition.json"]["ok"] is True
    assert r["job_skill.json"]["ok"] is True
    assert r["job_change_log.json"]["ok"] is True
    assert r["skill_dict_seed.json"]["ok"] is True

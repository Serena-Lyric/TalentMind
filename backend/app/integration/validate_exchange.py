"""M2/M3 交接文件校验器。"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field, ValidationError

from app.integration.m2_package import DEFAULT_PACKAGE_DIR, load_return_package, unwrap_payload

REPO_ROOT = Path(__file__).resolve().parents[3]
EXCHANGE_M2 = REPO_ROOT / "exchange" / "m2"
EXCHANGE_M3 = REPO_ROOT / "exchange" / "m3"
SKILL_DICT_PATH = REPO_ROOT / "backend" / "app" / "skills" / "skill_dict_seed.json"
SNAKE_RE = re.compile(r"^[a-z][a-z0-9_]*$")


class SkillEntryModel(BaseModel):
    skill_id: Optional[str] = None
    name: str
    weight: Optional[float] = None
    confidence: Optional[float] = None
    evidence: Optional[str] = None
    evidence_jd_count: Optional[int] = None
    is_required: Optional[bool] = None
    canonical_name: Optional[str] = None
    verification: Optional[str] = None


class JobDefinitionModel(BaseModel):
    job_name: str = Field(min_length=1)
    core_duties: str = ""
    required_skills: list = Field(default_factory=list)
    bonus_skills: list = Field(default_factory=list)
    scenarios: list = Field(default_factory=list)
    source: list = Field(default_factory=list)
    quality: Optional[float] = None
    is_emerging: Optional[bool] = None
    evolution: Optional[dict] = None
    first_seen: Optional[str] = None
    collected_at: Optional[str] = None
    updated_at: Optional[str] = None
    job_name_zh: Optional[str] = None
    source_jd_count: Optional[int] = None
    job_id: Optional[str] = None
    name_en: Optional[str] = None
    category: Optional[str] = None
    category_review: Optional[str] = None


class JobSkillFileModel(BaseModel):
    job_name: str = Field(min_length=1)
    skills: list[SkillEntryModel] = Field(default_factory=list)
    job_id: Optional[str] = None


CHANGE_TYPES = {
    "added", "removed", "modified", "duties_changed", "scenarios_added",
    "scenarios_removed", "evolution_changed",
}


class JobChangeLogModel(BaseModel):
    job_id: str
    change_type: str
    skill_name: str = ""
    detail: Optional[dict] = None
    source: Optional[list] = None
    reason: Optional[str] = None
    created_at: Optional[str] = None
    object_type: Optional[str] = None
    source_jd_time: Optional[str] = None


class GraphNodeModel(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    type: str
    size: Optional[float] = None
    color: Optional[str] = None
    status: Optional[str] = None
    jobs: Optional[int] = None
    industry: Optional[str] = None
    is_emerging: Optional[bool] = None


class GraphEdgeModel(BaseModel):
    source: str
    target: str
    type: str
    weight: Optional[float] = None
    is_required: Optional[bool] = None
    similar: Optional[float] = None


class GraphFileModel(BaseModel):
    nodes: list[GraphNodeModel] = Field(default_factory=list)
    edges: list[GraphEdgeModel] = Field(default_factory=list)


class SkillDictModel(BaseModel):
    canonical: str = Field(min_length=1)
    aliases: list = Field(default_factory=list)
    category: str = ""


class JdRecordModel(BaseModel):
    id: Optional[int] = None
    source: Optional[str] = None
    job_title: str = Field(min_length=1)
    raw_text: Optional[str] = None
    duties: Optional[str] = None
    experience: Optional[str] = None
    quality: Optional[float] = None
    dup_group: Optional[str] = None
    crawled_at: Optional[str] = None
    status: Optional[str] = None


MODEL_BY_KIND = {
    "job_definition": JobDefinitionModel,
    "job_skill": JobSkillFileModel,
    "job_change_log": JobChangeLogModel,
    "graph": GraphFileModel,
    "skill_dict": SkillDictModel,
    "jd": JdRecordModel,
}


def _load(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _items(value: Any) -> list:
    if isinstance(value, list):
        return value
    if isinstance(value, dict) and isinstance(value.get("items"), list):
        return value["items"]
    return []


def _check_snake_case(obj: Any, errors: list[str], prefix: str = "") -> None:
    if isinstance(obj, dict):
        for key, value in obj.items():
            if not SNAKE_RE.match(key):
                errors.append(f"{prefix}.{key}: 字段名不是 snake_case")
            _check_snake_case(value, errors, f"{prefix}.{key}" if prefix else key)
    elif isinstance(obj, list):
        for index, item in enumerate(obj):
            _check_snake_case(item, errors, f"{prefix}[{index}]")


def _load_skill_canonicals() -> set[str]:
    try:
        return {str(item["canonical"]).strip().lower() for item in _load(SKILL_DICT_PATH)}
    except Exception:
        return set()


def validate_exchange(path: Path, kind: str) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    model = MODEL_BY_KIND.get(kind)
    if model is None:
        return {"ok": False, "errors": [f"未知文件类型: {kind}"], "warnings": []}
    if not path.exists():
        return {"ok": False, "errors": [f"文件不存在: {path}"], "warnings": []}
    try:
        data = _load(path)
    except Exception as exc:
        return {"ok": False, "errors": [f"JSON 解析失败: {exc}"], "warnings": []}

    _check_snake_case(data, errors)
    try:
        if kind == "graph":
            model.model_validate(data)
            items = data
        else:
            items, _ = unwrap_payload(data)
            for index, item in enumerate(items):
                try:
                    model.model_validate(item)
                except ValidationError as exc:
                    for error in exc.errors():
                        loc = ".".join(str(part) for part in error["loc"])
                        errors.append(f"[{index}] {loc}: {error['msg']}")
    except Exception as exc:
        errors.append(f"结构校验异常: {exc}")

    if kind == "job_change_log":
        for index, item in enumerate(_items(data)):
            if item.get("change_type") not in CHANGE_TYPES:
                errors.append(f"[{index}] change_type 不在枚举内: {item.get('change_type')!r}")

    if kind in ("job_definition", "job_skill"):
        canonicals = _load_skill_canonicals()
        for index, item in enumerate(_items(data)):
            values = item.get("required_skills", []) + item.get("bonus_skills", []) if kind == "job_definition" else [skill.get("canonical_name") or skill.get("name") for skill in item.get("skills", [])]
            for value in values:
                if isinstance(value, str) and value.strip().lower() not in canonicals:
                    warnings.append(f"[{index}] 技能不在 skill_dict: {value}")
    return {"ok": not errors, "errors": errors, "warnings": warnings}


def validate_return_package(package_dir: Path | str | None = None) -> dict:
    try:
        package = load_return_package(package_dir or DEFAULT_PACKAGE_DIR)
    except Exception as exc:
        return {"ok": False, "errors": [str(exc)], "warnings": []}
    defs = package["definitions"]
    skills = package["skills"]
    logs = package["change_logs"]
    def_ids = {str(item.get("job_id")) for item in defs}
    skill_ids = {str(item.get("job_id")) for item in skills}
    warnings = []
    if len(defs) != 719:
        warnings.append(f"岗位定义数量为 {len(defs)}，本次预期 719")
    if def_ids != skill_ids:
        warnings.append(f"岗位/技能 job_id 集合不一致: missing={len(def_ids-skill_ids)}, extra={len(skill_ids-def_ids)}")
    return {"ok": True, "errors": [], "warnings": warnings, "summary": {
        "definitions": len(defs), "skill_records": len(skills), "change_logs": len(logs),
        "unique_definition_ids": len(def_ids), "skill_job_ids": len(skill_ids),
    }}


def validate_m2() -> dict:
    result = {}
    warnings: list[str] = []
    for name, kind in (("job_definition.json", "job_definition"), ("job_skill.json", "job_skill"), ("job_change_log.json", "job_change_log")):
        check = validate_exchange(EXCHANGE_M2 / name, kind)
        result[name] = check
        warnings.extend(check["warnings"])
    defs = _items(_load(EXCHANGE_M2 / "job_definition.json")) if (EXCHANGE_M2 / "job_definition.json").exists() else []
    skills = _items(_load(EXCHANGE_M2 / "job_skill.json")) if (EXCHANGE_M2 / "job_skill.json").exists() else []
    names = {str(item.get("job_name", "")).strip().lower() for item in defs}
    mismatch = [item.get("job_name") for item in skills if str(item.get("job_name", "")).strip().lower() not in names]
    if mismatch:
        warnings.append(f"job_skill 有 {len(mismatch)} 条 job_name 不在 job_definition 中: {mismatch[:3]}")
    result["_关联检查"] = {"ok": True, "errors": [], "warnings": warnings}
    result["skill_dict_seed.json"] = validate_exchange(SKILL_DICT_PATH, "skill_dict")
    return result


def validate_m3() -> dict:
    return validate_exchange(EXCHANGE_M3 / "graph.json", "graph")


if __name__ == "__main__":
    print(json.dumps(validate_m2(), ensure_ascii=False, indent=2)[:2000])

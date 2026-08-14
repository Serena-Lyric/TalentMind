"""exchange 交接文件校验器（A 集成层，2026-08-14）。

职责：回包/导入前对 exchange/*.json 做机读校验。
- 结构校验：用 pydantic 模型（复用已装依赖，不引 jsonschema）检查字段/类型/必填；
- 命名校验：字段名必须 snake_case；
- 软校验（警告不阻断）：job_skill.job_name 与 job_definition.job_name 关联、
  技能名对齐 skill_dict_seed（当前 M2 旧产出已知不满足，等 M2 二次开发修复后转硬校验）。
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field, ValidationError

REPO_ROOT = Path(__file__).resolve().parents[3]
EXCHANGE_M2 = REPO_ROOT / "exchange" / "m2"
EXCHANGE_M3 = REPO_ROOT / "exchange" / "m3"
SKILL_DICT_PATH = REPO_ROOT / "backend" / "app" / "skills" / "skill_dict_seed.json"

SNAKE_RE = re.compile(r"^[a-z][a-z0-9_]*$")


# ── pydantic 结构模型（与 DDL / 08-03 设计 §6/§7/§8 对齐） ──

class SkillEntryModel(BaseModel):
    skill_id: Optional[str] = None
    name: str
    weight: Optional[float] = None
    confidence: Optional[float] = None
    evidence: Optional[str] = None
    evidence_jd_count: Optional[int] = None
    is_required: Optional[bool] = None


class JobDefinitionModel(BaseModel):
    job_name: str = Field(min_length=1)
    core_duties: str = ""
    required_skills: list = []
    bonus_skills: list = []
    scenarios: list = []
    source: list = []
    quality: Optional[float] = None
    is_emerging: Optional[bool] = None
    evolution: Optional[dict] = None
    first_seen: Optional[str] = None
    collected_at: Optional[str] = None
    updated_at: Optional[str] = None
    # 2026-08-14 中英文统一：新增展示字段（允许缺失，等 M2 补齐）
    job_name_zh: Optional[str] = None
    # M2 现有额外字段（加字段自由，允许）
    source_jd_count: Optional[int] = None


class JobSkillFileModel(BaseModel):
    job_name: str = Field(min_length=1)
    skills: list[SkillEntryModel] = []


CHANGE_TYPES = {
    "added", "removed", "modified",
    "duties_changed", "scenarios_added", "scenarios_removed", "evolution_changed",
}


class JobChangeLogModel(BaseModel):
    job_id: str
    change_type: str
    skill_name: str = ""
    detail: Optional[dict] = None
    source: Optional[list] = None
    reason: Optional[str] = None
    created_at: Optional[str] = None


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
    nodes: list[GraphNodeModel] = []
    edges: list[GraphEdgeModel] = []


class SkillDictModel(BaseModel):
    canonical: str = Field(min_length=1)
    aliases: list = []
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


# 文件类型 → 单条模型（列表校验）
MODEL_BY_KIND = {
    "job_definition": JobDefinitionModel,
    "job_skill": JobSkillFileModel,
    "job_change_log": JobChangeLogModel,
    "graph": GraphFileModel,
    "skill_dict": SkillDictModel,
    "jd": JdRecordModel,
}


def _load(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _check_snake_case(obj, errors: list, prefix: str = ""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if not SNAKE_RE.match(k):
                errors.append(f"{prefix}.{k}: 字段名不是 snake_case")
            _check_snake_case(v, errors, f"{prefix}.{k}" if prefix else k)
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            _check_snake_case(item, errors, f"{prefix}[{i}]")


def _load_skill_canonicals() -> set[str]:
    try:
        entries = json.loads(SKILL_DICT_PATH.read_text(encoding="utf-8"))
        return {e["canonical"].strip().lower() for e in entries}
    except Exception:
        return set()


def validate_exchange(path: Path, kind: str) -> dict:
    """校验单个交接文件。返回 {ok, errors, warnings}。"""
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

    # 结构校验
    try:
        if kind == "graph":
            GraphFileModel.model_validate(data)
        elif isinstance(data, list):
            for i, item in enumerate(data):
                try:
                    model.model_validate(item)
                except ValidationError as exc:
                    for e in exc.errors():
                        loc = ".".join(str(x) for x in e["loc"])
                        errors.append(f"[{i}] {loc}: {e['msg']}")
        else:
            errors.append("顶层必须是 JSON 数组（graph 除外）")
    except Exception as exc:
        errors.append(f"结构校验异常: {exc}")

    # change_type 枚举硬校验（D32 扩展枚举）
    if kind == "job_change_log" and isinstance(data, list):
        for i, item in enumerate(data):
            ct = item.get("change_type") if isinstance(item, dict) else None
            if ct not in CHANGE_TYPES:
                errors.append(f"[{i}] change_type 不在枚举内: {ct!r}")

    # 软校验：技能 canonical 对齐（不阻断，输出警告）
    if kind in ("job_definition", "job_skill"):
        canonicals = _load_skill_canonicals()
        if canonicals:
            if kind == "job_definition":
                for i, d in enumerate(data or []):
                    for f in ("required_skills", "bonus_skills"):
                        for s in d.get(f, []):
                            if isinstance(s, str) and s.strip().lower() not in canonicals:
                                warnings.append(f"[{i}] 技能不在 skill_dict: {s}")
            else:
                for i, d in enumerate(data or []):
                    for s in d.get("skills", []):
                        name = s.get("name") if isinstance(s, dict) else s
                        if isinstance(name, str) and name.strip().lower() not in canonicals:
                            warnings.append(f"[{i}] 技能不在 skill_dict: {name}")

    return {"ok": not errors, "errors": errors, "warnings": warnings}


def validate_m2() -> dict:
    """校验 exchange/m2 全部产出 + 关联软校验。"""
    result = {}
    warnings_extra: list[str] = []
    # skill_dict 权威文件是 backend/app/skills/skill_dict_seed.json（D31），
    # exchange/m2 不要求单独交付 skill_dict.json（可选，若存在也校验）
    for name, kind in [
        ("job_definition.json", "job_definition"),
        ("job_skill.json", "job_skill"),
        ("job_change_log.json", "job_change_log"),
    ]:
        path = EXCHANGE_M2 / name
        r = validate_exchange(path, kind)
        result[name] = r
        warnings_extra.extend(r["warnings"])

    # 关联软校验：job_skill.job_name ⊆ job_definition.job_name（当前已知 0/22，等 M2 修复）
    defs = _load(EXCHANGE_M2 / "job_definition.json") if (EXCHANGE_M2 / "job_definition.json").exists() else []
    skills = _load(EXCHANGE_M2 / "job_skill.json") if (EXCHANGE_M2 / "job_skill.json").exists() else []
    en_names = {d.get("job_name", "").strip().lower() for d in defs}
    mismatch = [s.get("job_name") for s in skills if s.get("job_name", "").strip().lower() not in en_names]
    if mismatch:
        warnings_extra.append(
            f"job_skill 有 {len(mismatch)} 条 job_name 不在 job_definition 中（中英文分裂，待 M2 修复 L1-L3）: {mismatch[:3]}"
        )
    result["_关联检查"] = {"ok": True, "errors": [], "warnings": warnings_extra}
    # 版本头软提示（M2 P0：schema_version/contract_version/generated_at）
    version_hint = []
    for name in ("job_definition.json", "job_skill.json", "job_change_log.json"):
        fpath = EXCHANGE_M2 / name
        if fpath.exists():
            try:
                head = json.loads(fpath.read_text(encoding="utf-8"))
                if isinstance(head, list) and head:
                    first = head[0] if isinstance(head[0], dict) else {}
                    if not any(k in first for k in ("schema_version", "contract_version", "generated_at")):
                        version_hint.append(f"{name} 未带版本头（M2 P0 要求）")
            except Exception:
                pass
    if version_hint:
        result["_版本头"] = {"ok": True, "errors": [], "warnings": version_hint}
    # skill_dict 种子自校验
    result["skill_dict_seed.json"] = validate_exchange(SKILL_DICT_PATH, "skill_dict")
    return result


def validate_m3() -> dict:
    """校验 exchange/m3/graph.json。"""
    return validate_exchange(EXCHANGE_M3 / "graph.json", "graph")


if __name__ == "__main__":
    import json as _json
    print(_json.dumps(validate_m2(), ensure_ascii=False, indent=2)[:2000])

"""M2 返回包加载与一致性检查。

本模块只读取回包，不修改 input/ 原始资产；运行导入由 import_exchange 负责。
兼容旧数组根节点和 2026-09-01 起使用的 {items, ...} 包装格式。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PACKAGE_DIR = REPO_ROOT / "input" / "岗位数据-新一代与现有"


def unwrap_payload(value: Any) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)], {}
    if isinstance(value, dict) and isinstance(value.get("items"), list):
        metadata = {key: value[key] for key in value if key != "items"}
        return [item for item in value["items"] if isinstance(item, dict)], metadata
    raise ValueError("M2 文件顶层必须是数组或包含 items 数组的对象")


def load_json_items(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        return unwrap_payload(json.load(handle))


def _required_path(package_dir: Path, *relative: str) -> Path:
    path = package_dir.joinpath(*relative)
    if not path.exists():
        raise FileNotFoundError(f"M2 回包缺少文件: {path}")
    return path


def _detect_layout(root: Path) -> str | None:
    """识别回包目录布局：
    - legacy：input/岗位数据-新一代与现有 布局（新一代/现有分文件）
    - standard：exchange/m2 标准交接布局（job_definition.json / job_skill.json / job_change_log.json）
    """
    if all((root / name).exists() for name in ("新一代岗位_定义.json", "现有岗位_定义.json")):
        return "legacy"
    if (root / "job_definition.json").exists():
        return "standard"
    return None


def load_return_package(package_dir: Path | str | None = None) -> dict[str, Any]:
    root = Path(package_dir or DEFAULT_PACKAGE_DIR)
    layout = _detect_layout(root)
    if layout is None:
        raise FileNotFoundError(
            f"M2 回包目录未识别：{root}（需要 legacy 布局或 standard 布局 job_definition.json）"
        )
    defs: list[dict[str, Any]] = []
    skills: list[dict[str, Any]] = []
    metadata: dict[str, Any] = {}
    if layout == "legacy":
        definition_files = [
            _required_path(root, "新一代岗位_定义.json"),
            _required_path(root, "现有岗位_定义.json"),
        ]
        skill_files = [
            _required_path(root, "新一代岗位_技能.json"),
            _required_path(root, "现有岗位_技能.json"),
        ]
        for path in definition_files:
            items, head = load_json_items(path)
            defs.extend(items)
            metadata[path.name] = head
        for path in skill_files:
            items, head = load_json_items(path)
            skills.extend(items)
            metadata[path.name] = head
        logs, log_metadata = load_json_items(_required_path(root, "现有岗位_能力更新日志.json"))
        metadata["现有岗位_能力更新日志.json"] = log_metadata
    else:  # standard（exchange/m2 标准交接布局）
        defs, head_def = load_json_items(_required_path(root, "job_definition.json"))
        metadata["job_definition.json"] = head_def
        skills, head_skill = load_json_items(_required_path(root, "job_skill.json"))
        metadata["job_skill.json"] = head_skill
        logs, head_log = load_json_items(_required_path(root, "job_change_log.json"))
        metadata["job_change_log.json"] = head_log

    def_ids = {str(item.get("job_id", "")) for item in defs if item.get("job_id")}
    skill_ids = {str(item.get("job_id", "")) for item in skills if item.get("job_id")}
    missing_skill_ids = sorted(skill_ids - def_ids)
    if missing_skill_ids:
        raise ValueError(f"M2 技能记录关联不到岗位定义: {missing_skill_ids[:5]}")
    if len(def_ids) != len(defs):
        raise ValueError("M2 岗位定义 job_id 不唯一")
    if not defs:
        raise ValueError("M2 岗位定义为空")
    return {
        "package_dir": root,
        "definitions": defs,
        "skills": skills,
        "change_logs": logs,
        "metadata": metadata,
    }


def package_summary(package: dict[str, Any]) -> dict[str, Any]:
    defs = package["definitions"]
    skills = package["skills"]
    logs = package["change_logs"]
    def_ids = {str(item.get("job_id")) for item in defs}
    skill_ids = {str(item.get("job_id")) for item in skills}
    return {
        "package_dir": str(package["package_dir"]),
        "definitions": len(defs),
        "unique_definition_ids": len(def_ids),
        "skill_records": len(skills),
        "skill_job_ids": len(skill_ids),
        "change_logs": len(logs),
        "categories": {
            str(category): sum(1 for item in defs if item.get("category") == category)
            for category in sorted({item.get("category") for item in defs})
        },
        "sources": sorted({str(source) for item in defs for source in item.get("source", [])}),
    }

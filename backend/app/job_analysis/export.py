"""导出层 —— 写入最终 JSON 交付物 + 管道报告。"""
import json
from datetime import datetime, timezone
from pathlib import Path
from .models import (
    MergedJobDefinition, MergedJobSkillDetail, JobChangeLog,
    RejectedItem, PipelineStats, CostInfo,
)


def _write_json(output_dir: Path, filename: str, data: list):
    """安全写入 JSON 数组文件。"""
    path = output_dir / filename
    payload = {
        "schema_version": "1.0", "contract_version": "2026-08-31",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
        "module": "m2",
        "items": [item.model_dump() if hasattr(item, "model_dump") else item for item in data],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def _load_json(path: Path) -> list | None:
    """安全加载 JSON 文件，文件不存在或损坏返回 None。"""
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and isinstance(data.get("items"), list):
            return data["items"]
        return data if isinstance(data, list) else None
    except (json.JSONDecodeError, OSError):
        return None


def _is_valid_checkpoint(path: Path) -> bool:
    """检查中间文件是否存在且为有效 JSON 数组。"""
    data = _load_json(path)
    return data is not None and isinstance(data, list)


def export_all(
    job_defs: list[MergedJobDefinition],
    job_skills: list[MergedJobSkillDetail],
    change_logs: list[JobChangeLog],
    rejected: list[RejectedItem],
    manual: list[dict],
    output_dir: Path,
    accuracy: float | None = None,
    cost: dict | None = None,
    hallucination_control: dict | None = None,
    stage_counts: dict | None = None,
) -> PipelineStats:
    """导出所有交付物，返回统计信息。"""
    output_dir.mkdir(parents=True, exist_ok=True)

    _write_json(output_dir, "job_definition.json", job_defs)
    _write_json(output_dir, "job_skill.json", job_skills)
    _write_json(output_dir, "job_change_log.json", change_logs)
    _write_json(output_dir, "rejected.json", rejected)
    _write_json(output_dir, "manual_review.json", manual)

    cost_info = CostInfo(**(cost or {}))
    sc = stage_counts or {}

    # 统计各阶段数量
    stats = PipelineStats(
        total=len(job_defs) + len(rejected) + len(manual),
        rules_rejected=sum(
            1 for r in rejected
            if r.rule_id in ("empty_fields", "garbled", "duplicate")),
        stage1_passed=sc.get("stage1_passed", 0),
        stage1_rejected=sc.get("stage1_rejected", 0),
        stage1_manual=sc.get("stage1_manual", 0),
        stage2_passed=sc.get("stage2_passed", 0),
        stage2_rejected=sc.get("stage2_rejected", 0),
        stage2_manual=sc.get("stage2_manual", 0),
        stage3_passed=sc.get("stage3_passed", 0),
        stage3_manual=sc.get("stage3_manual", 0),
        final_job_definitions=len(job_defs),
        change_logs=len(change_logs),
        accuracy=accuracy,
        cost=cost_info,
        hallucination_control=hallucination_control or {},
    )
    _write_json(output_dir, "pipeline_report.json", [stats])
    return stats

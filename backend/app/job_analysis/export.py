"""导出层 —— 写入最终 JSON 交付物 + 管道报告。"""
import json
from pathlib import Path
from app.job_analysis.models import (
    MergedJobDefinition, MergedJobSkillDetail, JobChangeLog,
    RejectedItem, PipelineStats, CostInfo,
)


def _write_json(output_dir: Path, filename: str, data: list):
    """安全写入 JSON 数组文件。"""
    path = output_dir / filename
    with open(path, "w", encoding="utf-8") as f:
        json.dump(
            [item.model_dump() if hasattr(item, "model_dump") else item
             for item in data],
            f, ensure_ascii=False, indent=2,
        )


def _load_json(path: Path) -> list | None:
    """安全加载 JSON 文件，文件不存在或损坏返回 None。"""
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
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
) -> PipelineStats:
    """导出所有交付物，返回统计信息。"""
    output_dir.mkdir(parents=True, exist_ok=True)

    _write_json(output_dir, "job_definition.json", job_defs)
    _write_json(output_dir, "job_skill.json", job_skills)
    _write_json(output_dir, "job_change_log.json", change_logs)
    _write_json(output_dir, "rejected.json", rejected)
    _write_json(output_dir, "manual_review.json", manual)

    cost_info = CostInfo(**(cost or {}))

    # 统计各阶段数量
    stats = PipelineStats(
        total=len(job_defs) + len(rejected) + len(manual),
        rules_rejected=sum(
            1 for r in rejected
            if r.rule_id in ("empty_fields", "garbled", "duplicate")),
        final_job_definitions=len(job_defs),
        change_logs=len(change_logs),
        accuracy=accuracy,
        cost=cost_info,
    )
    _write_json(output_dir, "pipeline_report.json", [stats])
    return stats

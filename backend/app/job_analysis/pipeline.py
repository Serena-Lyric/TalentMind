"""管道编排 —— 7 步串联，每步写中间文件支持断点续跑。"""
import asyncio
import json
from pathlib import Path

from app.job_analysis.models import (
    PipelineStats, MergedJobDefinition, MergedJobSkillDetail,
    RejectedItem,
)
from app.job_analysis.db import parse_jd_pool
from app.job_analysis.rules import apply_rules
from app.job_analysis.stage1_relevance import run_stage1
from app.job_analysis.stage2_quality import run_stage2
from app.job_analysis.stage3_extract import run_stage3
from app.job_analysis.merge import merge_jobs
from app.job_analysis.differ import diff_jobs
from app.job_analysis.export import export_all, _write_json, _load_json, _is_valid_checkpoint
from app.job_analysis.llm import reset_cost_counters, get_cost_summary
from app.job_analysis.config import SKILL_DICT_PATH, DATA_DIR, EXCHANGE_DIR


async def _run_pipeline_async(
    input_path: str,
    output_dir: Path,
    force: bool = False,
    existing_job_defs_path: str | None = None,
    accuracy: float | None = None,
) -> PipelineStats:
    reset_cost_counters()
    rejected: list[RejectedItem] = []
    manual: list[dict] = []

    # ═══ checkpoint paths（data/ 目录，不交付） ═══
    ckpt_dir = DATA_DIR
    ckpt_dir.mkdir(parents=True, exist_ok=True)
    s1_path = ckpt_dir / "s1_passed.json"
    s2_path = ckpt_dir / "s2_result.json"
    s3_path = ckpt_dir / "s3_result.json"
    s4_path = ckpt_dir / "s4_result.json"

    # ═══ [1/7] 硬规则预筛 ═══
    print("[1/7] 硬规则预筛")
    if not force and _is_valid_checkpoint(s1_path):
        print("      断点: 加载已有 s1_passed.json")
        with open(s1_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        from app.job_analysis.models import JdRecord
        passed_rules = [JdRecord(**item) for item in data]
    else:
        records = parse_jd_pool(input_path)
        print(f"      加载 {len(records)} 条记录")
        passed_rules, rejected_rules = apply_rules(records)
        rejected.extend(rejected_rules)
        print(f"      通过: {len(passed_rules)}, 拒绝: {len(rejected_rules)}")
        _write_json(ckpt_dir, "s1_passed.json",
                    [r.model_dump() for r in passed_rules])
        with open(ckpt_dir / "s0_rejected.json", "w", encoding="utf-8") as f:
            json.dump([r.model_dump() for r in rejected_rules],
                      f, ensure_ascii=False, indent=2)

    if not passed_rules:
        return export_all([], [], [], rejected, manual, output_dir,
                          accuracy, get_cost_summary())

    # ═══ [2/7] 模型1: 相关性 ═══
    print("[2/7] 模型1: 相关性分类")
    if not force and _is_valid_checkpoint(s2_path):
        print("      断点: 加载已有 s2_result.json")
        with open(s2_path, "r", encoding="utf-8") as f:
            s2_data = json.load(f)
        from app.job_analysis.models import JdRecord
        r1_map = {r.id: r for r in passed_rules}
        passed_s1_ids = {d["jd_id"] for d in s2_data if d.get("verdict") == "pass"}
        passed_s1 = [r1_map[jid] for jid in passed_s1_ids if jid in r1_map]
        for d in s2_data:
            if d.get("verdict") == "reject":
                rejected.append(RejectedItem(
                    jd_id=d["jd_id"], rule_id="relevance_reject",
                    stage="model1", detail=d.get("reasoning", ""),
                ))
            elif d.get("verdict") == "manual":
                manual.append(d)
    else:
        passed_s1, results_s1 = await run_stage1(passed_rules)
        for r in results_s1:
            if r.verdict == "reject":
                rejected.append(RejectedItem(
                    jd_id=r.jd_id, rule_id="relevance_reject",
                    stage="model1", detail=r.reasoning,
                ))
            elif r.verdict == "manual":
                manual.append(r.model_dump())
        _write_json(ckpt_dir, "s2_result.json",
                    [r.model_dump() for r in results_s1])
        print(f"      通过: {len(passed_s1)}, "
              f"拒绝: {sum(1 for r in results_s1 if r.verdict == 'reject')}, "
              f"人工: {sum(1 for r in results_s1 if r.verdict == 'manual')}")

    if not passed_s1:
        return export_all([], [], [], rejected, manual, output_dir,
                          accuracy, get_cost_summary())

    # ═══ [3/7] 模型2: 质量 ═══
    print("[3/7] 模型2: 质量评分")
    if not force and _is_valid_checkpoint(s3_path):
        print("      断点: 加载已有 s3_result.json")
        with open(s3_path, "r", encoding="utf-8") as f:
            s3_data = json.load(f)
        r2_map = {r.id: r for r in passed_s1}
        passed_s2_ids = {d["jd_id"] for d in s3_data if d.get("verdict") == "pass"}
        passed_s2 = [r2_map[jid] for jid in passed_s2_ids if jid in r2_map]
        for d in s3_data:
            if d.get("verdict") == "reject":
                rejected.append(RejectedItem(
                    jd_id=d["jd_id"], rule_id="quality_reject",
                    stage="model2", detail=d.get("weak_points", ""),
                ))
            elif d.get("verdict") == "manual":
                manual.append(d)
    else:
        passed_s2, results_s2 = await run_stage2(passed_s1)
        for r in results_s2:
            if r.verdict == "reject":
                rejected.append(RejectedItem(
                    jd_id=r.jd_id, rule_id="quality_reject",
                    stage="model2", detail=r.weak_points,
                ))
            elif r.verdict == "manual":
                manual.append(r.model_dump())
        _write_json(ckpt_dir, "s3_result.json",
                    [r.model_dump() for r in results_s2])
        print(f"      通过: {len(passed_s2)}, "
              f"拒绝: {sum(1 for r in results_s2 if r.verdict == 'reject')}, "
              f"人工: {sum(1 for r in results_s2 if r.verdict == 'manual')}")

    if not passed_s2:
        return export_all([], [], [], rejected, manual, output_dir,
                          accuracy, get_cost_summary())

    # ═══ [4/7] 模型3: 提取 ═══
    print("[4/7] 模型3: 结构化提取（LLM自由提取技能）")

    if not force and _is_valid_checkpoint(s4_path):
        print("      断点: 加载已有 s4_result.json")
        with open(s4_path, "r", encoding="utf-8") as f:
            s4_data = json.load(f)
        from app.job_analysis.models import ExtractionResult
        results_s3 = [ExtractionResult(**item) for item in s4_data]
        manual_s3 = [item for item in s4_data if item.get("verdict") == "manual"]
        manual.extend(manual_s3)
    else:
        results_s3, manual_s3 = await run_stage3(passed_s2)
        manual.extend(manual_s3)
        _write_json(ckpt_dir, "s4_result.json",
                    [r.model_dump() for r in results_s3])

    passed_s3 = [r for r in results_s3 if r.verdict == "pass"]
    print(f"      通过: {len(passed_s3)}, "
          f"人工: {sum(1 for r in results_s3 if r.verdict == 'manual')}")

    # ── 收集 unknown_skills ──
    unknown_skills = set()
    for r in results_s3:
        unknown_skills.update(r.unknown_skills)
    if unknown_skills:
        candidates_path = ckpt_dir / "skill_candidates.json"
        candidates = set(_load_json(candidates_path) or [])
        for s in unknown_skills:
            candidates.add(s)
        _write_json(ckpt_dir, "skill_candidates.json", sorted(candidates))
        print(f"      候选技能: {len(unknown_skills)} 个 -> skill_candidates.json")

    # ═══ [5/7] 合并层 ═══
    print("[5/7] 合并层")
    job_defs, job_skills = merge_jobs(passed_s3)
    print(f"      合并后岗位: {len(job_defs)} (原始 {len(passed_s3)})")

    # ═══ [6/7] 对比层 ═══
    print("[6/7] 对比层")
    existing_defs: dict[str, MergedJobDefinition] = {}
    existing_skills: dict[str, MergedJobSkillDetail] = {}
    if existing_job_defs_path:
        ed_path = Path(existing_job_defs_path)
        if ed_path.exists():
            with open(ed_path, "r", encoding="utf-8") as f:
                for item in json.load(f):
                    jd = MergedJobDefinition(**item)
                    existing_defs[jd.job_name.strip().lower()] = jd
            esk_path = ed_path.parent / "job_skill.json"
            if esk_path.exists():
                with open(esk_path, "r", encoding="utf-8") as f:
                    for item in json.load(f):
                        js = MergedJobSkillDetail(**item)
                        existing_skills[js.job_name.strip().lower()] = js

    job_defs, job_skills, change_logs = await diff_jobs(
        job_defs, job_skills, existing_defs, existing_skills,
    )
    print(f"      变更日志: {len(change_logs)} 条")

    # ═══ [7/7] 导出 ═══
    print("[7/7] 导出")
    cost = get_cost_summary()
    # DeepSeek 定价: prompt $1.10/M, completion $0.28/M（Pro 折算）
    cost["estimated_cost_usd"] = round(
        cost["prompt_tokens"] / 1_000_000 * 1.10 +
        cost["completion_tokens"] / 1_000_000 * 0.28, 4,
    )
    stats = export_all(job_defs, job_skills, change_logs, rejected, manual,
                       output_dir, accuracy, cost)

    # ═══ [8/7] 翻译中文版 ═══
    print("[8/7] 翻译中文版")
    from app.job_analysis.translate import (translate_job_definitions,
                           translate_job_skills, translate_change_logs)

    en_path = output_dir / "job_definition.json"
    zh_path = output_dir / "job_definition_zh.json"
    if en_path.exists():
        await translate_job_definitions(str(en_path), str(zh_path))

    # job_skill.json → 直接写中文（技能名/evidence 保留英文）
    skill_path = output_dir / "job_skill.json"
    if skill_path.exists():
        await translate_job_skills(str(skill_path), str(skill_path))

    # job_change_log.json → 直接写中文
    changelog_path = output_dir / "job_change_log.json"
    if changelog_path.exists():
        await translate_change_logs(str(changelog_path), str(changelog_path))

    print(f"\n完成! {stats.model_dump_json(indent=2)}")
    return stats


def run_pipeline(
    input_path: str | None = None,
    output_dir: str | None = None,
    force: bool = False,
    existing_job_defs_path: str | None = None,
    accuracy: float | None = None,
) -> PipelineStats:
    """主入口：运行完整 7 步管道。"""
    inp = input_path or str(DATA_DIR / "seed_jd_pool.sql")
    # 如果 data/ 下没有，尝试从桌面加载
    if not Path(inp).exists():
        inp = str(Path(__file__).parent.parent.parent / "seed_jd_pool.sql")
    od = Path(output_dir) if output_dir else EXCHANGE_DIR
    return asyncio.run(_run_pipeline_async(
        inp, od, force, existing_job_defs_path, accuracy))


async def stage1_only(input_path: str, output_path: str):
    """单独运行模型1（调试用）。"""
    from app.job_analysis.db import parse_jd_pool
    from app.job_analysis.rules import apply_rules
    records = parse_jd_pool(input_path)
    passed_rules, _ = apply_rules(records)
    passed_s1, results_s1 = await run_stage1(passed_rules)
    _write_json(Path(output_path).parent, Path(output_path).name,
                [r.model_dump() for r in results_s1])
    print(f"模型1完成: {len(passed_s1)}/{len(passed_rules)} 通过 -> {output_path}")


async def stage2_only(input_path: str, output_path: str):
    """单独运行模型2（调试用）。"""
    from app.job_analysis.models import JdRecord
    parent = Path(input_path).parent
    s1_path = parent / "s1_passed.json"
    if not s1_path.exists():
        raise FileNotFoundError(f"需要 s1_passed.json: {s1_path}")
    with open(s1_path, "r", encoding="utf-8") as f:
        records = [JdRecord(**item) for item in json.load(f)]
    with open(input_path, "r", encoding="utf-8") as f:
        s2_data = json.load(f)
    passed_s1_ids = {d["jd_id"] for d in s2_data if d.get("verdict") == "pass"}
    passed_records = [r for r in records if r.id in passed_s1_ids]
    passed_s2, results_s2 = await run_stage2(passed_records)
    _write_json(parent, Path(output_path).name,
                [r.model_dump() for r in results_s2])
    print(f"模型2完成: {len(passed_s2)}/{len(passed_records)} 通过 -> {output_path}")


def merge_manual_review(review_path: str, job_defs_path: str) -> None:
    """合并人工复核结果到 job_definition.json。"""
    with open(review_path, "r", encoding="utf-8") as f:
        reviews = json.load(f)
    with open(job_defs_path, "r", encoding="utf-8") as f:
        defs = json.load(f)

    approved = [r for r in reviews
                if r.get("review_status") in ("approved", "modified")]
    for r in approved:
        if r.get("modified_fields"):
            defs.append(r["modified_fields"])

    with open(job_defs_path, "w", encoding="utf-8") as f:
        json.dump(defs, f, ensure_ascii=False, indent=2)
    print(f"合并 {len(approved)} 条人工复核记录 -> {job_defs_path}")

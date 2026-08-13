"""对比层 —— 新岗位定义 vs 已有定义，生成全字段 change_log。"""
from datetime import datetime, timezone
from app.job_analysis.models import (
    MergedJobDefinition, MergedJobSkillDetail,
    JobChangeLog,
)
from app.job_analysis.llm import call_llm


async def _duties_changed(old_duties: str, new_duties: str, model: str) -> dict | None:
    """用轻量模型快速判定职责是否有显著语义变化。"""
    prompt = f"""Compare two versions of core_duties for the same job.

Old: "{old_duties}"
New: "{new_duties}"

Do they describe significantly different work content? Answer JSON:
{{"has_significant_change": true/false, "summary": "one sentence describing the change (if any)"}}"""

    resp = await call_llm(prompt, model, temperature=0, max_tokens=256)
    return resp if "_error" not in resp else None


async def diff_jobs(
    new_defs: list[MergedJobDefinition],
    new_skills: list[MergedJobSkillDetail],
    existing_defs: dict[str, MergedJobDefinition],
    existing_skills: dict[str, MergedJobSkillDetail],
    duties_diff_model: str = "",
) -> tuple[
    list[MergedJobDefinition],
    list[MergedJobSkillDetail],
    list[JobChangeLog],
]:
    from app.job_analysis.config import MODEL_DUTIES_DIFF
    duties_diff_model = duties_diff_model or MODEL_DUTIES_DIFF
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    change_logs: list[JobChangeLog] = []

    new_skill_map = {s.job_name.strip().lower(): s for s in new_skills}

    for nd in new_defs:
        key = nd.job_name.strip().lower()
        old_def = existing_defs.get(key)
        old_skill = existing_skills.get(key)

        if old_def is None:
            # 新岗位
            nd.is_emerging = True
            nd.first_seen = nd.collected_at
            continue

        # 已有岗位: 保留 first_seen, 更新 updated_at
        nd.first_seen = old_def.first_seen
        nd.updated_at = now

        # ── skills diff ──
        if old_skill and key in new_skill_map:
            ns = new_skill_map[key]
            old_skill_names = {s.name for s in old_skill.skills}
            new_skill_names = {s.name for s in ns.skills}
            new_skill_map_by_name = {s.name: s for s in ns.skills}
            old_skill_map_by_name = {s.name: s for s in old_skill.skills}

            for name in new_skill_names - old_skill_names:
                sk = new_skill_map_by_name[name]
                change_logs.append(JobChangeLog(
                    job_id=nd.job_name,
                    change_type="added", object_type="skill",
                    skill_name=name,
                    detail={"old_value": None, "new_value": {
                        "confidence": sk.confidence,
                        "is_required": sk.is_required,
                    }},
                    source=nd.source,
                    reason=f"新JD要求 {name}",
                    created_at=now,
                ))

            for name in old_skill_names - new_skill_names:
                sk = old_skill_map_by_name[name]
                change_logs.append(JobChangeLog(
                    job_id=nd.job_name,
                    change_type="removed", object_type="skill",
                    skill_name=name,
                    detail={"old_value": {
                        "confidence": sk.confidence,
                        "is_required": sk.is_required,
                    }, "new_value": None},
                    source=nd.source,
                    reason=f"JD不再要求 {name}",
                    created_at=now,
                ))

            for name in new_skill_names & old_skill_names:
                old_conf = old_skill_map_by_name[name].confidence
                new_conf = new_skill_map_by_name[name].confidence
                if abs(new_conf - old_conf) > 0.2:
                    change_logs.append(JobChangeLog(
                        job_id=nd.job_name,
                        change_type="modified", object_type="skill",
                        skill_name=name,
                        detail={"old_value": {"confidence": old_conf},
                                "new_value": {"confidence": new_conf}},
                        source=nd.source,
                        reason=f"{name} 权重变化: {old_conf}→{new_conf}",
                        created_at=now,
                    ))

        # ── duties diff ──
        if old_def.core_duties != nd.core_duties:
            change = await _duties_changed(
                old_def.core_duties, nd.core_duties, duties_diff_model,
            )
            if change and change.get("has_significant_change"):
                change_logs.append(JobChangeLog(
                    job_id=nd.job_name,
                    change_type="duties_changed", object_type="core_duties",
                    skill_name="core_duties",
                    detail={
                        "old_value": old_def.core_duties,
                        "new_value": nd.core_duties,
                        "summary": change.get("summary", ""),
                    },
                    source=nd.source,
                    reason=change.get("summary", ""),
                    created_at=now,
                ))

        # ── scenarios diff ──
        old_scenarios = set(old_def.scenarios)
        new_scenarios = set(nd.scenarios)
        for s in new_scenarios - old_scenarios:
            change_logs.append(JobChangeLog(
                job_id=nd.job_name,
                change_type="scenarios_added", object_type="scenario",
                skill_name=s,
                detail={"old_value": None, "new_value": s},
                source=nd.source,
                reason=f"新增应用场景: {s}", created_at=now,
            ))
        for s in old_scenarios - new_scenarios:
            change_logs.append(JobChangeLog(
                job_id=nd.job_name,
                change_type="scenarios_removed", object_type="scenario",
                skill_name=s,
                detail={"old_value": s, "new_value": None},
                source=nd.source,
                reason=f"应用场景消失: {s}", created_at=now,
            ))

        # ── evolution diff ──
        if old_def.evolution.stage != nd.evolution.stage:
            change_logs.append(JobChangeLog(
                job_id=nd.job_name,
                change_type="evolution_changed", object_type="evolution",
                skill_name="stage",
                detail={
                    "old_value": old_def.evolution.stage,
                    "new_value": nd.evolution.stage,
                },
                source=nd.source,
                reason=f"演化阶段: {old_def.evolution.stage}→{nd.evolution.stage}",
                created_at=now,
            ))

    return new_defs, new_skills, change_logs

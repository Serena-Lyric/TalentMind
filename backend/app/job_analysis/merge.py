"""合并层 —— 同 job_name 的 ExtractionResult 聚合为一个岗位定义。"""
from collections import defaultdict
from datetime import datetime, timezone
from app.job_analysis.models import (
    ExtractionResult, MergedJobDefinition, MergedJobSkillDetail,
    MergedJobSkill, EvolutionInfo,
)


def merge_jobs(
    results: list[ExtractionResult],
) -> tuple[list[MergedJobDefinition], list[MergedJobSkillDetail]]:
    """
    同 job_name（lowercase）的 ExtractionResult 合并为一个岗位定义。

    规则:
      - skills: 按 name 分组，每个 name 保留 confidence 最高者；
                is_required = 至少一条为 required
      - quality: 加权均值（权重 = 该 JD 技能数 / 总技能数）
      - sources/scenarios: 取并集
      - core_duties: 保留技能最多的那条 JD 的 duties
      - is_emerging: 有任意一条 true 则为 true
      - evolution: 基于合并后数据重算
    """
    groups: dict[str, list[ExtractionResult]] = defaultdict(list)
    for r in results:
        if r.verdict != "pass":
            continue
        key = r.job_name.strip().lower()
        groups[key].append(r)

    definitions: list[MergedJobDefinition] = []
    skill_details: list[MergedJobSkillDetail] = []

    for key, group in groups.items():
        # 选代表性 JD 名（技能最多的那条的原始名）
        best = max(group, key=lambda x: len(x.required_skills) + len(x.bonus_skills))
        job_name = best.job_name

        # 合并 skills
        skill_map: dict[str, MergedJobSkill] = {}
        for r in group:
            for sk in r.required_skills + r.bonus_skills:
                if sk.name in skill_map:
                    existing = skill_map[sk.name]
                    if sk.confidence > existing.confidence:
                        existing.confidence = sk.confidence
                        existing.evidence = f"JD #{r.jd_id}: {sk.evidence}"
                    existing.is_required = existing.is_required or sk.is_required
                    existing.evidence_jd_count += 1
                else:
                    skill_map[sk.name] = MergedJobSkill(
                        skill_id=f"s_{sk.name}",
                        name=sk.name,
                        weight=0.0,
                        confidence=sk.confidence,
                        evidence=f"JD #{r.jd_id}: {sk.evidence}",
                        evidence_jd_count=1,
                        is_required=sk.is_required,
                    )

        # 归一化 weight
        total_conf = sum(s.confidence for s in skill_map.values())
        for s in skill_map.values():
            s.weight = round(s.confidence / total_conf, 3) if total_conf > 0 else 0.0

        skills_list = sorted(skill_map.values(), key=lambda x: x.confidence, reverse=True)
        required = [s.name for s in skills_list if s.is_required]
        bonus = [s.name for s in skills_list if not s.is_required]

        # quality 加权均值
        total_skills_across_group = sum(
            len(r.required_skills) + len(r.bonus_skills) for r in group
        )
        quality = 0.0
        if total_skills_across_group > 0:
            quality = sum(
                r.quality * (len(r.required_skills) + len(r.bonus_skills))
                / total_skills_across_group
                for r in group
            )

        # sources / scenarios 并集
        sources = list(set(r.source for r in group if r.source))
        scenarios = list(set(s for r in group for s in r.scenarios))

        # is_emerging
        is_emerging = any(r.is_emerging for r in group)

        # evolution 重算
        evolution = EvolutionInfo(
            stage=best.evolution.stage,
            stage_confidence=best.evolution.stage_confidence,
            indicators={
                "jd_count_in_batch": len(group),
                "source_diversity": len(sources),
                "skill_novelty": (
                    "high" if is_emerging else
                    "medium" if len(group) < 5 else "low"
                ),
            },
        )

        # first_seen: 取最早；collected_at: 取最晚
        dates = sorted(r.collected_at for r in group if r.collected_at)
        first_seen = dates[0] if dates else ""
        collected_at = dates[-1] if dates else ""
        updated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

        definitions.append(MergedJobDefinition(
            job_name=job_name,
            core_duties=best.core_duties,
            required_skills=required,
            bonus_skills=bonus,
            scenarios=scenarios,
            source=sources,
            quality=round(quality, 3),
            is_emerging=is_emerging,
            evolution=evolution,
            first_seen=first_seen,
            collected_at=collected_at,
            updated_at=updated_at,
            source_jd_count=len(group),
        ))

        skill_details.append(MergedJobSkillDetail(
            job_name=job_name,
            skills=skills_list,
        ))

    return definitions, skill_details

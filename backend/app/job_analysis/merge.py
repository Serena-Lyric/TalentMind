"""合并层 —— 同岗位类型的 ExtractionResult 聚合为一个岗位定义。"""
from collections import defaultdict
from datetime import datetime, timezone
import re
from .models import (
    ExtractionResult, MergedJobDefinition, MergedJobSkillDetail,
    MergedJobSkill, EvolutionInfo,
)

_SENIORITY_WORDS = re.compile(
    r"\b(senior|junior|lead|principal|staff|sr\.?|jr\.?|mid-?level|"
    r"entry-?level|intern|internship|trainee|graduate|associate|"
    r"高级|初级|资深|实习|应届)\b", re.I)
# 岗位标题词（用于在 hn 多段标题里挑出真正的岗位段）
_JOB_TITLE_WORDS = re.compile(
    r"(engineer|developer|programmer|architect|analyst|scientist|"
    r"designer|specialist|consultant|coordinator|administrator|manager|"
    r"director|officer|researcher|technician|devops|sre|"
    r"工程师|经理|专员|专家|分析师|设计师|开发|顾问|研究员|运维)",
    re.I)
# 标签段（非岗位）：薪资/地点/工作制等（每个分支都允许后续修饰）
_TAG_SEGMENT = re.compile(
    r"^(remote|onsite|hybrid|full-?time|part-?time|contract|freelance|"
    r"permanent|temporary|immediate|usa|us only|us|eu|uk|europe|canada|"
    r"apac|india|nyc|sf|bay area|location|relocation|visa|sponsor)"
    r"[\s(:，:（].*$", re.I)
_SALARY_SEGMENT = re.compile(r"^[\d$€£]\s*[\dk+\-–~]")
_ANY_SALARY = re.compile(r"^\d+\s?[kKyY]?\+?\s*(usd|eur)?\s*$")
# 多岗位聚合帖：不可归一化为单一类型，保留原文（避免错误合并）
_MULTI_ROLE = re.compile(
    r"multiple (roles|positions|positions available|openings|"
    r"engineering roles)|various (roles|positions)|"
    r"多岗位|多个岗位|职位多", re.I)

# hn 标题前缀："Company (Location) — Title" 或 "Company | Title"
_HN_PREFIX_RE = re.compile(
    r"^[^—–|:]{3,80}?[—–|]\s*(.+)$|^.+?\)\s*[—–]\s*(.+)$")


def _split_title_segments(name: str) -> list[str]:
    """按 hn 标题的分隔符切段，清洗空段。"""
    segs = [s.strip() for s in re.split(r"[|—–]", name)]
    return [s for s in segs if s]


def _is_tag_segment(s: str) -> bool:
    if not s:
        return True
    if _TAG_SEGMENT.match(s) or _SALARY_SEGMENT.match(s) or _ANY_SALARY.match(s):
        return True
    return False


def normalize_job_type(job_name: str) -> str:
    """归一化岗位类型：挑出岗位段、去 seniority 词，小写化。

    'PrairieLearn (Remote US) — Full-Stack Software Engineer'
      -> 'full-stack software engineer'
    'Senior Rust Engineer || 5Y+ || Remote (USA)' -> 'rust engineer'
    'SmarterDx | 150-250k+ | Remote (US only)' -> 'smarterdx'（无岗位段的兜底）
    """
    original = job_name.strip()
    name = original
    # 多岗位聚合帖：保留原标题（去公司前缀），不强行归一化
    if _MULTI_ROLE.search(name):
        m = _HN_PREFIX_RE.match(name)
        if m:
            name = next(g for g in m.groups() if g)
        return name.lower()

    segs = _split_title_segments(name)
    if len(segs) > 1:
        cands = [s for s in segs if not _is_tag_segment(s)]
        # 优先含岗位词的段
        titled = [s for s in cands if _JOB_TITLE_WORDS.search(s)]
        if titled:
            name = titled[0]
        elif cands:
            # 兜底改进：多段标题里岗位段常在末尾（hn 格式
            # "公司 | 岗位"），截断/无岗位词时取最后一段而非首段（公司名）
            name = cands[-1]
        else:
            # 全部是标签段：回退到原始标题的首段（公司名或岗位名）
            first = _split_title_segments(original)
            name = first[0] if first else original

    stripped = _SENIORITY_WORDS.sub("", name)
    # 清理 seniority 剥除后的斜杠/标点残渣（"Senior/Staff/Lead" → "//"）
    stripped = re.sub(r"^[\s/,.\-–—]+", "", stripped)
    stripped = re.sub(r"\s+", " ", stripped).strip(" ,")
    # 剥光或太短的（如截断残留 "Sa"）：回退到最后一个非标签候选段
    if (len(stripped) < 4 and "|" in original) and len(name) >= 4:
        _cands = [s for s in _split_title_segments(original)
                  if not _is_tag_segment(s)]
        if _cands and len(_cands[-1]) >= 4:
            stripped = _cands[-1]
    # 截断残留（"Youth Inc. ("、"Sa"、"full-time"）→ 统一占位名
    if len(stripped) < 4 or stripped.endswith("(") or \
            stripped in ("full-time", "fulltime", "remote", "onsite"):
        stripped = "unknown role"
    # 剥光了的（如标题只有 'Associate'）：保留原词
    if len(stripped) < 3 and len(name) >= 3:
        stripped = name
    return stripped.lower()


def _stable_job_id(job_name: str) -> str:
    """稳定关联键：岗位名归一后的 MD5 前 16 位。"""
    import hashlib
    return "j_" + hashlib.md5(job_name.strip().lower().encode("utf-8")).hexdigest()[:16]


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
        key = normalize_job_type(r.job_name)
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
                    if sk.verification == "suspicious":
                        existing.verification = "suspicious"
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
                        verification=(
                            "verified" if sk.verification in ("verified", "")
                            else "suspicious"),
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
            job_id=_stable_job_id(job_name),
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
            job_id=_stable_job_id(job_name),
            job_name=job_name,
            skills=skills_list,
        ))

    return definitions, skill_details

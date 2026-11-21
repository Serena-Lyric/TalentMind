"""人岗匹配：canonical 技能与必备/加分加权快捷匹配。"""

from typing import Dict, List, Optional, Set

from app.matching.canonical import to_canonical
from app.matching.skill_extractor import get_skill_category

# 技能权重配置（不同类别技能的重要程度）
SKILL_WEIGHTS = {
    '编程语言': 1.5,      # 编程语言权重较高
    '后端框架': 1.3,
    '前端技术': 1.0,
    '数据库': 1.2,
    '大数据/云': 1.1,
    'AI/机器学习': 1.2,
    'DevOps/运维': 1.0,
    '软件工程': 0.8,      # 通用的软技能权重较低
    '专业领域': 0.8,
    '其他': 0.5
}


def quick_match_weighted(resume_skills: List[str], required_skills: List[str],
                          bonus_skills: Optional[List[str]] = None) -> Dict:
    """
    带“必备/加分”区分的加权快速匹配（推荐排序用的真实分）：
    - 必备技能按分类权重占比 70%；加分技能占比 30%；
    - 分类权重基于技能类别（大小写不敏感），必备命中率低时真实分显著下降。
    """
    resume_set = {to_canonical(s) for s in resume_skills if s.strip()}
    required_set = {to_canonical(s) for s in required_skills or [] if s.strip()}
    bonus_set = {to_canonical(s) for s in bonus_skills or [] if s.strip()} - required_set
    job_set = required_set | bonus_set
    if not job_set:
        return {
            'total_score': 0, 'match_rate': 0, 'matched_skills': [],
            'unmatched_job_skills': [], 'resume_extra_skills': [],
            'category_scores': {}, 'matched_count': 0, 'job_required_count': len(required_set),
        }

    # 与学习路径共用 canonical；相关技术不自动当作已命中的岗位技能。
    matched = resume_set & job_set

    def _weight(skill: str) -> float:
        return SKILL_WEIGHTS.get(get_skill_category(skill), 1.0)

    def _matched_weight(core: Set[str]) -> float:
        return sum(_weight(skill) for skill in core if skill in matched)

    def _total_weight(core: Set[str]) -> float:
        return sum(_weight(skill) for skill in core)

    required_total = _total_weight(required_set)
    bonus_total = _total_weight(bonus_set)
    required_rate = _matched_weight(required_set) / required_total if required_total > 0 else None
    bonus_rate = _matched_weight(bonus_set) / bonus_total if bonus_total > 0 else None

    if required_rate is None:
        score = round(100 * bonus_rate, 1) if bonus_rate is not None else 0.0
    elif bonus_rate is None:
        score = round(100 * required_rate, 1)
    else:
        score = round(100 * (0.7 * required_rate + 0.3 * bonus_rate), 1)
    score = max(0.0, min(100.0, score))

    return {
        'total_score': score,
        'match_rate': round(len(matched) / len(job_set) * 100, 1) if job_set else 0,
        'matched_skills': [to_canonical(skill) for skill in sorted(matched)],
        'unmatched_job_skills': [to_canonical(skill) for skill in sorted(job_set - matched)],
        'resume_extra_skills': [to_canonical(skill) for skill in sorted(resume_set - job_set)],
        'category_scores': {}, 'matched_count': len(matched),
        'job_required_count': len(required_set),
    }

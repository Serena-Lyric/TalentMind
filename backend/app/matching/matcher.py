"""
人岗匹配器 V2
计算候选人与岗位之间的匹配度，生成匹配报告
优化：支持技能同义词、部分匹配、更智能的权重计算
"""

from typing import Dict, List, Set, Tuple, Optional
from app.matching.resume_parser import ResumeParser, parse_resume
from app.matching.job_parser import JobParser, parse_job
from app.matching.skill_extractor import extract_skills, categorize_skills, get_skill_category, SYNONYMS
from app.matching.canonical import to_canonical


class ResumeJobMatcher:
    """人岗匹配器 V2"""

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

    # 核心技能（必须有这些才能匹配）
    CORE_SKILLS = {
        '编程语言': 1,         # 至少需要掌握1门编程语言
        '后端框架': 0.5,      # 框架是加分类
        '数据库': 0.5,
    }

    def __init__(self):
        self.resume_parser = ResumeParser()
        self.job_parser = JobParser()

    def match(self, resume_text: str, job_text: str) -> Dict:
        """
        计算人岗匹配度

        Args:
            resume_text: 简历文本
            job_text: 岗位描述文本

        Returns:
            匹配结果字典
        """
        # 解析简历和岗位
        resume = self.resume_parser.parse(resume_text)
        job = self.job_parser.parse(job_text)

        if not resume or not job:
            return {
                'success': False,
                'error': '简历或岗位解析失败',
                'resume': resume,
                'job': job
            }

        # 提取技能列表
        resume_skills = set(resume.get('skills', []))
        job_skills = set(job.get('skills', []))

        # 如果岗位没有明确技能，尝试从任职要求中提取
        if not job_skills:
            job_skills = set(extract_skills(job_text))

        # 计算匹配度
        match_result = self._calculate_match_v2(resume_skills, job_skills, resume_text, job_text)

        # 构建匹配报告
        report = {
            'success': True,
            'resume_info': {
                'name': resume.get('personal_info', {}).get('name', '未知'),
                'experience_years': resume.get('personal_info', {}).get('experience_years', 0),
                'location': resume.get('personal_info', {}).get('location', '未知'),
            },
            'job_info': {
                'title': job.get('title', '未知'),
                'location': job.get('location', '未知'),
                'experience_required': job.get('experience_required', '不限'),
                'education_required': job.get('education_required', '不限'),
            },
            'skills_match': match_result,
            'recommendation': self._generate_recommendation_v2(match_result)
        }

        return report

    def _expand_skills(self, skills: Set[str]) -> Set[str]:
        """扩展技能：包含同义词和缩写"""
        expanded = set(skills)
        for skill in skills:
            skill_lower = skill.lower()
            # 添加同义词
            if skill_lower in SYNONYMS:
                expanded.add(SYNONYMS[skill_lower])
            # 添加反向映射
            for short, standard in SYNONYMS.items():
                if standard.lower() == skill_lower:
                    expanded.add(short)
                    expanded.add(standard)
        return expanded

    def _calculate_match_v2(self, resume_skills: Set[str], job_skills: Set[str],
                            resume_text: str = "", job_text: str = "") -> Dict:
        """计算技能匹配情况 V2（改进版）"""

        if not job_skills:
            return {
                'total_score': 0,
                'matched_skills': [],
                'unmatched_job_skills': [],
                'resume_extra_skills': [],
                'match_rate': 0,
                'category_scores': {}
            }

        # 扩展简历技能（包含同义词）
        expanded_resume = self._expand_skills(resume_skills)

        # 1. 精确匹配
        exact_matched = resume_skills & job_skills

        # 2. 模糊匹配（在扩展集合中找）
        fuzzy_matched = expanded_resume & job_skills - exact_matched
        fuzzy_matched_details = list(fuzzy_matched)

        # 合并匹配结果
        all_matched = exact_matched | fuzzy_matched

        # 未匹配的技能
        unmatched_job_skills = job_skills - all_matched
        # 简历额外技能
        resume_extra_skills = resume_skills - job_skills

        # 计算加权分数
        total_weight = 0
        matched_weight = 0
        category_scores = {}

        for skill in job_skills:
            category = get_skill_category(skill)
            weight = self.SKILL_WEIGHTS.get(category, 1.0)
            total_weight += weight

            if skill in all_matched:
                matched_weight += weight

            if category not in category_scores:
                category_scores[category] = {'matched': 0, 'total': 0, 'score': 0, 'weight': 0}
            category_scores[category]['total'] += 1
            category_scores[category]['weight'] += weight
            if skill in all_matched:
                category_scores[category]['matched'] += 1

        # 计算每个类别的得分
        for category, scores in category_scores.items():
            if scores['total'] > 0:
                scores['score'] = round(scores['matched'] / scores['total'] * 100, 1)

        # 总分（满分100）
        total_score = round(matched_weight / total_weight * 100, 1) if total_weight > 0 else 0

        # 基础分：即使没有完全匹配的技能，也给一定基础分
        # 如果有至少1个核心技能匹配，加分
        core_skills_matched = 0
        core_categories = ['编程语言', '后端框架', '数据库']
        for category in core_categories:
            if category in category_scores and category_scores[category]['matched'] > 0:
                core_skills_matched += 1

        # 核心技能bonus
        if core_skills_matched >= 2:
            total_score = min(100, total_score + 10)

        # 计算匹配率（基于技能数量）
        match_rate = round(len(all_matched) / len(job_skills) * 100, 1) if job_skills else 0

        # 输出技能名 canonical 归一（D31：对齐 skill_dict）
        return {
            'total_score': total_score,
            'match_rate': match_rate,
            'exact_matched': [to_canonical(s) for s in exact_matched],
            'fuzzy_matched': [to_canonical(s) for s in fuzzy_matched_details],
            'matched_skills': [to_canonical(s) for s in all_matched],
            'unmatched_job_skills': [to_canonical(s) for s in unmatched_job_skills],
            'resume_extra_skills': [to_canonical(s) for s in resume_extra_skills],
            'category_scores': category_scores,
            'matched_count': len(all_matched),
            'job_required_count': len(job_skills),
            'core_skills_matched': core_skills_matched
        }

    def _generate_recommendation_v2(self, match_result: Dict) -> str:
        """生成匹配建议 V2（更智能）"""
        score = match_result['total_score']
        matched = match_result['matched_count']
        required = match_result['job_required_count']
        unmatched = match_result['unmatched_job_skills']
        core_matched = match_result.get('core_skills_matched', 0)

        # 匹配率
        rate = match_result['match_rate']

        if score >= 90 or (core_matched >= 2 and rate >= 80):
            return "强烈推荐 - 技能完全匹配，非常适合该岗位"
        elif score >= 70 or (core_matched >= 1 and rate >= 60):
            if unmatched:
                return "建议面试 - 技能匹配度高，可考虑补充: {}".format(', '.join(unmatched[:3]))
            else:
                return "建议面试 - 技能匹配度高，符合岗位要求"
        elif score >= 50 or rate >= 40:
            if unmatched:
                return "可考虑的候选人，需要补充: {}".format(', '.join(unmatched[:5]))
            else:
                return "可考虑 - 部分技能匹配"
        elif score >= 30 or core_matched >= 1:
            return "基础技能匹配，可作为备选候选人"
        else:
            return "不太推荐 - 技能匹配度较低"


def match_resume_job(resume_text: str, job_text: str) -> Dict:
    """便捷函数：匹配简历和岗位"""
    matcher = ResumeJobMatcher()
    return matcher.match(resume_text, job_text)


def batch_match(resumes: List[str], jobs: List[str]) -> List[Dict]:
    """
    批量匹配多份简历和多个岗位

    Args:
        resumes: 简历文本列表
        jobs: 岗位描述文本列表

    Returns:
        匹配结果列表
    """
    matcher = ResumeJobMatcher()
    results = []

    for i, resume in enumerate(resumes):
        for j, job in enumerate(jobs):
            result = matcher.match(resume, job)
            result['resume_index'] = i
            result['job_index'] = j
            results.append(result)

    # 按匹配度排序
    results.sort(key=lambda x: x.get('skills_match', {}).get('total_score', 0), reverse=True)

    return results


# ============ 快速匹配函数 ============

def quick_match(resume_skills: List[str], job_skills: List[str]) -> Dict:
    """
    快速匹配：只比较技能列表，不解析文本
    用于已知技能列表的快速匹配
    """
    matcher = ResumeJobMatcher()
    resume_set = set(resume_skills)
    job_set = set(job_skills)

    result = matcher._calculate_match_v2(resume_set, job_set)
    return result


def similarity_score(skills1: List[str], skills2: List[str]) -> float:
    """
    计算两个技能列表的相似度
    Jaccard相似系数
    """
    set1 = set(skills1)
    set2 = set(skills2)

    if not set1 or not set2:
        return 0.0

    intersection = len(set1 & set2)
    union = len(set1 | set2)

    return round(intersection / union * 100, 2) if union > 0 else 0.0


if __name__ == '__main__':
    # 测试
    test_resume = """
    姓名：李四
    电话：13900139000
    邮箱：lisi@email.com
    年龄：30
    性别：男
    地点：北京
    经验：5年

    教育背景
    2015.09 - 2019.06 清华大学 计算机科学与技术 本科

    工作经历
    2021.07 - 至今 百度 高级后端工程师
    负责搜索引擎后端开发
    使用Python和Go语言
    熟练使用MySQL、Redis
    有高并发和分布式系统经验

    技能专长
    Python, Java, Go
    Django, Flask, Gin
    MySQL, Redis, Elasticsearch
    Docker, Kubernetes, AWS
    """

    test_job = """
    【高级后端工程师】

    工作地点：北京
    经验要求：3-5年
    学历要求：本科

    任职要求：
    1. 熟练使用Python或Go语言
    2. 熟悉Django、Flask或Gin框架
    3. 掌握MySQL、Redis，有高并发经验
    4. 熟悉Linux、Docker、K8s
    5. 有分布式系统经验优先
    """

    result = match_resume_job(test_resume, test_job)

    import json
    print(json.dumps(result, ensure_ascii=False, indent=2))
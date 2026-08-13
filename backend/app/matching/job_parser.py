"""
岗位描述解析器
从岗位 JD 中提取任职要求、技能要求、工作职责等信息
"""

import re
from typing import Dict, List
from app.matching.skill_extractor import extract_skills, categorize_skills


class JobParser:
    """岗位描述解析器"""

    def __init__(self):
        # 职位标题关键词
        self.title_keywords = ['职位', '岗位', 'Job', 'Position', 'Title']
        # 任职要求关键词
        self.require_keywords = ['任职要求', '岗位要求', '要求', 'Requirement', 'Qualification']
        # 职责关键词
        self.responsibility_keywords = ['职责', '工作内容', 'Responsibility', 'Duties', 'Job Description']
        # 加分项关键词
        self.bonus_keywords = ['加分', '优先', 'Plus', 'Nice to Have', '优先考虑']

    def parse(self, text: str) -> Dict:
        """
        解析岗位描述文本

        Args:
            text: 岗位描述文本内容

        Returns:
            解析后的岗位字典
        """
        if not text:
            return {}

        job = {
            'raw_text': text,
            'title': self._extract_title(text),
            'requirements': self._extract_requirements(text),
            'responsibilities': self._extract_responsibilities(text),
            'bonus_points': self._extract_bonus_points(text),
            'location': self._extract_location(text),
            'salary': self._extract_salary(text),
            'experience_required': self._extract_experience(text),
            'education_required': self._extract_education(text),
            'skills': [],
            'skills_by_category': {}
        }

        # 提取技能
        job['skills'] = extract_skills(text)
        job['skills_by_category'] = categorize_skills(job['skills'])

        return job

    def _extract_title(self, text: str) -> str:
        """提取职位名称"""
        lines = text.split('\n')

        for line in lines[:5]:  # 通常标题在前几行
            line = line.strip()
            # 去掉常见的职位描述前缀
            for prefix in ['【', '『', '[', '『', '职位：', '岗位：', 'Position: ', 'Job: ']:
                if line.startswith(prefix):
                    return line.replace(prefix, '').strip().rstrip('】』]')

            # 如果行较短且包含职位相关词，可能是标题
            if len(line) < 30 and any(kw in line for kw in ['工程师', 'Developer', 'Architect', 'Manager']):
                return line.strip()

        return ''

    def _extract_location(self, text: str) -> str:
        """提取工作地点"""
        # 常见地点模式
        location_patterns = [
            r'工作地点[：:]\s*([^\n]{2,20})',
            r'地点[：:]\s*([^\n]{2,20})',
            r'Location[：:]\s*([^\n]{2,20})',
            r'(北京|上海|广州|深圳|杭州|南京|苏州|成都|武汉|西安|天津|重庆)[^\n]{0,20}',
        ]

        for pattern in location_patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1) if match.lastindex else match.group(0)

        return ''

    def _extract_salary(self, text: str) -> str:
        """提取薪资范围"""
        salary_patterns = [
            r'薪资[：:]\s*(\d+[Kk]?-?\d*[Kk]?)',
            r'薪酬[：:]\s*(\d+[Kk]?-?\d*[Kk]?)',
            r'工资[：:]\s*(\d+[Kk]?-?\d*[Kk]?)',
            r'(\d+[Kk]?-?\d*[Kk]?)\s*(\d+[Kk]?)?\s*元[/(每月|/月|/年|年)]?',
            r'Salary[：:]\s*([^\n]{5,30})',
        ]

        for pattern in salary_patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(0)

        return ''

    def _extract_experience(self, text: str) -> str:
        """提取经验要求"""
        exp_patterns = [
            r'(\d+)\s*年.*以上.*经验',
            r'经验[：:]\s*(\d+\s*年)',
            r'(\d+)\s*年以上.*开发',
            r'(\d+)\s*-\s*(\d+)\s*年',
        ]

        for pattern in exp_patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(0)

        return ''

    def _extract_education(self, text: str) -> str:
        """提取学历要求"""
        edu_patterns = [
            r'学历[：:]\s*(本科|硕士|博士|大专|高中|中专)',
            r'本科及以上',
            r'硕士及以上',
            r'大专及以上',
            r'Education[：:]\s*([^\n]{2,10})',
        ]

        education_levels = ['博士', '硕士', '本科', '大专', '高中', '中专']

        for pattern in edu_patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1) if match.lastindex else match.group(0)

        # 直接搜索学历关键词
        for edu in education_levels:
            if edu in text:
                return edu

        return ''

    def _find_section(self, text: str, keywords: List[str]) -> tuple:
        """查找章节的起始和结束位置"""
        lines = text.split('\n')

        start_idx = -1
        end_idx = len(lines)

        # 查找起始位置
        for i, line in enumerate(lines):
            line_stripped = line.strip()
            for keyword in keywords:
                if keyword in line_stripped:
                    start_idx = i + 1
                    break
            if start_idx != -1:
                break

        if start_idx == -1:
            return None, None

        # 查找结束位置
        section_names = [
            '任职要求', '岗位要求', '工作职责', '职责', '加分项', '优先',
            'Responsibility', 'Requirement', 'Bonus', 'Qualification'
        ]

        for j in range(start_idx, len(lines)):
            line_stripped = lines[j].strip()
            for sn in section_names:
                if sn in keywords:
                    continue
                if line_stripped == sn or line_stripped.startswith(sn + '：') or line_stripped.startswith(sn + ':'):
                    end_idx = j
                    return start_idx, end_idx

        return start_idx, end_idx

    def _extract_requirements(self, text: str) -> List[str]:
        """提取任职要求"""
        requirements = []
        start_idx, end_idx = self._find_section(text, self.require_keywords)

        if start_idx is None:
            # 尝试在整个文本中提取
            lines = text.split('\n')
            start_idx = 0
            end_idx = len(lines)
        else:
            lines = text.split('\n')

        for line in lines[start_idx:end_idx]:
            line = line.strip()
            if line and len(line) > 2:
                # 去除常见的列表前缀
                line = re.sub(r'^[\d\.、\-\*•▸]\s*', '', line)
                if line:
                    requirements.append(line)

        return requirements

    def _extract_responsibilities(self, text: str) -> List[str]:
        """提取工作职责"""
        responsibilities = []
        start_idx, end_idx = self._find_section(text, self.responsibility_keywords)

        if start_idx is None:
            return responsibilities

        lines = text.split('\n')

        for line in lines[start_idx:end_idx]:
            line = line.strip()
            if line and len(line) > 2:
                line = re.sub(r'^[\d\.、\-\*•▸]\s*', '', line)
                if line:
                    responsibilities.append(line)

        return responsibilities

    def _extract_bonus_points(self, text: str) -> List[str]:
        """提取加分项"""
        bonus_points = []
        start_idx, end_idx = self._find_section(text, self.bonus_keywords)

        if start_idx is None:
            return bonus_points

        lines = text.split('\n')

        for line in lines[start_idx:end_idx]:
            line = line.strip()
            if line and len(line) > 2:
                line = re.sub(r'^[\d\.、\-\*•▸]\s*', '', line)
                if line:
                    bonus_points.append(line)

        return bonus_points


def parse_job(text: str) -> Dict:
    """便捷函数：解析岗位描述"""
    parser = JobParser()
    return parser.parse(text)


if __name__ == '__main__':
    # 测试
    test_job = """
    【高级后端工程师】

    工作地点：北京
    薪资：25K-40K·14薪
    经验要求：3-5年
    学历要求：本科及以上

    职位描述：
    负责公司核心业务后端开发，参与系统架构设计与优化。

    任职要求：
    1. 3年以上后端开发经验，熟悉微服务架构
    2. 精通Python或Java，熟悉Django、Spring Boot框架
    3. 熟练使用MySQL、Redis，有高并发项目经验
    4. 熟悉Linux、Docker、K8s
    5. 具备良好的编码习惯和团队协作能力

    加分项：
    - 有大规模分布式系统开发经验
    - 熟悉Elasticsearch、Kafka
    - 有机器学习相关经验
    - 开源项目贡献者
    """

    result = parse_job(test_job)
    import json
    print(json.dumps(result, ensure_ascii=False, indent=2))
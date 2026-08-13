"""
简历解析器
从文本格式的简历中提取个人信息、教育经历、工作经验、技能等信息
"""

import re
from typing import Dict, List, Optional
from app.matching.skill_extractor import extract_skills, categorize_skills


class ResumeParser:
    """简历解析器"""

    def __init__(self):
        # 个人信息模式
        self.patterns = {
            'name': r'(?:姓名[：:]\s*|name[：:]\s*|^)([^\s\n]{2,10})(?:$|\n)',
            'phone': r'(?:电话[：:]|手机[：:]|Tel[：:]|phone[：:]\s*)(1[3-9]\d{9})',
            'email': r'(?:邮箱[：:]|Email[：:]|E-mail[：:]\s*)([\w.-]+@[\w.-]+\.\w+)',
            'age': r'(?:年龄[：:]|age[：:]\s*)(\d{1,2})',
            'gender': r'(?:性别[：:]|gender[：:]\s*)(男|女)',
            'location': r'(?:地点[：:]|城市[：:]|location[：:]\s*)([^\n]{2,20})',
            'experience': r'(?:工作年限[：:]|经验[：:]|years?[：:]\s*)(\d{1,2})',
        }

        # 教育经历标题
        self.education_keywords = ['教育背景', '教育经历', 'Education', '学历']
        # 工作经历标题
        self.work_keywords = ['工作经历', '工作经验', 'Professional Experience', '工作履历']
        # 项目经历标题
        self.project_keywords = ['项目经历', '项目经验', 'Projects']
        # 技能标题
        self.skill_keywords = ['技能专长', '专业技能', 'Skills', '技术技能', '技能']

    def parse(self, text: str) -> Dict:
        """
        解析简历文本

        Args:
            text: 简历文本内容

        Returns:
            解析后的简历字典
        """
        if not text:
            return {}

        lines = text.strip().split('\n')

        resume = {
            'raw_text': text,
            'personal_info': self._extract_personal_info(text),
            'education': self._extract_education(text),
            'work_experience': self._extract_work_experience(text),
            'project_experience': self._extract_project_experience(text),
            'skills': [],
            'skills_by_category': {}
        }

        # 提取技能
        resume['skills'] = extract_skills(text)
        resume['skills_by_category'] = categorize_skills(resume['skills'])

        return resume

    def _extract_personal_info(self, text: str) -> Dict:
        """提取个人信息"""
        info = {}

        # 提取姓名
        name_match = re.search(self.patterns['name'], text, re.MULTILINE)
        if name_match:
            info['name'] = name_match.group(1).strip()

        # 提取手机号
        phone_match = re.search(self.patterns['phone'], text)
        if phone_match:
            info['phone'] = phone_match.group(1)

        # 提取邮箱
        email_match = re.search(self.patterns['email'], text)
        if email_match:
            info['email'] = email_match.group(1)

        # 提取年龄
        age_match = re.search(self.patterns['age'], text)
        if age_match:
            info['age'] = int(age_match.group(1))

        # 提取性别
        gender_match = re.search(self.patterns['gender'], text)
        if gender_match:
            info['gender'] = gender_match.group(1)

        # 提取地点
        location_match = re.search(self.patterns['location'], text)
        if location_match:
            info['location'] = location_match.group(1).strip()

        # 提取工作经验年限
        exp_match = re.search(self.patterns['experience'], text)
        if exp_match:
            info['experience_years'] = int(exp_match.group(1))

        return info

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

        # 查找结束位置（下一个章节标题或文件结尾）
        section_names = [
            '教育背景', '教育经历', '工作经历', '工作经验', '项目经历',
            '专业技能', '技能专长', '项目经验', '自我介绍', '自我评价',
            'Education', 'Experience', 'Projects', 'Skills'
        ]

        for j in range(start_idx, len(lines)):
            line_stripped = lines[j].strip()
            # 遇到新章节标题（独立的行且包含关键词）
            for sn in section_names:
                # 跳过刚找到的关键词本身
                if sn in keywords:
                    continue
                if line_stripped == sn or line_stripped.startswith(sn + '：') or line_stripped.startswith(sn + ':'):
                    end_idx = j
                    return start_idx, end_idx

        return start_idx, end_idx

    def _extract_education(self, text: str) -> List[Dict]:
        """提取教育经历"""
        education = []
        start_idx, end_idx = self._find_section(text, self.education_keywords)

        if start_idx is None:
            return education

        lines = text.split('\n')
        section_text = '\n'.join(lines[start_idx:end_idx])

        # 解析每条教育经历
        # 时间范围模式：2019.09 - 2023.06 或 2019/09 - 2023/06
        time_pattern = r'(\d{4}[./]\d{1,2})\s*[-~至]\s*(\d{4}[./]\d{1,2}|至今)'

        # 按行分割，每行可能是一条教育经历
        for line in lines[start_idx:end_idx]:
            line = line.strip()
            if not line:
                continue

            edu = {}

            # 提取时间
            time_match = re.search(time_pattern, line)
            if time_match:
                edu['start_date'] = time_match.group(1)
                edu['end_date'] = time_match.group(2)

            # 提取学校
            schools = ['清华大学', '北京大学', '复旦大学', '上海交通大学', '浙江大学',
                      '中国科学技术大学', '南京大学', '武汉大学', '中山大学', '同济大学',
                      '北京航空航天大学', '北京邮电大学', '华中科技大学', '西安交通大学',
                      '哈尔滨工业大学', '中国人民大学', '华东师范大学', '南开大学',
                      '厦门大学', '天津大学', '中南大学', '四川大学', '电子科技大学',
                      '大连理工大学', '湖南大学', '重庆大学', '北京理工大学',
                      '东北大学', '兰州大学', '西北工业大学', '华南理工大学']
            for school in schools:
                if school in line:
                    edu['school'] = school
                    break

            # 提取学历
            degrees = ['博士', '硕士', '本科', '大专', '高中']
            for deg in degrees:
                if deg in line:
                    edu['degree'] = deg
                    break

            # 提取专业
            majors = ['计算机科学与技术', '软件工程', '电子信息工程', '通信工程',
                     '自动化', '机械工程', '数学', '物理学', '经济学', '金融学',
                     '管理学', '工商管理', '会计学', '信息安全', '人工智能',
                     '数据科学与大数据技术', '网络工程', '物联网工程']
            for major in majors:
                if major in line:
                    edu['major'] = major
                    break

            if edu:
                education.append(edu)

        return education

    def _extract_work_experience(self, text: str) -> List[Dict]:
        """提取工作经历"""
        work_experience = []
        start_idx, end_idx = self._find_section(text, self.work_keywords)

        if start_idx is None:
            return work_experience

        lines = text.split('\n')

        # 时间范围模式
        time_pattern = r'(\d{4}[./]\d{1,2})\s*[-~至]\s*(\d{4}[./]\d{1,2}|至今)'

        current_company = None
        current_work = {}

        for line in lines[start_idx:end_idx]:
            line = line.strip()
            if not line:
                continue

            # 检查是否是公司行（包含时间）
            time_match = re.search(time_pattern, line)
            if time_match:
                # 保存上一份工作
                if current_company:
                    work_experience.append(current_work)

                current_work = {
                    'start_date': time_match.group(1),
                    'end_date': time_match.group(2),
                    'company': '',
                    'position': '',
                    'description': []
                }

                # 提取公司名（时间之后的部分）
                after_time = line[time_match.end():].strip()
                if after_time:
                    current_work['company'] = after_time
                    current_company = after_time
            elif current_company:
                # 描述行
                current_work['description'].append(line)

        # 保存最后一份工作
        if current_work:
            work_experience.append(current_work)

        # 提取职位
        for work in work_experience:
            company_text = work['company']
            # 常见职位关键词
            positions = ['工程师', '架构师', '开发', '经理', '总监', '主管', '专员',
                        'Designer', 'Developer', 'Engineer', 'Manager', 'Architect']
            for pos in positions:
                if pos in company_text:
                    work['position'] = company_text
                    break

        return work_experience

    def _extract_project_experience(self, text: str) -> List[Dict]:
        """提取项目经历"""
        projects = []
        start_idx, end_idx = self._find_section(text, self.project_keywords)

        if start_idx is None:
            return projects

        lines = text.split('\n')

        # 时间范围模式
        time_pattern = r'(\d{4}[./]\d{1,2})\s*[-~至]\s*(\d{4}[./]\d{1,2}|至今)'

        current_project = {}

        for line in lines[start_idx:end_idx]:
            line = line.strip()
            if not line:
                continue

            # 检查是否是项目行（包含时间或项目名）
            time_match = re.search(time_pattern, line)
            if time_match or ('项目' in line and len(line) < 50):
                # 保存上一个项目
                if current_project and 'name' in current_project:
                    projects.append(current_project)

                current_project = {
                    'name': '',
                    'time': '',
                    'description': []
                }

                if time_match:
                    current_project['time'] = time_match.group(0)
                    after_time = line[time_match.end():].strip()
                    if after_time:
                        current_project['name'] = after_time
                elif '项目' in line:
                    # 尝试提取项目名
                    parts = line.split('：')
                    if len(parts) > 1:
                        current_project['name'] = parts[1].strip()
                    else:
                        current_project['name'] = line.strip()
            elif current_project:
                current_project['description'].append(line)

        # 保存最后一个项目
        if current_project and 'name' in current_project:
            projects.append(current_project)

        return projects


def parse_resume(text: str) -> Dict:
    """便捷函数：解析简历"""
    parser = ResumeParser()
    return parser.parse(text)


if __name__ == '__main__':
    # 测试
    test_resume = """
    姓名：张三
    电话：13800138000
    邮箱：zhangsan@email.com
    年龄：28
    性别：男
    地点：北京

    教育背景
    2019.09 - 2023.06 北京大学 计算机科学与技术 硕士
    2015.09 - 2019.06 清华大学 计算机科学与技术 本科

    工作经历
    2023.07 - 至今 字节跳动 高级后端工程师
    负责推荐系统后端开发，使用Go语言和Python
    熟练使用MySQL、Redis、Elasticsearch
    2021.07 - 2023.06 阿里巴巴 研发工程师
    参与电商平台开发，使用Java和Spring Boot
    项目经历
    智能推荐系统 2022.03 - 2023.06
    使用PythonTensorFlow构建推荐模型
    负责后端API开发，使用Gin框架和MySQL
    技能专长
    编程语言: Python, Java, Go, JavaScript
    后端框架: Django, Flask, Spring Boot, Gin
    数据库: MySQL, Redis, MongoDB, Elasticsearch
    工具: Git, Docker, Kubernetes, AWS
    机器学习: TensorFlow, PyTorch
    """

    result = parse_resume(test_resume)
    import json
    print(json.dumps(result, ensure_ascii=False, indent=2))
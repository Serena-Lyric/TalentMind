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
            'role': r'(?:求职意向|意向岗位|应聘岗位|求职岗位|目标岗位|期望职位)\s*[：:]\s*([^\n]{1,60})',
            'education_line': r'(?:最高学历|学历)\s*[：:]\s*([^\n]{1,60})',
        }

        # 教育经历标题
        self.education_keywords = ['教育背景', '教育经历', 'Education', '学历']
        # 工作经历标题
        self.work_keywords = ['工作经历', '工作经验', 'Professional Experience', '工作履历']
        # 项目经历标题
        self.project_keywords = ['项目经历', '项目经验', 'Projects']
        # 技能标题
        self.skill_keywords = ['技能专长', '专业技能', 'Skills', '技术技能', '技能']
        # 竞赛与荣誉标题
        self.honor_keywords = ['竞赛与荣誉', '获奖情况', '所获荣誉', '荣誉奖项', '竞赛获奖', '个人荣誉', '获奖经历', '奖项荣誉']
        # 自我评价标题
        self.self_keywords = ['自我评价', '个人评价', '个人总结', '自我简介', '自我描述', '个人优势']

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
            'honors': self._extract_honors(text),
            'self_evaluation': self._extract_self_evaluation(text),
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

        # 提取姓名（走 _extract_name，避免标题行/同行内容/带岗位后缀导致误取）
        name = self._extract_name(text)
        if name:
            info['name'] = name

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

        # 应届毕业生：没有明确年限数字时按 0 年/应届处理
        if 'experience_years' not in info and re.search(r'应届\s*(?:毕业生)?', text):
            info['experience_years'] = 0
            info['is_fresh_graduate'] = True

        # 提取求职意向/角色（常见标签，取到第一个标点为止）
        role_match = re.search(self.patterns['role'], text)
        if role_match:
            role = re.split(r'[，。；;|｜]', role_match.group(1).strip())[0].strip()
            if role:
                info['role'] = role[:40]

        # 兜底：直接标注的“学历：xxx”（没有教育背景章节时也能显示）
        edu_match = re.search(self.patterns['education_line'], text)
        if edu_match:
            val = edu_match.group(1).strip()
            if val:
                info['education'] = val

        return info

    _NAME_BLACKLIST = {'个人简历', '简历', '求职简历', '我的简历', '中文简历', '英文简历', 'Resume', 'CV'}
    _NAME_SUFFIX_RE = re.compile(r'[-—–·](?:高级|资深|初级|中级|实习|专家|研发|助理|后端|前端|算法|测试|数据|软件|系统|产品|运营|开发|AI|机器学习)?(?:工程师|开发工程师|架构师|设计师|分析师|研究员|经理|主管|专员|顾问|助理).*$')
    _ROLE_RE = re.compile(
        r'((?:高级|资深|初级|中级|实习|专家|研发|助理)*'
        r'(?:后端|前端|算法|测试|数据|软件|系统|产品|运营|开发|机器学习|Java|Python|Go|C\+\+|AI)?'
        r'(?:工程师|开发工程师|架构师|设计师|分析师|研究员|经理|主管|专员|顾问|助理|Engineer|Developer|Manager|Designer|Analyst|Scientist))')

    def _extract_name(self, text: str) -> str:
        """更稳的姓名提取：优先显式“姓名/name”标签，只取到空白/标点；无标签时跳过常见标题行。"""
        m = re.search(r'(?:姓名|name)\s*[：:]\s*([^\s，。；;|｜（(【]{1,20})', text, re.IGNORECASE)
        if m:
            raw = m.group(1).strip()
            if raw:
                raw = self._NAME_SUFFIX_RE.sub('', raw)
                raw = raw.rstrip('，。；、:：')
            if raw:
                return raw[:10]
        for line in text.split('\n'):
            s = line.strip()
            if not s or s in self._NAME_BLACKLIST:
                continue
            if re.fullmatch(r'[\u4e00-\u9fff·]{2,4}', s):
                return s
            if re.fullmatch(r"[A-Za-z][A-Za-z .'\-]{1,30}", s) and not re.search(r'(engineer|developer|manager|designer|analyst|scientist|resume|cv)\b', s, re.I):
                return s
        return ''

    def _split_company_position(self, text: str):
        """把“公司 职位”拆开，返回 (company, position)。"""
        text = (text or '').strip()
        m = self._ROLE_RE.search(text)
        if m and m.start() > 0:
            company = text[:m.start()].strip().strip(' -–—·|')
            position = text[m.start():].strip()
            return company, position
        return text, ''

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
            '竞赛与荣誉', '获奖情况', '所获荣誉', '获奖经历', '个人荣誉', '个人评价', '个人总结',
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
        role_hint = re.compile(r'(工程师|开发|架构|设计|产品|运营|分析师|分析|专员|主管|经理|总监|顾问|研究员|助理|测试|算法|前端|后端|Engineer|Developer|Manager|Designer|Analyst|Scientist)', re.I)
        _action_words = ('负责', '参与', '主导', '从事', '进行', '独立', '支持', '协助', '带领', '跟进', '配合', '推动', '维护', '协调', '撰写')

        def _finish():
            nonlocal current_work
            if current_work and any((current_work.get('company'), current_work.get('position'), current_work.get('description'))):
                work_experience.append(current_work)
            current_work = {}

        current_work = {}
        stage = 'idle'  # idle | after_header(等待公司行) | have_company(等职位行) | desc

        def _looks_like_role(line_text):
            if len(line_text) > 24:
                return False
            if line_text.startswith(_action_words):
                return False
            return bool(role_hint.search(line_text))

        for line in lines[start_idx:end_idx]:
            line = line.strip()
            if not line:
                continue

            # 检查是否是公司行（包含时间）
            time_match = re.search(time_pattern, line)
            if time_match:
                _finish()
                current_work = {
                    'start_date': time_match.group(1),
                    'end_date': time_match.group(2),
                    'company': '',
                    'position': '',
                    'description': []
                }
                # 提取公司名与职位（时间之后的部分，尽量拆分）
                after_time = line[time_match.end():].strip()
                if after_time:
                    company, position = self._split_company_position(after_time)
                    current_work['company'] = company
                    current_work['position'] = position
                    stage = 'have_company' if (company and not position) else ('desc' if position else 'after_header')
                else:
                    stage = 'after_header'
                continue

            # 非时间行：按状态填充公司/职位/描述
            if stage == 'after_header':
                company, position = self._split_company_position(line)
                current_work['company'] = company or line
                current_work['position'] = position
                stage = 'have_company' if (company and not position) else ('desc' if position else 'have_company')
            elif stage == 'have_company':
                if _looks_like_role(line):
                    current_work['position'] = line
                    stage = 'desc'
                else:
                    current_work['description'].append(line)
            else:
                current_work['description'].append(line)

        _finish()

        # 兜底：公司字段里若仍残留职位文本，再拆分一次
        for work in work_experience:
            if not work.get('position') and work.get('company'):
                company, position = self._split_company_position(work['company'])
                work['company'] = company
                if position:
                    work['position'] = position

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
                    else:
                        # 形如“项目名 2022.03-2022.09”：时间段在行尾，取行首为项目名
                        before_time = line[:time_match.start()].strip().strip(' -–—|：:')
                        if before_time:
                            current_project['name'] = before_time
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


    def _extract_honors(self, text: str) -> List[Dict]:
        """提取竞赛与荣誉：每行一条（可选时间 + 荣誉标题）。"""
        honors = []
        start_idx, end_idx = self._find_section(text, self.honor_keywords)
        if start_idx is None:
            return honors
        lines = text.split('\n')
        for raw in lines[start_idx:end_idx]:
            line = raw.strip().strip('·-–—')
            if not line:
                continue
            m = re.match(r'^((?:\d{4}(?:[./]\d{1,2})?)(?:\s*[-~至]\s*(?:\d{4}(?:[./]\d{1,2})?))?)', line)
            time = ''
            title = line
            if m:
                time = m.group(1)
                title = line[m.end():].strip().lstrip('：: ').strip()
            if not title:
                continue
            honors.append({'time': time, 'title': title})
        return honors

    def _extract_self_evaluation(self, text: str) -> str:
        """提取自我评价段落（多行合并为一段）。"""
        start_idx, end_idx = self._find_section(text, self.self_keywords)
        if start_idx is None:
            return ''
        lines = text.split('\n')
        parts = []
        for raw in lines[start_idx:end_idx]:
            line = raw.strip()
            if not line:
                continue
            parts.append(line.rstrip('。；;'))
        return ('；'.join(parts)).strip() + ('。' if parts else '')

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
"""
测试数据生成器
生成多样化的简历和岗位数据，用于测试匹配功能
"""

import random
import json
from typing import List, Dict


# 姓名库
NAMES = ['张三', '李四', '王五', '赵六', '钱七', '孙八', '周九', '吴十',
         '陈晨', '刘洋', '杨明', '黄磊', '徐鹏', '孙浩', '马超', '朱杰',
         '胡伟', '郭靖', '何宇', '林峰', '高建', '罗勇', '宋凯', '韩磊']

# 地点库
LOCATIONS = ['北京', '上海', '广州', '深圳', '杭州', '南京', '苏州', '成都', '武汉', '西安', '天津', '重庆']

# 学校库
SCHOOLS = ['清华大学', '北京大学', '复旦大学', '上海交通大学', '浙江大学',
          '中国科学技术大学', '南京大学', '武汉大学', '中山大学', '同济大学',
          '北京航空航天大学', '北京邮电大学', '华中科技大学', '西安交通大学',
          '哈尔滨工业大学', '中国人民大学', '华东师范大学', '南开大学']

# 公司库
COMPANIES = ['字节跳动', '阿里巴巴', '腾讯', '百度', '美团', '京东',
            '拼多多', '网易', '快手', '滴滴', '哔哩哔哩', '小红书',
            '蔚来', '理想汽车', '小鹏汽车', '米哈游', '商汤科技', '旷视科技']

# 技能库
SKILLS = {
    'languages': ['Python', 'Java', 'JavaScript', 'Go', 'C++', 'C#', 'Rust', 'TypeScript', 'PHP', 'Ruby'],
    'frontend': ['React', 'Vue', 'Angular', 'Next.js', 'Node.js', 'TypeScript'],
    'backend': ['Django', 'Flask', 'Spring Boot', 'Gin', 'Express', 'NestJS', 'FastAPI'],
    'database': ['MySQL', 'PostgreSQL', 'MongoDB', 'Redis', 'Elasticsearch'],
    'cloud_devops': ['AWS', '阿里云', 'Docker', 'Kubernetes', 'Jenkins', 'GitLab CI'],
    'ai_ml': ['TensorFlow', 'PyTorch', 'Keras', 'Scikit-learn', 'Pandas', 'NLP']
}

# 职位库
POSITIONS = ['后端工程师', '前端工程师', '全栈工程师', '算法工程师',
            '架构师', '技术专家', '研发工程师', '高级工程师']

# 项目名库
PROJECT_NAMES = ['电商平台', '推荐系统', '搜索系统', '支付系统', '用户中心',
                '数据分析平台', '智能客服', '风控系统', '内容管理系统', '即时通讯系统']


def generate_resume(index: int = 0) -> str:
    """生成一份简历"""
    name = random.choice(NAMES)
    location = random.choice(LOCATIONS)
    age = random.randint(22, 40)
    experience = random.randint(1, 15)
    school = random.choice(SCHOOLS)
    company = random.choice(COMPANIES)
    position = random.choice(POSITIONS)

    # 随机选择技能组合
    langs = random.sample(SKILLS['languages'], random.randint(2, 4))
    backends = random.sample(SKILLS['backend'], random.randint(1, 3))
    dbs = random.sample(SKILLS['database'], random.randint(1, 3))
    cloud = random.sample(SKILLS['cloud_devops'], random.randint(1, 2))

    resume = f"""
姓名：{name}
电话：138{random.randint(10000000, 99999999)}
邮箱：{name.lower()}@email.com
年龄：{age}
性别：{'男' if index % 2 == 0 else '女'}
地点：{location}
工作年限：{experience}年

教育背景
{2019 - experience}.09 - {2019 - experience + 4}.06 {school} 计算机科学与技术 本科

工作经历
2023.01 - 至今 {company} {position}
负责后端系统开发和维护
使用{langs[0]}和{backends[0]}进行开发
熟练使用{', '.join(dbs)}，有高并发经验
熟悉{', '.join(cloud)}

项目经验
{PROJECT_NAMES[index % len(PROJECT_NAMES)]} {2022 - index % 3}.01 - {2023 - index % 3}.12
使用{langs[0]} + {backends[0]}开发后端服务
使用{', '.join(dbs[:2])}作为数据存储
日均处理请求量达100万+

技能专长
编程语言: {', '.join(langs)}
后端框架: {', '.join(backends)}
数据库: {', '.join(dbs)}
工具: {', '.join(cloud)}
"""
    return resume


def generate_job(index: int = 0) -> str:
    """生成一个岗位描述"""
    position = random.choice(POSITIONS)
    location = random.choice(LOCATIONS)
    exp_required = random.choice(['1-3年', '3-5年', '5-10年', '不限'])
    edu_required = random.choice(['本科及以上', '硕士及以上', '大专及以上'])

    # 根据岗位类型生成不同的技能要求
    if '算法' in position:
        required_skills = random.sample(SKILLS['ai_ml'], 3) + random.sample(SKILLS['languages'], 2)
        bonus = random.sample(['Kaggle竞赛', '顶会论文', '开源项目', '大数据处理'], 2)
    elif '前端' in position:
        required_skills = random.sample(SKILLS['frontend'], 3) + ['JavaScript', 'TypeScript']
        bonus = random.sample(['小程序开发', '跨平台开发', '性能优化', '可视化'], 2)
    else:
        required_skills = random.sample(SKILLS['languages'], 2) + \
                         random.sample(SKILLS['backend'], 2) + \
                         random.sample(SKILLS['database'], 2)
        bonus = random.sample(['高并发', '分布式', '微服务', '开源贡献'], 2)

    job = f"""
【{position}】

工作地点：{location}
薪资：{random.randint(15, 40)}K-{random.randint(25, 50)}K·14薪
经验要求：{exp_required}
学历要求：{edu_required}

职位描述：
负责公司核心业务系统开发，参与技术架构设计与优化。

任职要求：
1. {random.randint(2, 5)}年以上后端开发经验
2. 熟练使用{required_skills[0]}或{required_skills[1]}
3. 熟悉{', '.join(required_skills[2:5])}
4. 熟悉Linux操作系统，了解Docker
5. 具备良好的编码习惯和团队协作能力

加分项：
- {bonus[0]}
- {bonus[1]}
"""
    return job


def generate_dataset(num_resumes: int = 10, num_jobs: int = 5) -> Dict:
    """
    生成测试数据集

    Args:
        num_resumes: 简历数量
        num_jobs: 岗位数量

    Returns:
        包含简历和岗位的数据集
    """
    resumes = [generate_resume(i) for i in range(num_resumes)]
    jobs = [generate_job(i) for i in range(num_jobs)]

    return {
        'resumes': resumes,
        'jobs': jobs,
        'total_resumes': num_resumes,
        'total_jobs': num_jobs
    }


def save_test_data(output_dir: str = '.'):
    """生成并保存测试数据"""
    dataset = generate_dataset(num_resumes=10, num_jobs=5)

    # 保存简历
    with open(f'{output_dir}/test_resumes.json', 'w', encoding='utf-8') as f:
        json.dump(dataset['resumes'], f, ensure_ascii=False, indent=2)

    # 保存岗位
    with open(f'{output_dir}/test_jobs.json', 'w', encoding='utf-8') as f:
        json.dump(dataset['jobs'], f, ensure_ascii=False, indent=2)

    # 保存完整数据集
    with open(f'{output_dir}/test_dataset.json', 'w', encoding='utf-8') as f:
        json.dump(dataset, f, ensure_ascii=False, indent=2)

    print(f"[OK] 测试数据生成完成！")
    print(f"   - 简历: {dataset['total_resumes']} 份")
    print(f"   - 岗位: {dataset['total_jobs']} 个")
    print(f"   - 文件: test_resumes.json, test_jobs.json, test_dataset.json")


def load_test_data(input_dir: str = '.') -> Dict:
    """加载测试数据"""
    with open(f'{input_dir}/test_dataset.json', 'r', encoding='utf-8') as f:
        return json.load(f)


def print_sample_data():
    """打印样本数据"""
    print("=" * 60)
    print("📄 样本简历:")
    print("=" * 60)
    sample_resume = generate_resume(0)
    print(sample_resume)

    print("\n" + "=" * 60)
    print("📋 样本岗位:")
    print("=" * 60)
    sample_job = generate_job(0)
    print(sample_job)


if __name__ == '__main__':
    # 打印样本
    print_sample_data()

    # 生成测试数据
    print("\n\n生成测试数据集...")
    save_test_data()
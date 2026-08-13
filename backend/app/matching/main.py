"""
人岗匹配系统 - 主程序
演示完整的简历解析、技能提取、岗位匹配流程
"""

import json
import sys
import io
# 设置控制台编码
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from app.matching.matcher import ResumeJobMatcher, match_resume_job, batch_match
from app.matching.generate_test_data import generate_dataset, save_test_data, print_sample_data


# 简单的图标映射
ICONS = {
    'success': '[OK]',
    'error': '[X]',
    'match': '[Match]',
    'resume': '[Resume]',
    'job': '[Job]',
    'target': '[Target]',
    'check': '[v]',
    'cross': '[x]',
    'tip': '[Tip]',
    'chart': '[Stats]',
    'speak': '[Say]',
    'search': '[Search]',
    'box': '[Box]',
    'rocket': '[Run]',
    'trophy': '[Top]',
    'arrow': '->',
    'star': '*',
}


def print_match_result(result: dict, indent: int = 0):
    """格式化打印匹配结果"""
    prefix = "  " * indent

    if not result.get('success', False):
        print(f"{prefix}{ICONS['error']} 匹配失败: {result.get('error', '未知错误')}")
        return

    print(f"\n{'='*60}")
    print(f"{prefix}{ICONS['match']} 人岗匹配报告")
    print(f"{'='*60}")

    # 简历信息
    resume_info = result.get('resume_info', {})
    print(f"\n{prefix}{ICONS['resume']} 简历信息:")
    print(f"{prefix}  - 姓名: {resume_info.get('name', '未知')}")
    print(f"{prefix}  - 工作经验: {resume_info.get('experience_years', 0)} 年")
    print(f"{prefix}  - 期望地点: {resume_info.get('location', '未知')}")

    # 岗位信息
    job_info = result.get('job_info', {})
    print(f"\n{prefix}{ICONS['job']} 岗位信息:")
    print(f"{prefix}  - 职位: {job_info.get('title', '未知')}")
    print(f"{prefix}  - 工作地点: {job_info.get('location', '未知')}")
    print(f"{prefix}  - 经验要求: {job_info.get('experience_required', '不限')}")
    print(f"{prefix}  - 学历要求: {job_info.get('education_required', '不限')}")

    # 匹配结果
    skills_match = result.get('skills_match', {})
    print(f"\n{prefix}{ICONS['target']} 匹配结果:")
    print(f"{prefix}  - 综合得分: {skills_match.get('total_score', 0)} 分")
    print(f"{prefix}  - 技能匹配率: {skills_match.get('match_rate', 0)}%")
    print(f"{prefix}  - 已匹配技能: {skills_match.get('matched_count', 0)} / {skills_match.get('job_required_count', 0)}")

    # 匹配的技能
    matched = skills_match.get('matched_skills', [])
    if matched:
        print(f"\n{prefix}{ICONS['check']} 已匹配技能:")
        for skill in matched:
            print(f"{prefix}  - {skill}")

    # 缺失的技能
    unmatched = skills_match.get('unmatched_job_skills', [])
    if unmatched:
        print(f"\n{prefix}{ICONS['cross']} 缺失技能:")
        for skill in unmatched:
            print(f"{prefix}  - {skill}")

    # 简历额外技能
    extra = skills_match.get('resume_extra_skills', [])
    if extra:
        print(f"\n{prefix}{ICONS['tip']} 简历额外技能:")
        for skill in extra[:5]:
            print(f"{prefix}  - {skill}")
        if len(extra) > 5:
            print(f"{prefix}  ... 还有 {len(extra) - 5} 项")

    # 各类别得分
    category_scores = skills_match.get('category_scores', {})
    if category_scores:
        print(f"\n{prefix}{ICONS['chart']} 技能类别得分:")
        for category, scores in category_scores.items():
            print(f"{prefix}  - {category}: {scores.get('score', 0)}% ({scores.get('matched', 0)}/{scores.get('total', 0)})")

    # 推荐建议
    print(f"\n{prefix}{ICONS['speak']} 推荐建议:")
    print(f"{prefix}  {result.get('recommendation', '')}")


def demo_single_match():
    """演示单次匹配"""
    print("\n" + "="*60)
    print(f"{ICONS['search']} 演示：单次简历-岗位匹配")
    print("="*60)

    # 简历
    resume = """
姓名：王小明
电话：13800138000
邮箱：wangxm@email.com
年龄：28
性别：男
地点：北京
工作年限：5年

教育背景
2015.09 - 2019.06 北京大学 计算机科学与技术 本科

工作经历
2021.07 - 至今 字节跳动 高级后端工程师
负责推荐系统后端开发
使用Go语言和Python进行微服务开发
熟练使用MySQL、Redis、Elasticsearch
熟悉Kubernetes和Docker

项目经验
智能推荐系统 2022.03 - 2023.06
使用Go + Gin框架构建高性能API
使用MySQL和Redis进行数据存储
日均处理请求超100万

技能专长
编程语言: Python, Go, Java
后端框架: Gin, Flask, Django
数据库: MySQL, Redis, Elasticsearch
工具: Docker, Kubernetes, Git
"""

    # 岗位
    job = """
【高级后端工程师】

工作地点：北京
经验要求：3-5年
学历要求：本科

任职要求：
1. 3年以上后端开发经验
2. 熟练使用Go或Python语言
3. 熟悉Gin、Flask或Django框架
4. 掌握MySQL、Redis，有高并发经验
5. 熟悉Linux、Docker、K8s

加分项：
- 有分布式系统经验
- 熟悉Elasticsearch
- 有机器学习经验
"""

    result = match_resume_job(resume, job)
    print_match_result(result)


def demo_test_data_matching():
    """使用测试数据进行匹配"""
    print("\n" + "="*60)
    print(f"{ICONS['search']} 演示：使用测试数据进行批量匹配")
    print("="*60)

    # 生成测试数据
    dataset = generate_dataset(num_resumes=5, num_jobs=3)

    print(f"\n生成数据: {len(dataset['resumes'])} 份简历, {len(dataset['jobs'])} 个岗位")

    # 选取一份简历和三个岗位进行匹配
    resume = dataset['resumes'][0]

    print("\n" + "-"*60)
    print(f"{ICONS['resume']} 测试简历 (第1份):")
    print("-"*60)
    # 只打印前几行
    resume_lines = resume.strip().split('\n')[:10]
    for line in resume_lines:
        print(f"  {line}")
    print("  ...")

    print("\n" + "-"*60)
    print(f"匹配结果:")
    print("-"*60)

    # 与每个岗位匹配
    for i, job in enumerate(dataset['jobs']):
        result = match_resume_job(resume, job)
        skills_match = result.get('skills_match', {})
        score = skills_match.get('total_score', 0)
        print(f"\n岗位 {i+1}: 得分 {score} 分 - {result.get('recommendation', '')}")


def demo_batch_match():
    """演示批量匹配"""
    print("\n" + "="*60)
    print(f"{ICONS['search']} 演示：批量匹配 - 找出最佳候选人")
    print("="*60)

    # 简历列表
    resumes = [
        """
姓名：候选人A
地点：北京
工作年限：3年

技能专长
Python, Java, Go, MySQL, Redis, Django, Flask, Docker
""",
        """
姓名：候选人B
地点：上海
工作年限：5年

技能专长
Python, Go, MySQL, Redis, Elasticsearch, Gin, Kubernetes
""",
        """
姓名：候选人C
地点：深圳
工作年限：2年

技能专长
Java, Spring Boot, MySQL, Docker
"""
    ]

    # 岗位
    job = """
【高级后端工程师】

工作地点：北京
经验要求：3-5年

任职要求：
1. 熟练使用Python或Go语言
2. 熟悉Django或Gin框架
3. 掌握MySQL、Redis
4. 熟悉Docker、Kubernetes
"""

    print(f"\n有 {len(resumes)} 位候选人竞争1个岗位")
    print("岗位要求: Python/Go + Django/Gin + MySQL/Redis + Docker/Kubernetes")

    # 批量匹配
    results = batch_match(resumes, [job])

    print("\n排名结果:")
    print("-"*60)
    for i, result in enumerate(results):
        name = result.get('resume_info', {}).get('name', '未知')
        score = result.get('skills_match', {}).get('total_score', 0)
        match_rate = result.get('skills_match', {}).get('match_rate', 0)
        matched_skills = result.get('skills_match', {}).get('matched_skills', [])

        print(f"\n第 {i+1} 名: {name}")
        print(f"  得分: {score} 分 (匹配率: {match_rate}%)")
        print(f"  匹配技能: {', '.join(matched_skills)}")


def demo_full_workflow():
    """演示完整工作流"""
    print("\n" + "="*70)
    print(f"{ICONS['rocket']} 人岗匹配系统 - 完整工作流演示")
    print("="*70)

    # 1. 生成测试数据
    print(f"\n{ICONS['box']} 第1步: 生成测试数据")
    dataset = generate_dataset(num_resumes=8, num_jobs=4)
    print(f"   已生成 {len(dataset['resumes'])} 份简历和 {len(dataset['jobs'])} 个岗位")

    # 2. 选择一个岗位
    target_job = dataset['jobs'][1]
    print(f"\n{ICONS['job']} 第2步: 选择目标岗位")

    # 解析岗位信息
    from app.matching.job_parser import parse_job
    job_info = parse_job(target_job)
    print(f"   职位: {job_info.get('title', '未知')}")
    print(f"   地点: {job_info.get('location', '未知')}")
    print(f"   所需技能: {', '.join(job_info.get('skills', [])[:8])}")

    # 3. 对所有简历进行匹配
    print(f"\n{ICONS['search']} 第3步: 对所有简历进行匹配")
    results = []
    for i, resume in enumerate(dataset['resumes']):
        result = match_resume_job(resume, target_job)
        result['resume_index'] = i
        results.append(result)

    # 4. 按得分排序
    results.sort(key=lambda x: x.get('skills_match', {}).get('total_score', 0), reverse=True)

    # 5. 显示排名
    print(f"\n{ICONS['trophy']} 候选人排名:")
    print("-"*70)

    for rank, result in enumerate(results[:5], 1):
        resume_info = result.get('resume_info', {})
        skills_match = result.get('skills_match', {})

        name = resume_info.get('name', f'简历{rank}')
        location = resume_info.get('location', '未知')
        score = skills_match.get('total_score', 0)
        match_rate = skills_match.get('match_rate', 0)
        matched = skills_match.get('matched_count', 0)
        total = skills_match.get('job_required_count', 0)
        recommendation = result.get('recommendation', '')

        print(f"\n第{rank}名: {name} (地点: {location})")
        print(f"  得分: {score} 分 | 匹配率: {match_rate}% | 技能: {matched}/{total}")
        print(f"  建议: {recommendation}")


def main():
    """主函数"""
    print("\n" + ICONS['star'] * 30)
    print("欢迎使用人岗匹配系统！")
    print(ICONS['star'] * 30)

    # 运行所有演示
    demo_single_match()
    try:
        input("\n\n按回车继续...")
    except:
        pass

    demo_test_data_matching()
    try:
        input("\n\n按回车继续...")
    except:
        pass

    demo_batch_match()
    try:
        input("\n\n按回车继续...")
    except:
        pass

    demo_full_workflow()

    print("\n\n" + "="*70)
    print(f"{ICONS['success']} 演示完成！")
    print("="*70)
    print("\n你可以使用以下方式运行自己的匹配:")
    print("  1. 修改代码中的 resume 和 job 变量")
    print("  2. 从文件读取简历和岗位信息")
    print("  3. 调用 batch_match() 进行批量匹配")
    print("\n生成了测试数据文件: test_dataset.json, test_resumes.json, test_jobs.json")


if __name__ == '__main__':
    main()
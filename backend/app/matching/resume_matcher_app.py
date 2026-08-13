"""
人岗匹配系统 - 文件版
支持直接解析 PDF/Word 简历文件并匹配岗位
"""

import os
import sys
import io
import json
import argparse

# 设置控制台编码
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from app.matching.file_parser import ResumeFileParser, parse_resume_file, batch_parse_resume_files
from app.matching.resume_parser import ResumeParser
from app.matching.job_parser import JobParser
from app.matching.matcher import ResumeJobMatcher, match_resume_job, batch_match
from app.matching.generate_test_data import generate_dataset


# 简单的图标
ICONS = {
    'file': '[File]',
    'pdf': '[PDF]',
    'word': '[Word]',
    'parse': '[Parse]',
    'match': '[Match]',
    'ok': '[OK]',
    'error': '[X]',
    'star': '*',
}


class ResumeMatcherApp:
    """人岗匹配应用"""

    def __init__(self):
        self.file_parser = ResumeFileParser()
        self.resume_parser = ResumeParser()
        self.job_parser = JobParser()
        self.matcher = ResumeJobMatcher()

    def parse_resume_file(self, file_path: str, show_preview: bool = True) -> dict:
        """
        解析简历文件

        Args:
            file_path: 简历文件路径
            show_preview: 是否显示预览

        Returns:
            解析结果字典
        """
        print(f"\n{ICONS['file']} 正在解析简历文件: {os.path.basename(file_path)}")

        # 解析文件
        text = parse_resume_file(file_path)

        if not text:
            return {
                'success': False,
                'error': '文件解析失败或内容为空',
                'file': file_path
            }

        if show_preview:
            # 显示前500字符预览
            preview = text[:500] + "..." if len(text) > 500 else text
            print(f"\n--- 文件内容预览 ---")
            print(preview)
            print("-" * 30)

        # 提取信息
        resume_info = self.resume_parser.parse(text)

        return {
            'success': True,
            'file': file_path,
            'text': text,
            'extracted_info': resume_info
        }

    def match_resume_file_to_jobs(self, resume_file: str, job_texts: list, job_names: list = None) -> list:
        """
        将简历文件与多个岗位匹配

        Args:
            resume_file: 简历文件路径
            job_texts: 岗位描述列表
            job_names: 岗位名称列表（可选）

        Returns:
            匹配结果列表
        """
        # 解析简历文件
        parse_result = self.parse_resume_file(resume_file, show_preview=False)

        if not parse_result['success']:
            print(f"{ICONS['error']} 简历解析失败: {parse_result['error']}")
            return []

        resume_text = parse_result['text']

        # 与每个岗位匹配
        results = []
        for i, job_text in enumerate(job_texts):
            job_name = job_names[i] if job_names and i < len(job_names) else f"岗位{i+1}"

            result = match_resume_job(resume_text, job_text)
            result['job_name'] = job_name
            result['job_index'] = i
            results.append(result)

            # 显示结果
            skills_match = result.get('skills_match', {})
            score = skills_match.get('total_score', 0)
            print(f"  {job_name}: {score} 分 - {result.get('recommendation', '')}")

        # 按得分排序
        results.sort(key=lambda x: x.get('skills_match', {}).get('total_score', 0), reverse=True)

        return results

    def match_resume_to_job_files(self, resume_file: str, job_files: list) -> list:
        """
        将简历文件与岗位文件列表匹配

        Args:
            resume_file: 简历文件路径
            job_files: 岗位描述文件列表

        Returns:
            匹配结果列表
        """
        # 读取岗位文件
        job_texts = []
        job_names = []

        for job_file in job_files:
            with open(job_file, 'r', encoding='utf-8') as f:
                job_texts.append(f.read())
            job_names.append(os.path.basename(job_file))

        return self.match_resume_file_to_jobs(resume_file, job_texts, job_names)

    def interactive_mode(self):
        """交互模式"""
        print("\n" + ICONS['star'] * 30)
        print("人岗匹配系统 - 交互模式")
        print(ICONS['star'] * 30)

        # 步骤1：选择或输入简历
        print("\n--- 步骤1: 选择简历 ---")
        print("请选择简历来源:")
        print("  1. 输入文本简历")
        print("  2. 解析PDF简历文件")
        print("  3. 解析Word简历文件")

        choice = input("请选择 (1/2/3): ").strip()

        resume_text = ""
        if choice == '1':
            print("\n请输入简历文本 (输入完成后按 Ctrl+D 或 Ctrl+Z 结束):")
            try:
                resume_text = sys.stdin.read()
            except:
                resume_text = input("请粘贴简历文本: ").strip()
        elif choice in ['2', '3']:
            file_path = input("请输入文件路径: ").strip().strip('"')
            if os.path.exists(file_path):
                try:
                    resume_text = parse_resume_file(file_path)
                    print(f"{ICONS['ok']} 成功解析文件")
                except Exception as e:
                    print(f"{ICONS['error']} 解析失败: {e}")
                    return
            else:
                print(f"{ICONS['error']} 文件不存在: {file_path}")
                return
        else:
            print("无效选择")
            return

        if not resume_text:
            print("简历内容为空")
            return

        # 步骤2：选择或输入岗位
        print("\n--- 步骤2: 选择岗位 ---")
        print("请选择岗位来源:")
        print("  1. 输入文本岗位描述")
        print("  2. 解析岗位文件")

        choice2 = input("请选择 (1/2): ").strip()
        job_text = ""

        if choice2 == '1':
            print("\n请输入岗位描述:")
            job_text = input().strip()
        elif choice2 == '2':
            job_file = input("请输入岗位文件路径: ").strip().strip('"')
            if os.path.exists(job_file):
                with open(job_file, 'r', encoding='utf-8') as f:
                    job_text = f.read()
            else:
                print(f"{ICONS['error']} 文件不存在")
                return
        else:
            print("无效选择")
            return

        # 步骤3：匹配
        print("\n--- 步骤3: 匹配结果 ---")
        result = match_resume_job(resume_text, job_text)

        # 显示结果
        print(f"\n综合得分: {result['skills_match']['total_score']} 分")
        print(f"技能匹配率: {result['skills_match']['match_rate']}%")
        print(f"\n推荐建议: {result['recommendation']}")

        matched = result['skills_match'].get('matched_skills', [])
        if matched:
            print(f"\n已匹配技能: {', '.join(matched)}")

        unmatched = result['skills_match'].get('unmatched_job_skills', [])
        if unmatched:
            print(f"缺失技能: {', '.join(unmatched)}")

    def demo_file_parsing(self):
        """演示文件解析功能"""
        print("\n" + "=" * 60)
        print(f"{ICONS['parse']} 演示：简历文件解析")
        print("=" * 60)

        print(f"\n支持的格式: {self.file_parser.supported_formats}")

        # 检查是否有测试文件
        test_dir = "test_resumes"
        if not os.path.exists(test_dir):
            os.makedirs(test_dir)
            print(f"\n已创建测试目录: {test_dir}")
            print("请在该目录下放置 PDF 或 Word 格式的简历文件")
            print("然后运行:")
            print(f"  python -c \"from resume_matcher_app import *; app = ResumeMatcherApp(); app.demo_parse_directory('{test_dir}')\"")

        # 显示目录内容
        files = os.listdir(test_dir) if os.path.exists(test_dir) else []
        if files:
            print(f"\n测试目录中的文件:")
            for f in files:
                print(f"  - {f}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='人岗匹配系统')
    parser.add_argument('command', nargs='?', help='命令: parse, match, interactive')
    parser.add_argument('--resume', '-r', help='简历文件路径')
    parser.add_argument('--job', '-j', help='岗位文件路径或文本')
    parser.add_argument('--jobs', nargs='*', help='多个岗位文件')

    args = parser.parse_args()

    app = ResumeMatcherApp()

    if args.command == 'parse':
        # 解析简历文件
        if args.resume:
            result = app.parse_resume_file(args.resume)
            if result['success']:
                print(f"\n{ICONS['ok']} 解析成功!")
                print(f"提取的技能: {result['extracted_info'].get('skills', [])}")
            else:
                print(f"\n{ICONS['error']} 解析失败: {result.get('error')}")
        else:
            print("请指定简历文件: --resume <file>")

    elif args.command == 'match':
        # 匹配简历和岗位
        if args.resume and args.job:
            results = app.match_resume_to_job_files(args.resume, [args.job])
            if results:
                print("\n匹配完成!")
        else:
            print("请指定简历和岗位文件")

    elif args.command == 'interactive' or not args.command:
        # 交互模式
        app.interactive_mode()

    else:
        print(f"未知命令: {args.command}")
        print("可用命令: parse, match, interactive")


if __name__ == '__main__':
    # 如果直接运行，显示演示
    app = ResumeMatcherApp()
    app.demo_file_parsing()

    print("\n\n使用说明:")
    print("=" * 60)
    print("1. 交互模式: python resume_matcher_app.py interactive")
    print("2. 解析简历: python resume_matcher_app.py parse --resume <file>")
    print("3. 匹配岗位: python resume_matcher_app.py match --resume <file> --job <file>")
    print("=" * 60)
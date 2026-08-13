"""
文件解析器
支持解析 PDF、Word (.doc/.docx) 格式的简历文件
"""

import os
import re
from typing import Optional
from pathlib import Path


class FileParser:
    """文件解析器基类"""

    def parse(self, file_path: str) -> str:
        """解析文件并返回文本内容"""
        raise NotImplementedError


class PDFParser(FileParser):
    """PDF文件解析器"""

    def __init__(self):
        self.pdfplumber = None
        try:
            import pdfplumber
            self.pdfplumber = pdfplumber
        except ImportError:
            print("[警告] pdfplumber 未安装，请运行: pip install pdfplumber")

    def parse(self, file_path: str) -> str:
        """解析PDF文件"""
        if self.pdfplumber is None:
            raise ImportError("pdfplumber 未安装")

        text = ""
        try:
            with self.pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
            return text
        except Exception as e:
            print(f"[错误] 解析PDF文件失败: {e}")
            return ""


class DOCXParser(FileParser):
    """Word (.docx) 文件解析器"""

    def __init__(self):
        self.docx = None
        try:
            from docx import Document
            self.docx_module = Document
        except ImportError:
            print("[警告] python-docx 未安装，请运行: pip install python-docx")

    def parse(self, file_path: str) -> str:
        """解析docx文件"""
        if self.docx_module is None:
            raise ImportError("python-docx 未安装")

        text = ""
        try:
            doc = self.docx_module(file_path)
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"

            # 提取表格中的文本
            for table in doc.tables:
                for row in table.rows:
                    for cell in row.cells:
                        text += cell.text + " "
                    text += "\n"
            return text
        except Exception as e:
            print(f"[错误] 解析docx文件失败: {e}")
            return ""


class DOCParser(FileParser):
    """Word (.doc) 文件解析器 - 需要 antiword 或 textract"""

    def __init__(self):
        self.textract = None
        # 尝试导入 textract
        try:
            import textract
            self.textract = textract
        except ImportError:
            # 尝试使用 antiword
            self.has_antiword = self._check_antiword()

    def _check_antiword(self) -> bool:
        """检查antiword是否可用"""
        import subprocess
        try:
            subprocess.run(['antiword', '-h'], capture_output=True, check=True)
            return True
        except:
            return False

    def parse(self, file_path: str) -> str:
        """解析doc文件"""
        # 优先使用 textract
        if self.textract:
            try:
                text = self.textract.process(file_path)
                return text.decode('utf-8', errors='ignore') if isinstance(text, bytes) else str(text)
            except Exception as e:
                print(f"[警告] textract解析失败: {e}")

        # 尝试使用 antiword
        if self.has_antiword:
            try:
                import subprocess
                result = subprocess.run(
                    ['antiword', '-w', '0', file_path],
                    capture_output=True,
                    text=True
                )
                return result.stdout
            except Exception as e:
                print(f"[警告] antiword解析失败: {e}")

        # 回退：使用 mammoth 尝试转换
        try:
            import mammoth
            with open(file_path, 'rb') as doc_file:
                result = mammoth.convert_to_text(doc_file)
                return result.value
        except ImportError:
            print("[警告] mammoth 未安装，请运行: pip install mammoth")
        except Exception as e:
            print(f"[警告] mammoth解析失败: {e}")

        print("[错误] 无法解析 .doc 文件，请安装 textract 或 antiword")
        return ""


class ResumeFileParser:
    """简化的简历文件解析器"""

    def __init__(self):
        self.parsers = {
            '.pdf': PDFParser(),
            '.docx': DOCXParser(),
            '.doc': DOCParser(),
        }

        # 支持的格式
        self.supported_formats = list(self.parsers.keys())

    def is_supported(self, file_path: str) -> bool:
        """检查文件格式是否支持"""
        ext = Path(file_path).suffix.lower()
        return ext in self.supported_formats

    def parse(self, file_path: str) -> str:
        """
        解析简历文件

        Args:
            file_path: 简历文件路径

        Returns:
            解析后的文本内容
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")

        ext = Path(file_path).suffix.lower()

        if ext not in self.parsers:
            raise ValueError("不支持的文件格式: {}, 支持的格式: {}".format(ext, ', '.join(self.supported_formats)))

        parser = self.parsers[ext]
        text = parser.parse(file_path)

        # 清理文本
        text = self._clean_text(text)

        return text

    def _clean_text(self, text: str) -> str:
        """清理提取的文本"""
        if not text:
            return ""

        # 移除多余的空白字符
        lines = text.split('\n')
        cleaned_lines = []

        for line in lines:
            # 去除首尾空白
            line = line.strip()
            # 跳过空行
            if line:
                cleaned_lines.append(line)

        # 合并行
        text = '\n'.join(cleaned_lines)

        # 修复常见的PDF解析问题
        # 合并被断开的行（短行后面跟着非短行，可能是被PDF错误地断开了）
        lines = text.split('\n')
        merged_lines = []

        for i, line in enumerate(lines):
            if not line:
                merged_lines.append(line)
                continue

            # 如果当前行很短（可能是单词被断开），尝试与下一行合并
            if len(line) < 20 and i < len(lines) - 1:
                next_line = lines[i + 1]
                if next_line and not next_line.startswith(' ') and len(next_line) > 20:
                    merged_lines.append(line + ' ' + next_line)
                    continue

            merged_lines.append(line)

        return '\n'.join(merged_lines)

    def get_file_info(self, file_path: str) -> dict:
        """获取文件信息"""
        path = Path(file_path)

        return {
            'filename': path.name,
            'extension': path.suffix.lower(),
            'size': os.path.getsize(file_path),
            'supported': self.is_supported(file_path)
        }


def parse_resume_file(file_path: str) -> str:
    """便捷函数：解析简历文件"""
    parser = ResumeFileParser()
    return parser.parse(file_path)


def batch_parse_resume_files(directory: str, extensions: list = None) -> dict:
    """
    批量解析目录下的简历文件

    Args:
        directory: 目录路径
        extensions: 要处理的文件扩展名列表，默认为 ['.pdf', '.docx', '.doc']

    Returns:
        字典，key为文件名，value为解析后的文本
    """
    if extensions is None:
        extensions = ['.pdf', '.docx', '.doc']

    parser = ResumeFileParser()
    results = {}

    path = Path(directory)
    if not path.is_dir():
        raise ValueError(f"不是有效的目录: {directory}")

    for file_path in path.iterdir():
        if file_path.is_file() and file_path.suffix.lower() in extensions:
            try:
                print(f"正在解析: {file_path.name}")
                text = parser.parse(str(file_path))
                results[file_path.name] = text
                print(f"  -> 成功，提取 {len(text)} 字符")
            except Exception as e:
                print(f"  -> 失败: {e}")
                results[file_path.name] = None

    return results


if __name__ == '__main__':
    # 测试
    parser = ResumeFileParser()

    print("=== 简历文件解析器 ===")
    print(f"支持的格式: {parser.supported_formats}")

    # 检查依赖
    print("\n=== 依赖检查 ===")
    try:
        import pdfplumber
        print("[OK] pdfplumber")
    except ImportError:
        print("[X] pdfplumber 未安装")

    try:
        from docx import Document
        print("[OK] python-docx")
    except ImportError:
        print("[X] python-docx 未安装")

    try:
        import textract
        print("[OK] textract")
    except ImportError:
        print("[X] textract 未安装")

    try:
        import mammoth
        print("[OK] mammoth")
    except ImportError:
        print("[X] mammoth 未安装")
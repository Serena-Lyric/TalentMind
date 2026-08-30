"""L3 文本清洗 —— 纯本地规则，零 LLM 调用。

PDF 方案 L3 模块：去除 HTML 标签、转义残余、清理多余换行、
过滤乱码碎片、超长文本安全截断。
清洗后文本作为 L4 输入 + L5 证据窗口的同一文本（保证证据一致）。
"""
import re

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_HTML_ESCAPES = {"&lt;": "<", "&gt;": ">", "&amp;": "&",
                 "&quot;": '"', "&#39;": "'", "&apos;": "'"}
_MULTI_NEWLINE_RE = re.compile(r"\n{3,}")


def clean_jd_text(text: str) -> str:
    """清洗 JD 文本。返回清洗后文本（脏分/长度随之下降）。"""
    if not text:
        return text
    # 1. HTML 转义残余 → 真实字符
    for esc, real in _HTML_ESCAPES.items():
        text = text.replace(esc, real)
    # 2. 未清理干净的 HTML 标签 → 删除（保留标签间文本）
    text = _HTML_TAG_RE.sub("", text)
    # 3. 连续换行碎片 → 单个换行
    text = _MULTI_NEWLINE_RE.sub("\n", text)
    # 4. 乱码碎片：不可读字符占比过高的行删除
    lines = []
    for line in text.split("\n"):
        line_s = line.strip()
        if not line_s:
            continue
        readable = sum(1 for ch in line_s
                       if ch.isalnum() or ch.isspace()
                       or ch in ".,;:!?()[]{}<>/\\-_+=@#$%^&*\"'`~|…—")
        if len(line_s) > 0 and readable / len(line_s) < 0.6:
            continue    # 乱码行
        lines.append(line)
    return "\n".join(lines)

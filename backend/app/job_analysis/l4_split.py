"""L4 分流器 —— 纯文本规则分流，零 LLM 调用、零 token 开销。

长度超标 OR 脏分达标 → deepseek-v4-pro（稳定）；其余 → deepseek-v4-flash（快）。
两者都在官方 DeepSeek 端点（实测 11s/批 vs go 107s/批）。
"""
from __future__ import annotations
from dataclasses import dataclass

from .config import (L4_SPLIT_TEXT_LEN_THRESHOLD,
                    L4_SPLIT_DIRTY_SCORE_THRESHOLD)

MODEL_L4_FLASH = "deepseek-v4-flash"
MODEL_L4_KIMI = "deepseek-v4-pro"

# HTML 转义残余 / 标签 / 连续换行碎片
_HTML_ESCAPE_FRAGS = ("&lt;", "&gt;", "&amp;", "&quot;")
_HTML_TAG_FRAGS = ("<div>", "<p>", "<br>", "<span>", "<div ", "<p ", "<span ")


@dataclass
class SplitResult:
    target_model: str
    text_len: int
    dirty_score: int


def calc_dirty_score(text: str) -> int:
    """脏分：每命中一条 +1，不重复计数。"""
    score = 0
    if any(f in text for f in _HTML_ESCAPE_FRAGS):
        score += 1
    if "\n\n\n" in text:
        score += 1
    if any(f in text for f in _HTML_TAG_FRAGS):
        score += 1
    return score


def calc_split_result(text: str) -> SplitResult:
    """分流判定：长度超标 OR 脏分达标 → pro；其余 → flash。"""
    text_len = len(text)
    dirty = calc_dirty_score(text)
    target = MODEL_L4_FLASH
    if text_len > L4_SPLIT_TEXT_LEN_THRESHOLD \
            or dirty >= L4_SPLIT_DIRTY_SCORE_THRESHOLD:
        target = MODEL_L4_KIMI
    return SplitResult(target_model=target, text_len=text_len,
                       dirty_score=dirty)

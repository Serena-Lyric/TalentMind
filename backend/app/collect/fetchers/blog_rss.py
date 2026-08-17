"""技术博客 RSS 采集（D39 多源）：文章标题/描述按 skill_dict 匹配 -> signal（source=blog）。

技能匹配严格限定 skill_dict_seed.json 的 canonical/alias（反幻觉，不自由命名）。
"""
from __future__ import annotations
import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

import httpx

RSS_FEEDS = [
    ("infoq", "https://www.infoq.cn/feed"),
    ("oschina", "https://www.oschina.net/news/rss"),
    ("juejin", "https://juejin.cn/rss"),
]

_SKILL_TERMS: set[str] | None = None


@dataclass
class Signal:
    skill_or_job: str
    signal_type: str
    metric: str
    value: float
    source: str = "blog"


def _load_terms() -> set[str]:
    """加载 skill_dict 全部 canonical + alias（小写）。"""
    global _SKILL_TERMS
    if _SKILL_TERMS is None:
        p = Path(__file__).resolve().parents[2] / "skills" / "skill_dict_seed.json"
        entries = json.loads(p.read_text(encoding="utf-8"))
        terms: set[str] = set()
        for e in entries:
            canonical = e.get("canonical", "").lower()
            if canonical:
                terms.add(canonical)
            for a in e.get("aliases", []):
                a = a.lower()
                if a:
                    terms.add(a)
        _SKILL_TERMS = terms
    return _SKILL_TERMS


def _term_pattern(term: str) -> re.Pattern:
    """英文词用词边界（避免 ai 命中 said），中文/短词直接子串。"""
    if term and term[0].isascii() and term[-1].isascii():
        return re.compile(r"\b" + re.escape(term) + r"\b")
    return re.compile(re.escape(term))


def _matchable(term: str) -> bool:
    """英文 term 需 >=3 字符（避免 go/c 等误匹配）；中文 >=2。"""
    if term and term[0].isascii():
        return len(term) >= 3
    return len(term) >= 2


def extract_signals_from_text(text: str, terms: set[str] | None = None) -> dict[str, int]:
    """统计文本中命中 skill_dict 词条的次数。"""
    terms = terms or _load_terms()
    low = text.lower()
    counts: dict[str, int] = {}
    for term in terms:
        if not _matchable(term):
            continue
        if _term_pattern(term).search(low):
            counts[term] = counts.get(term, 0) + len(_term_pattern(term).findall(low))
    return counts


def parse_rss(xml_text: str, terms: set[str] | None = None) -> list[Signal]:
    """解析 RSS XML（兼容带命名空间），按标题+描述统计技能提及。"""
    terms = terms or _load_terms()
    root = ET.fromstring(xml_text)
    counts: dict[str, int] = {}
    for item in root.iter():
        if not item.tag.endswith("item"):
            continue
        title = desc = ""
        for child in item.iter():
            if child.tag.endswith("title") and not title:
                title = child.text or ""
            if child.tag.endswith("description") and not desc:
                desc = child.text or ""
        text = title + "\n" + desc
        for term, c in extract_signals_from_text(text, terms).items():
            counts[term] = counts.get(term, 0) + c
    return [Signal(skill_or_job=t, signal_type="tech_trend",
                   metric="mention_count", value=float(c), source="blog")
            for t, c in sorted(counts.items())]


def fetch_blog_signals(client: httpx.Client,
                       feeds: list[tuple[str, str]] | None = None) -> list[Signal]:
    """抓取多个 RSS 源，聚合技能提及信号。"""
    feeds = feeds or RSS_FEEDS
    out: list[Signal] = []
    for name, url in feeds:
        try:
            resp = client.get(url)
        except httpx.HTTPError as e:
            print(f"[blog_rss] {name} 请求失败: {e}")
            continue
        if resp.status_code != 200:
            print(f"[blog_rss] {name} HTTP {resp.status_code} 跳过")
            continue
        try:
            out.extend(parse_rss(resp.text))
        except ET.ParseError as e:
            print(f"[blog_rss] {name} XML 解析失败: {e}")
            continue
    return out

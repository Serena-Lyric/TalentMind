"""GitHub Trending 页面采集（D39 多源）：语言/主题热度 -> signal（source=github）。

合规：只抓公开 Trending 页面（无需 token），限速由调用方控制。
"""
from __future__ import annotations
from dataclasses import dataclass

import httpx
from bs4 import BeautifulSoup

LANGUAGES = ["python", "java", "go", "javascript", "typescript", "rust"]
TRENDING_URL = "https://github.com/trending/{lang}"


@dataclass
class Signal:
    skill_or_job: str
    signal_type: str
    metric: str
    value: float
    source: str = "github"


def parse_trending_html(html: str, language: str) -> list[Signal]:
    """解析 Trending 页面：返回语言 repo_count + 主题 mention_count。"""
    soup = BeautifulSoup(html, "html.parser")
    articles = soup.select("article.Box-row")
    topics: dict[str, int] = {}
    for article in articles:
        for a in article.select('a[href^="/topics/"]'):
            t = a.get_text(strip=True)
            if t:
                t = t.lower()
                topics[t] = topics.get(t, 0) + 1
    signals = [
        Signal(skill_or_job=language, signal_type="tech_trend",
               metric="repo_count", value=float(len(articles)), source="github"),
    ]
    for topic, cnt in sorted(topics.items()):
        signals.append(Signal(skill_or_job=topic, signal_type="tech_trend",
                              metric="mention_count", value=float(cnt), source="github"))
    return signals


def fetch_trending_signals(client: httpx.Client,
                           languages: list[str] | None = None) -> list[Signal]:
    """抓取多个语言 Trending 页面，聚合语言/主题信号。"""
    languages = languages or LANGUAGES
    out: list[Signal] = []
    for lang in languages:
        try:
            resp = client.get(TRENDING_URL.format(lang=lang), params={"since": "daily"})
        except httpx.HTTPError as e:
            print(f"[trending] {lang} 请求失败: {e}")
            continue
        if resp.status_code != 200:
            print(f"[trending] {lang} HTTP {resp.status_code} 跳过")
            continue
        out.extend(parse_trending_html(resp.text, lang))
    return out

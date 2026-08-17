"""D39 多源信号采集：fetcher 纯函数单测（不联网、不写库）。"""
import pytest

from app.collect.fetchers.trending import parse_trending_html
from app.collect.fetchers.blog_rss import parse_rss, extract_signals_from_text, _load_terms


TRENDING_HTML = """<html><body>
<article class="Box-row">
  <h2 class="h3 lh-condensed"><a href="/openai/rag-app">rag-app</a></h2>
  <a href="/topics/python">python</a>
  <a href="/topics/llm">llm</a>
</article>
<article class="Box-row">
  <h2 class="h3 lh-condensed"><a href="/x/agent">agent</a></h2>
  <a href="/topics/llm">llm</a>
</article>
</body></html>"""

RSS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
<item><title>Python 3.13 发布与 RAG 实践</title><description>LLM 应用开发经验</description></item>
<item><title>敏捷开发团队转型</title><description>agile 方法论落地</description></item>
</channel>
</rss>"""


def test_parse_trending_html_language_and_topics():
    signals = parse_trending_html(TRENDING_HTML, "python")
    by_key = {(s.skill_or_job, s.metric): s for s in signals}
    assert by_key[("python", "repo_count")].value == 2.0
    assert by_key[("llm", "mention_count")].value == 2.0
    assert by_key[("python", "mention_count")].value == 1.0
    assert all(s.source == "github" for s in signals)


def test_load_terms_size():
    terms = _load_terms()
    assert len(terms) >= 285  # 至少覆盖 285 canonical


def test_parse_rss_counts_skill_mentions():
    terms = _load_terms()
    signals = parse_rss(RSS_XML, terms)
    by_key = {(s.skill_or_job, s.metric): s for s in signals}
    # python（canonical）与 agile（canonical + 别名"敏捷"）必定在词典中
    assert by_key[("python", "mention_count")].value >= 1.0
    assert by_key[("agile", "mention_count")].value >= 1.0
    assert all(s.source == "blog" for s in signals)


def test_extract_short_english_terms_ignored():
    counts = extract_signals_from_text("go go go python", {"go", "python"})
    assert "python" in counts
    assert "go" not in counts  # 英文短词(2字符)不参与匹配，避免噪声
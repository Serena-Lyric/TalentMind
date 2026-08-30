"""联网新词查证层 —— 不确定区防误杀（PyPI/npm 存在性查证，异步+缓存）。

触发条件（由调用方控制）：LLM 低置信 + 词典零命中 + 自学习库也没有。
只在这些罕见路径上联网；网络失败自动降级，不阻塞管道。
"""
from __future__ import annotations
import asyncio
import re

import httpx

# 常见词/虚词跳过（不做候选）
KNOWN_SKIP = {
    "the", "and", "for", "you", "our", "your", "with", "will", "can",
    "are", "was", "were", "not", "this", "that", "have", "has", "had",
    "from", "they", "them", "their", "work", "team", "role", "job",
    "position", "experience", "years", "plus", "etc", "like", "good",
    "strong", "must", "should", "would", "could", "including", "include",
    "we", "us", "about", "apply", "join", "need", "looking", "remote",
    "hybrid", "onsite", "full", "time", "part", "salary", "equity",
    "benefits", "company", "companies", "engineer", "engineering",
    "developer", "development", "software", "senior", "junior", "lead",
    "manager", "management", "platform", "systems", "system", "data",
}

_TERM_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9+#\-]{1,30}[a-zA-Z0-9]")


def extract_candidate_terms(text: str, known_terms: set[str],
                            max_terms: int = 5) -> list[str]:
    """抽取可能的新技术词：混合大小写、缩写或含 -/. 的标识符，
    排除已知词、常见词、行尾句点。"""
    cands: list[str] = []
    seen: set[str] = set()
    for m in _TERM_RE.finditer(text):
        w = m.group(0)
        low = w.lower().rstrip(".")
        if len(low) < 4 or low in KNOWN_SKIP or low in known_terms:
            continue
        if low in seen:
            continue
        # 技术标识符特征：含 -/./+ 或驼峰（原大小写判断）或 全大写缩写
        is_tech_like = (("-" in low or "." in low or "+" in low)
                        or (w[0].isupper() and any(c.islower() for c in w[1:]))
                        or w.isupper())
        if is_tech_like:
            seen.add(low)
            cands.append(low)
            if len(cands) >= max_terms:
                break
    return cands


class TermLookup:
    """PyPI/npm 存在性查证。免费、无 key、JSON、异步并发、内存缓存。"""

    def __init__(self, client: httpx.AsyncClient | None = None,
                 timeout: float = 3.0):
        self._own = client is None
        self._client = client
        self._cache: dict[str, bool | None] = {}
        self._timeout = timeout

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self._timeout),
                follow_redirects=True)
        return self._client

    async def close(self) -> None:
        if self._own and self._client is not None:
            await self._client.aclose()

    async def exists(self, term: str) -> bool | None:
        """True=存在 False=不存在 None=查不到（网络失败）。"""
        if term in self._cache:
            return self._cache[term]
        client = self._get_client()
        urls = [f"https://pypi.org/pypi/{term}/json",
                f"https://registry.npmjs.org/{term}"]
        try:
            r1, r2 = await asyncio.gather(
                client.get(urls[0]), client.get(urls[1]),
                return_exceptions=True)
        except Exception:
            self._cache[term] = None
            return None
        found = False
        if isinstance(r1, httpx.Response) and r1.status_code == 200:
            found = True
        if isinstance(r2, httpx.Response) and r2.status_code == 200:
            found = True
        if isinstance(r1, Exception) and isinstance(r2, Exception):
            self._cache[term] = None
            return None
        self._cache[term] = found
        return found

    async def verify_many(self, terms: list[str]) -> list[str]:
        """并发查证多个词，返回确认存在的词列表。"""
        results = await asyncio.gather(
            *[self.exists(t) for t in terms], return_exceptions=True)
        found = [t for t, r in zip(terms, results) if r is True]
        return found

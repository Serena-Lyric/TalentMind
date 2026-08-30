"""L1 BM25 预筛 —— 零依赖本地向量召回层。

用 skill_dict_seed 的 canonical+aliases 作 query 词表，对 JD 打分。
只筛 linkedin 段（hn 段全是技术岗直通）。
"""
from __future__ import annotations
import json
import math
import re
from pathlib import Path

from .config import PREFILTER_THRESHOLD


def _tokenize(text: str) -> list[str]:
    """英文按词切，中文按双字滑窗切（粗糙但够用）。"""
    toks = re.findall(r"[a-z0-9+#.]+", text.lower())
    cjk = re.findall(r"[一-鿿]+", text)
    for seg in cjk:
        if len(seg) >= 2:
            toks += [seg[i:i + 2] for i in range(len(seg) - 1)]
    return toks


class Bm25Prefilter:
    def __init__(self, query_terms: list[str] | None = None,
                 threshold: float = PREFILTER_THRESHOLD,
                 k1: float = 1.5, b: float = 0.75):
        self.query_terms = set(t.lower() for t in (query_terms or []))
        self.threshold = threshold
        self.k1, self.b = k1, b
        self.doc_freq: dict[str, int] = {}
        self.doc_len: list[int] = []
        self.n_docs = 0

    def fit(self, corpus: list[str]) -> "Bm25Prefilter":
        self.doc_freq.clear()
        self.doc_len.clear()
        for doc in corpus:
            toks = _tokenize(doc)
            self.doc_len.append(len(toks))
            for t in set(toks):
                self.doc_freq[t] = self.doc_freq.get(t, 0) + 1
        self.n_docs = len(corpus)
        return self

    def _idf(self, term: str) -> float:
        df = self.doc_freq.get(term, 0)
        return math.log(1 + (self.n_docs - df + 0.5) / (df + 0.5))

    def score(self, text: str) -> float:
        toks = _tokenize(text)
        if not toks:
            return 0.0
        tf: dict[str, int] = {}
        for t in toks:
            tf[t] = tf.get(t, 0) + 1
        dl = len(toks)
        dl_avg = (sum(self.doc_len) / max(self.n_docs, 1)
                  if self.doc_len else 1)
        score = 0.0
        for t in tf:
            if t not in self.query_terms:
                continue
            idf = self._idf(t)
            score += idf * tf[t] * (self.k1 + 1) / (
                tf[t] + self.k1 * (1 - self.b + self.b * dl / max(dl_avg, 1)))
        return score

    def should_pass(self, text: str) -> bool:
        return self.score(text) >= self.threshold


def load_query_terms(skill_dict_path: Path) -> list[str]:
    if not skill_dict_path.exists():
        return ["python", "java", "docker", "kubernetes", "aws", "react",
                "frontend", "backend", "机器学习", "数据分析", "云原生"]
    data = json.load(open(skill_dict_path, encoding="utf-8"))
    terms: list[str] = []
    for item in data:
        terms.append(item["canonical"])
        terms.extend(item.get("aliases", []))
    return terms


def build_prefilter(skill_dict_path: Path, hn_corpus: list[str]
                    ) -> Bm25Prefilter:
    """fit 语料 = hn 纯技术岗文本（正样本）。"""
    pf = Bm25Prefilter(query_terms=load_query_terms(skill_dict_path))
    return pf.fit(hn_corpus)

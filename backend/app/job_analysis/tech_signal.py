"""客观技术信号层 —— 新一代信息技术判定的可验证证据。

LLM 语义判断给出"像不像"，本模块给出"原文里有什么"：
- newgen_hits: JD 命中新一代技能词典（skill_dict category）
- legacy_hits: JD 命中传统 IT 词表（helpdesk/桌面运维等）
- trend_hits: JD 命中实时趋势信号（signal_snapshot）

verdict_for() 把两层判断合成最终结论：
- LLM relevant + 客观命中 → pass
- LLM 拒绝 + 无客观命中 → reject
- 两层冲突（LLM 说相关但零命中 / LLM 拒绝但有强命中）→ manual
"""
from __future__ import annotations
import json
import re
from pathlib import Path

# 传统 IT 词表（新一代的"排除集"）
LEGACY_TERMS = {
    "helpdesk", "help desk", "desktop support", "it support",
    "windows xp", "windows 7", "windows 8", "microsoft office",
    "printer", "printer setup", "network administrator", "网管",
    "桌面运维", "it运维", "erp", "crm administrator", "sap basis",
    "sharepoint", "exchange server", "active directory",
}

# skill_dict category 中属"新一代信息技术"的分类
NEWGEN_CATEGORIES = {
    "AI/机器学习", "大数据/云", "软件工程", "编程语言",
    "前端技术", "后端框架", "DevOps/运维", "数据库", "专业领域",
}


class TechSignalScorer:
    def __init__(self, newgen_terms: set[str], legacy_terms: set[str],
                 trend_terms: set[str]):
        self.newgen = newgen_terms
        self.legacy = legacy_terms
        self.trend = trend_terms

    def score(self, text: str) -> dict:
        low = text.lower()
        ng = sum(1 for t in self.newgen if _term_in(t, low))
        lg = sum(1 for t in self.legacy if _term_in(t, low))
        tr = sum(1 for t in self.trend if _term_in(t, low))
        return {"newgen_hits": ng, "legacy_hits": lg, "trend_hits": tr}


def _term_in(term: str, text_lower: str) -> bool:
    # 词边界匹配；含空格或中文的词用子串
    if re.search(r"[\s一-鿿]", term):
        return term in text_lower
    return bool(re.search(rf"(?<![a-z0-9+#.]){re.escape(term)}(?![a-z0-9+#.-])",
                          text_lower))


def build_scorer(skill_dict_path: Path,
                 signal_path: Path | None = None,
                 learned_terms: set[str] | None = None) -> TechSignalScorer:
    newgen: set[str] = set()
    if skill_dict_path.exists():
        data = json.load(open(skill_dict_path, encoding="utf-8"))
        for item in data:
            if item.get("category") in NEWGEN_CATEGORIES:
                newgen.add(item["canonical"].lower())
                for a in item.get("aliases", []):
                    newgen.add(a.lower())
    # 自学习词回灌：管道往批发现的新词（skill_candidates.json）
    if learned_terms:
        for t in learned_terms:
            newgen.add(t.lower())
    trend: set[str] = set()
    if signal_path and signal_path.exists():
        sig = json.load(open(signal_path, encoding="utf-8"))
        trend = {s["skill_or_job"].lower() for s in sig}
    return TechSignalScorer(newgen_terms=newgen,
                            legacy_terms=LEGACY_TERMS,
                            trend_terms=trend)


def load_learned_terms(candidates_path: Path | None = None) -> set[str]:
    """从自学习候选文件读入往批发现的词典外新词。"""
    if candidates_path is None:
        from config import DATA_DIR
        candidates_path = DATA_DIR / "skill_candidates.json"
    if not candidates_path.exists():
        return set()
    try:
        data = json.load(open(candidates_path, encoding="utf-8"))
        return {str(t).strip().lower() for t in data if str(t).strip()}
    except (json.JSONDecodeError, OSError):
        return set()


def verdict_for(llm_relevant: bool, llm_conf: float,
                score: dict) -> str:
    """合成最终判定（全自动，召回优先）。

    实测教训（hn50）：真实 JD 常用通用语言（"fullstack engineering"）
    不列具体技能名 → 词典零命中。因此客观信号不做"必要条件"，
    只做：① 误杀救回（LLM 拒绝但强命中）② 传统 IT 否决（legacy 命中多）。

    矩阵：
    - LLM relevant + conf >= 0.7 → pass（LLM 主导，信号作参考记录）
    - LLM relevant + conf < 0.7 → 有客观命中(>=1) 或 legacy=0 且弱命中→pass
      否则 reject
    - LLM 拒绝 + newgen+trend >= 3 → pass（救回误杀）
    - LLM 拒绝 + 其他 → reject
    - legacy >= 3 且 newgen=0 且 trend=0 → reject（传统 IT 否决）
    """
    obj_hits = score["newgen_hits"] + score["trend_hits"]
    if llm_relevant and llm_conf >= 0.7:
        # 高置信相关：除非纯传统 IT 证据（legacy 多且零新一代命中）
        if score["legacy_hits"] >= 3 and obj_hits == 0:
            return "reject"
        return "pass"
    if llm_relevant and llm_conf < 0.7:
        # 低置信相关：有任一客观新一代命中则放行（召回优先）
        return "pass" if obj_hits >= 1 else "reject"
    if not llm_relevant and obj_hits >= 3:
        return "pass"          # 救回 LLM 误杀
    return "reject"


def auto_resolve_low_confidence(is_relevant: bool, confidence: float,
                                score: dict) -> str:
    """LLM 低置信（<0.7）的全自动裁决：有任一客观命中 → pass，否则 reject。"""
    obj_hits = score["newgen_hits"] + score["trend_hits"]
    if is_relevant and obj_hits >= 1:
        return "pass"
    return "reject"


def rescue_verdict_with_new_terms(found_terms: list[str] | None) -> str:
    """联网新词查证结果 → 救回判定。
    至少 1 个新词确认真实存在 → pass（新兴技术岗位）；否则 reject。
    """
    if found_terms and len(found_terms) >= 1:
        return "pass"
    return "reject"

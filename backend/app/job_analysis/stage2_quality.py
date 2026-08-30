"""模型2 —— 质量评分（含锚定校准示例）。"""
import asyncio
from .config import SLOT_POOLS, QUALITY_PASS, QUALITY_REJECT
from .llm import LLMClient
from .models import JdRecord, QualityResult, QualityDimensions, QualityFlags

QUALITY_SYSTEM = """You are a JD quality evaluator. Score each JD across 5 dimensions (0-1), then compute an overall quality score.

Anchor references (calibrate your scoring against these):

◆ Score ~0.90 (HIGH QUALITY):
  "负责公司AI中台核心模块的设计与开发，包括模型训练平台、推理引擎优化和特征工程框架。要求: 精通Python, 熟悉PyTorch/TensorFlow, 3年以上ML工程经验, 有分布式训练经验。参与百亿参数级模型训练与部署。"
  → completeness:0.92 clarity:0.90 tech_depth:0.88 freshness:0.90 originality:0.88

◆ Score ~0.65 (MEDIUM QUALITY):
  "招AI开发工程师，负责AI相关模块开发维护。要求: 熟悉Python，了解机器学习，有项目经验优先。"
  → completeness:0.55 clarity:0.50 tech_depth:0.55 freshness:0.65 originality:0.70

◆ Score ~0.35 (LOW QUALITY):
  "招聘Java开发。要求: 熟悉Java。"
  → completeness:0.25 clarity:0.30 tech_depth:0.20 freshness:0.40 originality:0.45

Scoring rules:
- completeness: Are duties, requirements, experience fully specified?
- clarity: Are technical requirements specific (framework+version?), not vague ("熟悉常用技术")?
- tech_depth: Real technical work, not buzzword lists?
- freshness: Current tech stack? Penalize deprecated tech (Python 2, Hadoop 1.x, AngularJS 1.x)
- originality: Original? Penalize obvious template copies (placeholder text, identical phrasing across JD)

Overall quality = weighted average (0.25*completeness + 0.20*clarity + 0.25*tech_depth + 0.15*freshness + 0.15*originality), adjust ±0.05 for special circumstances."""


def build_quality_prompt(record: JdRecord, text: str | None = None) -> str:
    text = text if text is not None else record.raw_text[:3000]
    return f"""Score this JD's quality.

Also detect:
- stale_tech: deprecated/outdated technology mentioned (if any)
- copied_pattern: signs of template copying (if any)
- skill_inflation: unreasonably long skill list >15 items (if any)

---
job_title: {record.job_title}
raw_text: {text}
---

Output JSON:
{{"quality": 0-1, "dimensions": {{"completeness":0-1, "clarity":0-1, "tech_depth":0-1, "freshness":0-1, "originality":0-1}}, "flags": {{...or null}}, "weak_points": "specific issues"}}"""


QUALITY_SCHEMA = {
    "type": "object",
    "properties": {
        "quality": {"type": "number", "minimum": 0, "maximum": 1},
        "dimensions": {
            "type": "object",
            "properties": {
                "completeness": {"type": "number"},
                "clarity": {"type": "number"},
                "tech_depth": {"type": "number"},
                "freshness": {"type": "number"},
                "originality": {"type": "number"},
            },
            "required": ["completeness", "clarity", "tech_depth",
                         "freshness", "originality"],
        },
        "flags": {
            "type": ["object", "null"],
            "properties": {
                "stale_tech": {"type": "string"},
                "copied_pattern": {"type": "string"},
                "skill_inflation": {"type": "string"},
            },
        },
        "weak_points": {"type": "string"},
    },
    "required": ["quality", "dimensions", "weak_points"],
}


def parse_quality_response(jd_id: int, response: dict, model: str) -> QualityResult:
    quality = response.get("quality", 0.5)
    dims = response.get("dimensions", {})
    flags_raw = response.get("flags") or {}

    # 质量层不再拒绝：只打分（分数作为合并权重参考）。
    # L2 相关性是唯一筛选闸门——只要是新一代信息技术岗位，无论质量高低全部收集。
    verdict = "pass"

    return QualityResult(
        jd_id=jd_id,
        quality=quality,
        dimensions=QualityDimensions(**dims) if dims else QualityDimensions(
            completeness=0, clarity=0, tech_depth=0, freshness=0, originality=0,
        ),
        flags=QualityFlags(**flags_raw) if flags_raw else None,
        weak_points=response.get("weak_points", ""),
        verdict=verdict,
        model=model,
    )


def apply_cross_source(quality: float, cross_source: bool) -> float:
    """多源交叉验证标记：quality 上浮至不低于 0.85（对齐数据包规则）。"""
    return max(quality, 0.85) if cross_source else quality


# ── 方案 A：L3 纯规则质量打分（零 LLM 调用）──
# 规则分替代 LLM 评分，作为合并权重参考。
# 质量分 = 基础分(文本长度+技能命中) + cross_source 上浮 + 原有 quality 列

def rule_score(record: JdRecord, cross_source: bool = False) -> float:
    """规则打分（0-1）：基于可观测数据，零 LLM 调用。

    组成：
    - 基础分：min(0.8, len(text)/5000*0.3 + skill_hits*0.15) 上限 0.8
    - 数据自带 quality 列占 0.2
    - cross_source 上浮至不低于 0.85
    """
    text = record.raw_text
    text_len_score = min(0.6, len(text) / 5000 * 0.3)
    skill_hits = sum(1 for w in SKILL_PROBE_WORDS if w in text.lower())
    skill_score = min(0.2, skill_hits * 0.03)
    base = min(0.8, text_len_score + skill_score)
    raw_quality = max(0.0, min(1.0, record.quality))
    score = base * 0.8 + raw_quality * 0.2
    if cross_source:
        score = max(score, 0.85)
    return round(score, 3)


# 技能探针词（规则打分的技能命中检测，取自 skill_dict 高频类别）
SKILL_PROBE_WORDS = {
    "python", "java", "javascript", "typescript", "go", "rust", "c++",
    "sql", "docker", "kubernetes", "k8s", "aws", "azure", "gcp",
    "react", "vue", "angular", "node", "terraform", "ci/cd", "git",
    "linux", "machine learning", "deep learning", "llm", "rag",
    "data science", "data engineering", "analytics", "spark", "kafka",
    "microservices", "cloud", "api", "devops", "sre", "security",
    "embedded", "iot", "区块链", "机器学习", "深度学习", "数据分析",
}


def build_rule_quality_result(record: JdRecord,
                              cross_source: bool = False) -> QualityResult:
    """构建规则质量结果（永不拒绝，只打分）。"""
    score = rule_score(record, cross_source)
    text = record.raw_text
    # dimensions 用可观测值填充（不再 0.5 占位）
    text_len_score = min(0.6, len(text) / 5000 * 0.3)
    skill_hits = sum(1 for w in SKILL_PROBE_WORDS if w in text.lower())
    return QualityResult(
        jd_id=record.id,
        quality=score,
        dimensions=QualityDimensions(
            completeness=min(1.0, len(text) / 4000),
            clarity=0.5 + text_len_score / 2,
            tech_depth=min(1.0, skill_hits * 0.1),
            freshness=record.quality,
            originality=record.quality,
        ),
        weak_points="rule-based score (zero LLM)",
        verdict="pass",
        model="rule",
    )


async def run_stage2(
    records: list[JdRecord],
    client: LLMClient | None = None,
    cross_source_ids: set[int] | None = None,
) -> tuple[list[JdRecord], list[QualityResult]]:
    """L3 规则质量打分（零 LLM 调用）：全部 pass，分数供合并权重。"""
    cross_ids = cross_source_ids or set()
    all_results: list[QualityResult] = []
    for record in records:
        all_results.append(build_rule_quality_result(
            record, cross_source=record.id in cross_ids))
    passed = [r for r, res in zip(records, all_results)
              if res.verdict == "pass"]
    return passed, all_results

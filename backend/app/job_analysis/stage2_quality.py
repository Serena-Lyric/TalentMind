"""模型2 —— 质量评分（含锚定校准示例）。"""
from app.job_analysis.config import MODEL_STAGE2, QUALITY_PASS, QUALITY_REJECT, BATCH_SIZE
from app.job_analysis.llm import call_llm_batch
from app.job_analysis.models import JdRecord, QualityResult, QualityDimensions, QualityFlags

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


def build_quality_prompt(record: JdRecord) -> str:
    return f"""Score this JD's quality.

Also detect:
- stale_tech: deprecated/outdated technology mentioned (if any)
- copied_pattern: signs of template copying (if any)
- skill_inflation: unreasonably long skill list >15 items (if any)

---
job_title: {record.job_title}
raw_text: {record.raw_text[:3000]}
duties: {record.duties[:1000]}
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

    if quality >= QUALITY_PASS:
        verdict = "pass"
    elif quality < QUALITY_REJECT:
        verdict = "reject"
    else:
        verdict = "manual"

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


async def run_stage2(
    records: list[JdRecord],
    model: str = "",
) -> tuple[list[JdRecord], list[QualityResult]]:
    model = model or MODEL_STAGE2
    prompts = [build_quality_prompt(r) for r in records]
    all_results: list[QualityResult] = []

    for i in range(0, len(prompts), BATCH_SIZE):
        batch_records = records[i:i + BATCH_SIZE]
        batch_prompts = prompts[i:i + BATCH_SIZE]
        responses = await call_llm_batch(
            batch_prompts, model, QUALITY_SCHEMA, system=QUALITY_SYSTEM,
        )

        for record, resp in zip(batch_records, responses):
            if "_error" in resp:
                all_results.append(QualityResult(
                    jd_id=record.id, quality=0,
                    dimensions=QualityDimensions(
                        completeness=0, clarity=0, tech_depth=0,
                        freshness=0, originality=0,
                    ),
                    weak_points=f"API error: {resp['_error']}",
                    verdict="manual", model=model,
                ))
            else:
                all_results.append(
                    parse_quality_response(record.id, resp, model))

    passed = [r for r, res in zip(records, all_results) if res.verdict == "pass"]
    return passed, all_results

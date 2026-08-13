"""模型3 —— 结构化提取（LLM 输出每个 skill 的 confidence；D31：候选限定 skill_dict）。"""
import json
from app.job_analysis.config import MODEL_STAGE3, BATCH_SIZE, MAX_RETRY, SKILL_DICT_PATH
from app.job_analysis.llm import call_llm_batch
from app.job_analysis.models import JdRecord, ExtractionResult, EvolutionInfo, SkillEntry

_SKILL_CACHE: tuple[set[str], dict[str, str]] | None = None


def _load_skill_dict() -> tuple[set[str], dict[str, str]]:
    """加载 skill_dict 种子：返回 (canonical 集合, alias→canonical 映射)。"""
    global _SKILL_CACHE
    if _SKILL_CACHE is None:
        with open(SKILL_DICT_PATH, "r", encoding="utf-8") as f:
            entries = json.load(f)
        canonicals = {e["canonical"] for e in entries}
        aliases = {}
        for e in entries:
            for a in e["aliases"]:
                aliases[a.lower()] = e["canonical"]
        _SKILL_CACHE = (canonicals, aliases)
    return _SKILL_CACHE


def _canonicalize(name: str) -> str | None:
    """把 LLM 输出的技能名映射为 skill_dict.canonical；无法映射返回 None。"""
    canonicals, aliases = _load_skill_dict()
    n = name.strip().lower()
    if n in aliases:
        return aliases[n]
    if n in canonicals:
        return n
    return None

EXTRACT_SYSTEM = """You are a job data extraction specialist. Extract structured information from JD text with precision.

Key rules:
- job_name: Standardize to recognized title. Strip marketing language ("急招!高薪!!RAG工程师" → "RAG工程师")
- core_duties: 1-2 concise sentences
- skills: Object list with {name, confidence, evidence, is_required}.
  confidence reflects how clearly the JD demands this skill:
    0.9+: explicitly required
    0.7-0.9: mentioned as important
    0.5-0.7: mentioned as nice-to-have
    0.3-0.5: hinted or listed among many
- evidence: Quote the exact phrase from the JD that mentions this skill
- scenarios: Real industry application scenarios
- evolution: Assess based on the skill combination's novelty and JD count patterns
- SKILL CONSTRAINTS (D31): skill names MUST be one of the canonical names in the skill_dict provided in the prompt. Map synonyms/aliases to the canonical form. If a skill cannot be mapped to the dict, DO NOT put it in skills; put it in unknown_skills instead."""


def build_extract_prompt(record: JdRecord) -> str:
    canonicals, _ = _load_skill_dict()
    skill_list = ", ".join(sorted(canonicals))
    return f"""Extract structured job info.

SKILL_DICT (canonical names; use ONLY these, map synonyms to them):
{skill_list}

Output format:
{{
  "job_name": "standardized title",
  "core_duties": "1-2 sentence summary",
  "skills": [
    {{"name": "skill_name", "confidence": 0.92, "evidence": "exact JD quote", "is_required": true}}
  ],
  "scenarios": ["application scenario"],
  "is_emerging": true/false,
  "evolution": {{
    "stage": "emerging|growth|mature|declining",
    "stage_confidence": 0.0-1.0,
    "indicators": {{"jd_count_in_batch": 1, "source_diversity": 1, "skill_novelty": "high|medium|low"}}
  }},
  "unknown_skills": ["skill_not_in_dict"]
}}

---
job_title: {record.job_title}
raw_text: {record.raw_text[:4000]}
duties: {record.duties[:1000]}
experience: {record.experience[:200]}
source: {record.source}
---

Output valid JSON only."""


EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {
        "job_name": {"type": "string"},
        "core_duties": {"type": "string"},
        "skills": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "evidence": {"type": "string"},
                    "is_required": {"type": "boolean"},
                },
                "required": ["name", "confidence", "evidence", "is_required"],
            },
        },
        "scenarios": {"type": "array", "items": {"type": "string"}},
        "is_emerging": {"type": "boolean"},
        "evolution": {
            "type": "object",
            "properties": {
                "stage": {"type": "string",
                          "enum": ["emerging", "growth", "mature", "declining"]},
                "stage_confidence": {"type": "number"},
                "indicators": {"type": "object"},
            },
            "required": ["stage", "stage_confidence", "indicators"],
        },
        "unknown_skills": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["job_name", "core_duties", "skills", "scenarios",
                 "is_emerging", "evolution"],
}


def _build_skill_entries(
    raw_skills: list[dict],
) -> tuple[list[SkillEntry], list[SkillEntry], list[str]]:
    """分离 required/bonus skills（D31：仅保留 skill_dict 内技能，未命中进 unknown）。"""
    required, bonus, unknown = [], [], []
    for s in raw_skills:
        canonical = _canonicalize(s.get("name", ""))
        if canonical is None:
            unknown.append(s.get("name", "").strip())
            continue
        entry = SkillEntry(
            name=canonical, confidence=s["confidence"],
            evidence=s["evidence"], is_required=s.get("is_required", True),
        )
        if entry.is_required:
            required.append(entry)
        else:
            bonus.append(entry)
    return required, bonus, list(set(unknown))


def _validate_extraction(result: ExtractionResult) -> list[str]:
    """返回校验错误列表，空列表 = 通过。"""
    errors = []
    if not result.job_name.strip():
        errors.append("job_name is empty")
    if not result.core_duties.strip():
        errors.append("core_duties is empty")
    if len(result.required_skills) + len(result.bonus_skills) == 0:
        errors.append("no skills extracted")
    for sk in result.required_skills + result.bonus_skills:
        if not sk.evidence.strip():
            errors.append(f"skill '{sk.name}' has empty evidence")
        if sk.confidence < 0 or sk.confidence > 1:
            errors.append(
                f"skill '{sk.name}' confidence out of range: {sk.confidence}")
    return errors


def parse_extraction_response(
    jd_id: int, response: dict,
    record_quality: float, collected_at: str, record_source: str, model: str,
) -> ExtractionResult:
    """解析 LLM 响应并校验。"""
    required, bonus, unknown = _build_skill_entries(
        response.get("skills", []))
    unknown += response.get("unknown_skills", [])
    unknown = list(set(unknown))

    evo = response.get("evolution", {})
    evolution = EvolutionInfo(
        stage=evo.get("stage", "growth"),
        stage_confidence=evo.get("stage_confidence", 0.5),
        indicators=evo.get("indicators", {}),
    )

    result = ExtractionResult(
        jd_id=jd_id,
        job_name=response.get("job_name", ""),
        core_duties=response.get("core_duties", ""),
        required_skills=required,
        bonus_skills=bonus,
        scenarios=response.get("scenarios", []),
        source=record_source,
        quality=record_quality,
        collected_at=collected_at,
        is_emerging=response.get("is_emerging", False),
        evolution=evolution,
        unknown_skills=unknown,
        verdict="pass",
        model=model,
    )

    errors = _validate_extraction(result)
    if errors:
        result.verdict = "manual"

    return result


async def run_stage3(
    records: list[JdRecord],
    model: str = "",
) -> tuple[list[ExtractionResult], list[dict]]:
    model = model or MODEL_STAGE3
    prompts = [build_extract_prompt(r) for r in records]
    all_results: list[ExtractionResult] = []
    manual_results: list[dict] = []

    for i in range(0, len(prompts), BATCH_SIZE):
        batch_records = records[i:i + BATCH_SIZE]
        batch_prompts = prompts[i:i + BATCH_SIZE]
        batch_results: list[ExtractionResult] = []

        for attempt in range(MAX_RETRY):
            responses = await call_llm_batch(
                batch_prompts, model, EXTRACT_SCHEMA, system=EXTRACT_SYSTEM,
            )
            batch_results = []
            batch_ok = True

            for record, resp in zip(batch_records, responses):
                if "_error" in resp:
                    result = ExtractionResult(
                        jd_id=record.id, job_name="", core_duties="",
                        quality=record.quality, collected_at=record.crawled_at,
                        verdict="manual", model=model,
                    )
                    batch_results.append(result)
                    manual_results.append({
                        "jd_id": record.id, "stage": "model3",
                        "reason": f"API error: {resp['_error']}",
                    })
                    batch_ok = False
                else:
                    result = parse_extraction_response(
                        record.id, resp,
                        record.quality, record.crawled_at, record.source, model,
                    )
                    batch_results.append(result)
                    if result.verdict == "manual":
                        manual_results.append({
                            "jd_id": record.id, "stage": "model3",
                            "reason": "schema validation failed",
                            "model_output": resp,
                        })
                        if attempt < MAX_RETRY - 1:
                            batch_ok = False

            if batch_ok:
                break
            elif attempt < MAX_RETRY - 1:
                for j, res in enumerate(batch_results):
                    if res.verdict == "manual":
                        errs = _validate_extraction(res)
                        batch_prompts[j] += (
                            f"\n\nVALIDATION ERRORS (fix these): {errs}")

        all_results.extend(batch_results)

    return all_results, manual_results

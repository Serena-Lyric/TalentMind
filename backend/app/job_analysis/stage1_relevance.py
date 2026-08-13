"""模型1 —— 相关性分类（快速筛除非新一代信息技术 JD）。"""
from app.job_analysis.config import MODEL_STAGE1, RELEVANCE_CONFIDENCE, BATCH_SIZE
from app.job_analysis.llm import call_llm_batch
from app.job_analysis.models import JdRecord, RelevanceResult

SYSTEM_PROMPT = """You are a job classification expert. Judge whether a job description (JD) is a TECHNOLOGY / IT role.

RELEVANT — includes ALL of these:
- Software engineering & development (frontend/backend/fullstack/mobile, any language)
- AI/ML/Data science/Data engineering/Analytics
- Cloud/DevOps/SRE/Infrastructure/Platform
- Cybersecurity/Network engineering
- QA/Test automation
- IT management/Technical PM/Scrum Master (if the work is tech-team-facing)
- Database administration/ETL/Data pipeline
- Hardware/IoT/Embedded systems
- Technical support/IT operations (internal IT for tech companies counts)

NOT RELEVANT — TRUE non-tech roles:
- Healthcare (nurse, doctor, therapist, lab tech)
- Legal (lawyer, paralegal)
- Retail/sales/cashier (non-tech sales)
- Construction/manufacturing/warehouse/housekeeping
- Education (teacher, professor)
- Finance/accounting/HR (non-tech corporate functions)
- Hospitality (hotel, restaurant staff)
- Agriculture/farming

Borderline cases: If a role title sounds non-tech but the duties clearly involve building software/systems, classify as RELEVANT. If a role uses computers only as office tools (email, spreadsheets), classify as NOT RELEVANT.

Positive examples: Backend Engineer, Python开发, 运维工程师, DevOps, 数据分析师, IT项目经理, 网络安全工程师
Negative examples: 护士, 律师助理, 仓库工人, 酒店前台, 财务会计, 房产中介"""


def build_relevance_prompt(record: JdRecord) -> str:
    return f"""Judge whether this JD is a TECHNOLOGY / IT role.

RELEVANT: Software engineering, AI/ML, cloud/devops, data, cybersecurity, QA, IT mgmt, tech support — any role where the CORE WORK is building, maintaining, or deeply applying technology.
NOT RELEVANT: Non-tech roles that only use computers as office tools (email, spreadsheets). Healthcare, legal, retail, construction, hospitality, finance, HR, agriculture.

---
job_title: {record.job_title}
raw_text: {record.raw_text[:3000]}
duties: {record.duties[:1000]}
---

Output JSON with keys: is_relevant(bool), confidence(0-1), evidence(quote from JD), reasoning(one sentence)"""


RELEVANCE_SCHEMA = {
    "type": "object",
    "properties": {
        "is_relevant": {"type": "boolean"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "evidence": {"type": "string"},
        "reasoning": {"type": "string"},
    },
    "required": ["is_relevant", "confidence", "evidence", "reasoning"],
}


def parse_relevance_response(jd_id: int, response: dict, model: str) -> RelevanceResult:
    is_relevant = response.get("is_relevant", False)
    confidence = response.get("confidence", 0.5)

    if is_relevant and confidence >= RELEVANCE_CONFIDENCE:
        verdict = "pass"
    elif not is_relevant and confidence >= RELEVANCE_CONFIDENCE:
        verdict = "reject"
    else:
        verdict = "manual"

    return RelevanceResult(
        jd_id=jd_id,
        is_relevant=is_relevant,
        confidence=confidence,
        evidence=response.get("evidence", ""),
        reasoning=response.get("reasoning", ""),
        verdict=verdict,
        model=model,
    )


async def run_stage1(
    records: list[JdRecord],
    model: str = "",
) -> tuple[list[JdRecord], list[RelevanceResult]]:
    model = model or MODEL_STAGE1
    prompts = [build_relevance_prompt(r) for r in records]
    all_results: list[RelevanceResult] = []

    for i in range(0, len(prompts), BATCH_SIZE):
        batch_records = records[i:i + BATCH_SIZE]
        batch_prompts = prompts[i:i + BATCH_SIZE]
        responses = await call_llm_batch(
            batch_prompts, model, RELEVANCE_SCHEMA, system=SYSTEM_PROMPT,
        )

        for record, resp in zip(batch_records, responses):
            if "_error" in resp:
                all_results.append(RelevanceResult(
                    jd_id=record.id, is_relevant=False, confidence=0,
                    evidence="", reasoning=f"API error: {resp['_error']}",
                    verdict="manual", model=model,
                ))
            else:
                all_results.append(
                    parse_relevance_response(record.id, resp, model))

    passed = [r for r, res in zip(records, all_results) if res.verdict == "pass"]
    return passed, all_results

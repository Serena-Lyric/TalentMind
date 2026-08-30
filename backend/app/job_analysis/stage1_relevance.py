# -*- coding: utf-8 -*-
"""Stage1: relevance classification.

Slot "relevance" (flash fast-screening) + objective tech-signal gate.
Fully automatic: no manual-review branch.
"""
import asyncio

from .config import SLOT_POOLS, RELEVANCE_CONFIDENCE
from .llm import LLMClient
from .models import JdRecord, RelevanceResult
from .tech_signal import (verdict_for, auto_resolve_low_confidence,
                         rescue_verdict_with_new_terms)

SYSTEM_PROMPT = """You are a job classification expert. Judge whether a job description (JD) belongs to the NEXT-GENERATION INFORMATION TECHNOLOGY domain (新一代信息技术) - the target scope: AI, big data, intelligent systems, IoT, cloud-native, cybersecurity, with software engineering as the evolving backbone.

STEP 1 - Is this a real JD at all? (垃圾内容判定)
A text is NOT a job description if it lacks EITHER hiring intent OR concrete job content:
- Meta/community posts (e.g. "please add a 4-day-week tag to listings", "this salary is too low")
- Ads/courses/training promos (selling courses or services, not hiring)
- Company news without concrete role requirements
- Placeholder texts with no duties or requirements
If NOT a real JD, reject with high confidence (even if tech words appear).

STEP 2 - Is it a NEXT-GEN IT role? (新一代信息技术判定)
RELEVANT - core domains:
- AI/ML/LLM: machine learning, deep learning, NLP, computer vision, LLM/RAG/Agent, MLOps
- Data: data science, data engineering, big data platforms, data analytics, BI
- Cloud and DevOps: cloud-native, microservices, SRE, platform engineering, Kubernetes
- Intelligent systems and IoT: embedded, robotics, autonomous systems, edge computing
- Cybersecurity / network engineering
- Software engineering (frontend/backend/fullstack/mobile, any language - baseline for capability evolution tracking)
- QA/test automation (automation-focused)

NOT RELEVANT - even if the title sounds "IT":
- Traditional enterprise IT support (helpdesk, desktop support, 桌面运维/网管)
- Traditional ERP/CRM administrators, office software trainers
- Non-tech roles: healthcare, legal, retail, sales, construction, education, finance/accounting, HR, hospitality, agriculture

Borderline cases: Roles where the CORE WORK is building or maintaining NEXT-GEN systems are RELEVANT (e.g. DevOps on modern cloud stacks). Roles only using computers as office tools, or supporting legacy IT infrastructure only, are NOT RELEVANT.

Positive examples: AI工程师, 大模型算法工程师, 数据科学家, 云原生工程师, DevOps, 物联网工程师, 网络安全工程师, Backend Engineer, MLOps Engineer
Negative examples: 护士, 律师助理, 仓库工人, 酒店前台, 财务会计, 桌面运维, Helpdesk, 网管"""


def build_relevance_prompt(record: JdRecord, text: str | None = None) -> str:
    text = text if text is not None else record.raw_text[:3000]
    return f"""Judge this text in two steps.

STEP 1 - Real JD or garbage (垃圾内容)?
Reject as garbage if it lacks hiring intent or concrete job content:
meta/community posts, course/sales ads, company news without role specifics, placeholders.
If garbage -> is_relevant=false with confidence >= 0.9.

STEP 2 - If it IS a JD: is it a NEXT-GENERATION INFORMATION TECHNOLOGY (新一代信息技术) role?

RELEVANT: AI/ML/LLM, big data, cloud-native, DevOps/SRE, IoT/embedded, cybersecurity, software engineering - any role where the CORE WORK is building, maintaining, or deeply applying NEXT-GEN technology.
NOT RELEVANT: Traditional IT support (helpdesk, 桌面运维, 网管), ERP/CRM admins, or non-tech roles (healthcare, legal, retail, construction, hospitality, finance, HR, agriculture) that only use computers as office tools.
JD may be in Chinese or English - judge by content, not language.

---
job_title: {record.job_title}
raw_text: {text}
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


def parse_relevance_response(jd_id: int, response: dict,
                             model: str) -> RelevanceResult:
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


async def _batch_by_pool(prompts, pool, schema, system, client):
    """Batch-call through the slot pool (semaphore limited)."""
    semaphore = asyncio.Semaphore(client.limiter.concurrent)

    async def bounded(p):
        async with semaphore:
            return await client.call_with_pool(p, pool, schema,
                                               system=system)

    return [r if not isinstance(r, Exception) else {"_error": str(r)}
            for r in await asyncio.gather(*[bounded(p) for p in prompts],
                                          return_exceptions=True)]


async def run_stage1(
    records: list[JdRecord],
    client: LLMClient | None = None,
    tech_scorer=None,
    term_lookup=None,
    batch_size: int = 50,
) -> tuple[list[JdRecord], list[RelevanceResult]]:
    # L2 走官方 DeepSeek 端点（实测 11s/批 vs go 107s/批）
    own_client = client is None
    if client is None:
        from config import DS_ENDPOINT
        client = LLMClient(endpoint_override=DS_ENDPOINT)
    pool = SLOT_POOLS["relevance"]
    model = pool[0]

    # 批量合并：动态切批 + 批间并行（semaphore 限 3，端点实测 6 并发
    # 即出现连接超时；失败的批整体重试一轮）。
    from batch_prompts import build_batch_relevance_prompt, \
        chunk_by_input_size
    chunks = chunk_by_input_size(records, max_batch=batch_size,
                                 max_chars_per_batch=30000, text_limit=3000)
    sem = asyncio.Semaphore(3)

    async def run_chunk(chunk):
        async with sem:
            prompt = build_batch_relevance_prompt(chunk)
            return await client.call_batch_consolidated(
                [prompt], model, system=SYSTEM_PROMPT, batch_size=1,
                max_tokens=16000, item_ids=[r.id for r in chunk])

    # 第一轮
    chunk_results = await asyncio.gather(
        *[run_chunk(c) for c in chunks], return_exceptions=True)
    # 失败批重试一轮
    for i, cr in enumerate(chunk_results):
        if isinstance(cr, Exception) or (isinstance(cr, list)
                                         and any("_error" in x
                                                 for x in cr)):
            chunk_results[i] = await run_chunk(chunks[i])
    all_raw: list[dict] = []
    for i, cr in enumerate(chunk_results):
        if isinstance(cr, Exception):
            all_raw.extend([{"_error": str(cr)} for _ in chunks[i]])
        else:
            all_raw.extend(cr)

    all_results: list[RelevanceResult] = []

    for record, resp in zip(records, all_raw):
        # ── 标题硬规则（双条件门，防误杀）──
        # 1. 标题强技术 → 直接 pass（省 LLM 调用）
        # 2. 标题强非技术 且 正文零技术信号 → 直接 reject
        # 3. 标题强非技术 但 正文有技术词（如 "Sales Engineer"）→ 交给 LLM
        from title_rules import title_verdict
        tv = title_verdict(record.job_title)
        if tv == "pass":
            all_results.append(RelevanceResult(
                jd_id=record.id, is_relevant=True, confidence=0.95,
                evidence=f"title: {record.job_title}",
                reasoning="strong tech title rule",
                verdict="pass", model="title_rule",
            ))
            continue
        if tv == "reject" and tech_scorer is not None:
            _score = tech_scorer.score(record.raw_text)
            _obj = _score["newgen_hits"] + _score["trend_hits"]
            # 标题强非技术 + 弱技术信号（<3）→ 拒。
            # 只有强信号（>=3）才豁免交 LLM（如 "Sales Engineer" 真技术岗）
            if _obj < 3:
                all_results.append(RelevanceResult(
                    jd_id=record.id, is_relevant=False, confidence=0.99,
                    evidence=f"title: {record.job_title}",
                    reasoning="strong non-tech title + weak tech signals",
                    verdict="reject", model="title_rule",
                ))
                continue
            # 强技术信号 → 不武断，交给 LLM 判定（继续往下走）
        if "_error" in resp:
            # API 错误 -> retry 状态（pipeline 不改记录状态，下次续跑自动重试）
            all_results.append(RelevanceResult(
                jd_id=record.id, is_relevant=False, confidence=0,
                evidence="", reasoning=f"API error: {resp['_error']}",
                verdict="retry", model=model,
            ))
            continue
        result = parse_relevance_response(record.id, resp, model)
        if tech_scorer is not None:
            # 客观技术信号层合并（全自动）
            score = tech_scorer.score(record.raw_text)
            if result.confidence < RELEVANCE_CONFIDENCE:
                final_verdict = auto_resolve_low_confidence(
                    result.is_relevant, result.confidence, score)
            else:
                final_verdict = verdict_for(result.is_relevant,
                                            result.confidence, score)
            if final_verdict != result.verdict:
                result.reasoning += (
                    f" [tech_signal: {score['newgen_hits']} newgen, "
                    f"{score['trend_hits']} trend, "
                    f"{score['legacy_hits']} legacy -> {final_verdict}]")
                result.verdict = final_verdict
            # 联网新词查证兜底：低置信 + 零客观命中
            obj_hits = score["newgen_hits"] + score["trend_hits"]
            if (term_lookup is not None
                    and result.verdict == "reject"
                    and result.is_relevant and obj_hits == 0):
                from new_term_lookup import extract_candidate_terms
                known = (tech_scorer.newgen | tech_scorer.trend
                         | tech_scorer.legacy)
                cands = extract_candidate_terms(record.raw_text, known)
                found = await term_lookup.verify_many(cands) \
                    if cands else []
                rescue = rescue_verdict_with_new_terms(found)
                if rescue == "pass":
                    result.reasoning += (
                        f" [online_verify: {found} confirmed -> pass]")
                    result.verdict = "pass"
        elif result.verdict == "manual":
            result.verdict = "pass" if result.is_relevant else "reject"
        all_results.append(result)

    passed = [r for r, res in zip(records, all_results)
              if res.verdict == "pass"]
    if own_client:
        await client.close()
    return passed, all_results

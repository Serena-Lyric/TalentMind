"""模型3 —— 结构化提取（LLM 输出每个 skill 的 confidence + 逐字证据）。"""
import asyncio
from .config import SLOT_POOLS, MAX_RETRY
from .llm import LLMClient
from .models import JdRecord, ExtractionResult, EvolutionInfo, SkillEntry

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
- evidence: VERBATIM quote from the JD text, copied character-for-character,
  no paraphrasing, no translation, no summarizing. Maximum 50 characters.
  If the JD text is Chinese, evidence must be in Chinese; if English,
  evidence must be in English. Never translate evidence.
  If you cannot find a supporting quote for a skill, DO NOT output that skill.
- scenarios: Real industry application scenarios
- evolution: Assess based on the skill combination's novelty and JD count patterns"""


def build_extract_prompt(record: JdRecord) -> str:
    return f"""Extract structured job info.

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
    """分离 required/bonus skills，LLM 自由提取不限制词表。"""
    required, bonus, unknown = [], [], []
    for s in raw_skills:
        entry = SkillEntry(
            name=s["name"], confidence=s["confidence"],
            evidence=s["evidence"], is_required=s.get("is_required", True),
        )
        if entry.is_required:
            required.append(entry)
        else:
            bonus.append(entry)
    # unknown_skills 来自 LLM 报告的未知技能
    return required, bonus, unknown


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

    # 提取层永不拒绝：校验错误仅触发重试，最终仍以 best-effort 结果通过
    # （残缺 JD 也收集，合并层聚合成完整岗位定义）
    return result


async def run_stage3(
    records: list[JdRecord],
    client: LLMClient | None = None,
    batch_size: int = 6,
    on_chunk_done=None,
    on_result=None,
) -> tuple[list[ExtractionResult], list[dict]]:
    # L4 走官方 DeepSeek 端点（实测 11s/批 vs go 107s/批）
    own_client = client is None
    if client is None:
        from config import DS_ENDPOINT
        client = LLMClient(endpoint_override=DS_ENDPOINT)
    manual_results: list[dict] = []
    # 逐条落库回调：每批完成立即通知调用方（断点续跑/进度可见）
    chunk_done = on_chunk_done
    # 流水线回调：每条解析完立即送出（L5 worker 并发消费）
    result_cb = on_result

    # ═══ L4 分流双队列（纯文本规则，零 LLM）═══
    # 先 L3 清洗（本地规则：去 HTML/转义/乱码），再分流：
    # 清洗后仍脏/长的走 pro，其余走 flash（快）。
    import asyncio as _a
    from batch_prompts import build_batch_extract_prompt
    from l3_clean import clean_jd_text
    from l4_split import calc_split_result, MODEL_L4_FLASH, MODEL_L4_KIMI
    from config import (L4_FLASH_MAX_CONCURRENT, L4_KIMI_MAX_CONCURRENT)

    flash_recs = []
    kimi_recs = []
    split_info: dict[int, dict] = {}
    clean_texts: dict[int, str] = {}
    for r in records:
        cleaned = clean_jd_text(r.raw_text)
        clean_texts[r.id] = cleaned
        sr = calc_split_result(cleaned)
        split_info[r.id] = {"used_l4_model": sr.target_model,
                            "text_len": sr.text_len,
                            "dirty_score": sr.dirty_score}
        # 用清洗后文本做提取（快 + 证据干净）
        r2 = r.model_copy(update={"raw_text": cleaned})
        (flash_recs if sr.target_model == MODEL_L4_FLASH
         else kimi_recs).append(r2)

    FLASH_TIMEOUT = 200.0
    KIMI_TIMEOUT = 240.0
    # 重试约束：仅 5xx/429 重试 2 次，退避 2s/4s；4xx 不重试。
    RETRY_DELAYS = [2.0, 4.0]

    def is_retryable(resp: dict) -> bool:
        err = resp.get("_error", "")
        if "HTTP 5" in err:
            return True
        if "429" in err:
            return True
        return False

    async def extract_queue(recs, model, sem, timeout, on_chunk=None):
        """单队列执行：独立信号量 + 5xx 有限重试。

        每批完成后立即回调 on_chunk(chunk_records, chunk_results)
        （逐条落库用，不再等整层结束才写）。
        """
        out: list[dict] = []

        async def run_chunk(chunk):
            async with sem:
                prompt = build_batch_extract_prompt(chunk)
                last_err = None
                # 初始 + 最多 2 次重试（仅 5xx/429）
                for attempt in range(3):
                    resp = await client.call_batch_consolidated(
                        [prompt], model, system=EXTRACT_SYSTEM,
                        batch_size=1, max_tokens=32000,
                        item_ids=[r.id for r in chunk])
                    if isinstance(resp, list) and resp and \
                            not all("_error" in x for x in resp):
                        if on_chunk:
                            on_chunk(chunk, resp)
                        return resp
                    err = resp[0] if isinstance(resp, list) and resp \
                        else {"_error": str(resp)}
                    last_err = err
                    if not is_retryable(err):
                        break
                    if attempt < 2:
                        await _a.sleep(RETRY_DELAYS[attempt])
                # 失败：不丢弃（用原文兜底），并回调落库
                failed = [{"_error": (last_err or {}).get(
                    "_error", "extract failed")} for _ in chunk]
                if on_chunk:
                    on_chunk(chunk, failed)
                return failed

        chunks = [recs[i:i + batch_size]
                  for i in range(0, len(recs), batch_size)]
        results = await _a.gather(
            *[run_chunk(c) for c in chunks], return_exceptions=True)
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                failed = [{"_error": str(r)} for _ in chunks[i]]
                if on_chunk:
                    on_chunk(chunks[i], failed)
                out.extend(failed)
            else:
                out.extend(r)
        return out

    flash_sem = _a.Semaphore(L4_FLASH_MAX_CONCURRENT)
    kimi_sem = _a.Semaphore(L4_KIMI_MAX_CONCURRENT)
    # 逐条落库：每批完成立即回调（用 raw resp 做轻量落库标记）
    def _cb(chunk_recs, chunk_results):
        if chunk_done:
            chunk_done(chunk_recs, chunk_results)

    # 两个队列并行执行
    flash_task = _a.create_task(extract_queue(
        flash_recs, MODEL_L4_FLASH, flash_sem, FLASH_TIMEOUT,
        on_chunk=_cb))
    kimi_task = _a.create_task(extract_queue(
        kimi_recs, MODEL_L4_KIMI, kimi_sem, KIMI_TIMEOUT,
        on_chunk=_cb))
    flash_out, kimi_out = await _a.gather(flash_task, kimi_task)

    # 按原顺序拼回 all_raw
    raw_by_id: dict[int, dict] = {}
    for r, resp in zip(flash_recs, flash_out):
        raw_by_id[r.id] = resp
    for r, resp in zip(kimi_recs, kimi_out):
        raw_by_id[r.id] = resp

    batch_results: list[ExtractionResult] = []

    for record in records:
        resp = raw_by_id.get(record.id, {"_error": "missing"})
        info = split_info.get(record.id, {})
        used_model = info.get("used_l4_model", "")
        if "_error" in resp:
            # API 错误：用原标题/原文兜底，best-effort 收集（不丢弃）。
            # 标题先过 normalize_job_type 清洗（剥公司/地点/工作制段）
            from merge import normalize_job_type
            result = ExtractionResult(
                jd_id=record.id,
                job_name=normalize_job_type(record.job_title),
                core_duties=record.duties or record.raw_text[:200],
                quality=record.quality, collected_at=record.crawled_at,
                verdict="pass", model=used_model,
            )
            batch_results.append(result)
            manual_results.append({
                "jd_id": record.id, "stage": "model3",
                "reason": f"API error (fallback to title): {resp['_error']}",
            })
        else:
            result = parse_extraction_response(
                record.id, resp,
                record.quality, record.crawled_at, record.source,
                used_model,
            )
            # job_name 提取失败或脏（含 | / 公司段）→ 清洗后兜底
            from merge import normalize_job_type
            if not result.job_name.strip() or "|" in result.job_name:
                cleaned = normalize_job_type(result.job_name or record.job_title)
                if cleaned:
                    result.job_name = cleaned
            if not result.core_duties.strip():
                result.core_duties = (
                    record.duties or record.raw_text[:200])
            batch_results.append(result)
            if result.verdict == "manual":
                manual_results.append({
                    "jd_id": record.id, "stage": "model3",
                    "reason": "schema validation failed",
                    "model_output": resp,
                })
        # 流水线：解析完立即送出（不阻塞队列）
        if result_cb is not None:
            try:
                result_cb(result)
            except Exception:
                pass    # 回调失败不影响主流程

    if own_client:
        await client.close()
    return batch_results, manual_results

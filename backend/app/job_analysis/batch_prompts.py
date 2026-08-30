"""批量合并调用 —— 一次 HTTP 调用塞多条 JD，按 jd_id 对齐拆分。

分层批量大小（输出量/请求 是主约束）：
- L2 相关性: 8 条/批（输出小）
- L4 提取:   2 条/批（输出巨大，2 条已 ~3000 token）
- L5 验证:   5 条/批（输出中等）
"""
from __future__ import annotations

from .models import JdRecord


def chunk_by_input_size(records: list[JdRecord], max_batch: int,
                        max_chars_per_batch: int = 40000,
                        text_limit: int = 3000) -> list[list[JdRecord]]:
    """动态切批：兼顾最大批量与每批输入字符总量。

    实测教训：50 条长 linkedin JD 拼一批 = 100K+ 字符，超上下文窗口
    导致调用失败。长 JD 自动降批数，短 JD 保持 max_batch。
    """
    chunks: list[list[JdRecord]] = []
    current: list[JdRecord] = []
    size = 0
    for r in records:
        n = min(len(r.raw_text), text_limit)
        if (current and (len(current) >= max_batch
                         or size + n > max_chars_per_batch)):
            chunks.append(current)
            current, size = [], 0
        current.append(r)
        size += n
    if current:
        chunks.append(current)
    return chunks


def build_batch_relevance_prompt(records: list[JdRecord]) -> str:
    items = []
    for r in records:
        # pipeline 的 _row_to_record 已把 seg_text 填进 raw_text
        # （L0 分段器产出的技能段，短且信息密度高）
        # 1500 字足够二元分类（是否新一代信息技术岗），省 40% 输入时间
        text = (r.raw_text[:1500] if len(r.raw_text) > 1500
                else r.raw_text)
        items.append(f"jd_id: {r.id}\njob_title: {r.job_title}\n"
                     f"raw_text: {text}\n")
    joined = "\n---\n".join(items)
    return f"""Classify EACH job description below as a NEXT-GENERATION
INFORMATION TECHNOLOGY role (新一代信息技术: AI/ML/LLM, big data, cloud,
IoT, cybersecurity, software engineering). NOT RELEVANT: traditional IT
support (helpdesk, 桌面运维), ERP/CRM admins, or non-tech roles.
Also reject as garbage any text that is not a real JD (meta posts, ads,
company news, placeholders).

{joined}

Output ONLY a JSON object with a "results" array, one entry per JD,
same order, each entry:
{{"jd_id": <int>, "is_relevant": true/false, "confidence": 0.0-1.0,
  "evidence": "short quote", "reasoning": "one sentence"}}"""


def build_batch_extract_prompt(records: list[JdRecord]) -> str:
    items = []
    for r in records:
        text = (r.raw_text[:4000] if len(r.raw_text) > 4000
                else r.raw_text)
        items.append(f"jd_id: {r.id}\njob_title: {r.job_title}\n"
                     f"raw_text: {text}\n")
    joined = "\n---\n".join(items)
    return f"""Extract structured job info for EACH JD below.

Rules:
- evidence: VERBATIM quote from the JD text, no paraphrasing,
  max 50 chars. If no supporting quote exists for a skill, do NOT
  output that skill.
- job_name: standardized title (strip marketing language).

{joined}

Output ONLY a JSON object with a "results" array, one entry per JD,
same order, each entry:
{{"jd_id": <int>, "job_name": "...", "core_duties": "1-2 sentences",
  "skills": [{{"name": "...", "confidence": 0.0-1.0,
               "evidence": "verbatim quote", "is_required": true/false}}],
  "scenarios": ["..."], "is_emerging": true/false,
  "evolution": {{"stage": "emerging|growth|mature|declining",
                  "stage_confidence": 0.0-1.0,
                  "indicators": {{}}}},
  "unknown_skills": ["..."]}}"""


def build_batch_verify_prompt(full_texts: dict[int, str],
                              skills_by_jd: dict[int, list],
                              jd_ids: list[int]) -> str:
    """一条批量验证：每 JD 带全文+技能列表，输出每 JD 的判定数组。"""
    items = []
    for jd_id in jd_ids:
        text = full_texts.get(jd_id, "")
        text = text[:4000] if len(text) > 4000 else text
        skills_json = str([{"name": s.name, "evidence": s.evidence}
                           for s in skills_by_jd.get(jd_id, [])])
        items.append(f"jd_id: {jd_id}\nJD TEXT:\n{text}\n"
                     f"SKILLS TO VERIFY:\n{skills_json}\n")
    joined = "\n---\n".join(items)
    return f"""For EACH JD below, check EACH skill against the JD text:
does the JD genuinely require or mention this skill?

Rules:
- supported=true only if the JD text mentions the skill or an obvious
  synonym; vague mentions ("熟悉主流框架" does NOT support "React")
  are false; missing evidence counts as false.
- Judge against the FULL JD text, not just the quoted evidence.

{joined}

Output ONLY a JSON object with a "results" array, one entry per JD,
same order, each entry:
{{"jd_id": <int>, "skills": [{{"name": "...", "supported": true/false,
                               "reason": "short"}}]}}"""


def split_batch_response(resp: dict, expected_ids: list[int]) -> list[dict]:
    """把批量响应的 results 数组按 expected_ids 对齐拆分。

    模型漏条目/错 id → 该条标 _error（调用方单独重试该条）。
    id 类型宽容：模型可能返回字符串 "1" 而非数字 1。
    """
    if "_error" in resp or not isinstance(resp, dict):
        return [{"_error": f"batch failed: {resp.get('_error', resp)}"}
                for _ in expected_ids]
    results = resp.get("results")
    if not isinstance(results, list):
        return [{"_error": f"bad batch response: {str(resp)[:100]}"}
                for _ in expected_ids]
    by_id = {}
    for entry in results:
        if isinstance(entry, dict) and "jd_id" in entry:
            try:
                by_id[int(entry["jd_id"])] = entry
            except (TypeError, ValueError):
                continue
    out = []
    for jd_id in expected_ids:
        if jd_id in by_id:
            out.append(by_id[jd_id])
        else:
            out.append({"_error": f"missing jd_id {jd_id} in batch response"})
    return out

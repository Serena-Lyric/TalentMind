"""L5 证据验证 —— 聚合后置双 Judge（按桌面 PDF 方案）。

- 双模型并行调用（非串行）
- 只输出异常标签的技能（POST_VERIFY_ONLY_OUTPUT_ABNORMAL）
- JSON 容错：去 markdown 代码块/截取片段/解析异常整批置 null
- 融合规则：双 Judge 同时异常→删除；一个异常→suspicious(-0.15)；
  都无→verified；任一模型错误→整批 null，绝不删技能
- 并发锁 3（PDF：>3 触发 API 排队延迟暴涨）；单批 200s 看门狗
"""
from __future__ import annotations
import asyncio
import json
import re

from .config import (SLOT_POOLS, POST_VERIFY_BATCH_SIZE,
                    POST_VERIFY_MAX_CONCURRENT)
from .models import SkillEntry

VERIFY_SYSTEM = """You are a strict fact-checker for extracted job skills.
Your job is to catch HALLUCINATED skills - skills that the extractor claims
but the JD text does not actually support.
你是一名严格的岗位技能核查员，职责是找出提取结果中无原文依据的幻觉技能。"""

# 只报异常版 prompt：默认全部技能通过，只列出无依据/模糊依据的
ABNORMAL_PROMPT_TMPL = """For EACH job below, list ONLY the skills that LACK
clear support in the JD text (abnormal). Skills not listed are considered
supported (verified).

Rules:
- A skill is ABNORMAL if the JD text does NOT clearly mention it or an
  obvious synonym (e.g. "K8s" for "Kubernetes").
- Vague mentions do NOT count as support ("熟悉主流框架" does NOT support
  "React").
- Missing evidence counts as abnormal.
- Output ONLY a JSON object with a "results" array, one entry per job,
  same order. Each entry:
  {{"jd_id": <int>, "abnormal": [{{"name": "...", "reason": "short"}}]}}

{items}"""


def build_abnormal_prompt(jd_ids: list[int],
                          full_texts: dict[int, str],
                          skills_by_jd: dict[int, list]) -> str:
    parts = []
    for jd_id in jd_ids:
        # full_texts 已是证据窗口拼接（run_verify_aggregated 构造），
        # 不再截断 —— 窗口正是为完整验证准备的
        text = full_texts.get(jd_id, "")
        skills_json = json.dumps(
            [{"name": s.name, "evidence": s.evidence}
             for s in skills_by_jd.get(jd_id, [])],
            ensure_ascii=False)
        parts.append(f"jd_id: {jd_id}\nJD TEXT:\n{text}\n"
                     f"SKILLS:\n{skills_json}\n")
    return ABNORMAL_PROMPT_TMPL.format(items="\n---\n".join(parts))


def parse_abnormal_response(resp: dict, jd_ids: list[int]) -> dict[int, set]:
    """解析只报异常响应。任何解析失败 → 该批全部 None（调用方不判定）。"""
    if isinstance(resp, Exception) or not isinstance(resp, dict):
        raise ValueError(f"verify response error: {resp}")
    if "_error" in resp:
        raise ValueError(f"verify API error: {resp['_error']}")
    results = resp.get("results")
    if not isinstance(results, list):
        raise ValueError(f"bad results format: {str(resp)[:100]}")
    out: dict[int, set] = {}
    for entry in results:
        if isinstance(entry, dict) and "jd_id" in entry:
            abnormal = entry.get("abnormal") or []
            names = {a.get("name", "").lower() for a in abnormal
                     if isinstance(a, dict) and a.get("name")}
            out[entry["jd_id"]] = names
    # 缺失的 jd_id 视为无异常（默认通过）；响应里没这个岗位说明该岗位全通过
    return out


def _robust_json_extract(text: str) -> dict:
    """Qwen JSON 容错：去 markdown 代码块、截取 JSON 片段。"""
    t = text.strip()
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", t)
    if m:
        t = m.group(1).strip()
    start, end = t.find("{"), t.rfind("}")
    if start != -1 and end > start:
        t = t[start:end + 1]
    return json.loads(t)


async def _one_judge(client, model: str, jd_ids: list[int],
                     full_texts: dict[int, str],
                     skills_by_jd: dict[int, list]):
    """单个 Judge：按 token 动态切批（8 岗位上限只是数量，必须 token 切分）。

    返回 (out, failed_jds)：
    - out: jd_id -> abnormal 技能名集合
    - failed_jds: 解析/调用失败的 jd_id（该批失败只废该批，按 PDF 规范）
    """
    sem = asyncio.Semaphore(POST_VERIFY_MAX_CONCURRENT)
    out: dict[int, set] = {}
    failed_jds: set[int] = set()

    # token 动态切批：岗位上限 8 + 全文累计 30000 字符
    chunks: list[list[int]] = []
    cur: list[int] = []
    size = 0
    for jd in jd_ids:
        n = min(len(full_texts.get(jd, "")), 4000)
        if cur and (len(cur) >= POST_VERIFY_BATCH_SIZE or size + n > 30000):
            chunks.append(cur)
            cur, size = [], 0
        cur.append(jd)
        size += n
    if cur:
        chunks.append(cur)

    async def run_chunk(chunk_ids):
        async with sem:
            prompt = build_abnormal_prompt(chunk_ids, full_texts, skills_by_jd)
            # 批失败重试一轮（解析失败/网络错误），仍失败才废本批
            last_exc = None
            for _attempt in range(2):
                try:
                    resp = await client.call(prompt, model,
                                             system=VERIFY_SYSTEM,
                                             max_tokens=16000)
                    parsed = _robust_json_extract(json.dumps(resp)) \
                        if isinstance(resp, (dict, list)) \
                        and "_error" not in resp else resp
                    return chunk_ids, parse_abnormal_response(
                        parsed, chunk_ids), None
                except (json.JSONDecodeError, ValueError, TypeError) as e:
                    last_exc = e
            return chunk_ids, {}, str(last_exc)

    chunk_results = await asyncio.gather(
        *[run_chunk(c) for c in chunks], return_exceptions=True)
    for i, cr in enumerate(chunk_results):
        if isinstance(cr, Exception):
            for jd in chunks[i]:
                out[jd] = set()
                failed_jds.add(jd)
            continue
        chunk_ids, parsed, err = cr
        if err:
            for jd in chunk_ids:
                out[jd] = set()
                failed_jds.add(jd)
            continue
        for jd in chunk_ids:
            out[jd] = parsed.get(jd, set())
    return out, failed_jds


async def run_verify_aggregated(client, job_groups: dict[str, dict]):
    """聚合后置 L5：job_groups = {job_key: {jd_ids, full_texts, skills}}。

    每个技能验证时带"证据窗口"（evidence 前后各 400 字），
    而不是全部 JD 全文截断拼接 —— 防止长岗位截断导致误杀。
    返回 {job_key: {"removed": [...], "downgraded": [...]}}，
    任一 Judge 对该岗位失败 → {"null": True}（不判定不删）。
    """
    pool = SLOT_POOLS["verify"]
    keys = list(job_groups.keys())
    jd_ids = list(range(len(keys)))
    full_texts: dict[int, str] = {}
    skills_by_jd: dict[int, list] = {}
    for idx, key in enumerate(keys):
        g = job_groups[key]
        # 证据窗口：对每个技能，从其 evidence 所在的 JD 文本中
        # 截取 evidence 前后各 400 字（技能名+证据上下文，可验证）
        windows: list[str] = []
        best: dict[str, dict] = {}
        for s in g["skills"]:
            n = s.name.lower()
            if n not in best or s.confidence > best[n]["confidence"]:
                best[n] = {"name": s.name, "confidence": s.confidence,
                           "evidence": s.evidence}
        for v in best.values():
            ev = v["evidence"]
            # 找 evidence 在哪个 JD 全文里（用于窗口）
            ctx = ""
            for t in g["full_texts"]:
                pos = t.find(ev[:50])
                if pos != -1:
                    ctx = t[max(0, pos - 400):pos + len(ev) + 400]
                    break
            if not ctx and g["full_texts"]:
                ctx = g["full_texts"][0][:1200]
            windows.append(f"skill: {v['name']}\nevidence context: {ctx}")
        full_texts[idx] = "\n\n".join(windows)[:16000]
        skills_by_jd[idx] = [SkillEntry(
            name=v["name"], confidence=v["confidence"],
            evidence=v["evidence"], is_required=True) for v in best.values()]

    # 双 Judge 并行（PDF 硬性要求：并行调用，非串行）
    (v1_map, v1_failed), (v2_map, v2_failed) = await asyncio.gather(
        _one_judge(client, pool[0], jd_ids, full_texts, skills_by_jd),
        _one_judge(client, pool[1], jd_ids, full_texts, skills_by_jd),
    )

    out = {}
    for idx, key in enumerate(keys):
        # 按 PDF：任一 Judge 对该岗位失败 → 该岗位置 null（不判定不删），
        # 只废失败岗位本身，不影响其他岗位
        if idx in v1_failed or idx in v2_failed:
            out[key] = {"null": True}
            continue
        a = v1_map.get(idx)
        b = v2_map.get(idx)
        abnormal = (a | b) if a is not None and b is not None else None
        if abnormal is None:
            out[key] = {"null": True}
            continue
        # 融合：双 Judge 都标异常 → removed；仅一个 → downgraded
        both = a & b
        either = a ^ b
        out[key] = {"removed": sorted(both), "downgraded": sorted(either)}
    return out


# ── 逐条 L5（POST_VERIFY_AFTER_AGGREGATE=False 时的回退基线）──

def build_verify_prompt(full_text: str, skills: list[SkillEntry]) -> str:
    skills_json = json.dumps(
        [{"name": s.name, "evidence": s.evidence} for s in skills],
        ensure_ascii=False)
    return f"""Below is a job description (JD) and a list of skills extracted from it.
For EACH skill, check the FULL JD TEXT (not just the quoted evidence):
Does the JD genuinely require or mention this skill?

Rules:
- supported=true only if the JD text itself mentions this skill or
  an obvious synonym (e.g. "K8s" for "Kubernetes", "机器学习" for "ML")
- The quoted evidence may be sloppy — that is NOT a reason to mark false.
  Judge against the FULL JD text.
- Skills that merely "fit the job title" but appear nowhere in the text
  are HALLUCINATIONS -> supported=false.
- Vague mentions count as supported only if clearly this skill
  (e.g. "熟悉主流框架" does NOT support "React")
- Missing evidence counts as false.
- Output ONLY a JSON array, one verdict per skill, same order:
  [{{"name": "...", "supported": true/false, "reason": "one short sentence"}}]

---
JD TEXT (full):
{full_text}

SKILLS TO VERIFY:
{skills_json}"""


def _verify_json(resp: dict, n: int) -> list[dict] | None:
    """API 出错时返回 None（调用方跳过验证、技能原样保留）。"""
    if "_error" in resp:
        return None
    if isinstance(resp, list):
        return resp
    return None


async def run_verify(client, full_text: str, skills: list[SkillEntry]):
    """两个验证模型并行跑（单 JD 版，保留兼容）。"""
    pool = SLOT_POOLS["verify"]
    prompt = build_verify_prompt(full_text, skills)

    async def one(model):
        return await client.call(prompt, model, system=VERIFY_SYSTEM,
                                 max_tokens=2048)

    v1, v2 = await asyncio.gather(one(pool[0]), one(pool[1]))
    n = len(skills)
    return _verify_json(v1, n), _verify_json(v2, n)


async def run_verify_batch(client, jd_ids: list[int],
                           full_texts: dict[int, str],
                           skills_by_jd: dict[int, list],
                           batch_size: int = 20):
    """批量验证：一次 HTTP 调用塞 batch_size 条 JD，两模型各一次。

    返回 {jd_id: (v1 判定列表|None, v2 判定列表|None)}
    """
    from batch_prompts import build_batch_verify_prompt, \
        split_batch_response
    pool = SLOT_POOLS["verify"]

    async def one(model: str) -> dict[int, list | None]:
        out: dict[int, list | None] = {}
        # 动态切批：每批最多 batch_size 条、30000 字符输入（验证全文较长）
        chunks: list[list[int]] = []
        cur: list[int] = []
        size = 0
        for jd in jd_ids:
            n = min(len(full_texts.get(jd, "")), 4000)
            if cur and (len(cur) >= batch_size or size + n > 30000):
                chunks.append(cur)
                cur, size = [], 0
            cur.append(jd)
            size += n
        if cur:
            chunks.append(cur)

        # 批间并行（semaphore 限 3，端点实测 6 并发超时）
        sem = asyncio.Semaphore(3)

        async def run_chunk(chunk_ids):
            async with sem:
                prompt = build_batch_verify_prompt(full_texts, skills_by_jd,
                                                   chunk_ids)
                return chunk_ids, await client.call(
                    prompt, model, system=VERIFY_SYSTEM, max_tokens=16000)

        chunk_results = await asyncio.gather(
            *[run_chunk(c) for c in chunks], return_exceptions=True)
        for i, cr in enumerate(chunk_results):
            if isinstance(cr, Exception):
                for jd in chunks[i]:
                    out[jd] = None
                continue
            chunk_ids, resp = cr
            if "_error" in resp or "results" not in resp:
                for jd in chunk_ids:
                    out[jd] = None
                continue
            split = split_batch_response(resp, chunk_ids)
            for jd, entry in zip(chunk_ids, split):
                if "_error" in entry:
                    out[jd] = None
                else:
                    skills = entry.get("skills")
                    out[jd] = skills if isinstance(skills, list) else None
        return out

    v1_map, v2_map = await asyncio.gather(one(pool[0]), one(pool[1]))
    return {jd: (v1_map.get(jd), v2_map.get(jd)) for jd in jd_ids}


def apply_verification(skills: list[SkillEntry], v1, v2):
    """双模型判定。任一验证结果不可用（None）→ 跳过验证，原样保留。

    返回 (保留的技能, 删除数, 降级数)。
    """
    if v1 is None or v2 is None:
        return skills, 0, 0
    kept: list[SkillEntry] = []
    removed = downgraded = 0
    for i, sk in enumerate(skills):
        a = v1[i].get("supported", False) if i < len(v1) else False
        b = v2[i].get("supported", False) if i < len(v2) else False
        if not sk.evidence.strip():
            a = False          # evidence 缺失按 false 处理
        if a and b:
            sk.verification = "verified"
            kept.append(sk)
        elif a or b:
            sk.verification = "suspicious"
            sk.confidence = max(0.0, sk.confidence - 0.15)
            kept.append(sk)
            downgraded += 1
        else:
            removed += 1       # 双 false → 删除（幻觉）
    return kept, removed, downgraded

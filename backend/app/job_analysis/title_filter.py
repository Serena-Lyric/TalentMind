"""L2a 标题快筛 —— 只看岗位名判定是否新一代信息技术（双模型交叉）。

赛题范围：新一代信息技术（AI、大数据、智能系统、物联网、云原生、
网络安全、软件工程）。岗位名是岗位类型的第一标识。
"""
from __future__ import annotations
import asyncio

from .config import SLOT_POOLS, DS_ENDPOINT
from .llm import LLMClient

TITLE_SYSTEM = """You are a job title classifier. Judge whether a job TITLE
belongs to the NEXT-GENERATION INFORMATION TECHNOLOGY domain
(新一代信息技术: AI/ML, big data, intelligent systems, IoT, cloud-native,
cybersecurity, software engineering).

Verdicts:
- "tech": a next-gen IT role by title
  (Software Engineer, DevOps, Data Scientist, AI工程师, 网络安全工程师...)
- "nontech": NOT a next-gen IT role by title - be decisive, err toward
  nontech for clearly non-IT professions
  (Law Clerk, Actuary, Warehouse Associate, Nurse, Teacher,
   Financial Reporting, Marketing, 会计, 护士, 精算...)
- "unclear": ONLY when the title could genuinely be either
  (Program Manager, Analyst, Consultant, Coordinator...)

Output ONLY a JSON object with a "results" array, one entry per title,
same order: {"results": [{"jd_id": <int>, "verdict": "tech|nontech|unclear",
"confidence": 0.0-1.0, "domain": "one word"}]}"""


def build_title_prompt(items: list[tuple[int, str]]) -> str:
    parts = [f"jd_id: {jd}\njob_title: {t}" for jd, t in items]
    return ("Classify each job title below. Be decisive: a title that is "
            "most likely NOT a next-gen IT role must be nontech, not "
            "unclear. Only truly ambiguous titles are unclear.\n\n"
            + "\n---\n".join(parts)
            + "\n\nOutput ONLY a JSON object with a \"results\" array, "
              "one entry per title, same order: {\"results\": ["
              "{\"jd_id\": <int>, \"verdict\": \"tech|nontech|unclear\", "
              "\"confidence\": 0.0-1.0, \"domain\": \"one word\"}]}")


async def run_title_filter(
    records,
    client: LLMClient | None = None,
    batch_size: int = 30,
    use_pro: bool = False,
) -> dict[int, dict]:
    """标题快筛（级联双模型）。返回 {jd_id: {verdict, confidence, domain}}。

    - 第一轮：flash 判全部标题（快）
      tech → pass；nontech → reject
    - 第二轮：pro 只复审 flash 判"模糊"的（强模型能对脏/两可标题下结论）
      tech → pass；nontech → reject
    - pro 仍模糊 → unclear（交 L2b 正文判定兜底）
    保证绝大多数标题在标题层出结果，只有真两可的才进正文。
    """
    own = client is None
    if client is None:
        client = LLMClient(endpoint_override=DS_ENDPOINT)
    out: dict[int, dict] = {}
    try:
        items = [(r.id, r.job_title) for r in records]
        async def judge_batch(chunk, model):
            prompt = build_title_prompt(chunk)
            # 端点偶发空输出（finish=length）→ 重试一轮
            for attempt in range(2):
                try:
                    resp = await client.call(prompt, model, system=TITLE_SYSTEM,
                                             max_tokens=8000)
                except Exception as e:
                    print(f"  [title {model}] 调用异常: {type(e).__name__} "
                          f"{str(e)[:100]}")
                    return {}     # 本批全部回退 unclear，不崩溃
                if isinstance(resp, dict) and resp.get("_error") \
                        == "empty content from model":
                    print(f"  [title {model}] 空输出，重试第 {attempt + 1} 次")
                    await asyncio.sleep(2)
                    continue
                break
            from batch_prompts import split_batch_response
            jd_ids = [jd for jd, _ in chunk]
            m_out = {}
            if isinstance(resp, dict) and "_error" not in resp \
                    and "results" in resp:
                split = split_batch_response(resp, jd_ids)
                for (jd, t), entry in zip(chunk, split):
                    if "_error" in entry:
                        # 不再静默丢弃：打印原因（诊断"全模糊"的关键）
                        print(f"  [title {model}] id={jd} "
                              f"{t[:30]!r} -> {entry['_error']}")
                    else:
                        m_out[jd] = {
                            "verdict": entry.get("verdict", "unclear"),
                            "confidence": entry.get("confidence", 0.0),
                            "domain": entry.get("domain", ""),
                        }
            else:
                print(f"  [title {model}] 整批失败: "
                      f"{str(resp)[:120]}")
            return m_out

        # ── 第一轮：flash 判全部 ──
        flash_out: dict[int, dict] = {}
        missing_items: list[tuple[int, str]] = []
        for i in range(0, len(items), batch_size):
            chunk = items[i:i + batch_size]
            m = await judge_batch(chunk, "deepseek-v4-flash")
            flash_out.update(m)
            # 漏条目收集（missing jd_id / 空输出的）
            missing_items.extend((jd, t) for jd, t in chunk
                                 if jd not in m)

        # ── 漏条目小批重试（5 条/批，防漏）──
        if missing_items:
            print(f"  [title] 漏条目 {len(missing_items)} 条，小批重试...")
            for i in range(0, len(missing_items), 5):
                chunk = missing_items[i:i + 5]
                m = await judge_batch(chunk, "deepseek-v4-flash")
                flash_out.update(m)

        unclear_items = []
        for jd, t in items:
            v = flash_out.get(jd, {}).get("verdict", "unclear")
            if v == "tech":
                out[jd] = flash_out[jd]
            elif v == "nontech":
                out[jd] = flash_out[jd]
            else:
                unclear_items.append((jd, t))

        # ── 第二轮：pro 复审模糊（use_pro=False 时跳过）──
        if unclear_items and use_pro:
            pro_out: dict[int, dict] = {}
            for i in range(0, len(unclear_items), batch_size):
                chunk = unclear_items[i:i + batch_size]
                pro_out.update(await judge_batch(chunk, "deepseek-v4-pro"))
            for jd, t in unclear_items:
                pv = pro_out.get(jd, {}).get("verdict", "unclear")
                if pv in ("tech", "nontech"):
                    out[jd] = pro_out[jd]
                else:
                    out[jd] = {"verdict": "unclear", "confidence": 0.0,
                               "domain": ""}
        elif unclear_items:
            # 跳过 pro：模糊直接标 unclear（对照实验用）
            for jd, t in unclear_items:
                out[jd] = {"verdict": "unclear", "confidence": 0.0,
                           "domain": ""}
    finally:
        if own:
            await client.close()
    return out

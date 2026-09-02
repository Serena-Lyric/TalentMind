"""M2 岗位名翻译辅助层。

只维护 job_name_zh 展示字段，不翻译技能 canonical；调用方负责稳定 job_id。
"""
from __future__ import annotations

from app.job_analysis.llm import LLMClient
from app.job_analysis.config import SLOT_POOLS

TRANSLATE_SYSTEM = """You are a professional job title translator.
Translate English job titles to natural Chinese. Keep technical proper nouns in English.
If the title is already Chinese, keep it unchanged.
Output only JSON: {\"results\":[{\"job_name\":\"original\",\"job_name_zh\":\"translated\"}]}"""


def build_translate_prompt(job_names: list[str]) -> str:
    names = "\n".join(f"- {name}" for name in job_names)
    return f"Translate each job title to natural Chinese.\n\n{names}\n\nOutput only the required JSON object."


async def translate_job_names(job_names: list[str], client: LLMClient | None = None, batch_size: int = 50) -> dict[str, str]:
    own = client is None
    client = client or LLMClient()
    result: dict[str, str] = {}
    try:
        for index in range(0, len(job_names), batch_size):
            chunk = job_names[index:index + batch_size]
            response = await client.call(build_translate_prompt(chunk), SLOT_POOLS["translate"][0], system=TRANSLATE_SYSTEM, max_tokens=8000)
            for item in response.get("results", []) if isinstance(response, dict) else []:
                if isinstance(item, dict) and item.get("job_name"):
                    result[str(item["job_name"])] = str(item.get("job_name_zh") or item["job_name"])
            for name in chunk:
                result.setdefault(name, name)
    finally:
        if own:
            await client.close()
    return result

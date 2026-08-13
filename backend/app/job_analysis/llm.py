"""LLM API 客户端 —— OpenAI 兼容格式，支持 DeepSeek/Claude/其他。"""
import json
import asyncio
import httpx
from app.job_analysis.config import LLM_API_KEY, LLM_BASE_URL

# 全局计数器（用于成本统计）
_call_count = 0
_total_prompt_tokens = 0
_total_completion_tokens = 0


def reset_cost_counters():
    global _call_count, _total_prompt_tokens, _total_completion_tokens
    _call_count = 0
    _total_prompt_tokens = 0
    _total_completion_tokens = 0


def get_cost_summary() -> dict:
    total = _total_prompt_tokens + _total_completion_tokens
    return {
        "total_tokens": total,
        "prompt_tokens": _total_prompt_tokens,
        "completion_tokens": _total_completion_tokens,
        "api_calls": _call_count,
    }


def _extract_json(text: str) -> dict:
    """尽力从 LLM 输出中提取 JSON。"""
    text = text.strip()
    # 直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # 提取 ```json ... ``` 块
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    # 提取第一个 { ... } 对
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass
    # 返回错误
    return {"_error": f"JSON parse failed: {text[:200]}"}


async def call_llm(
    prompt: str,
    model: str,
    response_schema: dict | None = None,
    temperature: float = 0.0,
    max_tokens: int = 4096,
    max_retries: int = 1,
    system: str = "You are a precise job data analyst. Output valid JSON only.",
) -> dict:
    """单次 LLM 调用（OpenAI 兼容 API）。"""
    global _call_count, _total_prompt_tokens, _total_completion_tokens

    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json",
    }
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": prompt},
    ]
    body: dict = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if response_schema:
        body["response_format"] = {"type": "json_object"}
        # DeepSeek 不支持 json_schema, 将 schema 注入 system prompt
        schema_hint = (
            f"\n\nYou MUST output a JSON object with exactly these keys: "
            f"{json.dumps(list(response_schema.get('properties', {}).keys()))}."
        )
        messages[0]["content"] += schema_hint

    last_error = None
    for attempt in range(max_retries + 1):
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{LLM_BASE_URL}/chat/completions",
                    json=body,
                    headers=headers,
                    timeout=120.0,
                )
                if resp.status_code >= 500:
                    last_error = f"HTTP {resp.status_code}"
                    if attempt < max_retries:
                        await asyncio.sleep(2)
                        continue
                    return {"_error": last_error}

                resp.raise_for_status()
                data = resp.json()
                _call_count += 1

                usage = data.get("usage", {})
                _total_prompt_tokens += usage.get("prompt_tokens", 0)
                _total_completion_tokens += usage.get("completion_tokens", 0)

                content = data["choices"][0]["message"]["content"]
                return _extract_json(content)

        except (httpx.TimeoutException, httpx.ConnectError) as e:
            last_error = str(e)
            if attempt < max_retries:
                await asyncio.sleep(2)
                continue
            return {"_error": last_error}
        except httpx.HTTPStatusError as e:
            last_error = f"HTTP {e.response.status_code}: {e.response.text[:200]}"
            if attempt < max_retries:
                await asyncio.sleep(2)
                continue
            return {"_error": last_error}

    return {"_error": last_error or "unknown error"}


async def call_llm_batch(
    prompts: list[str],
    model: str,
    response_schema: dict | None = None,
    temperature: float = 0.0,
    max_tokens: int = 4096,
    max_concurrent: int = 5,
    system: str = "You are a precise job data analyst. Output valid JSON only.",
) -> list[dict]:
    """批量 LLM 调用，semaphore 控制并发。"""
    semaphore = asyncio.Semaphore(max_concurrent)

    async def bounded(prompt):
        async with semaphore:
            return await call_llm(
                prompt, model, response_schema, temperature, max_tokens,
                system=system,
            )

    tasks = [bounded(p) for p in prompts]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return [
        {"_error": str(r)} if isinstance(r, Exception) else r
        for r in results
    ]


import re  # noqa: E402（_extract_json 需要）

"""LLM API 客户端 —— OpenAI 兼容格式，槽位池 + 高并发 + 自适应限速。"""
from __future__ import annotations
import asyncio
import json
import re
import time

import httpx

from .config import (LLM_API_KEY, LLM_BASE_URL, JD_MAX_CONCURRENT,
                    JD_TARGET_CONCURRENT, JD_LLM_TIMEOUT,
                    JD_CONNECT_TIMEOUT, JD_READ_TIMEOUT,
                    MODEL_TEMPERATURE_OVERRIDE, MODEL_NO_RESPONSE_FORMAT)

# 全局成本计数器（兼容旧接口）
_call_count = 0
_total_prompt_tokens = 0
_total_completion_tokens = 0
# per-model token 计数（成本估算用）
_model_tokens: dict[str, dict[str, int]] = {}

DEFAULT_SYSTEM = ("You are a precise job data analyst. "
                  "Output valid JSON only.")


def reset_cost_counters():
    global _call_count, _total_prompt_tokens, _total_completion_tokens
    _call_count = _total_prompt_tokens = _total_completion_tokens = 0
    _model_tokens.clear()


def get_cost_summary() -> dict:
    return {
        "total_tokens": _total_prompt_tokens + _total_completion_tokens,
        "prompt_tokens": _total_prompt_tokens,
        "completion_tokens": _total_completion_tokens,
        "api_calls": _call_count,
        "model_tokens": dict(_model_tokens),
    }


def _extract_json(text: str) -> dict:
    text = text.strip()
    if not text:
        return {"_error": "empty content from model"}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            pass
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(text[start:end + 1].strip())
        except json.JSONDecodeError:
            pass
        # 截断容错：模型输出被 max_tokens 截断时 JSON 不完整，
        # 尝试补闭合括号后解析（丢弃被截断的尾部条目）
        fragment = text[start:end + 1]
        for extra in ("}", "]}", "]}]", "\n]}", "\n]}]"):
            try:
                return json.loads(fragment + extra)
            except json.JSONDecodeError:
                continue
    return {"_error": f"JSON parse failed: {text[:200]}"}


class RateLimiter:
    """429 自适应：指数退避 + 降并发；平稳期逐步回升至 target。"""

    def __init__(self, base: int = JD_MAX_CONCURRENT,
                 target: int = JD_TARGET_CONCURRENT):
        self.concurrent = base
        self.target = target
        self.backoff_s = 1.0
        self._last_429 = 0.0

    def hit_429(self) -> None:
        self._last_429 = time.monotonic()
        self.concurrent = max(2, self.concurrent // 2)
        self.backoff_s = min(self.backoff_s * 2, 32.0)

    def step_up(self, monotonic: float | None = None) -> None:
        now = monotonic if monotonic is not None else time.monotonic()
        if now - self._last_429 > 60 and self.concurrent < self.target:
            self.concurrent = min(self.target, self.concurrent + 2)
            self.backoff_s = max(1.0, self.backoff_s / 2)

    def sleep_s(self) -> float:
        return self.backoff_s


class LLMClient:
    """会话级 httpx 客户端（持久连接池）。统计与降级计数内置。

    endpoint_override: {"base_url": ..., "api_key": ...} 时走该端点
    （官方 DeepSeek 等直连端点），否则走 config 默认的 go 端点。
    """

    def __init__(self, client: httpx.AsyncClient | None = None,
                 consecutive_fail_limit: int = 3,
                 endpoint_override: dict | None = None):
        self._own_client = client is None
        self._client = client
        self.consecutive_fail_limit = consecutive_fail_limit
        self._fail_counts: dict[str, int] = {}
        self.limiter = RateLimiter()
        self.endpoint = endpoint_override or {}

    def _base_url(self) -> str:
        return self.endpoint.get("base_url", LLM_BASE_URL)

    def _api_key(self) -> str:
        return self.endpoint.get("api_key", LLM_API_KEY)

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(
                    JD_READ_TIMEOUT, connect=JD_CONNECT_TIMEOUT),
                limits=httpx.Limits(
                    max_connections=JD_TARGET_CONCURRENT * 2,
                    max_keepalive_connections=JD_TARGET_CONCURRENT),
            )
        return self._client

    async def close(self) -> None:
        if self._own_client and self._client is not None:
            await self._client.aclose()

    def _record_failure(self, model: str) -> None:
        self._fail_counts[model] = self._fail_counts.get(model, 0) + 1

    def _reset_failures(self, model: str) -> None:
        self._fail_counts[model] = 0

    def _exhausted(self, model: str) -> bool:
        return self._fail_counts.get(model, 0) >= self.consecutive_fail_limit

    async def call(
        self, prompt: str, model: str,
        response_schema: dict | None = None,
        temperature: float = 0.0, max_tokens: int = 4096,
        max_retries: int = 3,
        system: str = DEFAULT_SYSTEM,
    ) -> dict:
        global _call_count, _total_prompt_tokens, _total_completion_tokens
        headers = {"Authorization": f"Bearer {self._api_key()}",
                   "Content-Type": "application/json"}
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ]
        # 模型怪癖覆写（探针实测）
        temperature = MODEL_TEMPERATURE_OVERRIDE.get(model, temperature)
        supports_format = model not in MODEL_NO_RESPONSE_FORMAT
        body: dict = {
            "model": model, "messages": messages,
            "temperature": temperature, "max_tokens": max_tokens,
        }
        if response_schema and supports_format:
            body["response_format"] = {"type": "json_object"}
            schema_hint = (
                "\n\nYou MUST output a JSON object with exactly these keys: "
                f"{json.dumps(list(response_schema.get('properties', {}).keys()))}."
            )
            messages[0]["content"] += schema_hint

        client = self._get_client()
        last_error = None
        for attempt in range(max_retries + 1):
            t0 = time.perf_counter()
            try:
                resp = await client.post(
                    f"{self._base_url()}/chat/completions",
                    json=body, headers=headers)
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                last_error = str(e)
                if attempt < max_retries:
                    await asyncio.sleep(2)
                    continue
                return {"_error": last_error}

            latency_ms = int((time.perf_counter() - t0) * 1000)
            if resp.status_code == 429:
                self.limiter.hit_429()
                self._record_failure(model)
                last_error = f"HTTP 429: {resp.text[:200]}"
                if attempt < max_retries:
                    await asyncio.sleep(self.limiter.sleep_s())
                    continue
                return {"_error": last_error}
            if resp.status_code >= 500:
                self._record_failure(model)
                last_error = f"HTTP {resp.status_code}"
                if attempt < max_retries:
                    await asyncio.sleep(2)
                    continue
                return {"_error": last_error}
            if resp.status_code != 200:
                self._record_failure(model)
                last_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
                return {"_error": last_error}

            data = resp.json()
            _call_count += 1
            self._reset_failures(model)
            usage = data.get("usage", {})
            pt = usage.get("prompt_tokens", 0)
            ct = usage.get("completion_tokens", 0)
            _total_prompt_tokens += pt
            _total_completion_tokens += ct
            mt = _model_tokens.setdefault(model, {"prompt": 0, "completion": 0})
            mt["prompt"] += pt
            mt["completion"] += ct
            # 模型统计（stats 表）
            self._record_stat(model, ok=True, error_type="",
                              latency_ms=latency_ms, pt=pt, ct=ct)
            content = data["choices"][0]["message"]["content"]
            return _extract_json(content)
        return {"_error": last_error or "unknown error"}

    def _record_stat(self, model, ok, error_type, latency_ms,
                     pt=0, ct=0, halluc_removed=0):
        """写模型统计到 SQLite（db_state 可用时）。"""
        try:
            from db_state import StateDB
            StateDB().record_stat(
                model, "all", ok=ok, error_type=error_type,
                latency_ms=latency_ms, prompt_tokens=pt,
                completion_tokens=ct,
                hallucinations_removed=halluc_removed)
        except Exception:
            pass    # 统计失败不影响主流程

    async def call_with_pool(
        self, prompt: str, slot_pool: list[str],
        response_schema: dict | None = None,
        temperature: float = 0.0, max_tokens: int = 4096,
        max_retries: int = 3, system: str = DEFAULT_SYSTEM,
    ) -> dict:
        """槽位池调用：按优先级取模型，连续失败超限自动降级到下一个。"""
        for model in slot_pool:
            if self._exhausted(model):
                continue
            r = await self.call(prompt, model, response_schema,
                                temperature, max_tokens, max_retries,
                                system=system)
            if "_error" not in r:
                return r
        return {"_error": f"all models in pool exhausted: {slot_pool}"}

    async def call_batch_consolidated(
        self, prompts: list[str], model: str,
        response_schema: dict | None = None,
        temperature: float = 0.0, max_tokens: int = 16000,
        system: str = DEFAULT_SYSTEM, batch_size: int = 5,
        item_ids: list[int] | None = None,
    ) -> list[dict]:
        """批量合并调用：一次 HTTP 调用塞 batch_size 条 prompt。

        与 call_batch 的区别：call_batch 是 N 次 HTTP 并发；
        本方法把 N 条拼进 1 个请求，模型返回 {"results": [...]}，
        按 item_ids（调用方显式传入）对齐拆分；未传则从 prompt
        正则兜底提取（仅测试用）。
        """
        semaphore = asyncio.Semaphore(self.limiter.concurrent)

        def ids_of(chunk: list[str]) -> list[int]:
            out = []
            for p in chunk:
                out.extend(int(m) for m in re.findall(
                    r"jd_id:\s*(\d+)", p))
            return out

        async def bounded(chunk, ids):
            async with semaphore:
                combined = "\n\n=== ITEM ===\n\n".join(chunk)
                resp = await self.call(combined, model, response_schema,
                                       temperature, max_tokens,
                                       system=system)
                if "_error" in resp or "results" not in resp:
                    return [{"_error": f"batch: {resp.get('_error', resp)}"}
                            for _ in chunk]
                from batch_prompts import split_batch_response
                return split_batch_response(resp, ids)

        chunks = [prompts[i:i + batch_size]
                  for i in range(0, len(prompts), batch_size)]
        # 每个 chunk 的对齐键：显式 item_ids 时按 prompt 内的标记数切片
        # （一个合并 prompt 含 N 条 → 该 chunk 应拿全部 N 个 id）；
        # 只保留真实存在的 id（防 JD 原文恰好含 "jd_id:" 字面误匹配）。
        chunk_ids: list[list[int]] = []
        if item_ids is not None:
            id_set = set(item_ids)
            for c in chunks:
                found = [i for i in ids_of(c) if i in id_set]
                chunk_ids.append(found if found else list(item_ids))
        else:
            chunk_ids = [ids_of(c) for c in chunks]
        chunk_results = await asyncio.gather(
            *[bounded(c, ids) for c, ids in zip(chunks, chunk_ids)],
            return_exceptions=True)
        out: list[dict] = []
        for i, r in enumerate(chunk_results):
            if isinstance(r, Exception):
                out.extend([{"_error": str(r)}
                            for _ in chunks[i]])
            else:
                out.extend(r)
        return out

    async def call_batch(
        self, prompts: list[str], model: str,
        response_schema: dict | None = None,
        temperature: float = 0.0, max_tokens: int = 4096,
        system: str = DEFAULT_SYSTEM,
    ) -> list[dict]:
        """批量调用，semaphore 由限速器并发控制。"""
        semaphore = asyncio.Semaphore(self.limiter.concurrent)

        async def bounded(p):
            async with semaphore:
                return await self.call(p, model, response_schema,
                                       temperature, max_tokens,
                                       system=system)

        results = await asyncio.gather(
            *[bounded(p) for p in prompts], return_exceptions=True)
        return [{"_error": str(r)} if isinstance(r, Exception) else r
                for r in results]


# ── 兼容旧接口（translate/differ/旧 stage 迁移期使用）──
_DEFAULT_CLIENT: LLMClient | None = None


def _default() -> LLMClient:
    global _DEFAULT_CLIENT
    if _DEFAULT_CLIENT is None:
        _DEFAULT_CLIENT = LLMClient()
    return _DEFAULT_CLIENT


async def call_llm(prompt: str, model: str,
                   response_schema: dict | None = None,
                   temperature: float = 0.0, max_tokens: int = 4096,
                   max_retries: int = 1, system: str = DEFAULT_SYSTEM) -> dict:
    return await _default().call(prompt, model, response_schema,
                                 temperature, max_tokens, max_retries,
                                 system=system)


async def call_llm_batch(prompts: list[str], model: str,
                         response_schema: dict | None = None,
                         temperature: float = 0.0, max_tokens: int = 4096,
                         max_concurrent: int = 5,
                         system: str = DEFAULT_SYSTEM) -> list[dict]:
    return await _default().call_batch(
        prompts, model, response_schema, temperature, max_tokens,
        system=system)

"""Explicit OpenAI-compatible endpoint, one request, bounded time, safe errors."""
import asyncio
from typing import Literal
from urllib.parse import urlsplit

import httpx
from pydantic import Field, model_validator

from ..baseline.contract import Strict, Text
from .processor import Completion


class CloudConfig(Strict):
    provider: Text
    endpoint: Text
    model: Text
    model_revision: Text
    account_region: Text
    policy_checked_on: Text
    policy_note: Text
    timeout_seconds: float = Field(gt=0, le=600)
    max_tokens: int = Field(gt=0, le=65536)
    thinking: Literal["enabled", "disabled"]
    reasoning_effort: Literal["low", "high", "max"] = "high"

    @model_validator(mode="after")
    def endpoint_without_credentials(self):
        url = urlsplit(self.endpoint)
        if url.scheme != "https" or not url.hostname or url.username or url.password or url.query or url.fragment:
            raise ValueError("explicit_https_endpoint_without_credentials_required")
        return self


class CloudProcessor:
    def __init__(self, config: CloudConfig, credential: str, client: httpx.AsyncClient | None = None):
        if not credential.strip():
            raise ValueError("missing_credential")
        self.config = config
        self.descriptor = config.model_dump()
        self._credential = credential.strip()
        self._client = client

    async def complete(self, messages):
        async def request(client):
            response = await client.post(self.config.endpoint,
                headers={"Authorization": f"Bearer {self._credential}"},
                json=dict(model=self.config.model, messages=messages, max_tokens=self.config.max_tokens,
                          thinking={"type": self.config.thinking}, response_format={"type": "json_object"},
                          reasoning_effort=self.config.reasoning_effort, stream=False))
            if response.status_code != 200:
                return Completion(status="http_error", metadata={"http_status": response.status_code})
            try:
                body = response.json()
                choice = body["choices"][0]
                finish = choice["finish_reason"]
                content = choice["message"].get("content")
                if choice["message"].get("refusal") or finish == "content_filter":
                    return Completion(status="refused", finish_reason="content_filter")
                if finish not in {"stop", "length"} or not isinstance(content, (str, type(None))):
                    raise ValueError("invalid_completion_shape")
                usage = body.get("usage", {})
                usage = {k: v for k, v in usage.items() if k in {
                    "prompt_tokens", "completion_tokens", "total_tokens", "prompt_cache_hit_tokens",
                    "prompt_cache_miss_tokens"} and type(v) is int and v >= 0}
                metadata = {k: body[k] for k in ("id", "model", "system_fingerprint")
                            if isinstance(body.get(k), str)}
                metadata["returned_model"] = metadata.pop("model", "not_reported")
                metadata["usage"] = usage
                return Completion(content=content or "", finish_reason=finish, metadata=metadata)
            except (ValueError, KeyError, IndexError, TypeError, AttributeError):
                return Completion(status="invalid_response")

        try:
            async with asyncio.timeout(self.config.timeout_seconds):
                if self._client is not None:
                    return await request(self._client)
                # No inherited proxy, implicit endpoint, redirects, SDK logging or automatic retries.
                async with httpx.AsyncClient(timeout=self.config.timeout_seconds, trust_env=False,
                                             follow_redirects=False) as client:
                    return await request(client)
        except (TimeoutError, httpx.TimeoutException):
            return Completion(status="timeout")
        except httpx.RequestError:
            return Completion(status="network_error")

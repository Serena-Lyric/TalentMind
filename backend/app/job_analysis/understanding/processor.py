"""Replaceable semantic processor boundary; a completion is never human truth."""
from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class Completion:
    content: str = ""
    finish_reason: str | None = None
    status: str = "ok"
    metadata: dict = field(default_factory=dict)
    request: list[dict] | None = None
    draft: dict | None = None


class Processor(Protocol):
    descriptor: dict

    async def complete(self, messages: list[dict]) -> Completion: ...

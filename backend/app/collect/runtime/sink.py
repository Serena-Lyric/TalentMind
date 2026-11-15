"""Persistence adapter for the existing pipeline/repository contract."""
from __future__ import annotations

from typing import Any, Callable


class DatabaseSink:
    """Keep the database provider injectable for isolated tests and runtime workers."""

    def __init__(self, provider: Callable[[], Any]):
        self._provider = provider
        self.last_stats: dict[str, Any] = {}

    def db_provider(self) -> Callable[[], Any]:
        return self._provider

    def record_stats(self, stats: dict[str, Any]) -> None:
        self.last_stats = dict(stats or {})

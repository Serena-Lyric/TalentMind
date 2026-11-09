"""The single Edge CDP execution engine used by all three platforms."""
from __future__ import annotations

from typing import Any, Callable

from app.collect import browser as legacy_browser
from app.collect import fetch_boss_jobs, fetch_cn_jobs
from app.collect.fetchers.cdp import CdpError
from app.collect.runtime.platforms import PLATFORMS, RuntimeConfig, get_platform


def _classify_error(exc: BaseException) -> str:
    message = str(exc).lower()
    if isinstance(exc, legacy_browser.AccessBlocked) or any(
        word in message for word in ('verification', 'security_check', 'content_limited', 'blocked')
    ):
        return 'blocked'
    if 'login' in message or '登录' in message:
        return 'needs_login'
    return 'failed'


def _classify_stats(stats: dict[str, Any]) -> str:
    reason = str(stats.get('stop_reason') or '').lower()
    if not reason:
        return 'success'
    if any(word in reason for word in ('verification', 'security', 'content_limited', 'blocked')):
        return 'blocked'
    if 'login' in reason or '登录' in reason:
        return 'needs_login'
    return 'failed'


class CdpEngine:
    """Dispatch one bounded page/detail cycle to the existing Edge CDP entrypoints."""

    def __init__(
        self,
        *,
        boss_runner: Callable[..., dict[str, Any]] | None = None,
        cn_runner: Callable[..., dict[str, Any]] | None = None,
    ) -> None:
        self._boss_runner = boss_runner or fetch_boss_jobs.run_fetch
        self._cn_runner = cn_runner or fetch_cn_jobs.run_fetch

    def fetch_once(
        self,
        platform: str,
        keyword: str,
        city: tuple[str, str],
        page: int,
        db_provider: Callable[[], Any],
        *,
        config: RuntimeConfig | None = None,
        on_event: Callable[[dict[str, Any]], None] | None = None,
    ) -> dict[str, Any]:
        definition = get_platform(platform)
        config = config or RuntimeConfig()
        config.validate()
        events: list[dict[str, Any]] = []

        def emit(event: dict[str, Any]) -> None:
            events.append(event)
            if on_event is not None:
                on_event(event)

        kwargs = dict(
            cdp_endpoint='auto',
            user_data_dir=str(definition.profile_dir),
            pages=1,
            detail_limit=config.detail_limit,
            max_jobs=config.max_jobs,
            delay=config.page_delay_min,
            settle=config.settle,
            login_timeout=0,
            db_provider=db_provider,
            on_event=emit,
        )
        try:
            if platform == 'boss':
                stats = self._boss_runner([keyword], [city], **kwargs)
            else:
                stats = self._cn_runner(platform, [keyword], [city], **kwargs)
            return {'status': _classify_stats(stats), 'stats': stats, 'events': events}
        except Exception as exc:
            return {
                'status': _classify_error(exc), 'stats': {}, 'events': events,
                'error_type': type(exc).__name__, 'error': str(exc),
            }

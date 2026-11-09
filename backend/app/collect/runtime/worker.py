"""Per-platform low-frequency rotation worker; no site parsing lives here."""
from __future__ import annotations

import argparse
import json
import time
from typing import Any, Callable

from app.collect.runtime import state as runtime_state
from app.collect.runtime.platforms import RuntimeConfig, config_from_payload


def _last_saved_identity(events: list[dict[str, Any]]) -> str | None:
    for event in reversed(events):
        if event.get('event') == 'persisted':
            for item in event.get('items') or []:
                value = item.get('source_detail')
                if value:
                    return str(value)
        job = event.get('job') or {}
        if job.get('url'):
            return str(job['url'])
    return None


def _advance(value: runtime_state.RuntimeState, config: RuntimeConfig, platform: str) -> float:
    cities = config.cities[platform]
    if value.page < config.pages:
        value.page += 1
        return config.page_delay_min
    value.page = 1
    value.city_index += 1
    if value.city_index >= len(cities):
        value.city_index = 0
        value.keyword_index += 1
        if value.keyword_index >= len(config.keywords):
            value.keyword_index = 0
    return config.switch_interval_min


def _wait_until(due: float, platform: str, *, state_root, clock, sleeper) -> bool:
    while True:
        if runtime_state.stop_requested(platform, root=state_root):
            return False
        remaining = due - clock()
        if remaining <= 0:
            return True
        sleeper(min(1.0, remaining))


def run_worker(
    platform: str,
    config: RuntimeConfig,
    *,
    engine,
    sink,
    state_root=None,
    max_rounds: int = 0,
    clock: Callable[[], float] = time.time,
    sleeper: Callable[[float], None] = time.sleep,
) -> runtime_state.RuntimeState:
    """Run one platform until stopped, blocked, failed, or max_rounds is reached."""
    config.validate()
    if type(max_rounds) is not int or max_rounds < 0:
        raise ValueError('max_rounds must be a non-negative integer')
    value = runtime_state.load_state(platform, root=state_root)
    rounds = 0
    try:
        while max_rounds == 0 or rounds < max_rounds:
            if value.next_run_at is not None:
                if not _wait_until(value.next_run_at, platform, state_root=state_root, clock=clock, sleeper=sleeper):
                    value.status = 'stopped'
                    value.next_run_at = None
                    value.updated_at = clock()
                    runtime_state.save_state(value, root=state_root)
                    return value
            if runtime_state.stop_requested(platform, root=state_root):
                value.status = 'stopped'
                value.next_run_at = None
                value.updated_at = clock()
                runtime_state.save_state(value, root=state_root)
                return value

            keywords = config.keywords
            cities = config.cities[platform]
            value.keyword_index %= len(keywords)
            value.city_index %= len(cities)
            if not 1 <= value.page <= config.pages:
                value.page = 1
            keyword = keywords[value.keyword_index]
            city = cities[value.city_index]
            value.status = 'running'
            value.next_run_at = None
            value.stop_reason = None
            value.updated_at = clock()
            runtime_state.save_state(value, root=state_root)

            try:
                result = engine.fetch_once(
                    platform, keyword, city, value.page, sink.db_provider(),
                    config=config,
                )
            except Exception as exc:
                value.status = 'failed'
                value.stop_reason = f'{type(exc).__name__}: {exc}'
                value.next_run_at = None
                value.updated_at = clock()
                runtime_state.save_state(value, root=state_root)
                return value

            status = result.get('status')
            stats = result.get('stats') or {}
            value.stats = stats
            if hasattr(sink, 'record_stats'):
                sink.record_stats(stats)
            if status in {'blocked', 'needs_login', 'failed'}:
                value.status = status
                value.stop_reason = str(result.get('error') or stats.get('stop_reason') or status)
                value.next_run_at = None
                value.updated_at = clock()
                runtime_state.save_state(value, root=state_root)
                return value
            if status != 'success':
                value.status = 'failed'
                value.stop_reason = f'unknown_engine_status:{status}'
                value.next_run_at = None
                value.updated_at = clock()
                runtime_state.save_state(value, root=state_root)
                return value

            value.last_success_at = clock()
            value.last_saved_identity = _last_saved_identity(result.get('events') or []) or value.last_saved_identity
            delay = _advance(value, config, platform)
            value.status = 'waiting'
            value.next_run_at = clock() + delay
            value.updated_at = clock()
            runtime_state.save_state(value, root=state_root)
            rounds += 1
            if max_rounds and rounds >= max_rounds:
                return value
            if not _wait_until(value.next_run_at, platform, state_root=state_root, clock=clock, sleeper=sleeper):
                value.status = 'stopped'
                value.next_run_at = None
                value.updated_at = clock()
                runtime_state.save_state(value, root=state_root)
                return value
    except Exception as exc:
        value.status = 'failed'
        value.stop_reason = f'{type(exc).__name__}: {exc}'
        value.next_run_at = None
        value.updated_at = clock()
        runtime_state.save_state(value, root=state_root)
        return value
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description='Run one isolated collection platform worker')
    parser.add_argument('--platform', required=True, choices=('boss', 'zhaopin', 'liepin'))
    parser.add_argument('--config-json', required=True)
    args = parser.parse_args()
    config = config_from_payload(json.loads(args.config_json))
    from app.db.mysql import get_db
    from app.collect.runtime.browser import CdpEngine
    from app.collect.runtime.sink import DatabaseSink

    result = run_worker(
        args.platform, config, engine=CdpEngine(), sink=DatabaseSink(get_db),
    )
    print(json.dumps(result.to_dict(), ensure_ascii=False))
    return 2 if result.status in {'failed', 'blocked', 'needs_login'} else 0


if __name__ == '__main__':
    raise SystemExit(main())

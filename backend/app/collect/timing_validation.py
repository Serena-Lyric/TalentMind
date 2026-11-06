"""Non-overridable timing floors for the three browser collection adapters.

The ranges are defaults, not maximum speeds: slower user settings remain valid.
This validation complements the persistent action gate; it cannot replace it.
"""
from __future__ import annotations

import math

from app.collect.frequency import PAGE_DELAY_MIN, SWITCH_INTERVAL_MIN


def validate_seconds(value: float, *, minimum: float = 0.0, name: str = 'seconds') -> None:
    if type(value) not in (int, float) or not math.isfinite(value) or value < minimum:
        raise ValueError(f'{name} 必须为有限数值且 >= {minimum:g} 秒')


def validate_range(lower: float, upper: float, *, minimum: float = 0.0, name: str = 'range') -> None:
    validate_seconds(lower, minimum=minimum, name=f'{name}_min')
    validate_seconds(upper, minimum=minimum, name=f'{name}_max')
    if upper < lower:
        raise ValueError(f'{name} 必须满足 lower <= upper')


def validate_collection_ranges(page_min, page_max, settle_min, settle_max, switch_min, switch_max) -> None:
    validate_range(page_min, page_max, minimum=PAGE_DELAY_MIN, name='page_delay')
    validate_range(settle_min, settle_max, minimum=5.0, name='settle')
    validate_range(switch_min, switch_max, minimum=SWITCH_INTERVAL_MIN, name='switch_interval')


def validate_fetch_timing(delay, settle) -> None:
    validate_seconds(delay, minimum=PAGE_DELAY_MIN, name='delay')
    validate_seconds(settle, minimum=5.0, name='settle')

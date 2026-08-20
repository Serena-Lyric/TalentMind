from __future__ import annotations

import random

import pytest

from app.collect.boss_collect_loop import QueryTarget, build_targets, run_loop


def test_build_targets_uses_stable_keyword_city_order():
    targets = build_targets(["Python", "Java"], [("北京", "101010100"), ("上海", "101020100")])
    assert targets == [
        QueryTarget("Python", "北京", "101010100"),
        QueryTarget("Python", "上海", "101020100"),
        QueryTarget("Java", "北京", "101010100"),
        QueryTarget("Java", "上海", "101020100"),
    ]


def test_build_targets_rejects_empty_input():
    with pytest.raises(ValueError):
        build_targets([], [])


def test_run_loop_rotates_targets_and_uses_bounded_intervals():
    targets = build_targets(["Python", "Java"], [("北京", "101010100")])
    calls: list[tuple[str, str, float, float]] = []
    sleeps: list[float] = []

    def fake_fetch(keywords, cities, **kwargs):
        calls.append((keywords[0], cities[0][0], kwargs["delay"], kwargs["settle"]))
        return {"new": 1}

    result = run_loop(
        targets,
        cdp_endpoint="http://127.0.0.1:9333",
        user_data_dir=None,
        rounds=3,
        page_delay_min=18,
        page_delay_max=18,
        settle_min=5,
        settle_max=5,
        switch_interval_min=480,
        switch_interval_max=480,
        sleeper=sleeps.append,
        fetcher=fake_fetch,
        rng=random.Random(1),
    )

    assert result == 0
    assert [call[:2] for call in calls] == [("Python", "北京"), ("Java", "北京"), ("Python", "北京")]
    assert all(call[2:] == (18, 5) for call in calls)
    assert sleeps == [480, 480]


def test_run_loop_stops_on_cdp_error():
    targets = [QueryTarget("Python", "北京", "101010100")]
    sleeps: list[float] = []

    def fake_fetch(*args, **kwargs):
        from app.collect.fetchers.cdp import CdpError

        raise CdpError("login required")

    result = run_loop(
        targets,
        cdp_endpoint="http://127.0.0.1:9333",
        user_data_dir=None,
        rounds=0,
        sleeper=sleeps.append,
        fetcher=fake_fetch,
        rng=random.Random(1),
    )

    assert result == 2
    assert sleeps == []
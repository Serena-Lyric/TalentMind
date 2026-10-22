"""Repository-wide test safety defaults."""
from __future__ import annotations

import os

import pytest


def pytest_collection_modifyitems(config, items):
    """Keep bare pytest runs out of service-writing integration tests."""
    if os.environ.get("TALENTMIND_ALLOW_INTEGRATION") == "1":
        return
    skip = pytest.mark.skip(
        reason=(
            "integration tests require an explicitly verified isolated instance; "
            "set TALENTMIND_ALLOW_INTEGRATION=1 only after checking the target"
        )
    )
    for item in items:
        if item.get_closest_marker("integration") is not None:
            item.add_marker(skip)

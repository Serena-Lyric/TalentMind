"""Repository-wide test safety defaults."""
from __future__ import annotations

import os

import pytest


def pytest_collection_modifyitems(config, items):
    """Never let a bare pytest run write through integration fixtures."""
    if os.environ.get("TALENTMIND_ALLOW_INTEGRATION") == "1":
        return
    skip = pytest.mark.skip(
        reason=(
            "integration tests require an explicitly verified isolated instance, "
            "TALENTMIND_ALLOW_INTEGRATION=1, and the destructive-import "
            "authorization file bound to the live target"
        )
    )
    for item in items:
        if item.get_closest_marker("integration") is not None:
            item.add_marker(skip)

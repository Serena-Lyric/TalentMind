"""No Neo4j server is used; exercise request and application resource ownership."""
import asyncio

import pytest

from app.db import neo4j
from app.main import app


class Driver:
    def __init__(self):
        self.closed = False
    def close(self): self.closed = True


@pytest.mark.parametrize("fail_application", [False, True])
def test_application_lifespan_releases_driver_even_on_failure(monkeypatch, fail_application):
    driver = Driver()
    monkeypatch.setattr(neo4j, "_driver", driver)
    async def exercise():
        try:
            async with app.router.lifespan_context(app):
                assert neo4j.get_neo4j() is driver
                if fail_application: raise RuntimeError("application failed")
        except RuntimeError:
            assert fail_application
        assert driver.closed
        assert neo4j._driver is None
    asyncio.run(exercise())


def test_driver_is_shared_lazily_and_recreated_after_shutdown(monkeypatch):
    created = []
    def factory(*args, **kwargs):
        driver = Driver()
        created.append(driver)
        return driver
    monkeypatch.setattr(neo4j, "_driver", None)
    monkeypatch.setattr(neo4j.GraphDatabase, "driver", factory)
    first = neo4j.get_neo4j()
    assert neo4j.get_neo4j() is first
    neo4j.close_neo4j()
    assert first.closed
    second = neo4j.get_neo4j()
    assert second is not first
    assert len(created) == 2
    neo4j.close_neo4j()
    assert second.closed

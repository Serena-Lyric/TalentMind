"""No Neo4j server is used; exercise request and application resource ownership."""
import asyncio

import pytest

from app.db import neo4j
from app.main import app
from app.routers import mvp


class Driver:
    def __init__(self):
        self.closed = False
        self.sessions_closed = 0
        self.fail_query = False
    def session(self):
        assert not self.closed
        driver = self
        class Session:
            def __enter__(self): return self
            def __exit__(self, *args): driver.sessions_closed += 1
            def run(self, *args):
                if driver.fail_query: raise RuntimeError("query failed")
                return self
            def data(self): return []
        return Session()
    def close(self): self.closed = True


@pytest.mark.parametrize("fail_query", [False, True])
def test_graph_requests_release_sessions_but_keep_shared_driver(monkeypatch, fail_query):
    driver = Driver()
    driver.fail_query = fail_query
    monkeypatch.setattr(mvp, "get_neo4j", lambda: driver)
    if fail_query:
        with pytest.raises(RuntimeError, match="query failed"):
            mvp.graph_data()
    else:
        mvp.graph_data()
    assert driver.sessions_closed == 1
    assert not driver.closed
    driver.fail_query = False
    mvp.graph_data()
    assert driver.sessions_closed == 2


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

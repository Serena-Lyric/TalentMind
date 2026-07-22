import pytest
from sqlalchemy import text
from app.db.mysql import get_db
from app.db.neo4j import get_neo4j
from app.db.redis import get_redis

pytestmark = pytest.mark.integration

def test_mysql_roundtrip():
    db = next(get_db())
    try:
        assert db.execute(text("SELECT 1")).scalar() == 1
    finally:
        db.close()

def test_neo4j_roundtrip():
    driver = get_neo4j()
    with driver.session() as s:
        assert s.run("RETURN 1 AS n").single()["n"] == 1

def test_redis_roundtrip():
    r = get_redis()
    r.set("tm:ping", "pong")
    assert r.get("tm:ping") == b"pong"
    r.delete("tm:ping")

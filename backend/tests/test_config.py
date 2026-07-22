import os
from app.config import get_settings

def test_settings_reads_env(monkeypatch):
    monkeypatch.setenv("MYSQL_URL", "mysql+pymysql://u:p@h:3306/db")
    monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
    monkeypatch.setenv("NEO4J_USER", "neo4j")
    monkeypatch.setenv("NEO4J_PASSWORD", "pw")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    get_settings.cache_clear()
    s = get_settings()
    assert s.mysql_url.startswith("mysql+pymysql://")
    assert s.openai_api_key == "sk-test"

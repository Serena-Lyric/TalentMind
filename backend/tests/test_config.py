import os
from app.config import get_settings

def test_settings_reads_env(monkeypatch):
    monkeypatch.setenv("MYSQL_URL", "mysql+pymysql://u:p@h:3306/db")
    monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
    monkeypatch.setenv("NEO4J_USER", "neo4j")
    monkeypatch.setenv("NEO4J_PASSWORD", "pw")
    get_settings.cache_clear()
    s = get_settings()
    assert s.mysql_url.startswith("mysql+pymysql://")
    assert s.neo4j_user == "neo4j"

def test_settings_github_token_defaults_to_empty(monkeypatch):
    monkeypatch.setenv("MYSQL_URL", "mysql+pymysql://u:p@h:3306/db")
    monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
    monkeypatch.setenv("NEO4J_USER", "neo4j")
    monkeypatch.setenv("NEO4J_PASSWORD", "pw")
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    get_settings.cache_clear()
    s = get_settings()
    assert s.github_token == ""


def test_settings_github_token_reads_env(monkeypatch):
    monkeypatch.setenv("MYSQL_URL", "mysql+pymysql://u:p@h:3306/db")
    monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
    monkeypatch.setenv("NEO4J_USER", "neo4j")
    monkeypatch.setenv("NEO4J_PASSWORD", "pw")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test123")
    get_settings.cache_clear()
    s = get_settings()
    assert s.github_token == "ghp_test123"

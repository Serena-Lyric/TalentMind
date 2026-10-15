"""离线验证真实采集编排及 SQL 提交；仅使用临时 SQLite 和合成岗位。"""
from contextlib import contextmanager

import pytest
from datetime import datetime

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session

from app.collect import fetch_boss_jobs as boss
from app.collect.fetchers.cdp import CdpError


@pytest.fixture
def offline(monkeypatch, tmp_path):
    from app.db import mysql

    db_path = tmp_path / "interruption.sqlite3"
    engine = create_engine(f"sqlite:///{db_path}")

    @event.listens_for(engine, "before_cursor_execute", retval=True)
    def sqlite_parameters(conn, cursor, statement, params, context, executemany):
        # 原始 SQL 没有 SQLAlchemy 日期类型绑定，测试显式适配避免 sqlite3 旧适配器。
        return statement, tuple(x.isoformat() if isinstance(x, datetime) else x for x in params)

    with engine.begin() as conn:
        conn.execute(text("""CREATE TABLE jd_pool (
            id INTEGER PRIMARY KEY AUTOINCREMENT, source TEXT, source_detail TEXT,
            job_title TEXT, raw_text TEXT, duties TEXT, experience TEXT, quality FLOAT,
            dup_group TEXT, crawled_at DATETIME, status TEXT)"""))

    def get_db():
        with Session(engine) as db:
            yield db

    monkeypatch.setattr(mysql, "get_db", get_db)
    monkeypatch.setattr(boss.time, "sleep", lambda _: None)
    clients = []

    class Client:
        closed = False

        def close(self):
            self.closed = True

        def navigate(self, url, **kwargs):
            self.url = url

        def evaluate(self, script):
            return {"description": "岗位职责：负责 Python 服务开发及维护", "company": "合成公司"}

    def connect(*args, **kwargs):
        client = Client()
        clients.append(client)
        return client

    monkeypatch.setattr(boss.CdpClient, "connect_first_page", connect)

    def rows():
        with engine.connect() as conn:
            return conn.execute(text("SELECT * FROM jd_pool ORDER BY id")).mappings().all()

    rows.engine = engine

    @contextmanager
    def run(**kwargs):
        try:
            yield lambda: boss.run_fetch(["Python"], [("合成城市", "1")], delay=0, settle=0, **kwargs)
        finally:
            assert all(c.closed for c in clients)

    try:
        yield Client, rows, run
    finally:
        engine.dispose()
        db_path.unlink(missing_ok=True)
        assert not db_path.exists()


def card(key, **kwargs):
    return {"url": f"https://www.zhipin.com/job_detail/{key}.html", "title": "合成 Python 岗位", **kwargs}


def test_committed_list_survives_next_page_browser_failure(offline, monkeypatch):
    _, rows, run = offline

    def fetch(client, url, settle):
        if "page=2" in url:
            assert len(rows()) == 1  # 下一页读取前已提交
            raise CdpError("synthetic browser closed")
        return [card("good", tags=["Python"]), card("empty", tags=["本科"])]

    monkeypatch.setattr(boss, "_fetch_search_page", fetch)
    with run(pages=2) as collect:
        with pytest.raises(CdpError, match="synthetic browser closed"):
            collect()
    assert len(rows()) == 1
    assert rows()[0]["source_detail"].endswith("/good.html")


def test_detail_commit_survives_later_failure_and_empty_card_is_discarded(offline, monkeypatch):
    Client, rows, run = offline
    monkeypatch.setattr(boss, "_fetch_search_page", lambda *args: [card("first"), card("empty"), card("last")])
    observed = []

    def detail(self, script):
        if "/first.html" in self.url:
            return {"description": "负责 Python 服务开发"}
        observed.append(len(rows()))
        raise CdpError("synthetic detail closed")

    monkeypatch.setattr(Client, "evaluate", detail)
    with run(pages=1, detail_limit=3) as collect:
        stats = collect()
    assert stats["new"] == 1
    assert observed == [1, 1]
    assert len(rows()) == 1
    assert "/first.html" in rows()[0]["source_detail"]


def test_saved_list_is_enriched_without_duplicate_or_downgrade(offline, monkeypatch):
    Client, rows, run = offline
    monkeypatch.setattr(boss, "_fetch_search_page", lambda *args: [card("same", tags=["Python"])])

    def detail(self, script):
        assert len(rows()) == 1  # 详情开始前列表已保存
        return {"description": "岗位职责：负责 Python 服务开发及维护"}

    monkeypatch.setattr(Client, "evaluate", detail)
    with run(pages=1) as collect:
        stats = collect()
    assert stats["new"] == 1
    assert len(rows()) == 1
    assert "负责 Python 服务开发" in rows()[0]["raw_text"]
    with run(pages=1, no_details=True) as collect:
        assert collect()["new"] == 0
    assert len(rows()) == 1
    assert "负责 Python 服务开发" in rows()[0]["raw_text"]


def test_previous_round_list_can_be_completed_after_detail_connect_failure(offline, monkeypatch):
    _, rows, run = offline
    monkeypatch.setattr(boss, "_fetch_search_page", lambda *args: [card("retry", tags=["Python"])])
    connect = boss.CdpClient.connect_first_page
    calls = 0

    def fail_second(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            assert len(rows()) == 1
            raise CdpError("synthetic connect failure")
        return connect(*args, **kwargs)

    monkeypatch.setattr(boss.CdpClient, "connect_first_page", fail_second)
    with run(pages=1) as collect:
        with pytest.raises(CdpError, match="synthetic connect failure"):
            collect()
    assert len(rows()) == 1
    monkeypatch.setattr(boss.CdpClient, "connect_first_page", connect)
    with run(pages=1) as collect:
        assert collect()["new"] == 0
    assert len(rows()) == 1
    assert "负责 Python 服务开发" in rows()[0]["raw_text"]


def test_limits_apply_across_pages_and_duplicate_urls(offline, monkeypatch):
    _, rows, run = offline
    monkeypatch.setattr(boss, "_fetch_search_page", lambda *args: [
        card("one", tags=["Python"]), card("one", tags=["Java"]), card("two", tags=["Python"]),
    ])
    with run(pages=3, max_jobs=1, detail_limit=1) as collect:
        stats = collect()
    assert stats["listed"] == 1
    assert stats["new"] == 1
    assert stats["details"] == 1
    assert len(rows()) == 1


@pytest.mark.parametrize("old_text,duties", [
    ("职位描述:\n负责既有 Java 服务", ""),
    ("没有标准标题的历史实质职责", ""),
    ("技能标签: Java", "负责既有服务"),
])
def test_existing_substantive_or_unknown_history_is_not_replaced(offline, monkeypatch, old_text, duties):
    _, rows, run = offline
    monkeypatch.setattr(boss, "_fetch_search_page", lambda *args: [card("history", tags=["Python"])])
    with rows.engine.begin() as conn:
        conn.execute(text("INSERT INTO jd_pool (source, source_detail, job_title, raw_text, duties) "
                          "VALUES ('boss', :url, 'synthetic history', :raw, :duties)"),
                     {"url": card("history")["url"], "raw": old_text, "duties": duties})
    with run(pages=1) as collect:
        assert collect()["new"] == 0
    assert len(rows()) == 1
    assert rows()[0]["raw_text"] == old_text
    assert rows()[0]["duties"] == duties


def test_failed_insert_rolls_back_current_record_and_keeps_previous_commit(offline, monkeypatch):
    _, rows, run = offline
    monkeypatch.setattr(boss, "_fetch_search_page", lambda *args: [
        card("first", tags=["Python"]), card("fail", tags=["Java"]),
    ])
    with rows.engine.begin() as conn:
        conn.execute(text("""CREATE TRIGGER synthetic_failure BEFORE INSERT ON jd_pool
            WHEN NEW.source_detail LIKE '%/fail.html'
            BEGIN SELECT RAISE(FAIL, 'synthetic write failure'); END"""))
    from sqlalchemy.exc import IntegrityError

    with run(pages=1, no_details=True) as collect:
        with pytest.raises(IntegrityError, match="synthetic write failure"):
            collect()
    assert len(rows()) == 1
    assert rows()[0]["source_detail"] == card("first")["url"]


def test_detail_redirect_keeps_list_identity(offline, monkeypatch):
    Client, rows, run = offline
    monkeypatch.setattr(boss, "_fetch_search_page", lambda *args: [card("valid", tags=["本科"])])
    monkeypatch.setattr(Client, "evaluate", lambda *args: {
        "url": "https://www.zhipin.com/job_detail/redirect.html", "description": "负责 Python 开发",
    })
    with run(pages=1) as collect:
        assert collect()["new"] == 1
    assert len(rows()) == 1
    assert rows()[0]["source_detail"] == card("valid")["url"]


def test_invalid_detail_cannot_pollute_saved_list(offline, monkeypatch):
    Client, rows, run = offline
    monkeypatch.setattr(boss, "_fetch_search_page", lambda *args: [card("valid", tags=["Python"])])
    monkeypatch.setattr(Client, "evaluate", lambda *args: {"description": "扫码领券，欢迎购买"})
    with run(pages=1) as collect:
        assert collect()["new"] == 1
    assert len(rows()) == 1
    assert "Python" in rows()[0]["raw_text"]
    assert "扫码" not in rows()[0]["raw_text"]


@pytest.mark.parametrize("description", ["暂无描述，详情面议", "", "薪资：20-30K"])
def test_placeholder_detail_does_not_block_next_round_completion(offline, monkeypatch, description):
    Client, rows, run = offline
    monkeypatch.setattr(boss, "_fetch_search_page", lambda *args: [card("retry", tags=["Python"])])
    monkeypatch.setattr(Client, "evaluate", lambda *args: {"description": description})
    with run(pages=1) as collect:
        assert collect()["new"] == 1
    assert len(rows()) == 1
    assert "职位描述" not in rows()[0]["raw_text"]
    monkeypatch.setattr(Client, "evaluate", lambda *args: {"description": "负责 Python 后端服务开发"})
    with run(pages=1) as collect:
        assert collect()["new"] == 0
    assert len(rows()) == 1
    assert "负责 Python 后端服务开发" in rows()[0]["raw_text"]

"""D40 HN Who-is-hiring 采集：纯函数单测（mock Algolia API，不联网不写库）。"""
import httpx

from app.collect.fetchers.hn_hiring import (
    find_current_hiring_post, fetch_hiring_comments, comments_to_rawjds,
)

SEARCH_JSON = {"hits": [
    {"title": "Ask HN: Who is hiring? (August 2026)", "objectID": "49156683"},
    {"title": "Show HN: Other", "objectID": "1"},
]}

ITEMS_JSON = {"children": [
    {"author": "alice", "text": "Acme — Senior Backend Engineer (Python)\nBuild high-scale services with Django and PostgreSQL.\nEmail apply@acme.com"},
    {"author": "bob", "text": "BobCorp | Frontend Engineer | Remote\nReact/TypeScript stack.\nhttps://bob.example/jobs"},
    {"author": "short", "text": "ping"},
]}


class _FakeResp:
    def __init__(self, json_data, status=200):
        self._j = json_data
        self.status_code = status
    def json(self):
        return self._j


class _FakeClient:
    def __init__(self):
        self.calls = []
    def get(self, url, params=None):
        self.calls.append((url, params))
        if "items/" in url:
            return _FakeResp(ITEMS_JSON)
        if "search" in url:
            return _FakeResp(SEARCH_JSON)
        return _FakeResp({}, 404)


def test_find_current_hiring_post():
    c = _FakeClient()
    oid = find_current_hiring_post(c, month_start=1785542400)
    assert oid == "49156683"
    assert c.calls[0][1]["tags"] == "story"


def test_fetch_hiring_comments_filters_short():
    c = _FakeClient()
    comments = fetch_hiring_comments(c, "49156683")
    assert len(comments) == 2  # 短评论被过滤
    assert comments[0]["author"] == "alice"


def test_comments_to_rawjds():
    comments = [{"author": "alice", "text": "Acme — Senior Backend Engineer (Python)\nBuild services.\napply@acme.com"}]
    raws = comments_to_rawjds(comments, "49156683")
    assert len(raws) == 1
    r = raws[0]
    assert r.source == "hn"
    assert r.job_title.startswith("Acme")
    assert "Build services" in r.raw_html
    assert "item?id=49156683" in r.source_detail
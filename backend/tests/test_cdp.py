"""CDP 连接层测试，不启动真实浏览器。"""
from __future__ import annotations

import json
from collections import deque
import pytest

from app.collect.fetchers import cdp


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeWebSocket:
    def __init__(self):
        self.sent = []
        self.received = deque()

    def send(self, raw):
        message = json.loads(raw)
        self.sent.append(message)
        method = message["method"]
        if method == "Target.getTargets":
            self.received.append({
                "id": message["id"],
                "result": {
                    "targetInfos": [
                        {"targetId": "blank", "type": "page", "url": "about:blank"},
                        {"targetId": "boss", "type": "page", "url": "https://www.zhipin.com/web/geek/jobs"},
                    ]
                },
            })
        elif method == "Target.attachToTarget":
            self.received.append({"id": message["id"], "result": {"sessionId": "session-boss"}})
        elif method == "Runtime.evaluate":
            self.received.append({
                "id": message["id"],
                "sessionId": message.get("sessionId"),
                "result": {"result": {"value": "complete"}},
            })
        else:
            self.received.append({"id": message["id"], "result": {}})

    def recv(self, **kwargs):
        return json.dumps(self.received.popleft())

    def close(self):
        return None


def test_read_devtools_active_port(tmp_path):
    (tmp_path / "DevToolsActivePort").write_text(
        "3180\n/devtools/browser/test-id\n", encoding="utf-8"
    )
    assert cdp._read_devtools_active_port(str(tmp_path)) == (
        "http://127.0.0.1:3180",
        "ws://127.0.0.1:3180/devtools/browser/test-id",
    )


def test_connects_browser_websocket_and_attaches_boss_page(monkeypatch):
    fake_ws = FakeWebSocket()
    monkeypatch.setattr(cdp, "connect", lambda *args, **kwargs: fake_ws)

    client = cdp.CdpClient.connect_first_page("ws://127.0.0.1:3180/devtools/browser/test-id", "zhipin.com")
    try:
        assert client.evaluate("document.readyState") == "complete"
        assert fake_ws.sent[0]["method"] == "Target.getTargets"
        assert fake_ws.sent[1]["method"] == "Target.attachToTarget"
        assert fake_ws.sent[1]["params"]["targetId"] == "boss"
        assert fake_ws.sent[2]["sessionId"] == "session-boss"
    finally:
        client.close()


def test_list_page_targets_uses_active_port_when_fixed_endpoint_fails(monkeypatch, tmp_path):
    (tmp_path / "DevToolsActivePort").write_text("3180\n/devtools/browser/test-id\n", encoding="utf-8")
    calls = []

    def fake_get(url, timeout, **kwargs):
        calls.append(url)
        if url == "http://127.0.0.1:9222/json/list":
            raise cdp.httpx.ConnectError("refused")
        return FakeResponse([
            {"type": "page", "url": "https://www.zhipin.com/web/geek/jobs", "webSocketDebuggerUrl": "ws://page"}
        ])

    monkeypatch.setattr(cdp.httpx, "get", fake_get)
    targets = cdp.list_page_targets(
        "http://127.0.0.1:9222",
        user_data_dir=str(tmp_path),
        target_url_contains="zhipin.com",
    )
    assert targets[0]["webSocketDebuggerUrl"] == "ws://page"
    assert calls == ["http://127.0.0.1:9222/json/list", "http://127.0.0.1:3180/json/list"]


@pytest.mark.parametrize('url', ['https://www.liepin.com/job/1', 'https://zhipin.com.evil.test/', 'https://evil.test/?next=zhipin.com'])
def test_http_missing_exact_platform_never_falls_back(monkeypatch, url):
    monkeypatch.setattr(cdp, '_get_json', lambda _: [
        {'type': 'page', 'url': url, 'webSocketDebuggerUrl': 'ws://127.0.0.1:9333/devtools/page/other'}])
    assert cdp.list_page_targets('http://127.0.0.1:9333', target_url_contains='zhipin.com') == []


def test_browser_websocket_missing_platform_never_attaches_other_page(monkeypatch):
    ws = FakeWebSocket()
    send = ws.send
    def without_boss(raw):
        send(raw)
        if json.loads(raw)['method'] == 'Target.getTargets':
            ws.received[-1]['result']['targetInfos'] = [{'targetId': 'other', 'type': 'page', 'url': 'https://www.liepin.com/'}]
    ws.send = without_boss
    monkeypatch.setattr(cdp, 'connect', lambda *a, **kw: ws)
    with pytest.raises(cdp.CdpError):
        cdp.CdpClient.connect_first_page('ws://127.0.0.1:9333/devtools/browser/id', 'zhipin.com')
    assert all(item['method'] != 'Target.attachToTarget' for item in ws.sent)


@pytest.mark.parametrize('endpoint', ['http://192.168.1.20:9333', 'ws://evil.test/devtools/browser/id', 'http://user:password@127.0.0.1:9333'])
def test_remote_or_credentialed_cdp_rejected_before_io(monkeypatch, endpoint):
    def io(*a, **kw):
        pytest.fail('invalid endpoint must be rejected before network IO')
    monkeypatch.setattr(cdp, '_get_json', io)
    monkeypatch.setattr(cdp, 'connect', io)
    with pytest.raises(cdp.CdpError):
        cdp.CdpClient.connect_first_page(endpoint, 'zhipin.com')


def test_http_discovery_cannot_redirect_websocket_to_other_local_browser(monkeypatch):
    monkeypatch.setattr(cdp,'_get_json',lambda url: [
        {'type':'page','url':'https://www.zhipin.com/', 'webSocketDebuggerUrl':'ws://127.0.0.1:9444/devtools/page/other'}]
        if url.endswith('/json/list') else {'webSocketDebuggerUrl':'ws://127.0.0.1:9444/devtools/browser/other'})
    def foreign(*a,**kw): pytest.fail('Must not connect to another browser port')
    monkeypatch.setattr(cdp,'connect',foreign)
    with pytest.raises(cdp.CdpError):
        cdp.CdpClient.connect_first_page('http://127.0.0.1:9333','zhipin.com')

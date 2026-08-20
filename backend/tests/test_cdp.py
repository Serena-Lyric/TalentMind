"""CDP 连接层测试，不启动真实浏览器。"""
from __future__ import annotations

import json
from collections import deque

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

    def recv(self):
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

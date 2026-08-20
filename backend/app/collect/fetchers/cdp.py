"""Chrome DevTools Protocol 的最小同步客户端（只连接用户已启动的浏览器）。"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import httpx
from websockets.sync.client import connect


class CdpError(RuntimeError):
    pass


def _json_value(value: Any) -> Any:
    if isinstance(value, dict) and "value" in value:
        return value["value"]
    return value


def _http_base(endpoint: str) -> str:
    base = endpoint.rstrip("/")
    if base.endswith("/json/version"):
        return base[: -len("/json/version")]
    if base.endswith("/json/list"):
        return base[: -len("/json/list")]
    return base


def _read_devtools_active_port(user_data_dir: str | None) -> tuple[str, str] | None:
    if not user_data_dir:
        return None
    path = Path(user_data_dir).expanduser() / "DevToolsActivePort"
    try:
        lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        port = int(lines[0])
        websocket_path = lines[1] if len(lines) > 1 else ""
    except (OSError, ValueError, IndexError) as exc:
        if path.exists():
            raise CdpError(f"无法读取 Edge DevToolsActivePort: {path}: {exc}") from exc
        return None
    return f"http://127.0.0.1:{port}", f"ws://127.0.0.1:{port}{websocket_path}"


def _endpoint_candidates(endpoint: str, user_data_dir: str | None) -> tuple[list[str], list[str]]:
    http_endpoints: list[str] = []
    browser_websockets: list[str] = []
    if endpoint.startswith(("ws://", "wss://")):
        browser_websockets.append(endpoint)
    elif endpoint.lower() != "auto":
        http_endpoints.append(_http_base(endpoint))
    active = _read_devtools_active_port(user_data_dir)
    if active:
        active_http, active_ws = active
        if active_http not in http_endpoints:
            http_endpoints.append(active_http)
        if active_ws not in browser_websockets:
            browser_websockets.append(active_ws)
    return http_endpoints, browser_websockets


def _get_json(url: str) -> Any:
    response = httpx.get(url, timeout=5, trust_env=False)
    response.raise_for_status()
    return response.json()


def _page_targets_from_http(base: str, target_url_contains: str = "") -> list[dict]:
    targets = _get_json(f"{base}/json/list")
    if not isinstance(targets, list):
        return []
    pages = [
        target
        for target in targets
        if isinstance(target, dict)
        and target.get("type") == "page"
        and target.get("webSocketDebuggerUrl")
    ]
    if target_url_contains:
        matched = [target for target in pages if target_url_contains in str(target.get("url", ""))]
        if matched:
            return matched
    return pages


def _browser_websocket_from_http(base: str) -> str | None:
    version = _get_json(f"{base}/json/version")
    if isinstance(version, dict):
        websocket_url = version.get("webSocketDebuggerUrl")
        if websocket_url:
            return str(websocket_url)
    return None


def list_page_targets(
    endpoint: str,
    user_data_dir: str | None = None,
    target_url_contains: str = "",
) -> list[dict]:
    """发现标准 CDP 页面目标；必要时从 DevToolsActivePort 切换动态端口。"""
    http_endpoints, _ = _endpoint_candidates(endpoint, user_data_dir)
    errors: list[str] = []
    for base in http_endpoints:
        try:
            return _page_targets_from_http(base, target_url_contains)
        except (httpx.HTTPError, ValueError) as exc:
            errors.append(f"{base}: {exc}")
    if errors:
        raise CdpError("CDP 页面发现失败: " + "；".join(errors))
    return []


class CdpClient:
    def __init__(self, websocket_url: str, session_id: str | None = None):
        self._ws = connect(websocket_url, open_timeout=8, close_timeout=3, max_size=16 * 1024 * 1024)
        self._session_id = session_id
        self._next_id = 0

    @classmethod
    def _connect_browser_target(cls, websocket_url: str, target_url_contains: str = "") -> "CdpClient":
        client = cls(websocket_url)
        try:
            result = client.call("Target.getTargets")
            targets = result.get("targetInfos", [])
            pages = [
                target
                for target in targets
                if target.get("type") == "page" and target.get("url")
            ]
            if target_url_contains:
                matched = [target for target in pages if target_url_contains in str(target.get("url", ""))]
                if matched:
                    pages = matched
            if not pages:
                raise CdpError("浏览器级 CDP 没有可用页面目标")
            attached = client.call(
                "Target.attachToTarget",
                {"targetId": pages[0]["targetId"], "flatten": True},
            )
            session_id = attached.get("sessionId")
            if not session_id:
                raise CdpError("浏览器级 CDP 附加页面未返回 sessionId")
            client._session_id = session_id
            return client
        except Exception:
            client.close()
            raise

    @classmethod
    def connect_first_page(
        cls,
        endpoint: str,
        target_url_contains: str = "",
        user_data_dir: str | None = None,
    ) -> "CdpClient":
        http_endpoints, browser_websockets = _endpoint_candidates(endpoint, user_data_dir)
        errors: list[str] = []
        for base in http_endpoints:
            try:
                targets = _page_targets_from_http(base, target_url_contains)
                if targets:
                    return cls(targets[0]["webSocketDebuggerUrl"])
            except (httpx.HTTPError, ValueError, CdpError) as exc:
                errors.append(f"{base}: {exc}")
            try:
                websocket_url = _browser_websocket_from_http(base)
                if websocket_url and websocket_url not in browser_websockets:
                    browser_websockets.append(websocket_url)
            except (httpx.HTTPError, ValueError) as exc:
                errors.append(f"{base}/json/version: {exc}")
        for websocket_url in browser_websockets:
            try:
                return cls._connect_browser_target(websocket_url, target_url_contains)
            except (OSError, CdpError) as exc:
                errors.append(f"{websocket_url}: {exc}")
        detail = "；".join(errors[-4:])
        hint = "请确认 Edge 仍在运行，并检查 --user-data-dir 下的 DevToolsActivePort 是否为当前进程生成。"
        raise CdpError(f"CDP 没有可用页面: {endpoint}。{hint}" + (f" 详情: {detail}" if detail else ""))

    def call(self, method: str, params: dict | None = None) -> dict:
        self._next_id += 1
        request_id = self._next_id
        message = {"id": request_id, "method": method, "params": params or {}}
        if self._session_id:
            message["sessionId"] = self._session_id
        self._ws.send(json.dumps(message))
        while True:
            received = json.loads(self._ws.recv())
            if received.get("id") != request_id:
                continue
            if "error" in received:
                raise CdpError(f"{method} 失败: {received['error']}")
            return received.get("result", {})

    def evaluate(self, expression: str) -> Any:
        result = self.call(
            "Runtime.evaluate",
            {"expression": expression, "returnByValue": True, "awaitPromise": True},
        )
        exception = result.get("exceptionDetails")
        if exception:
            raise CdpError(f"页面脚本执行失败: {exception.get('text') or exception}")
        return _json_value(result.get("result", {}))

    def navigate(self, url: str, settle_seconds: float = 2.0) -> None:
        self.call("Page.navigate", {"url": url})
        deadline = time.monotonic() + max(settle_seconds, 0)
        while time.monotonic() < deadline:
            try:
                if self.evaluate("document.readyState") in {"interactive", "complete"}:
                    break
            except CdpError:
                pass
            time.sleep(0.2)
        if settle_seconds > 0:
            time.sleep(min(1.0, settle_seconds / 2))

    def close(self) -> None:
        self._ws.close()

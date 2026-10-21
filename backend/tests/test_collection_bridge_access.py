from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.collect import bridge_access


class Request(SimpleNamespace):
    def __init__(self, *, host="127.0.0.1", origin: str | None = None, token: str | None = None):
        headers = {}
        if origin is not None:
            headers["origin"] = origin
        if token is not None:
            headers[bridge_access.TOKEN_HEADER] = token
        super().__init__(client=SimpleNamespace(host=host), headers=headers)


@pytest.fixture(autouse=True)
def token(tmp_path, monkeypatch):
    path = tmp_path / "bridge.token"
    monkeypatch.setattr(bridge_access, "_TOKEN_PATH", path)
    value = bridge_access.get_bridge_token()
    assert value
    assert path.read_text(encoding="utf-8") == value
    return value


def test_valid_extension_request_uses_token_and_fixed_origin(token):
    origin = f"chrome-extension://{bridge_access.EXTENSION_ID}"

    bridge_access.require_bridge_access(Request(origin=origin, token=token))


@pytest.mark.parametrize(
    "request_factory",
    [
        lambda token: Request(origin=f"chrome-extension://{bridge_access.EXTENSION_ID}"),
        lambda token: Request(origin=f"chrome-extension://{bridge_access.EXTENSION_ID}", token="wrong"),
        lambda token: Request(host="192.0.2.8", origin=f"chrome-extension://{bridge_access.EXTENSION_ID}", token=token),
        lambda token: Request(origin="http://evil.example", token=token),
        lambda token: Request(origin="chrome-extension://aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", token=token),
    ],
)
def test_invalid_extension_requests_are_denied(token, request_factory):
    with pytest.raises(HTTPException) as exc:
        bridge_access.require_bridge_access(request_factory(token))

    assert exc.value.status_code == 403


@pytest.mark.parametrize("origin", ["http://127.0.0.1:18080", "http://localhost:18080"])
def test_local_management_pairing_does_not_expose_token_without_local_origin(origin):
    bridge_access.require_bridge_management(Request(origin=origin))

    with pytest.raises(HTTPException) as exc:
        bridge_access.require_bridge_management(Request(origin="http://127.0.0.1:5173"))

    assert exc.value.status_code == 403


def test_manifest_public_key_derives_the_accepted_extension_id(tmp_path):
    manifest = tmp_path / "manifest.json"
    source = bridge_access._manifest_path()
    manifest.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    assert bridge_access.extension_id_from_manifest(manifest) == bridge_access.EXTENSION_ID

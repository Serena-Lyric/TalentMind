"""Trusted-proxy access for raw JD endpoints; development loopback remains unchanged."""
from starlette.requests import Request

from fastapi import HTTPException

from app.routers.collection import _require_local_raw


def _call(headers=None, client=("10.0.0.5", 123)):
    raw_headers = [(key.lower().encode("latin-1"), value.encode("latin-1"))
                   for key, value in (headers or {}).items()]
    request = Request({
        "type": "http",
        "method": "GET",
        "path": "/probe",
        "query_string": b"",
        "headers": raw_headers,
        "client": client,
        "server": ("testserver", 80),
        "scheme": "http",
    })
    try:
        _require_local_raw(request)
    except HTTPException as exc:
        return exc.status_code, exc.detail
    return 200, None


def test_trusted_secret_allows_non_loopback(monkeypatch):
    monkeypatch.setenv("TALENTMIND_LOCAL_RAW", "1")
    monkeypatch.setenv("TALENTMIND_TRUSTED_PROXY_SECRET", "s3cret")

    status, detail = _call({"X-TalentMind-Proxy-Secret": "s3cret"})

    assert (status, detail) == (200, None)


def test_wrong_secret_is_forbidden(monkeypatch):
    monkeypatch.setenv("TALENTMIND_LOCAL_RAW", "1")
    monkeypatch.setenv("TALENTMIND_TRUSTED_PROXY_SECRET", "s3cret")

    status, detail = _call({"X-TalentMind-Proxy-Secret": "wrong"})

    assert status == 403
    assert detail == "仅允许已启用的本地原文访问"


def test_missing_secret_is_forbidden(monkeypatch):
    monkeypatch.setenv("TALENTMIND_LOCAL_RAW", "1")
    monkeypatch.setenv("TALENTMIND_TRUSTED_PROXY_SECRET", "s3cret")

    status, detail = _call()

    assert status == 403
    assert detail == "仅允许已启用的本地原文访问"


def test_cross_site_is_forbidden_even_with_secret(monkeypatch):
    monkeypatch.setenv("TALENTMIND_LOCAL_RAW", "1")
    monkeypatch.setenv("TALENTMIND_TRUSTED_PROXY_SECRET", "s3cret")

    status, detail = _call({
        "X-TalentMind-Proxy-Secret": "s3cret",
        "Sec-Fetch-Site": "cross-site",
    })

    assert status == 403
    assert detail == "仅允许已启用的本地原文访问"


def test_local_raw_env_is_required(monkeypatch):
    monkeypatch.delenv("TALENTMIND_LOCAL_RAW", raising=False)
    monkeypatch.setenv("TALENTMIND_TRUSTED_PROXY_SECRET", "s3cret")

    status, detail = _call({"X-TalentMind-Proxy-Secret": "s3cret"})

    assert status == 403
    assert detail == "仅允许已启用的本地原文访问"


def test_dev_loopback_without_secret_still_works(monkeypatch):
    monkeypatch.setenv("TALENTMIND_LOCAL_RAW", "1")
    monkeypatch.delenv("TALENTMIND_TRUSTED_PROXY_SECRET", raising=False)

    status, detail = _call(
        {"Host": "127.0.0.1:18000", "Origin": "http://127.0.0.1:18080"},
        client=("127.0.0.1", 50000),
    )

    assert (status, detail) == (200, None)

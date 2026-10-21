"""Loopback and fixed-extension access checks for manual captures."""
from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
from ipaddress import ip_address
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import HTTPException, Request

TOKEN_HEADER = "X-TalentMind-Bridge-Token"
_REPO_ROOT = Path(__file__).resolve().parents[3]
_TOKEN_PATH = _REPO_ROOT / "data" / "local" / "collection" / "bridge.token"
_MANIFEST_PATH = _REPO_ROOT / "frontend" / "bridge-extension" / "manifest.json"
_MANAGEMENT_ORIGINS = {
    "http://127.0.0.1:18080",
    "http://localhost:18080",
}
_LOCAL_HOSTS = {"127.0.0.1:18000", "localhost:18000"}


def _manifest_path() -> Path:
    return _MANIFEST_PATH


def extension_id_from_manifest(path: Path) -> str:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    key = str(manifest.get("key") or "")
    if not key:
        raise ValueError("bridge extension manifest is missing its public key")
    digest = hashlib.sha256(base64.b64decode(key, validate=True)).hexdigest()[:32]
    return "".join(chr(ord("a") + int(value, 16)) for value in digest)


EXTENSION_ID = extension_id_from_manifest(_MANIFEST_PATH)
EXTENSION_ORIGIN = f"chrome-extension://{EXTENSION_ID}"


def _atomic_write_token(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(value, encoding="utf-8")
        try:
            os.chmod(temporary, 0o600)
        except OSError:
            pass
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def get_bridge_token(*, create: bool = True) -> str:
    if _TOKEN_PATH.exists():
        value = _TOKEN_PATH.read_text(encoding="utf-8").strip()
        if len(value) >= 32:
            return value
    if not create:
        return ""
    value = secrets.token_urlsafe(32)
    _atomic_write_token(_TOKEN_PATH, value)
    return _TOKEN_PATH.read_text(encoding="utf-8").strip()


def _require_loopback(request: Request) -> None:
    client = getattr(request, "client", None)
    try:
        loopback = bool(client and ip_address(client.host).is_loopback)
    except ValueError:
        loopback = False
    host_header = str(request.headers.get("host") or "").strip().lower()
    if not loopback or host_header not in _LOCAL_HOSTS:
        raise HTTPException(status_code=403, detail="仅允许本机回环桥接请求")


def _origin(request: Request) -> str:
    return str(request.headers.get("origin") or "").rstrip("/")


def require_bridge_management(request: Request) -> None:
    _require_loopback(request)
    if str(request.headers.get("sec-fetch-site") or "").lower() == "cross-site":
        raise HTTPException(status_code=403, detail="拒绝跨站管理请求")
    origin = _origin(request)
    if origin in _MANAGEMENT_ORIGINS:
        return
    if not origin:
        referer = urlsplit(str(request.headers.get("referer") or ""))
        referer_origin = f"{referer.scheme}://{referer.netloc}".rstrip("/")
        if referer_origin in _MANAGEMENT_ORIGINS:
            return
    raise HTTPException(status_code=403, detail="仅允许本地管理页面读取桥接配对信息")


def require_bridge_access(request: Request) -> None:
    _require_loopback(request)
    if _origin(request) != EXTENSION_ORIGIN:
        raise HTTPException(status_code=403, detail="扩展来源未获授权")
    expected = get_bridge_token(create=False)
    provided = str(request.headers.get(TOKEN_HEADER) or "")
    if not expected or not provided or not secrets.compare_digest(expected, provided):
        raise HTTPException(status_code=403, detail="桥接令牌缺失或无效")

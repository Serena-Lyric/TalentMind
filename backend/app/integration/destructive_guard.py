"""Explicit authorization for destructive integration imports.

Pytest markers and environment switches may prevent accidental collection, but
they do not identify the actual database being changed. These guards therefore
verify the live target identity before every destructive import and require a
separate authorization file that is bound to that identity and operation.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit, urlunsplit

from neo4j import READ_ACCESS, Driver
from sqlalchemy import text
from sqlalchemy.orm import Session


AUTHORIZATION_ENV = "TALENTMIND_DESTRUCTIVE_AUTHORIZATION_FILE"


class DestructiveOperationDenied(RuntimeError):
    """Raised before a destructive import can issue a write."""


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def target_fingerprint(target: Mapping[str, Any]) -> str:
    digest = hashlib.sha256(_canonical(dict(target)).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _safe_uri(uri: str) -> str:
    parsed = urlsplit(uri)
    host = parsed.hostname or ""
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    if parsed.port is not None:
        host = f"{host}:{parsed.port}"
    return urlunsplit((parsed.scheme, host, parsed.path, parsed.query, parsed.fragment))


def _configured_host(session: Session) -> str | None:
    bind = getattr(session, "bind", None)
    if bind is None:
        get_bind = getattr(session, "get_bind", None)
        if callable(get_bind):
            try:
                bind = get_bind()
            except Exception:
                bind = None
    url = getattr(bind, "url", None)
    return url.host if url is not None else None


def mysql_target_identity(session: Session) -> dict[str, Any]:
    row = (
        session.execute(
            text(
                """
                SELECT @@hostname AS hostname,
                       @@server_uuid AS server_uuid,
                       DATABASE() AS database_name,
                       @@port AS port,
                       VERSION() AS version
                """
            )
        )
        .mappings()
        .one()
    )
    return {
        "kind": "mysql",
        "host": _configured_host(session),
        "port": int(row["port"]),
        "database": row["database_name"],
        "hostname": row["hostname"],
        "server_uuid": row["server_uuid"],
        "version": row["version"],
    }


def neo4j_target_identity(driver: Driver, *, uri: str) -> dict[str, Any]:
    with driver.session(default_access_mode=READ_ACCESS) as session:
        info = session.run(
            """
            CALL db.info()
            YIELD id, name, creationDate
            RETURN id, name, creationDate
            """
        ).single()
        components = session.run(
            """
            CALL dbms.components()
            YIELD versions, edition
            RETURN versions, edition
            """
        ).single()
    if info is None or components is None:
        raise DestructiveOperationDenied("could not identify the Neo4j target")
    versions = list(components["versions"])
    return {
        "kind": "neo4j",
        "uri": _safe_uri(uri),
        "database": info["name"],
        "database_id": info["id"],
        "creation_date": info["creationDate"],
        "version": versions[0] if versions else None,
        "edition": components["edition"],
    }


def _authorization_path(path: Path | str | None) -> Path:
    if path is None:
        raw = os.environ.get(AUTHORIZATION_ENV)
        if not raw:
            raise DestructiveOperationDenied(
                f"authorization file is required: set {AUTHORIZATION_ENV} "
                "or pass an explicit authorization file"
            )
        path = raw
    resolved = Path(path).expanduser()
    if not resolved.is_file():
        raise DestructiveOperationDenied(
            f"authorization file does not exist: {resolved}"
        )
    return resolved


def _parse_utc(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise DestructiveOperationDenied(f"authorization {field} is required")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise DestructiveOperationDenied(
            f"authorization {field} must be ISO-8601"
        ) from exc
    if parsed.tzinfo is None:
        raise DestructiveOperationDenied(
            f"authorization {field} must include a timezone"
        )
    return parsed.astimezone(timezone.utc)


def authorize_destructive_operation(
    *,
    operation: str,
    target: Mapping[str, Any],
    authorization_file: Path | str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    path = _authorization_path(authorization_file)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DestructiveOperationDenied(
            f"authorization file is unreadable or invalid JSON: {path}"
        ) from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise DestructiveOperationDenied(
            "authorization schema_version must be 1"
        )
    if payload.get("operation") != operation:
        raise DestructiveOperationDenied(
            f"authorization operation mismatch: expected {operation!r}"
        )
    if not str(payload.get("authorized_by") or "").strip():
        raise DestructiveOperationDenied(
            "authorization authorized_by is required"
        )
    if not str(payload.get("purpose") or "").strip():
        raise DestructiveOperationDenied("authorization purpose is required")

    actual_target = dict(target)
    expected_fingerprint = target_fingerprint(actual_target)
    if payload.get("target_fingerprint") != expected_fingerprint:
        raise DestructiveOperationDenied(
            "authorization target fingerprint mismatch for the live target"
        )
    if payload.get("target") != actual_target:
        raise DestructiveOperationDenied(
            "authorization target details mismatch for the live target"
        )

    expires_at = _parse_utc(payload.get("expires_at"), "expires_at")
    current_time = now or datetime.now(timezone.utc)
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)
    if current_time.astimezone(timezone.utc) >= expires_at:
        raise DestructiveOperationDenied("authorization has expired")
    return payload


def require_mysql_destructive_authorization(
    operation: str,
    session: Session,
    *,
    authorization_file: Path | str | None = None,
) -> dict[str, Any]:
    try:
        target = mysql_target_identity(session)
    except Exception as exc:
        raise DestructiveOperationDenied(
            "could not verify the live MySQL target"
        ) from exc
    return authorize_destructive_operation(
        operation=operation,
        target=target,
        authorization_file=authorization_file,
    )


def require_neo4j_destructive_authorization(
    operation: str,
    driver: Driver,
    *,
    uri: str,
    authorization_file: Path | str | None = None,
) -> dict[str, Any]:
    try:
        target = neo4j_target_identity(driver, uri=uri)
    except DestructiveOperationDenied:
        raise
    except Exception as exc:
        raise DestructiveOperationDenied(
            "could not verify the live Neo4j target"
        ) from exc
    return authorize_destructive_operation(
        operation=operation,
        target=target,
        authorization_file=authorization_file,
    )

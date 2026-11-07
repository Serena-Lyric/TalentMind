"""Write-once semantic results with a digest manifest."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
from uuid import uuid4

from ..foundation.inputs import canonical, check_public, parse_json
from ..foundation.store import safe_destination


def save_result(path: Path | str, value: dict) -> str:
    destination = safe_destination(path)
    if destination.exists():
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    check_public(value)
    raw = canonical(value).encode("utf-8")
    staging = destination.parent / ('.pending-' + uuid4().hex)
    staging.mkdir()
    try:
        with (staging / "value.json").open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        sha256 = hashlib.sha256(raw).hexdigest()
        with (staging / "manifest.json").open("x", encoding="utf-8") as stream:
            stream.write(canonical(dict(schema_version="m2-knowledge-result-manifest-1", sha256=sha256)))
            stream.flush()
            os.fsync(stream.fileno())
        staging.rename(destination)
    finally:
        if staging.exists():
            for name in ('value.json', 'manifest.json'):
                (staging / name).unlink(missing_ok=True)
            staging.rmdir()
    return sha256


def read_result(path: Path | str) -> dict:
    root = Path(path)
    manifest = parse_json((root / "manifest.json").read_text(encoding="utf-8"))
    raw = (root / "value.json").read_bytes()
    if (not isinstance(manifest, dict) or manifest.get("schema_version") != "m2-knowledge-result-manifest-1"
            or hashlib.sha256(raw).hexdigest() != manifest.get("sha256")):
        raise ValueError("result digest mismatch")
    value = parse_json(raw.decode("utf-8"))
    check_public(value)
    return value

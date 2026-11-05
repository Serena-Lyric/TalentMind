"""Write-once semantic results with a digest manifest."""
from __future__ import annotations

import hashlib
from pathlib import Path

from ..foundation.inputs import canonical, check_public, parse_json
from ..foundation.store import safe_destination


def save_result(path: Path | str, value: dict) -> str:
    destination = safe_destination(path)
    destination.mkdir(parents=True, exist_ok=False)
    check_public(value)
    raw = canonical(value).encode("utf-8")
    try:
        with (destination / "value.json").open("xb") as stream:
            stream.write(raw)
        sha256 = hashlib.sha256(raw).hexdigest()
        with (destination / "manifest.json").open("x", encoding="utf-8") as stream:
            stream.write(canonical(dict(schema_version="m2-knowledge-result-manifest-1", sha256=sha256)))
    except BaseException:
        # Keep the partially created directory for diagnosis; never reuse it as valid.
        raise
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

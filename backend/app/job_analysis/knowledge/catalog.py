"""Read immutable knowledge directories and verify their committed manifest."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path

from ..foundation.inputs import check_public, parse_json
from .models import KnowledgeSnapshot, validate_snapshot


@dataclass(frozen=True)
class LoadedSnapshot:
    path: Path
    snapshot: KnowledgeSnapshot
    sha256: str


def load_snapshot(path: Path | str) -> LoadedSnapshot:
    root = Path(path).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("knowledge snapshot must be an explicit directory")
    raw = (root / "knowledge.json").read_bytes()
    manifest = parse_json((root / "manifest.json").read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or manifest.get("schema_version") != "m2-knowledge-manifest-1":
        raise ValueError("unknown knowledge manifest version")
    sha256 = hashlib.sha256(raw).hexdigest()
    if manifest.get("sha256") != sha256:
        raise ValueError("knowledge digest mismatch")
    try:
        value = parse_json(raw.decode("utf-8"))
        check_public(value)
        snapshot = validate_snapshot(value)
    except (UnicodeError, ValueError, TypeError) as exc:
        if "digest" in str(exc):
            raise
        raise ValueError("invalid knowledge snapshot") from None
    return LoadedSnapshot(root, snapshot, sha256)

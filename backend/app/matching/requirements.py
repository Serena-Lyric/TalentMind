"""Stable identity for the persisted profile requirements, without schema changes."""
import hashlib
import json


def requirements_version(required: list, bonus: list) -> str:
    # Preserve spelling and type: an edit must invalidate the prior explanation.
    payload = {"required": sorted({s.strip() for s in required if isinstance(s, str) and s.strip()}), "bonus": sorted({s.strip() for s in bonus if isinstance(s, str) and s.strip()})}
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()

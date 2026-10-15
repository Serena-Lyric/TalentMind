"""Strict local JSON/JSONL snapshots. No SQL conversion or implicit data source."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path


def canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def parse_json(text: str):
    return json.loads(text, object_pairs_hook=_pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("non-finite JSON number")))


def check_public(value):
    """Reject credential-bearing keys before persisting inputs or manifests."""
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("JSON keys must be text")
            name = key.lower().replace("-", "_")
            if any(word in name for word in ("api_key", "password", "secret", "authorization", "cookie", "access_token")):
                raise ValueError("credential field prohibited")
            check_public(item)
    elif isinstance(value, list):
        for item in value:
            check_public(item)


@dataclass(frozen=True)
class InputRecord:
    namespace: str
    jd_id: str
    payload_json: str
    observation: str | None

    @property
    def payload(self) -> dict:
        return parse_json(self.payload_json)

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(self.payload_json.encode("utf-8")).hexdigest()

    @classmethod
    def from_row(cls, namespace: str, row: dict):
        if not isinstance(row, dict):
            raise ValueError("record must be an object")
        check_public(row)
        identity = row.get("id")
        if type(identity) not in (int, str) or not str(identity).strip():
            raise ValueError("id must be a nonempty string or integer")
        for field in ("source", "job_title", "raw_text"):
            if not isinstance(row.get(field), str) or not row[field].strip():
                raise ValueError(f"{field} must be nonempty text")
        for field in ("duties", "experience", "requirements"):
            if field in row and not isinstance(row[field], str):
                raise ValueError(f"{field} must be text when supplied")
        observation = row.get("crawled_at")
        if observation is not None and (not isinstance(observation, str) or not observation.strip()):
            raise ValueError("crawled_at must be text or null")
        payload = {key: value for key, value in row.items() if key not in ("id", "crawled_at")}
        return cls(namespace, str(identity), canonical(payload), observation)


@dataclass(frozen=True)
class InputBatch:
    namespace: str
    path: Path
    raw_bytes: bytes
    records: tuple[InputRecord, ...]

    @property
    def digest(self):
        return hashlib.sha256(self.raw_bytes).hexdigest()


def read_snapshot(path: Path | str, namespace: str) -> InputBatch:
    if not isinstance(namespace, str) or not namespace.strip():
        raise ValueError("explicit dataset namespace required")
    path = Path(path).resolve()
    if path.suffix.lower() not in (".json", ".jsonl"):
        raise ValueError("only JSON arrays and JSONL objects are supported")
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
        rows = (parse_json(text) if path.suffix.lower() == ".json" else
                [parse_json(line) for line in text.splitlines() if line.strip()])
    except (ValueError, UnicodeError):
        raise ValueError("invalid UTF-8 JSON snapshot") from None
    if not isinstance(rows, list) or not rows:
        raise ValueError("snapshot must contain a nonempty record list")
    records = []
    seen = set()
    for index, row in enumerate(rows, 1):
        try:
            record = InputRecord.from_row(namespace, row)
        except (ValueError, TypeError):
            raise ValueError(f"invalid record at position {index}") from None
        if record.jd_id in seen:
            raise ValueError(f"duplicate identity at position {index}")
        records.append(record)
        seen.add(record.jd_id)
    return InputBatch(namespace, path, raw, tuple(records))

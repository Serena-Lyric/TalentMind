"""Retain malformed input units for audit while sharing A's exact record fingerprint."""
from dataclasses import dataclass
import hashlib
from pathlib import Path

from ..foundation.inputs import InputRecord, check_public, parse_json


@dataclass(frozen=True)
class Unit:
    position: int
    jd_id: str | None
    record: InputRecord | None
    error: str | None


@dataclass(frozen=True)
class Batch:
    namespace: str
    path: Path
    raw_bytes: bytes | None
    sha256: str
    units: tuple[Unit, ...]


def read_batch(path, namespace):
    if not isinstance(namespace, str) or not namespace.strip():
        raise ValueError("explicit dataset namespace required")
    path = Path(path).resolve()
    if path.suffix.lower() not in (".json", ".jsonl"):
        raise ValueError("only JSON arrays and JSONL supported")
    raw = path.read_bytes()
    sha256 = hashlib.sha256(raw).hexdigest()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeError:
        return Batch(namespace, path, None, sha256, (Unit(0, None, None, "input_container_invalid"),))
    if path.suffix.lower() == ".json":
        try:
            rows = parse_json(text)
            if not isinstance(rows, list) or not rows:
                raise ValueError()
        except (ValueError, TypeError):
            return Batch(namespace, path, None, sha256, (Unit(0, None, None, "input_container_invalid"),))
        entries = list(enumerate(rows, 1))
    else:
        entries = []
        for number, line in enumerate(text.splitlines(), 1):
            if not line.strip():
                continue
            try:
                row = parse_json(line)
            except (ValueError, TypeError):
                row = None
            entries.append((number, row))
        if not entries:
            return Batch(namespace, path, None, sha256, (Unit(0, None, None, "input_container_invalid"),))
    units, seen = [], set()
    retain_raw = True
    for position, row in entries:
        identity = row.get("id") if isinstance(row, dict) else None
        identity = str(identity) if type(identity) in (int, str) and str(identity).strip() else None
        try:
            check_public(row)
        except ValueError:
            # Never persist a credential-bearing input file or identity from that row.
            retain_raw = False
            units.append(Unit(position, None, None, "input_prohibited_field"))
            continue
        try:
            record = InputRecord.from_row(namespace, row)
        except (ValueError, TypeError, OverflowError):
            units.append(Unit(position, identity, None, "input_record_invalid"))
            continue
        if record.jd_id in seen:
            units.append(Unit(position, identity, None, "input_duplicate_identity"))
        else:
            units.append(Unit(position, identity, record, None))
            seen.add(record.jd_id)
    # A malformed unit has not passed recursive credential checks; retain only its hash/reference.
    return Batch(namespace, path, raw if retain_raw and all(not u.error for u in units) else None, sha256, tuple(units))

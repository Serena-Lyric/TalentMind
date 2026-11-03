"""Private append-only run directories; manifest is committed last, never repaired."""
import hashlib
from pathlib import Path

from ..baseline.contract import validate_analysis
from ..foundation.inputs import canonical, check_public, parse_json
from ..foundation.store import safe_destination


def _write_run(path: Path, value):
    path = safe_destination(path)
    validate_analysis(value["analysis"])
    check_public(value)
    raw = canonical(value).encode("utf-8")
    with (path / "run.json").open("xb") as stream:
        stream.write(raw)
    with (path / "manifest.json").open("x", encoding="utf-8") as stream:
        stream.write(canonical(dict(schema_version="m2-p1-run-manifest-1",
                                    sha256=hashlib.sha256(raw).hexdigest())))


def save_run(path, value):
    path = safe_destination(path)
    path.mkdir(parents=True, exist_ok=False)
    _write_run(path, value)


def read_run(path):
    path = Path(path)
    manifest = parse_json((path / "manifest.json").read_text(encoding="utf-8"))
    raw = (path / "run.json").read_bytes()
    if (not isinstance(manifest, dict) or manifest.get("schema_version") != "m2-p1-run-manifest-1" or
            hashlib.sha256(raw).hexdigest() != manifest.get("sha256")):
        raise ValueError("run_digest_mismatch")
    result = parse_json(raw.decode("utf-8"))
    if not isinstance(result, dict) or result.get("schema_version") != "m2-p1-run-1":
        raise ValueError("unknown_run_version")
    check_public(result)
    validate_analysis(result["analysis"])
    return result

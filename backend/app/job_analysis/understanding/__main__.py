"""Explicit single snapshot in, private immutable run out; stdout is always a safe summary."""
import argparse
import asyncio
import json
from pathlib import Path

from .cloud import CloudConfig, CloudProcessor
from .core import analyze
from .storage import _write_run, read_run
from ..foundation.inputs import canonical, parse_json
from ..foundation.store import safe_destination


def summary(value):
    analysis = value["analysis"]
    return dict(status=value["execution"]["status"], outcome=analysis["outcome"],
                claims=len(analysis["claims"]), relations=len(analysis["relations"]),
                coverage={d: c["status"] for d, c in analysis["coverage"].items()},
                input_sha256=analysis["input_sha256"], analyzer_sha256=analysis["analyzer"]["sha256"],
                elapsed_seconds=value["execution"]["elapsed_seconds"],
                usage=value["execution"]["metadata"].get("usage", {}),
                semantic_review=analysis["semantic_review"])


def main():
    parser = argparse.ArgumentParser(description="P1 independent JD understanding; explicit private files only")
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("analyze")
    run.add_argument("snapshot", type=Path, help="Single P0 InputRecord row JSON, not a database")
    run.add_argument("--namespace", required=True)
    run.add_argument("--input-version", required=True)
    run.add_argument("--config", required=True, type=Path)
    run.add_argument("--key-file", required=True, type=Path)
    run.add_argument("--output", required=True, type=Path)
    read = commands.add_parser("read")
    read.add_argument("path", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "read":
            value = read_run(args.path)
        else:
            args.output = safe_destination(args.output)
            row = parse_json(args.snapshot.read_text(encoding="utf-8-sig"))
            config = CloudConfig.model_validate(parse_json(args.config.read_text(encoding="utf-8-sig")))
            processor = CloudProcessor(config, args.key_file.read_text(encoding="utf-8-sig"))
            # Reserve before any paid request. A crash leaves a diagnosable pending directory.
            args.output.mkdir(parents=True, exist_ok=False)
            (args.output / "pending.json").write_text(canonical(dict(status="started")), encoding="utf-8")
            value = asyncio.run(analyze(args.namespace, row, args.input_version, processor))
            _write_run(args.output, value)
        print(json.dumps(summary(value), ensure_ascii=True))
        return 0 if value["execution"]["status"] in {"ok", "partial", "no_recognized_results"} else 2
    except (ValueError, OSError, KeyError, TypeError):
        print(json.dumps(dict(status="rejected", reason="invalid_or_unavailable_private_run")))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

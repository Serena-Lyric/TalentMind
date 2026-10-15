"""Explicit offline entry: python -m app.job_analysis.screening."""
import argparse
import json
from pathlib import Path
import sqlite3
import sys

from ..foundation.inputs import parse_json
from ..foundation.runner import publish
from ..foundation.store import safe_destination
from .rules import manifest
from .runner import execute, output_path, replay, resume
from .store import ScreeningStore


def main(argv=None):
    parser = argparse.ArgumentParser(description="M2 B1 offline JD validity and scope audit; no model or services.")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("run", "resume", "replay"):
        command = commands.add_parser(name)
        command.add_argument("--state", required=True)
        command.add_argument("--output", required=True)
        if name == "run":
            command.add_argument("--input", required=True)
            command.add_argument("--dataset", required=True)
            command.add_argument("--scope", required=True, help="Explicit versioned offline scope JSON")
            command.add_argument("--rules-version", default="v1")
        else:
            command.add_argument("--run", required=True)
    args = parser.parse_args(argv)
    try:
        destination = safe_destination(args.output)
        if args.command == "run":
            scope_path = Path(args.scope).resolve()
            scope = parse_json(scope_path.read_text(encoding="utf-8-sig"))
            manifest(scope, args.rules_version)
            source = Path(args.input).resolve()
            state = safe_destination(args.state)
            if source == state or scope_path == state or source == destination or source.is_relative_to(destination) or scope_path == destination or scope_path.is_relative_to(destination):
                raise ValueError("input, scope, state and output must be separate")
        with ScreeningStore(args.state) as store:
            if args.command == "run":
                result = execute(store, source, args.dataset, scope=scope,
                                 rules_revision=args.rules_version, output=destination)
            elif args.command == "resume":
                result = resume(store, args.run, output=destination)
            else:
                result = replay(store, args.run)
                output_path(store, destination, Path(result["input_path"]))
                publish(result, destination, args.run)
        print(json.dumps(dict(run_id=result["run_id"], output=str(destination / (result["run_id"] + ".json")),
                              audit=result["audit"]), ensure_ascii=True))
        return 2 if result["audit"]["input_failed"] + result["audit"]["screening_failed"] else 0
    except (ValueError, OSError, sqlite3.Error):
        print("B1 configuration, storage or publication failure; no successful audit published.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

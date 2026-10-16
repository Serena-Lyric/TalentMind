"""Explicit offline entry: python -m app.job_analysis.semantics."""
import argparse
import json
from pathlib import Path
import sqlite3
import sys

from ..foundation.inputs import read_snapshot
from ..foundation.runner import publish, _output_path as output_path
from .runner import execute, replay, resume
from .store import SemanticStore


def main(argv=None):
    parser = argparse.ArgumentParser(description="B2 round one offline skill semantics; no services or models.")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("run", "resume", "replay"):
        command = commands.add_parser(name)
        command.add_argument("--state", required=True)
        command.add_argument("--output", required=True)
        if name == "run":
            command.add_argument("--input", required=True)
            command.add_argument("--dataset", required=True)
            command.add_argument("--rules-version", default="v1")
        else:
            command.add_argument("--run", required=True)
    args = parser.parse_args(argv)
    try:
        # Strict A input parsing rejects malformed batches before creating a semantic run.
        batch = read_snapshot(args.input, args.dataset) if args.command == "run" else None
        with SemanticStore(args.state) as store:
            if args.command == "run":
                result = execute(store, batch, rules_revision=args.rules_version, output=args.output)
            elif args.command == "resume":
                result = resume(store, args.run, output=args.output)
            else:
                result = replay(store, args.run)
                destination = output_path(store, args.output, Path(result["input_path"]))
                publish(result, destination, args.run)
        print(json.dumps(dict(run_id=result["run_id"], audit=result["audit"]), ensure_ascii=True))
        return 2 if result["audit"]["failed"] else 0
    except (ValueError, OSError, sqlite3.Error):
        print("B2 input, configuration, storage or publication failed; no successful audit published.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

"""Explicit local candidate run/replay, review ingestion and review snapshot export."""
import argparse
import json
from pathlib import Path
import sqlite3
import sys

from ...foundation.inputs import check_public, parse_json, read_snapshot
from ...foundation.runner import publish, _output_path as output_path
from .runner import execute, replay, review_export
from .store import CanonicalStore


def load_json(path):
    path = Path(path)
    if path.suffix.lower() != ".json":
        raise ValueError("explicit JSON file required")
    value = parse_json(path.read_text(encoding="utf-8-sig"))
    check_public(value)
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description="B3-2 explicit pending candidates; no formal admission or extraction.")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("run", "replay", "review", "export-reviews"):
        command = commands.add_parser(name)
        command.add_argument("--state", required=True)
        if name != "review":
            command.add_argument("--output", required=True)
        if name == "run":
            for field in ("input", "dataset", "submission", "catalog"):
                command.add_argument("--" + field, required=True)
            command.add_argument("--rules-version", default="v1")
        elif name == "review":
            command.add_argument("--result", required=True)
            command.add_argument("--event", required=True)
        else:
            command.add_argument("--run", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "run":
            batch = read_snapshot(args.input, args.dataset)
            marks, catalog = load_json(args.submission), load_json(args.catalog)
        with CanonicalStore(args.state) as store:
            if args.command == "run":
                result = execute(store, batch, marks, catalog, revision=args.rules_version, output=args.output,
                                 input_paths=(args.submission, args.catalog))
            elif args.command == "review":
                identity = store.record_review(args.result, load_json(args.event))
                print(json.dumps(dict(review_id=identity, formal_admitted=False)))
                return 0
            else:
                # Check destination before committing a review export.
                saved = replay(store, args.run)
                destination = output_path(store, args.output)
                for path in saved["input_paths"]:
                    output_path(store, destination, Path(path))
                result = review_export(store, args.run) if args.command == "export-reviews" else saved
                publish(result, destination, result["run_id"])
        print(json.dumps(dict(run_id=result["run_id"], **({"export_id": result["export_id"]} if "export_id" in result else {}),
                              formal_admitted=False, formal_statistics_eligible=False)))
        return 0
    except (ValueError, OSError, KeyError, TypeError, sqlite3.Error):
        print("Candidate input, review, history or publication failed; committed reports can be replayed.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

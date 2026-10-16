"""Explicit offline annotation importer. Run/replay only; no classifier or implicit resume."""
import argparse
import json
from pathlib import Path
import sqlite3
import sys

from ..foundation.inputs import check_public, parse_json, read_snapshot
from ..foundation.runner import publish, _output_path as output_path
from .models import AnnotationBatch, Taxonomy
from .runner import execute, replay
from .store import RoleStore


def _read(path):
    path = Path(path).resolve()
    if path.suffix.lower() != ".json":
        raise ValueError("annotation and taxonomy must be explicit JSON files")
    value = parse_json(path.read_text(encoding="utf-8-sig"))
    check_public(value)
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description="B3-0 offline role assertions; no production classification.")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("run", "replay"):
        command = commands.add_parser(name)
        command.add_argument("--state", required=True)
        command.add_argument("--output", required=True)
        if name == "run":
            command.add_argument("--input", required=True)
            command.add_argument("--dataset", required=True)
            command.add_argument("--annotations", required=True)
            command.add_argument("--taxonomy", required=True)
            command.add_argument("--rules-version", default="v1")
        else:
            command.add_argument("--run", required=True)
    args = parser.parse_args(argv)
    try:
        # Malformed containers never become successful empty runs or persisted raw responses.
        if args.command == "run":
            batch = read_snapshot(args.input, args.dataset)
            annotations = AnnotationBatch.model_validate(_read(args.annotations)).model_dump()["annotations"]
            taxonomy = Taxonomy.model_validate(_read(args.taxonomy)).model_dump()
        with RoleStore(args.state) as store:
            if args.command == "run":
                result = execute(store, batch, annotations, taxonomy, revision=args.rules_version,
                    output=args.output, input_paths=(args.annotations, args.taxonomy))
            else:
                result = replay(store, args.run)
                destination = output_path(store, args.output)
                for path in result["input_paths"]:
                    output_path(store, destination, Path(path))
                publish(result, destination, result["run_id"])
        print(json.dumps(dict(run_id=result["run_id"], audit=result["audit"], formal_statistics_eligible=False)))
        return 0
    except (ValueError, OSError, KeyError, TypeError, sqlite3.Error):
        print("Role assertion input, history or publication failed; committed reports can be replayed.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

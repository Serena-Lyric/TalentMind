"""B3-1 explicit run/replay. Does not import models, services or B1/B2 executors."""
import argparse
import json
from pathlib import Path
import sqlite3
import sys

from ...foundation.inputs import read_snapshot
from ...foundation.runner import publish, _output_path as output_path
from .models import load_taxonomy
from .runner import execute, replay
from .store import ProposalStore


def main(argv=None):
    parser = argparse.ArgumentParser(description="B3-1 offline pending family suggestions; finite grammar only.")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("run", "replay"):
        command = commands.add_parser(name)
        command.add_argument("--state", required=True)
        command.add_argument("--output", required=True)
        if name == "run":
            command.add_argument("--input", required=True)
            command.add_argument("--dataset", required=True)
            command.add_argument("--taxonomy", required=True)
            command.add_argument("--rules-version", default="v1")
        else:
            command.add_argument("--run", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "run":
            batch = read_snapshot(args.input, args.dataset)
            taxonomy = load_taxonomy(args.taxonomy)
        with ProposalStore(args.state) as store:
            if args.command == "run":
                result = execute(store, batch, taxonomy, revision=args.rules_version,
                    output=args.output, input_paths=(args.taxonomy,))
            else:
                result = replay(store, args.run)
                destination = output_path(store, args.output)
                for path in result["input_paths"]:
                    output_path(store, destination, Path(path))
                publish(result, destination, result["run_id"])
        print(json.dumps(dict(run_id=result["run_id"], audit=result["audit"], review_status="pending_review",
                              classification_complete=False, formal_statistics_eligible=False)))
        return 0
    except (ValueError, OSError, KeyError, TypeError, sqlite3.Error):
        print("Suggestion input, history or publication failed; committed reports can be replayed.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

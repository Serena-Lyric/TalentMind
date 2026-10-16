"""Explicit offline CLI. Existing B2 run is mandatory; never implicitly invoke extractors."""
import argparse
import json
from pathlib import Path
import sqlite3
import sys

from ..foundation.runner import publish, _output_path as output_path
from ..foundation.inputs import digest
from .evaluation import evaluate, load_benchmark, project_predictions
from .runner import execute, replay
from .store import GovernanceStore


def main(argv=None):
    parser = argparse.ArgumentParser(description="B2 round two offline governance; formal admission disabled.")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("run", "replay", "evaluate"):
        command = commands.add_parser(name)
        command.add_argument("--state", required=True)
        command.add_argument("--output", required=True)
        if name == "run":
            command.add_argument("--b2-run", required=True)
            command.add_argument("--rules-version", default="v1")
        else:
            command.add_argument("--run", required=True)
            if name == "evaluate":
                command.add_argument("--benchmark", required=True)
    args = parser.parse_args(argv)
    try:
        with GovernanceStore(args.state) as store:
            if args.command == "run":
                result = execute(store, args.b2_run, revision=args.rules_version, output=args.output)
            elif args.command == "replay":
                result = replay(store, args.run)
                publish(result, output_path(store, args.output, Path(result["input_path"])), args.run)
            else:
                annotations = load_benchmark(args.benchmark)
                report = replay(store, args.run)
                predictions = project_predictions(report, annotations)
                result = evaluate(annotations, predictions)
                artifact = dict(evaluation=result, predictions=predictions, annotations=annotations)
                identity = digest(artifact)
                destination = output_path(store, args.output, Path(args.benchmark).resolve())
                output_path(store, args.output, Path(report["input_path"]))
                publish(artifact, destination, identity)
                print(json.dumps(dict(evaluation_id=identity, mode=result["mode"], quality_claim_allowed=result["quality_claim_allowed"])))
                return 0
        print(json.dumps(dict(run_id=result["run_id"], audit=result["audit"]), ensure_ascii=True))
        return 2 if result["audit"]["upstream_failed"] else 0
    except (ValueError, OSError, KeyError, TypeError, sqlite3.Error):
        print("Governance input, configuration, history or publication failed; use saved report for replay if committed.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

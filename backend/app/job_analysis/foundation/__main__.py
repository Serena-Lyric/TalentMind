"""Explicit offline entry: python -m app.job_analysis.foundation --help."""
import argparse
import json
import re
import sqlite3
import sys

from .aggregate import replay
from .inputs import read_snapshot
from .models import AnalyzerSpec
from .runner import execute, publish, resume
from .store import AnalysisStore, safe_destination


class LiteralDemoAnalyzer:
    """Python token demonstration, not a production extractor or semantic classifier."""
    spec = AnalyzerSpec(extractor="literal-demo-v1", prompt="none", model="offline-demo", configuration="python-only-v1")

    def analyze(self, record):
        facts = []
        text = record.payload["raw_text"]
        match = re.search(r"\bpython\b", text, re.IGNORECASE)
        if match:
            facts.append({"kind": "skill", "name": "python", "requirement": "unclassified",
                "evidence": {"namespace": record.namespace, "jd_id": record.jd_id,
                             "field": "raw_text", "quote": match.group()}})
        return {"coverage": "complete", "facts": facts}


def main(argv=None):
    parser = argparse.ArgumentParser(description="M2 stage A OFFLINE DEMO. No services, credentials or model API.")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("run", "resume", "replay"):
        command = commands.add_parser(name)
        command.add_argument("--state", required=True, help="Dedicated persistent SQLite file; never legacy StateDB")
        command.add_argument("--output", required=True, help="Isolated artifact directory")
        if name == "run":
            command.add_argument("--input", required=True, help="UTF-8 JSON array or JSONL")
            command.add_argument("--dataset", required=True)
            command.add_argument("--analysis-version", default="v1")
            command.add_argument("--aggregate-version", default="v1")
            command.add_argument("--force", action="store_true")
        elif name == "resume":
            command.add_argument("--run", required=True)
        else:
            command.add_argument("--aggregate", required=True)
    args = parser.parse_args(argv)
    try:
        # Parse before creating state: bad input is never a successful empty run.
        batch = read_snapshot(args.input, args.dataset) if args.command == "run" else None
        destination = safe_destination(args.output)
        with AnalysisStore(args.state) as store:
            if args.command == "run":
                result = execute(store, batch, LiteralDemoAnalyzer(), analysis_revision=args.analysis_version,
                                 aggregate_revision=args.aggregate_version, force=args.force, output=destination)
                identity = result["run_id"]
            elif args.command == "resume":
                result = resume(store, args.run, LiteralDemoAnalyzer(), output=destination)
                identity = args.run
            else:
                result = replay(store, args.aggregate)
                identity = args.aggregate
                publish(result, destination, identity)
        print(json.dumps({"mode": "offline-demo", "aggregate_id": result["aggregate_id"],
                          "run_id": result.get("run_id"), "business_sha256": result["business_sha256"],
                          "output": str(destination / (identity + ".json"))}, ensure_ascii=True))
        return 0
    except (ValueError, OSError, sqlite3.Error) as exc:
        # Errors contain no raw model responses, exception bodies or credentials.
        print(f"M2 offline failure: {str(exc) if isinstance(exc, ValueError) else type(exc).__name__}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

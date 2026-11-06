"""Explicit offline P3 CLI. Full JSON output is private and contains source text."""
import argparse
import json
from pathlib import Path
import sqlite3

from ..baseline.contract import validate_analysis
from ..foundation.inputs import digest, parse_json
from ..knowledge.catalog import load_snapshot
from ..understanding.storage import read_run
from .service import apply_batch
from .storage import CandidateStore
from .suggestions import check_suggestion


def _analysis(path):
    value = (read_run(path)["analysis"] if path.is_dir() else parse_json(path.read_text(encoding="utf-8-sig")))
    # A detached run JSON must not bypass its P1 digest manifest.
    if not isinstance(value, dict) or value.get("schema_version") == "m2-p1-run-1":
        raise ValueError("use manifest-bound P1 directory or explicit semantic analysis")
    validate_analysis(value)
    return value


def build_parser():
    parser = argparse.ArgumentParser(description="P3/P4 offline work-candidate research (private JSON output)")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("init", "apply", "show", "history", "jd", "source", "suggestion"):
        command = commands.add_parser(name)
        command.add_argument("--state", type=Path, required=True)
        if name in {"show", "jd"}:
            command.add_argument("--revision", type=int)
        if name == "history":
            command.add_argument("--candidate", required=True)
        if name == "jd":
            command.add_argument("--namespace", required=True)
            command.add_argument("--jd-id", required=True)
        if name == "apply":
            command.add_argument("--batch", type=Path, required=True)
            command.add_argument("--analysis", type=Path, action="append", default=[])
            command.add_argument("--knowledge", type=Path, required=True)
        if name == "source":
            command.add_argument("--kind", choices=["analysis", "knowledge", "alignment", "review", "comparison"], required=True)
            command.add_argument("--sha256", required=True)
        if name == "suggestion":
            command.add_argument("--id", required=True)
            command.add_argument("--baseline", type=Path, required=True, help="JSON file containing the exact binding object")
    return parser


def main():
    args = build_parser().parse_args()
    try:
        if args.command == "apply":
            request = parse_json(args.batch.read_text(encoding="utf-8-sig"))
            values = [_analysis(path) for path in args.analysis]
            analyses = {digest(value): value for value in values}
            knowledge = load_snapshot(args.knowledge)
        with CandidateStore(args.state, create=args.command == "init") as store:
            if args.command in {"init", "show"}:
                result = store.read(getattr(args, "revision", None))
            elif args.command == "apply":
                result = apply_batch(store, request, analyses, knowledge)
            elif args.command == "history":
                result = dict(schema_version="m2-work-history-1", history=store.history(args.candidate))
            elif args.command == "source":
                result = store.source(args.kind, args.sha256)
            elif args.command == "suggestion":
                result = check_suggestion(store, args.id, parse_json(args.baseline.read_text(encoding="utf-8-sig")))
            else:
                state = store.read(args.revision)
                sources = [sha for sha in state["analysis_sha256s"]
                           if (store.source("analysis", sha)["namespace"], store.source("analysis", sha)["jd_id"])
                           == (args.namespace, args.jd_id)]
                result = dict(schema_version="m2-work-jd-1", binding=state["binding"], namespace=args.namespace,
                              jd_id=args.jd_id, analysis_sha256s=sources,
                              relations=[r for _, r in sorted(state["relations"].items())
                                         if (r["namespace"], r["jd_id"]) == (args.namespace, args.jd_id)],
                              not_a_vacancy_count=True)
        print(json.dumps(result, ensure_ascii=True, sort_keys=True, allow_nan=False))
        return 0
    except (ValueError, OSError, KeyError, TypeError, sqlite3.Error):
        # Validation messages can contain private input values; keep them off stdout/stderr.
        print(json.dumps(dict(status="rejected", reason="invalid_input_or_registry")))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

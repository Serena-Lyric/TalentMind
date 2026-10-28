"""Explicit local files only; no service initialization or network clients."""
import argparse
import json
from pathlib import Path

from ..foundation.inputs import parse_json
from .bundle import BundleError, audit_bundle
from .contract import validate_analysis


def main():
    parser = argparse.ArgumentParser(description="P0 offline structural audit; no semantic evaluation")
    parser.add_argument("kind", choices=["analysis", "bundle"])
    parser.add_argument("path", type=Path)
    parser.add_argument("--archive", type=Path)
    args = parser.parse_args()
    try:
        if args.kind == "analysis":
            result = validate_analysis(parse_json(args.path.read_text(encoding="utf-8-sig")))
            summary = {"contract_version": result.contract_version, "claims": len(result.claims), "semantic_review": result.semantic_review}
        else:
            summary = audit_bundle(args.path, args.archive)
    except BundleError as exc:
        print(json.dumps({"status": "rejected", "reason": str(exc)}))
        return 1
    except FileNotFoundError:
        print(json.dumps({"status": "rejected", "reason": "local_file_missing"}))
        return 1
    except (ValueError, OSError, KeyError, TypeError):
        # ValidationError can contain private input; do not echo its message to stdout.
        print(json.dumps({"status": "rejected", "reason": "invalid_or_unavailable_local_evidence"}))
        return 1
    print(json.dumps({"status": "structurally_valid", **summary}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

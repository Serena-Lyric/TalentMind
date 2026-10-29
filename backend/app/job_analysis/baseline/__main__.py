"""Explicit local files only; no service initialization or network clients."""
import argparse
import json
from pathlib import Path

from ..foundation.inputs import parse_json
from .bundle import BundleError, audit_bundle
from .contract import validate_analysis
from .case_assertions import audit_case_assertions
from .approved_assertions import audit_approved_assertions


def main():
    parser = argparse.ArgumentParser(description="P0 offline structural audit; no semantic evaluation")
    parser.add_argument("kind", choices=["analysis", "bundle", "assertions", "approved-assertions"])
    parser.add_argument("path", type=Path)
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--approval", type=Path, help="Explicit separate owner receipt for approved conditions")
    parser.add_argument("--samples", nargs="+", help="Audit only these explicit snapshot/annotation pairs; other files are not opened")
    args = parser.parse_args()
    try:
        if args.approval is not None and args.kind != "approved-assertions":
            raise ValueError("approval_only_valid_for_approved_conditions")
        if args.kind == "analysis":
            result = validate_analysis(parse_json(args.path.read_text(encoding="utf-8-sig")))
            summary = {"contract_version": result.contract_version, "claims": len(result.claims), "semantic_review": result.semantic_review}
        elif args.kind == "bundle":
            summary = audit_bundle(args.path, args.archive, sample_ids=args.samples)
        elif args.kind == "assertions":
            if args.manifest is None or args.archive is not None or args.samples is not None:
                raise ValueError("assertions_require_manifest_and_no_scope_override")
            summary = audit_case_assertions(args.path, args.manifest)
        else:
            if args.manifest is None or args.approval is None or args.archive is not None or args.samples is not None:
                raise ValueError("approved_conditions_require_manifest_receipt_and_no_scope_override")
            summary = audit_approved_assertions(args.path, args.manifest, args.approval)
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

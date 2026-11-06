"""Safe CLI for the explicit P2-1 offline knowledge workflow."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..baseline.contract import validate_analysis
from ..foundation.inputs import check_public, digest, parse_json
from ..understanding.storage import read_run
from .alignment import align_analysis
from .candidates import CandidateRegistry, load_projection
from .catalog import load_snapshot
from .impact import locate_impact
from .models import AlignmentResult, RoleComparisonSet
from .profile import build_profile
from .roles import compare_roles
from .storage import read_result, save_result


def _load_analysis(path: Path) -> dict:
    if Path(path).is_dir():
        return validate_analysis(read_run(path)["analysis"]).model_dump()
    value = parse_json(Path(path).read_text(encoding="utf-8-sig"))
    check_public(value)
    if isinstance(value, dict) and value.get("schema_version") == "m2-p1-run-1":
        raise ValueError("saved P1 runs require their manifest-bound directory")
    if not isinstance(value, dict):
        raise ValueError("analysis object required")
    return validate_analysis(value).model_dump()


def _alignment(path: Path) -> AlignmentResult:
    return AlignmentResult.model_validate(read_result(path))


def _comparison(path: Path) -> RoleComparisonSet:
    return RoleComparisonSet.model_validate(read_result(path))


def _write_summary(value: dict):
    print(json.dumps(value, ensure_ascii=True, sort_keys=True))


def _alignment_summary(result: AlignmentResult):
    counts = {"exact_synonym": 0, "ambiguous": 0, "unknown": 0}
    for item in result.alignments:
        counts[item.state] += 1
    return dict(status="ok", knowledge_id=result.knowledge_id,
                knowledge_revision=result.knowledge_revision,
                knowledge_sha256=result.knowledge_sha256,
                source_analysis_sha256=result.source_analysis_sha256,
                source_outcome=result.source_outcome,
                source_coverage={key: value.status for key, value in result.source_coverage.items()},
                requirements=len(result.requirements), **counts,
                candidate_projection_sha256=result.candidate_projection_sha256,
                semantic_review=result.semantic_review)


def build_parser():
    parser = argparse.ArgumentParser(description="P2-1 versioned knowledge workflow")
    commands = parser.add_subparsers(dest="command", required=True)

    for name in ("attribute", "reexplain"):
        command = commands.add_parser(name)
        command.add_argument("--analysis" if name == "attribute" else "--previous", required=True, type=Path)
        command.add_argument("--snapshot", required=True, type=Path)
        command.add_argument("--policy", required=True, type=Path)
        command.add_argument("--candidate-projection", type=Path)
        command.add_argument("--method", choices=("bounded", "context", "evidence", "work"), default="bounded")
        command.add_argument("--local-model", type=Path, help="explicit hash-bound local runtime manifest; never downloads")
        command.add_argument("--task-retriever", type=Path, help="explicit local ONNX priority manifest; evidence method only")
        command.add_argument("--pairs-per-role", type=int, choices=(1, 2, 3), default=1)
        command.add_argument("--output", required=True, type=Path)
    historical = commands.add_parser("read-attribution")
    historical.add_argument("--result", required=True, type=Path)

    validate = commands.add_parser("validate")
    validate.add_argument("--snapshot", required=True, type=Path)

    align = commands.add_parser("align")
    align.add_argument("--analysis", required=True, type=Path)
    align.add_argument("--snapshot", required=True, type=Path)
    align.add_argument("--output", required=True, type=Path)
    align.add_argument("--candidate-projection", type=Path)

    compare = commands.add_parser("compare")
    compare.add_argument("--analysis", required=True, type=Path)
    compare.add_argument("--snapshot", required=True, type=Path)
    compare.add_argument("--output", required=True, type=Path)

    govern = commands.add_parser("govern")
    govern.add_argument("--analysis", required=True, type=Path)
    govern.add_argument("--alignment", required=True, type=Path)
    govern.add_argument("--registry", required=True, type=Path)

    profile = commands.add_parser("profile")
    profile.add_argument("--role-id", required=True)
    profile.add_argument("--comparisons", required=True, type=Path)
    profile.add_argument("--alignments", required=True, nargs="+", type=Path)
    profile.add_argument("--output", required=True, type=Path)

    impact = commands.add_parser("impact")
    impact.add_argument("--old", required=True, type=Path)
    impact.add_argument("--new", required=True, type=Path)
    impact.add_argument("--old-candidate-projection", type=Path)
    impact.add_argument("--new-candidate-projection", type=Path)
    impact.add_argument("--alignments", required=True, nargs="+", type=Path)
    impact.add_argument("--output", required=True, type=Path)
    return parser


def main():
    args = build_parser().parse_args()
    try:
        if args.command in {"attribute", "reexplain", "read-attribution"}:
            from .attribution import attribute_roles, read_attribution
            from .role_policy import load_policy

            if args.command == "read-attribution":
                result = read_attribution(args.result)
            else:
                previous = read_attribution(args.previous) if args.command == "reexplain" else None
                source = previous.source_analysis.model_dump() if previous else _load_analysis(args.analysis)
                from .local_semantics import load_local_model
                if args.task_retriever:
                    from .task_retrieval import LocalTaskRetriever
                    retriever = LocalTaskRetriever(args.task_retriever)
                else:
                    retriever = None
                result = attribute_roles(source, load_snapshot(args.snapshot), load_policy(args.policy),
                                         load_projection(args.candidate_projection) if args.candidate_projection else None,
                                         method=args.method, local_model=load_local_model(args.local_model) if args.local_model else None,
                                         task_retriever=retriever, pairs_per_role=args.pairs_per_role)
                if previous:
                    result.reinterprets_sha256 = digest(previous.model_dump())
                save_result(args.output, result.model_dump())
            semantic = getattr(result, "semantic", None)
            tasks = getattr(result, "task_assessments", [])
            selection = getattr(result, "task_selection", None)
            _write_summary(dict(status="partial" if (semantic and semantic.status == "failed") or any(a.state == "failed" for a in tasks) else "ok",
                                semantic_status=semantic.status if semantic else "not_run",
                                task_execution_status=("not_run" if not tasks else "partial" if
                                    any(a.state == "failed" for a in tasks) or selection.pending_selected_pair_ids else "completed"),
                                checked_task_pairs=len(tasks), supported_task_pairs=sum(a.state == "machine_supported" for a in tasks),
                                selected_task_pairs=len(selection.selected_pair_ids) if selection else 0,
                                pending_task_pairs=len(selection.pending_selected_pair_ids) if selection else 0,
                                schema_version=result.schema_version,
                                source_analysis_sha256=result.source_analysis_sha256,
                                knowledge_sha256=result.knowledge_sha256, policy_sha256=result.policy_sha256,
                                implementation_sha256=result.implementation_sha256,
                                candidate_projection_sha256=result.alignment.candidate_projection_sha256,
                                checked_roles=len(result.comparisons), work_shape=result.work_shape,
                                axes={name: getattr(result.axes, name).status for name in type(result.axes).model_fields},
                                semantic_review=result.semantic_review, change_kind=result.change_kind))
            return 0
        if args.command == "validate":
            loaded = load_snapshot(args.snapshot)
            _write_summary(dict(status="ok", id=loaded.snapshot.id,
                                revision=loaded.snapshot.revision, sha256=loaded.sha256,
                                concepts=len(loaded.snapshot.concepts),
                                roles=len(loaded.snapshot.roles),
                                sources=len(loaded.snapshot.sources)))
            return 0
        if args.command == "align":
            knowledge = load_snapshot(args.snapshot)
            result = align_analysis(_load_analysis(args.analysis), knowledge,
                                    load_projection(args.candidate_projection) if args.candidate_projection else None)
            save_result(args.output, result.model_dump())
            _write_summary(_alignment_summary(result))
            return 0
        if args.command == "compare":
            knowledge = load_snapshot(args.snapshot)
            result = compare_roles(_load_analysis(args.analysis), knowledge)
            save_result(args.output, result.model_dump())
            counts = {"supported": 0, "unresolved": 0, "not_supported": 0}
            for item in result.comparisons:
                counts[item.judgment] += 1
            _write_summary(dict(status="ok", checked_roles=len(result.checked_role_ids),
                                comparison_status=result.comparison_status,
                                knowledge_revision=result.knowledge_revision,
                                source_analysis_sha256=result.source_analysis_sha256,
                                source_outcome=result.source_outcome,
                                source_coverage={key: value.status
                                                 for key, value in result.source_coverage.items()},
                                **counts))
            return 0
        if args.command == "govern":
            analysis = _load_analysis(args.analysis)
            registry = CandidateRegistry(args.registry)
            observations = registry.observe(analysis, _alignment(args.alignment))
            projection = registry.project()
            _write_summary(dict(status="ok", observations=len(observations),
                                candidates=sorted({item.candidate_id for item in observations}),
                                projection_sha256=projection.sha256,
                                projection_concepts=len(projection.projection.concepts)))
            return 0
        if args.command == "profile":
            result = build_profile(args.role_id, _comparison(args.comparisons),
                                   [_alignment(path) for path in args.alignments])
            save_result(args.output, result.model_dump())
            _write_summary(dict(status="ok", role_id=result.role_id,
                                members=len(result.members), mode=result.mode,
                                claim_scope=result.claim_scope,
                                knowledge_revision=result.knowledge_revision,
                                candidate_projection_sha256=result.candidate_projection_sha256,
                                knowledge_sha256=result.knowledge_sha256))
            return 0
        if args.command == "impact":
            result = locate_impact(
                load_snapshot(args.old), load_snapshot(args.new),
                [_alignment(path) for path in args.alignments],
                old_candidate_projection=(load_projection(args.old_candidate_projection)
                                          if args.old_candidate_projection else None),
                new_candidate_projection=(load_projection(args.new_candidate_projection)
                                          if args.new_candidate_projection else None),
            )
            save_result(args.output, result.model_dump())
            _write_summary(dict(status="ok", affected=len(result.affected),
                                conservative=result.conservative,
                                candidate_projection_changed=result.candidate_projection_changed,
                                old_revision=result.old_revision,
                                new_revision=result.new_revision))
            return 0
        raise ValueError("unknown command")
    except (OSError, ValueError, KeyError, TypeError):
        _write_summary(dict(status="rejected", reason="invalid_or_unavailable_input_or_output"))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

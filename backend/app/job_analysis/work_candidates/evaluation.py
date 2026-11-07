"""Private, zero-network continuous replay; diagnostics are not human semantic truth."""
import argparse
import asyncio
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from ..foundation.inputs import canonical, digest, parse_json
from ..foundation.store import safe_destination
from ..knowledge.catalog import load_snapshot
from ..understanding.storage import read_run
from .service import algorithm_version, apply_batch
from .storage import CandidateStore


def replay_cli_baseline(current_output, output, backend, knowledge_path):
    """Run an explicitly selected checkout's real CLI, with identical inputs and seeds."""
    current_output, backend = Path(current_output).resolve(), Path(backend).resolve()
    root = safe_destination(output)
    root.mkdir(parents=True, exist_ok=False)
    source_root = backend / "app/job_analysis"
    source_sha256s = {p.relative_to(backend).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                     for directory in ("work_candidates", "knowledge", "foundation", "baseline", "semantics")
                     for p in sorted((source_root / directory).glob("*.py"))}
    commands = []

    def cli(name, *args):
        command = [sys.executable, "-m", "app.job_analysis.work_candidates", *map(str, args)]
        run = subprocess.run(command, cwd=backend, capture_output=True, encoding="utf-8")
        commands.append(dict(command=command, cwd=str(backend), returncode=run.returncode))
        if run.returncode:
            raise ValueError("baseline CLI rejected input; private command retained in memory")
        value = parse_json(run.stdout)
        (root / (name + "-state.json")).write_text(canonical(value), encoding="utf-8")
        return value

    state_path = root / "state.db"
    state = cli("initial", "init", "--state", state_path)
    current = parse_json((current_output / "evaluation.json").read_text(encoding="utf-8"))
    rows = []
    for index in range(1, current["input_count"] + 1):
        name = f"batch-{index}"
        request = parse_json((current_output / (name + "-request.json")).read_text(encoding="utf-8"))
        request["baseline"] = state["binding"]
        request_path = root / (name + "-request.json")
        request_path.write_text(canonical(request), encoding="utf-8")
        state = cli(name, "apply", "--state", state_path, "--batch", request_path,
                    "--analysis", current_output / f"analysis-{index}.json", "--knowledge", knowledge_path)
        rows.append(dict(batch_id=name, analysis_sha256s=request["analysis_sha256s"],
                         automatic_candidate_ids=state["report"]["searches"][0]["matched_candidate_ids"],
                         binding=state["binding"]))
    if any(hashlib.sha256((backend / name).read_bytes()).hexdigest() != sha for name, sha in source_sha256s.items()):
        raise ValueError("baseline source changed during replay")
    result = dict(batch_count=len(rows), source_sha256s=source_sha256s, rows=rows, commands=commands,
                  input_nature=current["input_nature"], independent_human_denominator=0,
                  accuracy=None, scope="full_continuous_original_CLI_with_identical_order_inputs_and_explicit_seeds")
    (root / "evaluation.json").write_text(canonical(result), encoding="utf-8")
    (root / "manifest.json").write_text(canonical(dict(files={p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.iterdir()) if p.is_file()})), encoding="utf-8")
    return result


def evaluate_analyses(analyses, knowledge, output, *, source_bindings, via_delivery=False):
    root = safe_destination(output)
    root.mkdir(parents=True, exist_ok=False)

    def save(name, value):
        (root / name).write_text(canonical(value), encoding="utf-8")

    rows, states, commands, delivery_results = [], [], [], {}
    if via_delivery:
        from ..delivery.runner import execute
        from ..delivery.store import DeliveryStore
        engine = DeliveryStore(root / "delivery", create=True)
    else:
        engine = CandidateStore(root / "state.db", create=True)
    with engine:
        store = engine.candidates if via_delivery else engine
        def apply(label, values=(), operations=()):
            if via_delivery and not values:
                values = analyses[:1]  # delivery maintenance replay carries an unchanged explicit input
            request = dict(schema_version="m2-work-batch-1", batch_id=label,
                           baseline=store.read()["binding"], operation_version="controlled-replay-1",
                           analysis_sha256s=sorted(digest(a) for a in values), operations=list(operations))
            if via_delivery:
                delivery_request = dict(schema_version="m2-delivery-request-1", baseline=request["baseline"],
                    items=[dict(namespace=a["namespace"], row=a["input_row"], input_version=a["input_version"],
                                analysis=a) for a in values], operations=list(operations))
                result = asyncio.run(execute(engine, label, delivery_request, knowledge))
                if result["status"] != "completed" or result["work"] is None:
                    raise ValueError("delivery replay did not complete")
                state = result["work"]
                delivery_results[label] = result
                save(label + "-delivery-request.json", delivery_request)
                save(label + "-delivery-result.json", result)
            else:
                state = apply_batch(store, request, {digest(a): a for a in values}, knowledge)
            save(label + "-request.json", request)
            save(label + "-state.json", state)
            commands.append(dict(batch_id=label, request_sha256=digest(request), result_binding=state["binding"]))
            return state

        for index, analysis in enumerate(analyses, 1):
            sha = digest(analysis)
            save(f"analysis-{index}.json", analysis)
            work = [c for c in analysis["claims"] if c["kind"] == "duty" and c.get("core") is not False]
            # One explicit observation seed per input is a replay control, not automatic discovery.
            operations = [dict(op="create", candidate_id=f"observation-{index}",
                description="受控实际职责观察种子", research_question="后批是否存在逐成员直接支持的局部共同工作？",
                core_work=[dict(analysis_sha256=sha, claim_id=c["id"]) for c in work])] if work else []
            state = apply(f"batch-{index}", [analysis], operations)
            states.append(state)
            search = state["report"]["searches"][0]
            alignment = store.source("alignment", state["report"]["alignments"][sha])
            members = [m for requirement in alignment["requirements"] for m in requirement["alignments"]]
            rows.append(dict(namespace=analysis["namespace"], jd_id=analysis["jd_id"], analysis_sha256=sha,
                             p1_outcome=analysis["outcome"], p1_coverage=analysis["coverage"],
                             p1_semantic_review=analysis["semantic_review"],
                             skill_alignment=dict(state_counts=dict(Counter(m["state"] for m in members)),
                                 knowledge_status_counts=dict(Counter(m["knowledge_status"] for m in members)),
                                 members=members, correctness="not_adjudicated"),
                             baseline=state["report"]["baseline"],
                             automatic_candidate_ids=search["matched_candidate_ids"],
                             literal_baseline_candidate_ids=[m["candidate_id"] for m in search["lexical_matches"]],
                             candidate_checks=search["candidate_checks"],
                             delivery=delivery_results[f"batch-{index}"]["items"][0] if via_delivery else None,
                             explicit_seed_ids=[op["candidate_id"] for op in operations]))

        head = store.read()
        automatic = [r for r in head["relations"].values()
                     if r.get("discovery", {}).get("kind") == "automatic_bounded_semantic"]
        maintenance = dict(status="not_run_no_relations")
        # A controlled withdrawal verifies consumption, not a judgment that the real link is wrong.
        chosen = next(iter(automatic or list(head["relations"].values())), None)
        if chosen:
            old_revision = head["revision"]
            old = head
            reduced = apply("maintenance-withdraw", operations=[dict(op="correct", relation_id=chosen["id"],
                expected_sha256=digest(chosen), decision="withdraw", verification=None,
                reason="受控维护操作：仅验证收窄和后批消费，不是对真实同组的人审裁决")])
            replay = store.source("analysis", chosen["analysis_sha256"])
            after = apply("maintenance-consumer", [replay])
            maintenance = dict(status="controlled_mechanism_on_real_inputs", relation_id=chosen["id"],
                revised_binding=reduced["binding"], consumer_binding=after["binding"],
                history_preserved=store.read(old_revision) == old,
                later_batch_consumed_revised_binding=after["report"]["baseline"] == reduced["binding"],
                withdrawn_relation_not_revived=after["relations"][chosen["id"]]["state"] == "withdrawn",
                removed_comparison_work=reduced["report"]["evolution"][chosen["candidate_id"]]["removed_comparison_work"])
        integrity = store.conn.execute("PRAGMA integrity_check").fetchone()[0]
        result = dict(schema_version="m2-cross-batch-evaluation-1", algorithm=algorithm_version(),
            execution_entry="delivery.execute" if via_delivery else "work_candidates.apply_batch",
            source_bindings=source_bindings, knowledge_sha256=knowledge.sha256,
            input_nature="synthetic_mechanism" if all(a["namespace"] == "synthetic" for a in analyses) else "controlled_dev_historical_p1_replay",
            input_count=len(analyses), automatic_links=len(automatic),
            literal_baseline="p3-bigram-overlap-at-least-two-on-the-same-frozen-current-candidate-state",
            baseline_limitation="词面反事实使用同一当前冻结候选；不是重跑完整历史算法，也不表示真值。",
            real_grouping_human_denominator=0, grouping_accuracy=None, grouping_recall=None,
            evolution_human_denominator=0, evolution_accuracy=None,
            network_requests=0, fresh_model_calls=0, new_model_cost=0,
            rows=rows, maintenance=maintenance, integrity_check=integrity,
            limitations=["DEV是开发材料，不是独立留出", "显式逐JD观察种子是评价输入，不计自动发现",
                         "有界工作方面规则可能漏未知表述，局部关联不证明整岗同组", "维护操作属于机制对照，不是独立演化方向裁决"])
        save("evaluation.json", result)
        save("commands.json", commands)
    files = {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob("*")) if p.is_file()}
    save("manifest.json", dict(schema_version="m2-cross-batch-files-1", files=files))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-runs", type=Path, required=True, help="Explicit approved DEV run map; never scans directories")
    parser.add_argument("--knowledge", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--via-delivery", action="store_true")
    args = parser.parse_args()
    source = parse_json(args.source_runs.read_text(encoding="utf-8"))
    analyses, bindings = [], []
    for name, item in sorted(source.items()):
        if not name.startswith("DEV-"):
            raise ValueError("only explicitly selected DEV inputs are allowed")
        run = read_run(item["path"])
        if digest(run) != item["run_sha256"]:
            raise ValueError("frozen run binding mismatch")
        analyses.append(run["analysis"])
        bindings.append(dict(case_id=name, **item, analysis_sha256=digest(run["analysis"])))
    result = evaluate_analyses(analyses, load_snapshot(args.knowledge), args.output, source_bindings=bindings, via_delivery=args.via_delivery)
    print(json.dumps({k: result[k] for k in ("input_count", "automatic_links", "grouping_accuracy", "maintenance", "integrity_check")}, ensure_ascii=False))


if __name__ == "__main__":
    main()

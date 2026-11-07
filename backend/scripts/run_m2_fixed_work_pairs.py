"""Explicit local fixed-pair research; private paths and diagnoses stay in a manifest.

Manifest: {records:[{sample, previous_work, pairs:[{claim_id,role_id,reference_id,
diagnosis,previous_state}]}]}. It never discovers datasets, reads HOLD, or writes DB.
Each response is freshly generated; historical states are comparison metadata only.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
import re
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.job_analysis.foundation.inputs import digest
from app.job_analysis.foundation.store import safe_destination
from app.job_analysis.knowledge.attribution import read_attribution, attribute_roles, IMPLEMENTATION_SHA256
from app.job_analysis.knowledge.catalog import load_snapshot
from app.job_analysis.knowledge.role_policy import load_policy
from app.job_analysis.knowledge.local_semantics import load_local_model
from app.job_analysis.knowledge.storage import save_result
from app.job_analysis.knowledge.work_comparison import (
    start_work_comparison, _work_input, work_prompts, WorkInterpretation, WorkVerification, add_work_response)
from app.job_analysis.knowledge.research_summary import build_delivery_research
from app.job_analysis.knowledge import work_semantics  # Freeze import before inference.


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, choices=(1, 2), default=1)
    args = parser.parse_args()
    source = json.loads(args.manifest.read_text(encoding="utf-8-sig"))
    samples = [r["sample"] for r in source["records"]]
    if (len(samples) != len(set(samples)) or any(not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", sample)
            or re.fullmatch(r"CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9]", sample, re.I) for sample in samples)):
        raise ValueError("manifest sample must be a unique safe path component")
    args.output = safe_destination(args.output)
    args.output.mkdir(parents=True, exist_ok=False)
    root = Path(__file__).resolve().parents[1] / "app/job_analysis/knowledge"
    snapshot = {p.name: p.read_text(encoding="utf-8-sig") for p in root.glob("*.py")}
    (args.output / "implementation.private.json").write_text(json.dumps(snapshot), encoding="utf-8")
    knowledge = load_snapshot(root / "catalog/role-references.v3")
    policy = load_policy(root / "policies/role-attribution.v2.json")
    model = load_local_model(args.model)
    jobs, records = [], []
    for record in source["records"]:
        previous = read_attribution(record["previous_work"])
        context = attribute_roles(previous.source_analysis.model_dump(), knowledge, policy, method="context")
        save_result(args.output / "offline" / record["sample"], build_delivery_research(previous.source_analysis.model_dump(), knowledge))
        for pair in record["pairs"]:
            jobs.append((record["sample"], pair, context))

    def run(job):
        sample, pair, context = job
        result = start_work_comparison(context, version=3)
        identity = (pair["claim_id"], pair["role_id"], pair["reference_id"])
        data = _work_input(result, *identity)
        prompts = work_prompts(data["model_input"])
        responses, seconds, errors = [], [], []
        # Both questions run on all fixed pairs: a guard cannot hide a failing pair
        # by preventing the fresh comparison used for this diagnostic.
        for prompt, schema in zip(prompts, (WorkInterpretation, WorkVerification)):
            start = time.monotonic()
            try:
                response = model.complete_json(prompt, schema.model_json_schema())
                error = None
            except (OSError, ValueError, TimeoutError, subprocess.TimeoutExpired) as exc:
                response, error = None, type(exc).__name__
            responses.append(response)
            seconds.append(time.monotonic()-start)
            errors.append(error)
        result = add_work_response(result, *identity, *responses, model.manifest.binding.model_dump(),
            model.manifest.prompt_format, *seconds)
        item = result.task_assessments[-1]
        save_result(args.output / "fresh" / sample / item.id, result.model_dump())
        row = dict(sample=sample, **pair, pair_id=item.id, state=item.state, reason_code=item.reason_code,
            source_analysis_sha256=result.source_analysis_sha256, result_sha256=digest(result.model_dump()),
            fresh_model_calls=2, elapsed_seconds=sum(seconds), errors=errors)
        print(json.dumps(row, ensure_ascii=True), flush=True)
        return row

    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for row in pool.map(run, jobs):
            records.append(row)
            (args.output / "progress.private.json").write_text(json.dumps(records, indent=2), encoding="utf-8")
    summary = dict(records=records, fixed_pairs=len(jobs), fresh_model_calls=len(jobs)*2,
        historical_response_revalidations=0, elapsed_seconds=time.monotonic()-started,
        implementation_sha256=IMPLEMENTATION_SHA256, source_snapshot_sha256=digest(snapshot),
        manifest_sha256=digest(source), model_binding=model.manifest.binding.model_dump(),
        knowledge_sha256=knowledge.sha256, policy_sha256=policy.sha256,
        independent_human_denominator=0, precision=None, recall=None, external_calls=0, database_writes=0)
    (args.output / "evaluation.private.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()

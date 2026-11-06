"""Reproducible six-batch synthetic CLI evidence. Never loads private JD or a model."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from ..baseline.contract import DIMENSIONS, validate_analysis
from ..foundation.inputs import InputRecord, canonical, digest
from ..foundation.store import safe_destination
from .storage import CandidateStore


def synthetic_analysis(jd_id, duties, stack):
    """Explicit invented statements for mechanism checks, not generated human labels."""
    goal, target = "保障交易正确性。", "交易服务。"
    row = dict(id=jd_id, source="Synthetic P4 control", job_title="受控工程样例",
               raw_text="目标：" + goal + "\n对象：" + target + "\n" + "\n".join(duties) + "\n技术要求：" + stack + "。")
    record = InputRecord.from_row("synthetic", row)

    def claim(cid, kind, text, requirement=None):
        start = row["raw_text"].index(text)
        ev = dict(namespace="synthetic", jd_id=jd_id, fingerprint=record.fingerprint, field="raw_text",
                  start=start, end=start + len(text), quote=text)
        if requirement:
            requirement["scope_evidence"] = [ev]
        return dict(id=cid, kind=kind, text=text, core=True if kind == "duty" else None,
                    evidence=[ev], requirement=requirement, reason="公开合成机制材料，非真实或人审语义")

    requirement = dict(state="required", target="capability", category="technical_skill", members=[stack],
                       combination="single", open_set=False, degree=None, degree_polarity=None,
                       condition=None, reason="合成原文显式要求")
    claims = [claim(f"d{i}", "duty", text) for i, text in enumerate(duties, 1)]
    claims += [claim("g1", "goal", goal), claim("o1", "object", target), claim("r1", "requirement", stack, requirement)]
    coverage = {k: dict(status="not_run" if k == "classification" else "complete", reason="显式合成夹具") for k in sorted(DIMENSIONS)}
    versions = {k: dict(id="synthetic-" + k, revision="1", sha256=digest(["p4-demo", k, "1"]))
                for k in ("analyzer", "model", "prompt", "configuration")}
    value = dict(contract_version="m2-semantic-0.2", namespace="synthetic", jd_id=jd_id, input_row=row,
                 input_sha256=record.fingerprint, input_version="synthetic-p4-1", **versions,
                 knowledge=[], outcome="partial", coverage=coverage, claims=claims, alignments=[],
                 relations=[], role_judgments=[], semantic_review="machine_unreviewed")
    validate_analysis(value)
    return value


def run_demo(output, knowledge):
    """Every apply/show/retry runs through the public CLI in a fresh process."""
    root = safe_destination(output)
    root.mkdir(parents=True, exist_ok=False)
    state_path = root / "state.db"
    commands = []

    def write(name, value):
        path = root / name
        with path.open("x", encoding="utf-8") as stream:
            stream.write(canonical(value))
        return path

    def cli(name, *args):
        command = [sys.executable, "-m", "app.job_analysis.work_candidates", *map(str, args)]
        result = subprocess.run(command, cwd=Path(__file__).resolve().parents[3], capture_output=True,
                                text=True, encoding="utf-8")
        commands.append(dict(command=command, returncode=result.returncode))
        if result.returncode:
            raise ValueError("synthetic CLI sequence failed")
        value = json.loads(result.stdout)
        write(name + ".json", value)
        return value

    a = synthetic_analysis("seed-python", ["开发订单交易接口。"], "Python")
    other = synthetic_analysis("seed-go", ["开发订单交易接口。"], "Go")
    b = synthetic_analysis("new-support", ["开发订单交易接口。", "执行幂等校验并维护去重记录。"], "Go")
    c = synthetic_analysis("scope-check", ["执行幂等校验并维护去重记录。"], "Go")
    paths = {digest(v): write(v["jd_id"] + ".json", v) for v in (a, other, b, c)}
    initial = cli("zero", "init", "--state", state_path)
    states, requests = [], []

    def apply(values=(), operations=()):
        prior = states[-1] if states else initial
        name = "batch-" + str(len(states) + 1)
        request = dict(schema_version="m2-work-batch-1", batch_id=name, baseline=prior["binding"],
                       operation_version="synthetic-p4-demo-1", analysis_sha256s=sorted(digest(v) for v in values), operations=list(operations))
        request_path = write(name + "-request.json", request)
        args = ["apply", "--state", state_path, "--batch", request_path, "--knowledge", knowledge]
        for sha in request["analysis_sha256s"]:
            args += ["--analysis", paths[sha]]
        states.append(cli(name, *args))
        requests.append(args)

    core = [dict(analysis_sha256=digest(v), claim_id="d1") for v in (a, other)]
    apply([a, other], [dict(op="create", candidate_id="work-orders", description="交易接口研究种子",
                           research_question="相关职责能否形成有界工作组合？", core_work=core)])
    apply([b], [dict(op="link", candidate_id="work-orders", analysis_sha256=digest(b), work_ids=["d1", "d2"],
                    reason="合成序列提供待研究的具体职责范围，不认证同组")])
    apply([c])

    def correct(jd_id, decision):
        old = next(r for r in states[-1]["relations"].values() if r["jd_id"] == jd_id)
        return dict(op="correct", relation_id=old["id"], expected_sha256=digest(old), decision=decision,
                    reason="受控反例：局部检索不证明整体同组，撤除旧假设的扩展范围", verification=None,
                    counterevidence=[dict(analysis_sha256=old["analysis_sha256"], claim_id="d1")])

    apply(operations=[correct("new-support", "weakens"), correct("scope-check", "withdraw")])
    apply(operations=[correct("new-support", "withdraw")])
    apply([a, other])
    replay = cli("historical-two", "show", "--state", state_path, "--revision", 2)
    retried = cli("exact-retry-two", *requests[1])
    head = cli("reopened-head", "show", "--state", state_path)
    third_pairs = [p for m in states[2]["report"]["searches"][0]["matches"] for p in m["pairs"]]
    used_new = any(p["core_reference"] == dict(analysis_sha256=digest(b), claim_id="d2") for p in third_pairs)
    with CandidateStore(state_path) as store:
        source_hashes = [dict(kind=k, sha256=s) for k, s in store.conn.execute("SELECT kind,sha256 FROM sources ORDER BY kind,sha256")]
        for source in source_hashes:
            if digest(store.source(source["kind"], source["sha256"])) != source["sha256"]:
                raise ValueError("source replay failed")
    summary = dict(batches=6, input_jd_identities=4, source_analyses=4,
                   research_versions=[s["candidates"]["work-orders"]["research"]["version"] for s in states],
                   bindings=[s["binding"] for s in states], source_hashes=source_hashes,
                   third_batch_used_second_effective_work=used_new,
                   historical_readback=replay == states[1], exact_retry_preserved_head=retried == states[1] and head == states[-1],
                   real_human_grouping_denominator=0, real_semantic_accuracy="unverified",
                   independent_sources=None, vacancies=None, formal_roles=head["formal_roles"])
    if not all((used_new, summary["historical_readback"], summary["exact_retry_preserved_head"])):
        raise ValueError("synthetic behavior self-check failed")
    write("commands.json", commands)
    write("summary.json", summary)
    files = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.iterdir()) if p.is_file()}
    write("manifest.json", dict(schema_version="m2-p4-demo-files-1", files=files))
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--knowledge", type=Path, required=True)
    args = parser.parse_args()
    result = run_demo(args.output, args.knowledge)
    print(json.dumps({k: result[k] for k in ("batches", "research_versions", "third_batch_used_second_effective_work",
                                            "historical_readback", "exact_retry_preserved_head", "real_semantic_accuracy")}))


if __name__ == "__main__":
    main()

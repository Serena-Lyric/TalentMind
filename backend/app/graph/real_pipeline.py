"""Versioned offline M1/B1/B2/B22 -> M3 bundle, without services or production rebuild."""
import argparse
from collections import Counter
import hashlib
import importlib.metadata
import json
from pathlib import Path
from urllib.parse import quote

from ..job_analysis.foundation.inputs import InputRecord, canonical, digest, parse_json, read_snapshot, check_public
from ..job_analysis.screening.inputs import read_batch
from ..job_analysis.screening.rules import ScopeDefinition
from ..job_analysis.screening.store import ScreeningStore
from ..job_analysis.screening.runner import execute as screen
from ..job_analysis.semantics.store import SemanticStore
from ..job_analysis.semantics.runner import execute as semantics
from ..job_analysis.governance.store import GovernanceStore
from ..job_analysis.governance.runner import execute as govern
from ..job_analysis.governance.extract import verify_evidence
from .candidate_layout import build_layout, snapshot_hash
from .research.algorithms import pair_scores, community_run

VERSION = "real-jd-quality-replay-v2"
ROOT = Path(__file__).resolve().parents[3]


def write_json(path, body):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(canonical(body) + "\n")


def project(sources):
    """Graph facts are attributed algorithm statements, never human-reviewed requirements."""
    nodes, edges, sets = {}, [], {}
    for index, record in enumerate(sources["records"]):
        decision, overlay = record["screening"], record["governance"]
        if not record["eligible"] or overlay is None:
            continue
        job = "jd:" + quote(record["namespace"], safe="") + ":" + quote(record["jd_id"], safe="")
        nodes[job] = dict(id=job, type="job", name=record["payload"]["job_title"], source=[record["payload"]["source"]],
            entity_semantics="original_jd_record_not_standard_occupation_or_vacancy", source_records=[index],
            canonical_job=None, family=None, core_duties=record["payload"].get("duties", ""),
            analysis_complete=False, formal_statistics_eligible=False)
        sets[job] = set()
        original = overlay["original_semantics"]
        statements = {s["id"]: s for s in original["statements"]}
        for skill in overlay["skills"]:
            sid = "skill:" + quote(skill["canonical"], safe="")
            nodes.setdefault(sid, dict(id=sid, type="skill", name=skill["canonical"], source_records=[]))
            if index not in nodes[sid]["source_records"]:
                nodes[sid]["source_records"].append(index)
            for statement_id in skill["statement_ids"]:
                statement = statements[statement_id]
                names = {member["name"] for member in statement["skills"] if member.get("evidence") == skill["evidence"]}
                if not names:
                    names = {member["name"] for member in statement["skills"] if member["name"] == skill["canonical"]}
                conflict = any(e["skill"] in names and e["conflict"] and statement_id in e["statement_ids"] + e["group_ids"] for e in original["effective"])
                edge = dict(id=f"assertion:{index}:{skill['id']}:{statement_id}", source=job, target=sid,
                    type="HAS_SKILL_STATEMENT", state=statement["state"], conflict=conflict,
                    relation=statement["relation"], requirement_object=statement["requirement_object"],
                    degree=statement["degree"], condition=statement["condition"], target_context=statement["target"],
                    statement_id=statement_id, evidence=skill["evidence"], statement=statement,
                    normalization={k: v for k, v in skill.items() if k not in ("context", "evidence")},
                    source_record=index, semantic_validation="deterministic_rules_only", semantic_review="unreviewed",
                    formal_statistics_eligible=False)
                edges.append(edge)
                if statement["state"] in ("required", "preferred") and not conflict and not statement["relation"] and not statement["condition"]:
                    sets[job].add(sid)
    return dict(schema_version="m3-real-facts-1", interpretation="attributed bounded M2 observations; not verified semantic truth",
        nodes=sorted(nodes.values(), key=lambda n: n["id"]), edges=sorted(edges, key=lambda e: e["id"])), sets


def code_hashes():
    files = [Path(__file__), ROOT / "backend/app/graph/candidate_layout.py", ROOT / "backend/app/graph/research/algorithms.py"]
    for folder in ("foundation", "screening", "semantics", "governance"):
        files.extend((ROOT / "backend/app/job_analysis" / folder).glob("*.py"))
    files.extend([ROOT / "backend/app/job_analysis/governance/policy.v1.json", ROOT / "backend/app/skills/skill_dict_seed.json", ROOT / "backend/app/skills/normalizer.py", ROOT / "backend/app/collect/cleaner.py"])
    return {p.relative_to(ROOT).as_posix(): snapshot_hash(p.read_bytes()) for p in sorted(files)}


def derive(graph, sets, graph_hash):
    similarity = [dict(source=e["source"], target=e["target"], score=e["jaccard"], shared=e["shared"]) for e in pair_scores(sets) if e["jaccard"] >= .10]
    partition = community_run(sorted(sets), similarity, "leiden", 1., 42)["members"] if sets else []
    derived = dict(schema_version="m3-real-derived-1", source_graph_sha256_lf=graph_hash,
        projection="non-conflicting, unconditional required/preferred singles only; no group flattening",
        algorithm="Jaccard>=0.10 + Leiden RBConfiguration resolution=1 seed=42", edges=similarity, communities=partition)
    layout = build_layout(graph, graph_hash, partition=partition, similarity=similarity)
    layout["parameters"] = dict(layout["parameters"], projection=derived["projection"])
    layout["interpretation"] = "real JD bounded observations; display only; no formal occupation classification"
    layout["algorithm_source"] = "candidate_layout.py + research/algorithms.py (hashes in manifest)"
    layout["derived_sha256"] = digest(derived)
    return derived, layout


def run_pipeline(input_path, dataset, output, provenance_path=None):
    input_path, output = Path(input_path).resolve(), Path(output).resolve()
    if output.exists():
        raise ValueError("output must not exist; use verify for immutable bundles")
    if output.is_relative_to(ROOT) and not output.is_relative_to(ROOT / "data/local"):
        raise ValueError("private output inside repository must be under data/local")
    if input_path.is_relative_to(output):
        raise ValueError("input must be outside output")
    raw_input = input_path.read_bytes()
    rows = parse_json(raw_input.decode("utf-8-sig"))
    if not isinstance(rows, list) or not rows:
        raise ValueError("pipeline requires a nonempty JSON array")
    check_public(rows)
    batch = read_batch(input_path, dataset)
    records = [u.record for u in batch.units if u.record is not None]
    scope = ScopeDefinition.model_validate(parse_json((ROOT / "backend/app/job_analysis/screening/software-related.offline.json").read_text(encoding="utf-8"))).model_dump()
    output.mkdir(parents=True)
    (output / "input.json").write_bytes(raw_input)
    if provenance_path is not None:
        provenance = parse_json(Path(provenance_path).read_text(encoding="utf-8"))
        if provenance["input_sha256"] != hashlib.sha256(raw_input).hexdigest():
            raise ValueError("source provenance input hash mismatch")
        write_json(output / "source-provenance.json", provenance)
    state = output / "analysis.sqlite3"
    reports = output / "m2"
    with ScreeningStore(state) as store:
        screening = screen(store, input_path, dataset, scope=scope, output=reports)
    eligible = {m["jd_id"] for m in screening["members"] if m["validity"] == "valid" and m["scope_status"] == "in_scope" and m["execution_status"] == "completed"}
    selected = [dict(id=r.jd_id, **r.payload, **({"crawled_at": r.observation} if r.observation else {})) for r in records if r.jd_id in eligible]
    selected_path = output / "eligible.json"
    write_json(selected_path, selected)
    semantic_report, governance_report = None, None
    if selected:
        with SemanticStore(state) as store:
            semantic_report = semantics(store, read_snapshot(selected_path, dataset), output=reports)
        with GovernanceStore(state) as store:
            governance_report = govern(store, semantic_report["run_id"], output=reports)
    decisions = {m["input_position"]: m for m in screening["members"]}
    overlays = {m["jd_id"]: m for m in governance_report["members"]} if governance_report else {}
    sources = dict(schema_version="m3-real-sources-1", input_sha256=hashlib.sha256(raw_input).hexdigest(), records=[])
    for position, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            raise ValueError("pipeline source rows must be objects")
        jd_id = str(row.get("id", ""))
        decision = decisions[position]
        included = decision["validity"] == "valid" and decision["scope_status"] == "in_scope" and decision["execution_status"] == "completed"
        overlay = overlays.get(jd_id) if included else None
        payload = {k: v for k, v in row.items() if k not in ("id", "crawled_at")}
        sources["records"].append(dict(namespace=dataset, jd_id=jd_id, fingerprint=digest(payload),
            payload=payload, observation=row.get("crawled_at"), screening=decision,
            eligible=included, governance=overlay["body"] if overlay else None,
            m2_reference={k: overlay[k] for k in ("result_id", "source_attempt", "source_status", "snapshot_id")} if overlay else None))
    graph, sets = project(sources)
    write_json(output / "sources.json", sources)
    write_json(output / "facts.json", graph)
    derived, layout = derive(graph, sets, snapshot_hash((output / "facts.json").read_bytes()))
    similarity, partition = derived["edges"], derived["communities"]
    write_json(output / "derived.json", derived)
    write_json(output / "layout.json", layout)
    manifest = dict(schema_version="m3-real-bundle-1", pipeline_version=VERSION, dataset=dataset,
        data_version=digest(dict(input=sources["input_sha256"], code=code_hashes(), scope=scope)),
        input_sha256=sources["input_sha256"], implementation=code_hashes(),
        software={p: importlib.metadata.version(p) for p in ("networkx", "igraph", "leidenalg", "pydantic")},
        m2_runs=dict(screening=screening["run_id"], semantics=semantic_report["run_id"] if semantic_report else None,
            governance=governance_report["run_id"] if governance_report else None),
        m2_audits=dict(screening=screening["audit"], semantics=semantic_report["audit"] if semantic_report else None,
            governance=governance_report["audit"] if governance_report else None),
        counts=dict(input=len(rows), eligible_jd=len(eligible), excluded_or_pending=len(rows)-len(eligible),
            fact_nodes=len(graph["nodes"]), fact_edges=len(graph["edges"]), similarity_edges=len(similarity), communities=len(partition),
            nontrivial_communities=sum(len(group)>1 for group in partition),
            states=dict(Counter(e["state"] for e in graph["edges"])), conflicts=sum(e["conflict"] for e in graph["edges"])),
        formal_statistics_eligible=False, analysis_complete=False, semantic_review="not_performed",
        limitations=["bounded rules, not open-domain analysis", "no formal B3 catalog", "JD identities are not vacancies", "unresolved fragments retained in sources"],
        fallback="remove graphDataset=real; historical graph and P2.5 remain unchanged",
        artifacts={p.relative_to(output).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(output.rglob("*.json"))})
    write_json(output / "manifest.json", manifest)
    verify_bundle(output)
    return manifest


def verify_bundle(output):
    output = Path(output).resolve()
    manifest = parse_json((output / "manifest.json").read_text(encoding="utf-8"))
    for name, expected in manifest["artifacts"].items():
        path = (output / name).resolve()
        if not path.is_relative_to(output) or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("artifact hash mismatch")
    sources = parse_json((output / "sources.json").read_text(encoding="utf-8"))
    graph = parse_json((output / "facts.json").read_text(encoding="utf-8"))
    raw_input = (output / "input.json").read_bytes()
    if hashlib.sha256(raw_input).hexdigest() != manifest["input_sha256"] or sources["input_sha256"] != manifest["input_sha256"]:
        raise ValueError("source input hash mismatch")
    rows = parse_json(raw_input.decode("utf-8-sig"))
    if len(rows) != len(sources["records"]):
        raise ValueError("source input count mismatch")
    screening = parse_json((output / "m2" / (manifest["m2_runs"]["screening"] + ".json")).read_text(encoding="utf-8"))
    decisions = {m["input_position"]: m for m in screening["members"]}
    governance_id = manifest["m2_runs"]["governance"]
    governance = parse_json((output / "m2" / (governance_id + ".json")).read_text(encoding="utf-8")) if governance_id else None
    overlays = {m["jd_id"]: m["body"] for m in governance["members"]} if governance else {}
    for position, (row, record) in enumerate(zip(rows, sources["records"]), 1):
        expected_payload = {k:v for k,v in row.items() if k not in ("id", "crawled_at")}
        if (record["payload"] != expected_payload or record["jd_id"] != str(row.get("id", "")) or record["namespace"] != manifest["dataset"]
                or record["observation"] != row.get("crawled_at") or record["screening"] != decisions[position]):
            raise ValueError("source M1/B1 binding mismatch")
        decision = decisions[position]
        eligible = decision["validity"] == "valid" and decision["scope_status"] == "in_scope" and decision["execution_status"] == "completed"
        if record["eligible"] != eligible or record["governance"] != (overlays.get(record["jd_id"]) if eligible else None):
            raise ValueError("source M2 governance binding mismatch")
        if digest(record["payload"]) != record["fingerprint"]:
            raise ValueError("source fingerprint mismatch")
        if record["governance"]:
            value = InputRecord(record["namespace"], record["jd_id"], canonical(record["payload"]), record["observation"])
            verify_evidence(record["governance"], value)
    rebuilt, sets = project(sources)
    if rebuilt != graph:
        raise ValueError("fact source projection mismatch")
    layout = parse_json((output / "layout.json").read_text(encoding="utf-8"))
    if layout["snapshot_sha256_lf"] != snapshot_hash((output / "facts.json").read_bytes()) or {n["id"] for n in layout["nodes"]} != {n["id"] for n in graph["nodes"]}:
        raise ValueError("layout binding mismatch")
    expected_derived, expected_layout = derive(graph, sets, snapshot_hash((output / "facts.json").read_bytes()))
    if parse_json((output / "derived.json").read_text(encoding="utf-8")) != expected_derived:
        raise ValueError("derived recomputation mismatch")
    if layout != expected_layout:
        raise ValueError("layout recomputation mismatch")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("run", "verify"))
    parser.add_argument("--input", type=Path)
    parser.add_argument("--dataset")
    parser.add_argument("--provenance", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "run" and (not args.input or not args.dataset):
        parser.error("run requires explicit --input and --dataset")
    result = run_pipeline(args.input, args.dataset, args.output, args.provenance) if args.command == "run" else verify_bundle(args.output)
    print(json.dumps(dict(data_version=result["data_version"], counts=result["counts"]), ensure_ascii=True))


if __name__ == "__main__":
    main()

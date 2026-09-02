"""Build the full Neo4j graph from the imported M2 catalog."""
from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import text

from app.db.mysql import SessionLocal
from app.db.neo4j import get_neo4j

REPO_ROOT = Path(__file__).resolve().parents[3]
GRAPH_PATH = REPO_ROOT / "exchange" / "m3" / "graph.json"


def _list(value: Any) -> list:
    if isinstance(value, list):
        return value
    if not value:
        return []
    try:
        parsed = json.loads(value) if isinstance(value, str) else value
        return parsed if isinstance(parsed, list) else []
    except (TypeError, json.JSONDecodeError):
        return []


def _object(value: Any) -> dict:
    if isinstance(value, dict):
        return value
    if not value:
        return {}
    try:
        parsed = json.loads(value) if isinstance(value, str) else value
        return parsed if isinstance(parsed, dict) else {}
    except (TypeError, json.JSONDecodeError):
        return {}


def _slug(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "-", value.strip().lower()).strip("-")
    return value or "unknown"


def _skill_id(name: str) -> str:
    return f"skill:{_slug(name)}"


def build_graph_data(rows: list[dict[str, Any]], skill_rows: list[dict[str, Any]]) -> dict[str, list]:
    skill_by_job: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in skill_rows:
        for item in _list(row.get("skills")):
            if isinstance(item, dict):
                skill_by_job[int(row["jd_id"])].append(item)

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    job_skill_sets: dict[str, set[str]] = {}
    related_candidates: dict[tuple[str, str], int] = defaultdict(int)
    industry_jobs: dict[str, set[str]] = defaultdict(set)

    for row in rows:
        internal_id = int(row["id"])
        m2_id = str(row.get("m2_job_id") or f"db-{internal_id}")
        job_id = f"job:{_slug(m2_id)}"
        required = [str(item) for item in _list(row.get("required_skills")) if str(item).strip()]
        bonus = [str(item) for item in _list(row.get("bonus_skills")) if str(item).strip()]
        details = skill_by_job.get(internal_id, [])
        aliases: dict[str, str] = {}
        for item in details:
            display = str(item.get("name") or "").strip().lower()
            canonical = str(item.get("canonical_name") or item.get("name") or "").strip().lower()
            if display and canonical:
                aliases[display] = canonical
            if canonical:
                aliases[canonical] = canonical
        required_ids = [_skill_id(aliases.get(skill.lower(), skill.lower())) for skill in required]
        bonus_ids = [_skill_id(aliases.get(skill.lower(), skill.lower())) for skill in bonus]
        all_skill_ids = set(required_ids + bonus_ids)
        job_skill_sets[job_id] = all_skill_ids
        source = _list(row.get("source"))
        scenarios = [str(item).strip() for item in _list(row.get("scenarios")) if str(item).strip()]
        nodes.append({
            "id": job_id, "type": "job", "kind": "job", "name": str(row.get("name_en") or row.get("job_name") or ""),
            "name_zh": str(row.get("job_name_zh") or row.get("job_name") or ""), "name_en": str(row.get("name_en") or ""),
            "category": str(row.get("category") or ""), "is_emerging": bool(row.get("is_emerging")),
            "evolution": _object(row.get("evolution")),
            "source": source, "platform": "/".join(source), "core_duties": str(row.get("core_duties") or ""),
            "required_skills": required, "bonus_skills": bonus, "quality": float(row.get("quality") or 0),
            "jd_count": int(row.get("source_jd_count") or 0),
        })
        for skill, sid in zip(required, required_ids):
            node = next((item for item in nodes if item.get("id") == sid), None)
            if node is None:
                node = {"id": sid, "type": "skill", "kind": "skill", "name": aliases.get(skill.lower(), skill), "display_name": skill, "job_count": 0}
                nodes.append(node)
            node["job_count"] = int(node.get("job_count") or 0) + 1
            edges.append({"source": job_id, "target": sid, "type": "REQUIRES", "weight": 1.0, "is_required": True})
        for skill, sid in zip(bonus, bonus_ids):
            node = next((item for item in nodes if item.get("id") == sid), None)
            if node is None:
                node = {"id": sid, "type": "skill", "kind": "skill", "name": aliases.get(skill.lower(), skill), "display_name": skill, "job_count": 0}
                nodes.append(node)
            node["job_count"] = int(node.get("job_count") or 0) + 1
            edges.append({"source": job_id, "target": sid, "type": "REQUIRES", "weight": 0.6, "is_required": False})
        for scenario in scenarios[:8]:
            industry_id = f"industry:{_slug(scenario)}"
            if not any(item.get("id") == industry_id for item in nodes):
                nodes.append({"id": industry_id, "type": "industry", "kind": "industry", "name": scenario, "display_name": scenario, "job_count": 0, "color": "#c77dff"})
            industry_jobs[industry_id].add(job_id)
            edges.append({"source": job_id, "target": industry_id, "type": "APPLIES_TO", "weight": 1.0})

    for item in nodes:
        if item.get("type") == "industry":
            item["job_count"] = len(industry_jobs.get(item["id"], set()))
    skill_jobs: dict[str, list[str]] = defaultdict(list)
    for job_id, skill_ids in job_skill_sets.items():
        for skill_id in skill_ids:
            skill_jobs[skill_id].append(job_id)
    for values in skill_jobs.values():
        names = sorted(set(values))
        for index, left in enumerate(names):
            for right in names[index + 1:index + 11]:
                related_candidates[(left, right)] += 1
    for (left, right), shared in sorted(related_candidates.items(), key=lambda item: -item[1]):
        union = job_skill_sets[left] | job_skill_sets[right]
        similarity = shared / len(union) if union else 0
        if similarity >= 0.35:
            edges.append({"source": left, "target": right, "type": "RELATED_TO", "similar": round(similarity, 4)})

    unique_nodes = list({node["id"]: node for node in nodes}.values())
    unique_edges = list({(edge["source"], edge["target"], edge["type"]): edge for edge in edges}.values())
    return {"nodes": unique_nodes, "edges": unique_edges}


def rebuild() -> dict[str, int]:
    db = SessionLocal()
    try:
        rows = [dict(row) for row in db.execute(text("""
            SELECT id, job_name, name_en, job_name_zh, m2_job_id, category, is_emerging, evolution,
                   core_duties, required_skills, bonus_skills, scenarios, source, quality, source_jd_count
            FROM job_definition ORDER BY id
        """)).mappings().all()]
        skill_rows = [dict(row) for row in db.execute(text("SELECT jd_id, skills FROM job_skill")).mappings().all()]
    finally:
        db.close()
    graph = build_graph_data(rows, skill_rows)
    graph["metadata"] = {
        "node_count": len(graph["nodes"]), "edge_count": len(graph["edges"]),
        "source": "M2 full return package", "version": "m2-full-2026-09-02",
        "exported_at": datetime.now(timezone.utc).isoformat(),
    }
    GRAPH_PATH.parent.mkdir(parents=True, exist_ok=True)
    GRAPH_PATH.write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")

    driver = get_neo4j()
    try:
        with driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n").consume()
            for node_type, label in (("job", "Job"), ("skill", "Skill"), ("industry", "Industry")):
                payload = []
                for node in graph["nodes"]:
                    if node.get("type") != node_type:
                        continue
                    props = {key: (json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) and key == "evolution" else value) for key, value in node.items() if key not in {"id", "type", "kind"}}
                    props.setdefault("name", node.get("name") or node["id"])
                    payload.append({"node_id": node["id"], "props": props})
                if payload:
                    session.run(f"UNWIND $nodes AS node MERGE (n:{label} {{node_id: node.node_id}}) SET n += node.props", nodes=payload).consume()
            for relation in ("REQUIRES", "RELATED_TO", "APPLIES_TO"):
                payload = [{"source": edge["source"], "target": edge["target"], "props": {key: value for key, value in edge.items() if key not in {"source", "target", "type"}}} for edge in graph["edges"] if edge.get("type") == relation]
                if payload:
                    session.run(f"UNWIND $edges AS edge MATCH (a {{node_id: edge.source}}), (b {{node_id: edge.target}}) MERGE (a)-[r:{relation}]->(b) SET r += edge.props", edges=payload).consume()
            counts = session.run("MATCH (n) WITH count(n) AS nodes OPTIONAL MATCH ()-[r]->() RETURN nodes, count(r) AS edges").single()
    finally:
        driver.close()
    return {"job_rows": len(rows), "nodes": int(counts["nodes"]), "edges": int(counts["edges"])}


if __name__ == "__main__":
    print(json.dumps(rebuild(), ensure_ascii=False, indent=2))

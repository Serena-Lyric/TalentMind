"""Build and replace the Neo4j graph from the Chinese-platform catalog."""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from sqlalchemy import text

from app.db.mysql import SessionLocal
from app.db.neo4j import get_neo4j

REPO_ROOT = Path(__file__).resolve().parents[3]
GRAPH_PATH = REPO_ROOT / "exchange" / "m3" / "graph.json"
SOURCES = ("boss", "zhaopin", "liepin")


def _json_list(value: Any) -> list:
    if isinstance(value, list):
        return value
    if not value:
        return []
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, list) else []
    except (TypeError, json.JSONDecodeError):
        return []


def build_graph_data(rows: list[dict[str, Any]]) -> dict[str, list]:
    jobs = []
    skills: dict[str, dict[str, Any]] = {}
    edges = []
    related_candidates: dict[tuple[str, str], int] = defaultdict(int)
    job_skill_sets: dict[str, set[str]] = {}

    for row in rows:
        job_name = str(row.get("job_name") or "").strip()
        if not job_name:
            continue
        required = list(dict.fromkeys(str(item).lower() for item in _json_list(row.get("required_skills"))))
        bonus = list(dict.fromkeys(str(item).lower() for item in _json_list(row.get("bonus_skills"))))
        all_skills = set(required + bonus)
        job_skill_sets[job_name] = all_skills
        source = _json_list(row.get("source"))
        jobs.append({
            "id": job_name,
            "type": "job",
            "kind": "job",
            "name": job_name,
            "name_zh": job_name,
            "source": source,
            "platform": source[0] if len(source) == 1 else "多平台",
            "core_duties": str(row.get("core_duties") or ""),
            "required_skills": required,
            "bonus_skills": bonus,
            "quality": float(row.get("quality") or 0),
        })
        for skill in required + bonus:
            meta = skills.setdefault(skill, {"id": skill, "type": "skill", "kind": "skill", "name": skill, "job_count": 0})
            meta["job_count"] += 1
            edges.append({"source": job_name, "target": skill, "type": "REQUIRES", "weight": 1.0 if skill in required else 0.6, "is_required": skill in required})

    # Use an inverted index instead of all-pairs comparison. Keep only strong, useful job links.
    skill_jobs: dict[str, list[str]] = defaultdict(list)
    for job_name, skill_set in job_skill_sets.items():
        for skill in skill_set:
            skill_jobs[skill].append(job_name)
    for job_names in skill_jobs.values():
        names = sorted(set(job_names))
        for index, left in enumerate(names):
            for right in names[index + 1:index + 21]:
                related_candidates[(left, right)] += 1
    for (left, right), shared in sorted(related_candidates.items(), key=lambda item: -item[1])[:300]:
        left_skills = job_skill_sets[left]
        right_skills = job_skill_sets[right]
        union = left_skills | right_skills
        similarity = shared / len(union) if union else 0
        if similarity >= 0.35:
            edges.append({"source": left, "target": right, "type": "RELATED_TO", "similar": round(similarity, 4)})

    return {"nodes": jobs + list(skills.values()), "edges": edges}


def rebuild() -> dict[str, int]:
    db = SessionLocal()
    try:
        rows = db.execute(text("""
            SELECT job_name, core_duties, required_skills, bonus_skills, source, quality
            FROM job_definition
            WHERE source LIKE '%boss%' OR source LIKE '%zhaopin%' OR source LIKE '%liepin%'
            ORDER BY id
        """)).mappings().all()
    finally:
        db.close()
    graph = build_graph_data([dict(row) for row in rows])
    GRAPH_PATH.parent.mkdir(parents=True, exist_ok=True)
    graph["metadata"] = {
        "node_count": len(graph["nodes"]),
        "edge_count": len(graph["edges"]),
        "source": "Chinese platform jd_pool -> job_definition",
        "version": "chinese-platform-v1",
    }
    GRAPH_PATH.write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")

    driver = get_neo4j()
    try:
        with driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n").consume()
            session.run("""
                UNWIND $nodes AS node
                CALL {
                  WITH node
                  FOREACH (_ IN CASE WHEN node.type = 'job' THEN [1] ELSE [] END |
                    MERGE (j:Job {name: node.name})
                    SET j.name_zh = node.name_zh,
                        j.source = node.source,
                        j.platform = node.platform,
                        j.core_duties = node.core_duties,
                        j.required_skills = node.required_skills,
                        j.bonus_skills = node.bonus_skills,
                        j.quality = node.quality)
                  FOREACH (_ IN CASE WHEN node.type = 'skill' THEN [1] ELSE [] END |
                    MERGE (s:Skill {name: node.name})
                    SET s.job_count = node.job_count)
                } IN TRANSACTIONS OF 500 ROWS
            """, nodes=graph["nodes"]).consume()
            session.run("""
                UNWIND $edges AS edge
                WITH edge WHERE edge.type = 'REQUIRES'
                MATCH (j:Job {name: edge.source}), (s:Skill {name: edge.target})
                MERGE (j)-[r:REQUIRES]->(s)
                SET r.weight = edge.weight, r.is_required = edge.is_required
            """, edges=graph["edges"]).consume()
            session.run("""
                UNWIND $edges AS edge
                WITH edge WHERE edge.type = 'RELATED_TO'
                MATCH (a:Job {name: edge.source}), (b:Job {name: edge.target})
                MERGE (a)-[r:RELATED_TO]->(b)
                SET r.similar = edge.similar
            """, edges=graph["edges"]).consume()
            counts = session.run("""
                MATCH (n) WITH count(n) AS nodes
                OPTIONAL MATCH ()-[r]->() RETURN nodes, count(r) AS edges
            """).single()
    finally:
        driver.close()
    result = {"job_rows": len(rows), "nodes": int(counts["nodes"]), "edges": int(counts["edges"])}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


if __name__ == "__main__":
    rebuild()
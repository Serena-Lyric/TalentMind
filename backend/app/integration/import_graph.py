"""graph.json → Neo4j 导入（A 集成层，MVP）。

节点：Job（对齐 job_name）/ Skill（对齐 skill_dict.canonical）
关系：REQUIRES（weight, is_required）/ RELATED_TO（similar）
幂等：Cypher MERGE，重复执行不产生重复节点/边。
"""
import json
from pathlib import Path

from app.db.neo4j import get_neo4j

REPO_ROOT = Path(__file__).resolve().parents[3]
GRAPH_PATH = REPO_ROOT / "exchange" / "m3" / "graph.json"


def import_graph(path: Path | None = None) -> dict:
    driver = get_neo4j()
    path = path or GRAPH_PATH
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    nodes = data.get("nodes", [])
    edges = data.get("edges", [])

    with driver.session() as s:
        # 节点
        for n in nodes:
            ntype = n.get("type")
            name = n.get("name") or n.get("id")
            if not name:
                continue
            if ntype == "job":
                s.run(
                    "MERGE (j:Job {name: $name}) "
                    "SET j.core_duties = $d, j.is_emerging = $e",
                    name=name,
                    d=n.get("core_duties", ""),
                    e=bool(n.get("is_emerging", False)),
                )
            elif ntype == "skill":
                s.run("MERGE (s:Skill {name: $name})", name=name)

        # 边
        for e in edges:
            etype = e.get("type")
            source = e.get("source")
            target = e.get("target")
            if not source or not target:
                continue
            if etype == "REQUIRES":
                s.run(
                    "MATCH (j:Job {name: $s}), (sk:Skill {name: $t}) "
                    "MERGE (j)-[r:REQUIRES]->(sk) "
                    "SET r.weight = $w, r.is_required = $r",
                    s=source, t=target,
                    w=float(e.get("weight", 1.0)),
                    r=bool(e.get("is_required", True)),
                )
            elif etype == "RELATED_TO":
                s.run(
                    "MATCH (a:Job {name: $s}), (b:Job {name: $t}) "
                    "MERGE (a)-[r:RELATED_TO]->(b) SET r.similar = $sim",
                    s=source, t=target, sim=float(e.get("similar", 0.0)),
                )

        # 统计
        node_count = s.run("MATCH (n) RETURN count(n) AS c").single()["c"]
        edge_count = s.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]

    return {"nodes": node_count, "edges": edge_count}


if __name__ == "__main__":
    print(import_graph())
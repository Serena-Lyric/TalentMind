"""graph.json → Neo4j 导入。

节点使用 node_id 作为稳定键；兼容旧 graph.json 的 id/name 与 Job/Skill 节点。
"""
from __future__ import annotations

import json
from pathlib import Path

from app.db.neo4j import get_neo4j

REPO_ROOT = Path(__file__).resolve().parents[3]
GRAPH_PATH = REPO_ROOT / "exchange" / "m3" / "graph.json"


def import_graph(path: Path | None = None) -> dict:
    path = path or GRAPH_PATH
    data = json.loads(path.read_text(encoding="utf-8"))
    nodes = data.get("nodes", [])
    edges = data.get("edges", [])
    driver = get_neo4j()
    try:
        with driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n").consume()
            for node_type, label in (("job", "Job"), ("skill", "Skill"), ("industry", "Industry")):
                payload = []
                for node in nodes:
                    if str(node.get("type") or "entity").lower() != node_type:
                        continue
                    node_id = str(node.get("id") or node.get("node_id") or node.get("name") or "").strip()
                    if not node_id:
                        continue
                    props = {key: (json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else value) for key, value in node.items() if key not in {"id", "type", "kind"}}
                    props.setdefault("name", node.get("name") or node_id)
                    payload.append({"node_id": node_id, "props": props})
                if payload:
                    session.run(f"UNWIND $nodes AS node MERGE (n:{label} {{node_id: node.node_id}}) SET n += node.props", nodes=payload).consume()
            for relation in ("REQUIRES", "RELATED_TO", "APPLIES_TO"):
                payload = [{"source": str(edge.get("source") or ""), "target": str(edge.get("target") or ""), "props": {key: (json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else value) for key, value in edge.items() if key not in {"source", "target", "type"}}} for edge in edges if str(edge.get("type") or "RELATED_TO").upper() == relation and edge.get("source") and edge.get("target")]
                if payload:
                    session.run(f"UNWIND $edges AS edge MATCH (a {{node_id: edge.source}}), (b {{node_id: edge.target}}) MERGE (a)-[r:{relation}]->(b) SET r += edge.props", edges=payload).consume()
            counts = session.run("MATCH (n) WITH count(n) AS nodes OPTIONAL MATCH ()-[r]->() RETURN nodes, count(r) AS edges").single()
            return {"nodes": int(counts["nodes"]), "edges": int(counts["edges"])}
    finally:
        driver.close()


if __name__ == "__main__":
    print(import_graph())

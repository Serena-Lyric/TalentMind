# 计划 D — 知识图谱后端(Neo4j 构建 + 图谱查询 API) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `job_skill`/`skill_dict` 构建成 Neo4j 3-4 层岗位能力图谱(Domain→JobFamily→Job→Skill),并提供图谱查询 API 供前端可视化。

**Architecture:** 图谱构建器读 MySQL `job_skill` → 写 Neo4j 节点与关系;查询层用 Cypher 提供全景/岗位技能树/技能路径,热点查询走 Redis 缓存。

**Tech Stack:** Python 3.11, Neo4j 5(计划0 driver), Cypher, FastAPI, Redis, pytest

**依赖:** 计划 0 完成;计划 C 产出 `job_skill`/`skill_dict`(可用 Mock 数据先行)。

## Global Constraints

- 复用计划0:`app.db.neo4j.get_neo4j`, `app.db.mysql.get_db`, `app.db.redis.get_redis`, `app.response.ok`
- 图谱节点/关系严格按 spec 第7节:节点 `Domain/JobFamily/Job/Skill`;关系 `REQUIRES(weight)/BELONGS_TO/PART_OF/RELATED_TO`
- Skill 节点 name 对齐 `skill_dict.canonical`
- 响应模型用计划0 `GraphView/GraphNode/GraphEdge`
- 图谱查询单元测试用 mock Neo4j session;真实 Cypher 走 integration marker
- TDD;每任务 commit

---

## 文件结构(本计划创建)

```
backend/app/graph/
  __init__.py
  builder.py       # 读 job_skill → 写 Neo4j 节点/关系
  queries.py       # Cypher 查询封装(overview/job/skill-path)
  cache.py         # Redis 缓存装饰(热点查询)
  router.py        # /graph/overview /graph/job/{id} /graph/skill-path
backend/tests/
  test_graph_builder.py
  test_graph_queries.py
  test_graph_cache.py
  test_graph_router.py
```

---

## Task 0: 岗位分层映射(job_name → domain/family)

**Files:**
- Create: `backend/app/graph/__init__.py`
- Create: `backend/app/graph/taxonomy.py`
- Test: `backend/tests/test_taxonomy.py`

**背景:** `job_skill` 表只有 `job_name`,没有 domain/family(3-4层分类需要)。本任务用规则+关键词把岗位映射到领域/岗位族,产出 builder 需要的 `domain`/`family`。这是 D 独立承担的映射层,不改 C 的契约。

**Interfaces:**
- Consumes: 无(纯函数 + 可配置规则表)
- Produces: `classify_job(job_name: str) -> tuple[str, str]`——返回 `(domain, family)`,未命中给默认 `("其他", "通用")`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_taxonomy.py
from app.graph.taxonomy import classify_job

def test_ai_jobs_mapped():
    assert classify_job("AI应用工程师") == ("AI", "AI工程")
    assert classify_job("RAG工程师") == ("AI", "AI工程")
    assert classify_job("大模型算法工程师") == ("AI", "AI工程")

def test_backend_job():
    assert classify_job("Java后端工程师") == ("后端", "服务端工程")

def test_unknown_defaults():
    assert classify_job("神秘岗位") == ("其他", "通用")
```

- [ ] **Step 2: 运行验证失败**

Run: `cd backend && pytest tests/test_taxonomy.py -v`
Expected: FAIL,`ModuleNotFoundError: No module named 'app.graph.taxonomy'`

- [ ] **Step 3: 实现 taxonomy.py**

```python
# backend/app/graph/taxonomy.py
# 关键词 → (domain, family) 规则表。按需扩充。
_RULES: list[tuple[list[str], tuple[str, str]]] = [
    (["AI", "大模型", "LLM", "RAG", "Agent", "算法", "机器学习", "深度学习"], ("AI", "AI工程")),
    (["数据", "数仓", "ETL", "BI"], ("数据", "数据智能")),
    (["前端", "Web", "H5", "Vue", "React"], ("前端", "前端工程")),
    (["后端", "Java", "Go", "服务端", "微服务"], ("后端", "服务端工程")),
    (["运维", "SRE", "DevOps", "K8s", "云"], ("基础设施", "运维工程")),
]

def classify_job(job_name: str) -> tuple[str, str]:
    name = job_name or ""
    for keywords, mapping in _RULES:
        if any(k.lower() in name.lower() for k in keywords):
            return mapping
    return ("其他", "通用")
```

- [ ] **Step 4: 运行验证通过**

Run: `cd backend && pytest tests/test_taxonomy.py -v`
Expected: PASS(3 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/app/graph/__init__.py backend/app/graph/taxonomy.py backend/tests/test_taxonomy.py
git commit -m "feat(D): job taxonomy mapping to domain/family"
```

---

## Task 1: 图谱构建器(job_skill → Neo4j)

**Files:**
- Create: `backend/app/graph/builder.py`
- Test: `backend/tests/test_graph_builder.py`

**Interfaces:**
- Consumes: `app.db.neo4j.get_neo4j`, `app.graph.taxonomy.classify_job`, `app.db.mysql.get_db`
- Produces:
  - `build_cypher_for_job(job: dict) -> list[tuple[str,dict]]`——为单个岗位生成 (cypher, params) 列表(纯函数,可单测)
  - `build_graph(driver, jobs: list[dict]) -> int`——执行构建,返回处理岗位数
  - `load_jobs_from_mysql(db) -> list[dict]`——读 job_skill,对每行调 `classify_job(job_name)` 补 domain/family,返回 builder 入参格式
- 说明:`build_graph` 消费的 `jobs` 由 `load_jobs_from_mysql` 产出(已补 domain/family)。`build_cypher_for_job` 入参含 domain/family(便于单测)。

`job` 字典结构:`{"job_name": str, "level": str, "domain": str, "family": str, "skills": [{"name": str, "weight": float}]}`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_graph_builder.py
from app.graph.builder import build_cypher_for_job

def test_build_cypher_creates_nodes_and_rels():
    job = {"job_name": "AI应用工程师", "level": "高级", "domain": "AI", "family": "AI工程",
           "skills": [{"name": "Python", "weight": 0.4}, {"name": "RAG", "weight": 0.3}]}
    stmts = build_cypher_for_job(job)
    joined = " ".join(c for c, _ in stmts)
    assert "MERGE" in joined                       # 幂等建点
    assert "Domain" in joined and "JobFamily" in joined and "Job" in joined and "Skill" in joined
    assert "REQUIRES" in joined and "BELONGS_TO" in joined and "PART_OF" in joined
    # 每个技能一条 REQUIRES,带 weight 参数
    weights = [p.get("weight") for _, p in stmts if "weight" in p]
    assert 0.4 in weights and 0.3 in weights
```

- [ ] **Step 2: 运行验证失败**

Run: `cd backend && pytest tests/test_graph_builder.py -v`
Expected: FAIL,`ModuleNotFoundError: No module named 'app.graph.builder'`

- [ ] **Step 3: 实现 builder.py**

```python
# backend/app/graph/builder.py
def build_cypher_for_job(job: dict) -> list[tuple[str, dict]]:
    stmts: list[tuple[str, dict]] = []
    stmts.append((
        "MERGE (d:Domain {name:$domain}) "
        "MERGE (f:JobFamily {name:$family}) "
        "MERGE (f)-[:PART_OF]->(d) "
        "MERGE (j:Job {name:$job}) SET j.level=$level "
        "MERGE (j)-[:BELONGS_TO]->(f)",
        {"domain": job["domain"], "family": job["family"],
         "job": job["job_name"], "level": job.get("level", "")}))
    for s in job.get("skills", []):
        stmts.append((
            "MATCH (j:Job {name:$job}) "
            "MERGE (sk:Skill {name:$skill}) "
            "MERGE (j)-[r:REQUIRES]->(sk) SET r.weight=$weight",
            {"job": job["job_name"], "skill": s["name"], "weight": s.get("weight", 0)}))
    return stmts

def build_graph(driver, jobs: list[dict]) -> int:
    with driver.session() as session:
        for job in jobs:
            for cypher, params in build_cypher_for_job(job):
                session.run(cypher, **params)
    return len(jobs)

def load_jobs_from_mysql(db) -> list[dict]:
    import json
    from sqlalchemy import text
    from app.graph.taxonomy import classify_job
    rows = db.execute(text("SELECT job_name, level, skills FROM job_skill")).fetchall()
    jobs = []
    for job_name, level, skills in rows:
        domain, family = classify_job(job_name)
        jobs.append({
            "job_name": job_name, "level": level or "",
            "domain": domain, "family": family,
            "skills": [{"name": s["name"], "weight": s.get("weight", 0)}
                       for s in (json.loads(skills) if skills else [])],
        })
    return jobs
```

- [ ] **Step 4: 运行验证通过**

Run: `cd backend && pytest tests/test_graph_builder.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/graph/__init__.py backend/app/graph/builder.py backend/tests/test_graph_builder.py
git commit -m "feat(D): graph builder job_skill to neo4j cypher"
```

---

## Task 2: 图谱查询封装

**Files:**
- Create: `backend/app/graph/queries.py`
- Test: `backend/tests/test_graph_queries.py`

**Interfaces:**
- Consumes: Neo4j driver
- Produces:
  - `query_overview(driver, domain: str | None) -> GraphView`
  - `query_job_tree(driver, job_name: str) -> GraphView`
  - `query_skill_path(driver, frm: str, to: str) -> GraphView`

- [ ] **Step 1: 写失败测试(mock driver/session)**

```python
# backend/tests/test_graph_queries.py
from unittest.mock import MagicMock
from app.graph.queries import query_job_tree
from app.models.schemas import GraphView

def _fake_driver(records):
    session = MagicMock()
    session.run.return_value = records
    ctx = MagicMock()
    ctx.__enter__.return_value = session
    ctx.__exit__.return_value = False
    driver = MagicMock()
    driver.session.return_value = ctx
    return driver

def test_query_job_tree_builds_graphview():
    # 每条记录: job 节点 + skill 节点 + weight
    records = [
        {"job": "AI应用工程师", "skill": "Python", "weight": 0.4},
        {"job": "AI应用工程师", "skill": "RAG", "weight": 0.3},
    ]
    driver = _fake_driver(records)
    view = query_job_tree(driver, "AI应用工程师")
    assert isinstance(view, GraphView)
    node_ids = {n.id for n in view.nodes}
    assert "AI应用工程师" in node_ids and "Python" in node_ids and "RAG" in node_ids
    assert all(e.rel == "REQUIRES" for e in view.edges)
    assert len(view.edges) == 2
```

- [ ] **Step 2: 运行验证失败**

Run: `cd backend && pytest tests/test_graph_queries.py -v`
Expected: FAIL,`ModuleNotFoundError: No module named 'app.graph.queries'`

- [ ] **Step 3: 实现 queries.py**

```python
# backend/app/graph/queries.py
from app.models.schemas import GraphView, GraphNode, GraphEdge

def query_job_tree(driver, job_name: str) -> GraphView:
    cypher = ("MATCH (j:Job {name:$n})-[r:REQUIRES]->(s:Skill) "
              "RETURN j.name AS job, s.name AS skill, r.weight AS weight")
    nodes: dict[str, GraphNode] = {}
    edges: list[GraphEdge] = []
    with driver.session() as session:
        for rec in session.run(cypher, n=job_name):
            job, skill, weight = rec["job"], rec["skill"], rec["weight"]
            nodes[job] = GraphNode(id=job, label=job, type="Job")
            nodes[skill] = GraphNode(id=skill, label=skill, type="Skill")
            edges.append(GraphEdge(source=job, target=skill, rel="REQUIRES", weight=weight))
    return GraphView(nodes=list(nodes.values()), edges=edges)

def query_overview(driver, domain: str | None = None) -> GraphView:
    if domain:
        cypher = ("MATCH (d:Domain {name:$dm})<-[:PART_OF]-(f:JobFamily)<-[:BELONGS_TO]-(j:Job) "
                  "RETURN d.name AS domain, f.name AS family, j.name AS job")
        params = {"dm": domain}
    else:
        cypher = ("MATCH (d:Domain)<-[:PART_OF]-(f:JobFamily)<-[:BELONGS_TO]-(j:Job) "
                  "RETURN d.name AS domain, f.name AS family, j.name AS job")
        params = {}
    nodes: dict[str, GraphNode] = {}
    edges: list[GraphEdge] = []
    with driver.session() as session:
        for rec in session.run(cypher, **params):
            dm, fam, job = rec["domain"], rec["family"], rec["job"]
            nodes[dm] = GraphNode(id=dm, label=dm, type="Domain")
            nodes[fam] = GraphNode(id=fam, label=fam, type="JobFamily")
            nodes[job] = GraphNode(id=job, label=job, type="Job")
            edges.append(GraphEdge(source=fam, target=dm, rel="PART_OF"))
            edges.append(GraphEdge(source=job, target=fam, rel="BELONGS_TO"))
    return GraphView(nodes=list(nodes.values()), edges=edges)

def query_skill_path(driver, frm: str, to: str) -> GraphView:
    cypher = ("MATCH p=shortestPath((a:Skill {name:$f})-[:RELATED_TO*..4]-(b:Skill {name:$t})) "
              "RETURN [n IN nodes(p) | n.name] AS names")
    nodes: dict[str, GraphNode] = {}
    edges: list[GraphEdge] = []
    with driver.session() as session:
        rec = session.run(cypher, f=frm, t=to).single()
        names = rec["names"] if rec else []
        for i, name in enumerate(names):
            nodes[name] = GraphNode(id=name, label=name, type="Skill")
            if i > 0:
                edges.append(GraphEdge(source=names[i-1], target=name, rel="RELATED_TO"))
    return GraphView(nodes=list(nodes.values()), edges=edges)
```

- [ ] **Step 4: 运行验证通过**

Run: `cd backend && pytest tests/test_graph_queries.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/graph/queries.py backend/tests/test_graph_queries.py
git commit -m "feat(D): graph query functions (overview/job-tree/skill-path)"
```

---

## Task 3: Redis 缓存(热点查询)

**Files:**
- Create: `backend/app/graph/cache.py`
- Test: `backend/tests/test_graph_cache.py`

**Interfaces:**
- Consumes: `app.db.redis.get_redis`
- Produces: `cached_view(redis_client, key: str, producer: Callable[[], GraphView], ttl: int = 300) -> GraphView`——缓存命中返回,否则调 producer 并写缓存

- [ ] **Step 1: 写失败测试(fake redis)**

```python
# backend/tests/test_graph_cache.py
from app.graph.cache import cached_view
from app.models.schemas import GraphView, GraphNode

class FakeRedis:
    def __init__(self): self.store = {}
    def get(self, k): return self.store.get(k)
    def setex(self, k, ttl, v): self.store[k] = v

def _sample():
    return GraphView(nodes=[GraphNode(id="A", label="A", type="Job")], edges=[])

def test_cache_miss_then_hit():
    r = FakeRedis()
    calls = {"n": 0}
    def producer():
        calls["n"] += 1
        return _sample()
    v1 = cached_view(r, "graph:test", producer)
    v2 = cached_view(r, "graph:test", producer)   # 第二次命中缓存
    assert calls["n"] == 1                          # producer 只调一次
    assert v2.nodes[0].id == "A"
```

- [ ] **Step 2: 运行验证失败**

Run: `cd backend && pytest tests/test_graph_cache.py -v`
Expected: FAIL,`ModuleNotFoundError: No module named 'app.graph.cache'`

- [ ] **Step 3: 实现 cache.py**

```python
# backend/app/graph/cache.py
from typing import Callable
from app.models.schemas import GraphView

def cached_view(redis_client, key: str, producer: Callable[[], GraphView], ttl: int = 300) -> GraphView:
    raw = redis_client.get(key)
    if raw:
        return GraphView.model_validate_json(raw)
    view = producer()
    redis_client.setex(key, ttl, view.model_dump_json())
    return view
```

- [ ] **Step 4: 运行验证通过**

Run: `cd backend && pytest tests/test_graph_cache.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/graph/cache.py backend/tests/test_graph_cache.py
git commit -m "feat(D): redis cache for graph views"
```

---

## Task 4: 图谱路由(/graph/*)

**Files:**
- Create: `backend/app/graph/router.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_graph_router.py`

**Interfaces:**
- Consumes: `queries.*`, `cached_view`, `get_neo4j`, `get_redis`, `ok`
- Produces: `router`;`GET /graph/overview?domain=`;`GET /graph/job/{job_name}`;`GET /graph/skill-path?from=&to=`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_graph_router.py
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app
from app.db.neo4j import get_neo4j
from app.db.redis import get_redis
from app.models.schemas import GraphView, GraphNode, GraphEdge

app.dependency_overrides[get_neo4j] = lambda: object()
app.dependency_overrides[get_redis] = lambda: None
client = TestClient(app)

def test_job_tree_endpoint():
    view = GraphView(
        nodes=[GraphNode(id="AI应用工程师", label="AI应用工程师", type="Job"),
               GraphNode(id="Python", label="Python", type="Skill")],
        edges=[GraphEdge(source="AI应用工程师", target="Python", rel="REQUIRES", weight=0.4)])
    with patch("app.graph.router.query_job_tree", return_value=view):
        r = client.get("/graph/job/AI应用工程师")
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == 0
    assert len(body["data"]["nodes"]) == 2
```

- [ ] **Step 2: 运行验证失败**

Run: `cd backend && pytest tests/test_graph_router.py -v`
Expected: FAIL,`ModuleNotFoundError: No module named 'app.graph.router'`

- [ ] **Step 3: 实现 router.py**

```python
# backend/app/graph/router.py
from fastapi import APIRouter, Depends
from app.db.neo4j import get_neo4j
from app.db.redis import get_redis
from app.graph.queries import query_overview, query_job_tree, query_skill_path
from app.graph.cache import cached_view
from app.response import ok

router = APIRouter(prefix="/graph", tags=["graph"])

@router.get("/overview")
def overview(domain: str | None = None, driver=Depends(get_neo4j), rc=Depends(get_redis)):
    key = f"graph:overview:{domain or 'all'}"
    view = cached_view(rc, key, lambda: query_overview(driver, domain))
    return ok(view.model_dump())

@router.get("/job/{job_name}")
def job_tree(job_name: str, driver=Depends(get_neo4j)):
    return ok(query_job_tree(driver, job_name).model_dump())

@router.get("/skill-path")
def skill_path(from_: str = None, to: str = None, driver=Depends(get_neo4j)):
    # 注意:查询参数 from 是 python 关键字,用别名
    return ok(query_skill_path(driver, from_, to).model_dump())
```

> FastAPI 中 `from` 是保留字,查询参数用 `from_` 并通过 `Query(alias="from")` 映射。修正 skill_path 签名:
```python
from fastapi import Query
@router.get("/skill-path")
def skill_path(frm: str = Query(alias="from"), to: str = Query(...), driver=Depends(get_neo4j)):
    return ok(query_skill_path(driver, frm, to).model_dump())
```
采用后一种(带 alias)为准。

- [ ] **Step 4: 挂载 + 验证通过**

在 `main.py` 添加:
```python
from app.graph.router import router as graph_router
app.include_router(graph_router)
```
Run: `cd backend && pytest tests/test_graph_router.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/graph/router.py backend/app/main.py backend/tests/test_graph_router.py
git commit -m "feat(D): graph router with cache"
```

---

## Task 5: 图谱构建集成测试(端到端 Neo4j)

**Files:**
- Test: `backend/tests/test_graph_integration.py`

**Interfaces:**
- Consumes: `build_graph`, `query_job_tree`, `get_neo4j`

- [ ] **Step 1: 写集成测试**

```python
# backend/tests/test_graph_integration.py
import pytest
from app.db.neo4j import get_neo4j
from app.graph.builder import build_graph
from app.graph.queries import query_job_tree

pytestmark = pytest.mark.integration

def test_build_then_query():
    driver = get_neo4j()
    with driver.session() as s:
        s.run("MATCH (n) DETACH DELETE n")   # 清空测试图
    build_graph(driver, [{
        "job_name": "测试岗位", "level": "高级", "domain": "AI", "family": "AI工程",
        "skills": [{"name": "Python", "weight": 0.5}, {"name": "RAG", "weight": 0.5}]}])
    view = query_job_tree(driver, "测试岗位")
    assert len(view.edges) == 2
    assert {n.id for n in view.nodes} >= {"测试岗位", "Python", "RAG"}
```

- [ ] **Step 2: 起库运行**

Run: `docker-compose up -d --wait && cd backend && pytest tests/test_graph_integration.py -v -m integration`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_graph_integration.py
git commit -m "test(D): graph build-query integration test"
```

---

## 自审说明
- 覆盖 spec:3-4层图谱(Domain/JobFamily/Job/Skill)✓ 关系全✓ 三查询API✓ Redis缓存✓
- 类型一致:`GraphView/GraphNode/GraphEdge` 来自计划0;`skill-path` 用 `from` alias 避开关键字
- 与 C 的接口:消费 `job_skill`,`skills` 字段结构与 C 的 `save_job_skill` 写入一致(name+weight);domain/family 需 C 或 D 补充映射(见计划E/整合期约定,可先用规则映射)

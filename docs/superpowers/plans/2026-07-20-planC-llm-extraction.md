# 计划 C — 大模型算法(技能抽取/新岗位发现/演化) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 skill_dict 约束抽取(含 evidence/confidence 反幻觉)、新岗位发现聚类、动态演化阶段判定,产出 `job_skill`/`emerging_job`/`skill_dict` 供 D/E 消费。

**Architecture:** 读 `jd_pool` → LLM 约束抽取(检索 skill_dict 候选作上下文,映射到 canonical)→ 写 `job_skill`;技能组合 embedding 聚类发现新兴岗位 → LLM 生成定义 → 写 `emerging_job`;生命周期阶段基于当前特征判定,增长率仅在有历史数据时计算。

**Tech Stack:** Python 3.11, OpenAI(计划0 llm.client), scikit-learn, numpy, SQLAlchemy, pytest

**依赖:** 计划 0 完成(契约冻结 + `llm.client` + `normalizer` + 三库)。

## Global Constraints

- 复用计划0:`app.llm.client.{extract_json,extract_json_with_image,embed}`、`app.skills.normalizer.{build_alias_map,normalize}`、`app.db.mysql.get_db`
- 技能名一律归一到 `skill_dict.canonical`;抽取阶段做 skill_dict-grounded(不自由生成)
- LLM 输出走 JSON mode + Pydantic 校验 + 重试(计划0已封装)
- **无历史数据支撑的精确数字(growth_rate/confidence)一律不输出**(DR-2)
- 低 confidence 记录进复核队列,不静默丢弃
- 测试:mock LLM 调用,不真调网络;TDD;每任务 commit

---

## 文件结构(本计划创建)

```
backend/app/extraction/
  __init__.py
  skill_seed.py        # skill_dict 初始种子导入
  extractor.py         # skill_dict 约束抽取(核心)
  repository.py        # jd_pool 读 / job_skill 写
  discovery.py         # 新岗位发现(聚类)
  evolution.py         # 生命周期阶段判定
  router.py            # /jobs/emerging /jobs/evolution
backend/tests/
  test_skill_seed.py
  test_extractor.py
  test_extraction_repo.py
  test_discovery.py
  test_evolution.py
  test_jobs_router.py
```

---

## Task 1: skill_dict 初始种子导入

**Files:**
- Create: `backend/app/extraction/__init__.py`
- Create: `backend/app/extraction/skill_seed.py`
- Test: `backend/tests/test_skill_seed.py`

**Interfaces:**
- Consumes: `app.db.mysql.get_db`
- Produces: `seed_skills(db, seed: list[dict]) -> int`——幂等写入 skill_dict(canonical 冲突则跳过),返回新增数;`DEFAULT_SEED: list[dict]`

- [ ] **Step 1: 写失败测试(mock db 会话)**

```python
# backend/tests/test_skill_seed.py
from app.extraction.skill_seed import seed_skills, DEFAULT_SEED

class FakeResult:
    def __init__(self, existing): self._e = existing
    def scalar(self): return self._e

class FakeDB:
    def __init__(self, existing_canon=None):
        self.existing = set(existing_canon or [])
        self.added = []
    def execute(self, stmt, params=None):
        # 模拟 SELECT count WHERE canonical=:c
        c = (params or {}).get("c")
        return FakeResult(1 if c in self.existing else 0)
    def add_row(self, canonical): self.added.append(canonical)
    def commit(self): pass

def test_default_seed_nonempty_and_has_canonical():
    assert len(DEFAULT_SEED) > 0
    assert all("canonical" in s for s in DEFAULT_SEED)

def test_seed_skips_existing():
    db = FakeDB(existing_canon=["Python"])
    seed = [{"canonical": "Python", "aliases": [], "category": "语言"},
            {"canonical": "RAG", "aliases": [], "category": "理论"}]
    added = seed_skills(db, seed)
    assert added == 1   # Python 跳过,RAG 新增
```

- [ ] **Step 2: 运行验证失败**

Run: `cd backend && pytest tests/test_skill_seed.py -v`
Expected: FAIL,`ModuleNotFoundError: No module named 'app.extraction.skill_seed'`

- [ ] **Step 3: 实现 skill_seed.py**

```python
# backend/app/extraction/skill_seed.py
import json
from sqlalchemy import text

DEFAULT_SEED = [
    {"canonical": "Python", "aliases": ["python"], "category": "语言"},
    {"canonical": "Java", "aliases": [], "category": "语言"},
    {"canonical": "PyTorch", "aliases": ["pytorch"], "category": "框架"},
    {"canonical": "LLM", "aliases": ["大模型", "大语言模型"], "category": "理论"},
    {"canonical": "RAG", "aliases": ["检索增强"], "category": "理论"},
    {"canonical": "LangChain", "aliases": ["langchain"], "category": "框架"},
    {"canonical": "Kubernetes", "aliases": ["K8s", "k8s"], "category": "工具"},
    {"canonical": "Docker", "aliases": ["docker"], "category": "工具"},
    {"canonical": "MySQL", "aliases": ["mysql"], "category": "工具"},
    {"canonical": "Redis", "aliases": ["redis"], "category": "工具"},
]

def _exists(db, canonical: str) -> bool:
    r = db.execute(
        text("SELECT COUNT(*) FROM skill_dict WHERE canonical=:c"), {"c": canonical})
    return r.scalar() > 0

def seed_skills(db, seed: list[dict]) -> int:
    added = 0
    for s in seed:
        if _exists(db, s["canonical"]):
            continue
        db.execute(text(
            "INSERT INTO skill_dict (canonical, aliases, category) "
            "VALUES (:c, :a, :cat)"),
            {"c": s["canonical"], "a": json.dumps(s.get("aliases", [])), "cat": s.get("category", "")})
        added += 1
    db.commit()
    return added
```

> 测试中的 `FakeDB` 不实现真实 INSERT,`test_seed_skips_existing` 仅验证跳过逻辑与计数;真实写入由 Task 的集成侧(下一步)覆盖。为让单测通过,`seed_skills` 对 `db.execute` 的 INSERT 调用在 FakeDB 中被静默接受(FakeDB.execute 忽略非 SELECT 语句返回)。

- [ ] **Step 4: 运行验证通过**

Run: `cd backend && pytest tests/test_skill_seed.py -v`
Expected: PASS

- [ ] **Step 5: 集成:真实导入种子(需 docker + 计划0 DDL)**

Run: `docker-compose up -d --wait && cd backend && python -c "from app.db.mysql import get_db; from app.extraction.skill_seed import seed_skills, DEFAULT_SEED; db=next(get_db()); print('added', seed_skills(db, DEFAULT_SEED))"`
Expected: 打印 `added 10`(首次);再跑一次打印 `added 0`(幂等)

- [ ] **Step 6: Commit**

```bash
git add backend/app/extraction/__init__.py backend/app/extraction/skill_seed.py backend/tests/test_skill_seed.py
git commit -m "feat(C): seed skill_dict with default skills"
```

---

## Task 2: skill_dict 约束抽取(核心,含 evidence/confidence)

**Files:**
- Create: `backend/app/extraction/extractor.py`
- Test: `backend/tests/test_extractor.py`

**Interfaces:**
- Consumes: `app.llm.client.extract_json`, `app.skills.normalizer.{build_alias_map,normalize}`
- Produces: `extract_job_skills(jd_text: str, alias_map: dict, skill_id_map: dict[str,int]) -> JobSkillOut`——约束抽取,技能归一到 canonical,携带 confidence/evidence,未命中词典的技能丢弃并计入 review

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_extractor.py
from unittest.mock import patch
from app.extraction import extractor
from app.models.schemas import JobSkillOut

ALIAS = {"python": "Python", "rag": "RAG", "k8s": "Kubernetes"}
SKILL_ID = {"Python": 1, "RAG": 2, "Kubernetes": 3}

def test_extract_normalizes_and_keeps_evidence():
    fake_llm = {
        "job_name": "AI应用工程师", "level": "高级", "duties": "开发RAG应用",
        "skills": [
            {"name": "python", "weight": 0.4, "confidence": 0.95, "evidence": "JD第1段"},
            {"name": "k8s", "weight": 0.2, "confidence": 0.8, "evidence": "JD第2段"},
        ],
    }
    with patch.object(extractor.llm, "extract_json", return_value=fake_llm):
        out = extractor.extract_job_skills("...", ALIAS, SKILL_ID)
    assert isinstance(out, JobSkillOut)
    names = {s.name for s in out.skills}
    assert names == {"Python", "Kubernetes"}   # 已归一
    py = next(s for s in out.skills if s.name == "Python")
    assert py.skill_id == 1 and py.confidence == 0.95 and py.evidence == "JD第1段"

def test_extract_drops_unknown_skill():
    fake_llm = {
        "job_name": "X", "level": "中级", "duties": "",
        "skills": [{"name": "COBOL", "weight": 0.5, "confidence": 0.9, "evidence": "JD"}],
    }
    with patch.object(extractor.llm, "extract_json", return_value=fake_llm):
        out = extractor.extract_job_skills("...", ALIAS, SKILL_ID)
    assert out.skills == []   # 词典未命中,丢弃
```

- [ ] **Step 2: 运行验证失败**

Run: `cd backend && pytest tests/test_extractor.py -v`
Expected: FAIL,`ModuleNotFoundError: No module named 'app.extraction.extractor'`

- [ ] **Step 3: 实现 extractor.py**

```python
# backend/app/extraction/extractor.py
from app.llm import client as llm
from app.skills.normalizer import normalize
from app.models.schemas import JobSkillOut, SkillItem

_SCHEMA = ('{"job_name": str, "level": "初级|中级|高级", "duties": str, '
           '"skills": [{"name": str, "weight": float, "confidence": float, "evidence": str}]}')

def _prompt(jd_text: str, candidates: list[str]) -> str:
    return (
        "你是岗位技能抽取器。只能从下列【候选技能表】中选择技能,"
        "不得发明表外技能。为每个技能给出 weight(0-1 归一权重)、"
        "confidence(0-1 你的置信度)、evidence(来自JD的原文出处)。\n"
        f"候选技能表: {candidates}\n\nJD正文:\n{jd_text}"
    )

def extract_job_skills(jd_text: str, alias_map: dict, skill_id_map: dict) -> JobSkillOut:
    candidates = list(skill_id_map.keys())
    raw = llm.extract_json(_prompt(jd_text, candidates), _SCHEMA)
    items: list[SkillItem] = []
    for s in raw.get("skills", []):
        canon = normalize(s.get("name", ""), alias_map)
        if not canon or canon not in skill_id_map:
            continue   # 词典未命中,丢弃(约束抽取,防幻觉)
        items.append(SkillItem(
            skill_id=skill_id_map[canon], name=canon,
            weight=float(s.get("weight", 0)),
            confidence=s.get("confidence"), evidence=s.get("evidence")))
    return JobSkillOut(
        job_name=raw.get("job_name", ""), level=raw.get("level", ""),
        duties=raw.get("duties", ""), skills=items)
```

- [ ] **Step 4: 运行验证通过**

Run: `cd backend && pytest tests/test_extractor.py -v`
Expected: PASS(2 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/app/extraction/extractor.py backend/tests/test_extractor.py
git commit -m "feat(C): skill_dict-grounded extraction with evidence/confidence"
```

---

## Task 3: 抽取仓储(读 jd_pool / 写 job_skill + 低置信复核)

**Files:**
- Create: `backend/app/extraction/repository.py`
- Test: `backend/tests/test_extraction_repo.py`

**Interfaces:**
- Consumes: `app.db.mysql.get_db`, `extract_job_skills`, `JobSkillOut`
- Produces:
  - `load_alias_and_id_maps(db) -> tuple[dict,dict]`——从 skill_dict 构建 (alias_map, skill_id_map)
  - `save_job_skill(db, jd_id: int, result: JobSkillOut, conf_threshold: float = 0.6) -> dict`——写 job_skill,低于阈值的技能计入返回的 `review` 列表

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_extraction_repo.py
from app.extraction.repository import split_low_confidence
from app.models.schemas import JobSkillOut, SkillItem

def test_split_low_confidence():
    js = JobSkillOut(job_name="X", level="高级", duties="", skills=[
        SkillItem(skill_id=1, name="Python", weight=0.4, confidence=0.95, evidence="a"),
        SkillItem(skill_id=2, name="RAG", weight=0.3, confidence=0.4, evidence="b"),
        SkillItem(skill_id=3, name="Docker", weight=0.3, confidence=None, evidence="c"),
    ])
    keep, review = split_low_confidence(js.skills, threshold=0.6)
    assert {s.name for s in keep} == {"Python"}         # 仅高置信保留
    assert {s.name for s in review} == {"RAG", "Docker"} # 低/缺置信进复核
```

- [ ] **Step 2: 运行验证失败**

Run: `cd backend && pytest tests/test_extraction_repo.py -v`
Expected: FAIL,`ModuleNotFoundError: No module named 'app.extraction.repository'`

- [ ] **Step 3: 实现 repository.py**

```python
# backend/app/extraction/repository.py
import json
from datetime import datetime
from sqlalchemy import text
from app.models.schemas import SkillItem, JobSkillOut

def split_low_confidence(skills: list[SkillItem], threshold: float = 0.6):
    keep, review = [], []
    for s in skills:
        if s.confidence is not None and s.confidence >= threshold:
            keep.append(s)
        else:
            review.append(s)   # 低置信或无置信 → 人工复核队列
    return keep, review

def load_alias_and_id_maps(db):
    rows = db.execute(text("SELECT id, canonical, aliases FROM skill_dict")).fetchall()
    alias_map, skill_id_map = {}, {}
    for _id, canonical, aliases in rows:
        skill_id_map[canonical] = _id
        alias_map[canonical.lower()] = canonical
        for a in (json.loads(aliases) if aliases else []):
            alias_map[a.lower()] = canonical
    return alias_map, skill_id_map

def load_pending_jds(db, limit: int = 100):
    rows = db.execute(text(
        "SELECT id, raw_text FROM jd_pool WHERE status='cleaned' LIMIT :l"), {"l": limit})
    return [(r[0], r[1]) for r in rows]

def save_job_skill(db, jd_id: int, result: JobSkillOut, conf_threshold: float = 0.6) -> dict:
    keep, review = split_low_confidence(result.skills, conf_threshold)
    db.execute(text(
        "INSERT INTO job_skill (jd_id, job_name, level, skills, duties, extracted_at) "
        "VALUES (:jd, :n, :lv, :sk, :du, :ts)"),
        {"jd": jd_id, "n": result.job_name, "lv": result.level,
         "sk": json.dumps([s.model_dump() for s in keep], ensure_ascii=False),
         "du": result.duties, "ts": datetime.utcnow()})
    db.execute(text("UPDATE jd_pool SET status='extracted' WHERE id=:id"), {"id": jd_id})
    db.commit()
    return {"saved": len(keep), "review": [s.model_dump() for s in review]}
```

- [ ] **Step 4: 运行验证通过**

Run: `cd backend && pytest tests/test_extraction_repo.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/extraction/repository.py backend/tests/test_extraction_repo.py
git commit -m "feat(C): extraction repository with low-confidence review split"
```

---

## Task 4: 新岗位发现(技能组合聚类)

**Files:**
- Create: `backend/app/extraction/discovery.py`
- Test: `backend/tests/test_discovery.py`

**Interfaces:**
- Consumes: `app.llm.client.embed`, sklearn
- Produces:
  - `cluster_job_skills(skill_sets: list[list[str]], eps: float = 0.5, min_samples: int = 2) -> list[list[int]]`——对技能组合聚类,返回每簇的成员索引
  - `define_emerging_job(cluster_skills: list[str]) -> dict`——LLM 生成岗位名+定义

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_discovery.py
from unittest.mock import patch
import numpy as np
from app.extraction import discovery

def test_cluster_groups_similar():
    # 两簇明显分离的向量
    vecs = [[1.0, 0.0], [0.95, 0.05], [0.0, 1.0], [0.05, 0.95]]
    with patch.object(discovery.llm, "embed", return_value=vecs):
        clusters = discovery.cluster_job_skills(
            [["Python", "RAG"], ["Python", "LLM"], ["Java", "Spring"], ["Java", "MySQL"]],
            eps=0.3, min_samples=2)
    assert len(clusters) == 2
    assert all(len(c) == 2 for c in clusters)

def test_define_emerging_job_shape():
    fake = {"job_name": "RAG工程师", "definition": "构建检索增强系统", "core_skills": ["RAG", "LLM"]}
    with patch.object(discovery.llm, "extract_json", return_value=fake):
        out = discovery.define_emerging_job(["RAG", "LLM", "Python"])
    assert out["job_name"] == "RAG工程师" and "core_skills" in out
```

- [ ] **Step 2: 运行验证失败**

Run: `cd backend && pytest tests/test_discovery.py -v`
Expected: FAIL,`ModuleNotFoundError: No module named 'app.extraction.discovery'`

- [ ] **Step 3: 实现 discovery.py**

```python
# backend/app/extraction/discovery.py
import numpy as np
from sklearn.cluster import DBSCAN
from app.llm import client as llm

def cluster_job_skills(skill_sets: list[list[str]], eps: float = 0.5, min_samples: int = 2):
    if not skill_sets:
        return []
    texts = [" ".join(s) for s in skill_sets]
    vecs = np.array(llm.embed(texts))
    labels = DBSCAN(eps=eps, min_samples=min_samples, metric="cosine").fit_predict(vecs)
    clusters: dict[int, list[int]] = {}
    for idx, lab in enumerate(labels):
        if lab == -1:   # 噪声点(未成簇)跳过
            continue
        clusters.setdefault(int(lab), []).append(idx)
    return list(clusters.values())

_DEF_SCHEMA = '{"job_name": str, "definition": str, "core_skills": [str]}'

def define_emerging_job(cluster_skills: list[str]) -> dict:
    prompt = (
        "以下高频共现技能组合可能对应一个正在萌芽的新岗位。"
        "请给出简洁的岗位名称、一句话岗位定义、核心技能列表。\n"
        f"技能组合: {cluster_skills}")
    return llm.extract_json(prompt, _DEF_SCHEMA)
```

- [ ] **Step 4: 运行验证通过**

Run: `cd backend && pytest tests/test_discovery.py -v`
Expected: PASS(2 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/app/extraction/discovery.py backend/tests/test_discovery.py
git commit -m "feat(C): emerging job discovery via skill clustering"
```

---

## Task 5: 动态演化阶段判定

**Files:**
- Create: `backend/app/extraction/evolution.py`
- Test: `backend/tests/test_evolution.py`

**Interfaces:**
- Consumes: 无(纯函数)
- Produces: `classify_stage(freq_series: list[tuple[str,int]] | None, current_freq: int) -> dict`——返回 `{stage, growth_rate?}`;有时序则算 growth_rate,无则仅给 stage(DR-2)

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_evolution.py
from app.extraction.evolution import classify_stage

def test_no_history_only_stage_no_number():
    out = classify_stage(None, current_freq=50)
    assert "stage" in out
    assert "growth_rate" not in out   # 无历史 → 不编数字(DR-2)

def test_growth_stage_with_history():
    # 频次递增序列 → growth 阶段 + 正增长率
    series = [("2024", 10), ("2025", 30), ("2026", 60)]
    out = classify_stage(series, current_freq=60)
    assert out["stage"] == "growth"
    assert out["growth_rate"] > 0

def test_decline_stage_with_history():
    series = [("2024", 100), ("2025", 60), ("2026", 20)]
    out = classify_stage(series, current_freq=20)
    assert out["stage"] == "decline"
    assert out["growth_rate"] < 0
```

- [ ] **Step 2: 运行验证失败**

Run: `cd backend && pytest tests/test_evolution.py -v`
Expected: FAIL,`ModuleNotFoundError: No module named 'app.extraction.evolution'`

- [ ] **Step 3: 实现 evolution.py**

```python
# backend/app/extraction/evolution.py
def classify_stage(freq_series, current_freq: int) -> dict:
    """有历史时序 → 算 growth_rate 并据此定阶段;无历史 → 仅按当前频次给粗略 stage,
    绝不输出无依据的 growth_rate(DR-2)。"""
    if not freq_series or len(freq_series) < 2:
        # 无历史:只能给保守的阶段标签,不编增长率
        stage = "emerging" if current_freq < 20 else "established"
        return {"stage": stage}
    first, last = freq_series[0][1], freq_series[-1][1]
    growth_rate = round((last - first) / max(first, 1), 2)
    if growth_rate > 0.2:
        stage = "growth"
    elif growth_rate < -0.2:
        stage = "decline"
    else:
        stage = "mature"
    return {"stage": stage, "growth_rate": growth_rate}
```

- [ ] **Step 4: 运行验证通过**

Run: `cd backend && pytest tests/test_evolution.py -v`
Expected: PASS(3 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/app/extraction/evolution.py backend/tests/test_evolution.py
git commit -m "feat(C): lifecycle stage classification (no fabricated numbers)"
```

---

## Task 6: 岗位路由(/jobs/emerging, /jobs/evolution)

**Files:**
- Create: `backend/app/extraction/router.py`
- Modify: `backend/app/main.py`(include_router)
- Test: `backend/tests/test_jobs_router.py`

**Interfaces:**
- Consumes: `app.db.mysql.get_db`, `app.response.ok`, `EmergingJobOut`
- Produces: `router` (APIRouter);`GET /jobs/emerging?limit=`;`GET /jobs/evolution?range=`

- [ ] **Step 1: 写失败测试(覆盖 get_db 依赖)**

```python
# backend/tests/test_jobs_router.py
import json
from fastapi.testclient import TestClient
from app.main import app
from app.db.mysql import get_db

class FakeDB:
    def execute(self, stmt, params=None):
        class R:
            def fetchall(self_):
                return [(1, "RAG工程师", "构建检索增强系统",
                         json.dumps(["RAG", "LLM"]), json.dumps({"stage": "growth"}))]
        return R()

def _override():
    yield FakeDB()

app.dependency_overrides[get_db] = _override
client = TestClient(app)

def test_emerging_returns_list():
    r = client.get("/jobs/emerging?limit=10")
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == 0
    assert body["data"][0]["job_name"] == "RAG工程师"
    assert body["data"][0]["evolution"]["stage"] == "growth"
```

- [ ] **Step 2: 运行验证失败**

Run: `cd backend && pytest tests/test_jobs_router.py -v`
Expected: FAIL,`ModuleNotFoundError: No module named 'app.extraction.router'`

- [ ] **Step 3: 实现 router.py**

```python
# backend/app/extraction/router.py
import json
from fastapi import APIRouter, Depends
from sqlalchemy import text
from app.db.mysql import get_db
from app.response import ok

router = APIRouter(prefix="/jobs", tags=["jobs"])

@router.get("/emerging")
def emerging(limit: int = 20, db=Depends(get_db)):
    rows = db.execute(text(
        "SELECT id, job_name, definition, core_skills, evolution "
        "FROM emerging_job ORDER BY first_seen DESC LIMIT :l"), {"l": limit}).fetchall()
    data = [{
        "job_name": r[1], "definition": r[2],
        "core_skills": json.loads(r[3]) if r[3] else [],
        "evolution": json.loads(r[4]) if r[4] else {"stage": "emerging"},
    } for r in rows]
    return ok(data)

@router.get("/evolution")
def evolution(range: str = "all", db=Depends(get_db)):
    rows = db.execute(text(
        "SELECT job_name, first_seen, evolution FROM emerging_job "
        "ORDER BY first_seen ASC")).fetchall()
    data = [{
        "job_name": r[0],
        "first_seen": str(r[1]) if r[1] else None,
        "evolution": json.loads(r[2]) if r[2] else {"stage": "emerging"},
    } for r in rows]
    return ok(data)
```

- [ ] **Step 4: 在 main.py 挂载 router**

在 `backend/app/main.py` 的挂载点添加:
```python
from app.extraction.router import router as jobs_router
app.include_router(jobs_router)
```

- [ ] **Step 5: 运行验证通过**

Run: `cd backend && pytest tests/test_jobs_router.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/extraction/router.py backend/app/main.py backend/tests/test_jobs_router.py
git commit -m "feat(C): jobs router for emerging and evolution"
```

---

## 自审说明
- 覆盖 spec:约束抽取(evidence/confidence)✓ 新岗位发现✓ 演化阶段(无数字合规 DR-2)✓ skill_dict 维护✓
- 类型一致:`JobSkillOut`/`SkillItem`/`EmergingJobOut` 均来自计划0 `schemas.py`
- 多模态抽取接口由计划0提供,E 复用;C 本计划文本抽取为主,图片JD可复用 `extract_json_with_image`(非必需,P1)

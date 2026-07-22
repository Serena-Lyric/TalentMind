# 计划 A — 数据采集(多源爬取 + 清洗去重交叉验证) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 多源采集招聘/技术生态/社区数据,清洗、交叉验证去重、标签化,写入 `jd_pool`(+ `signal` P1),为下游解锁数据。

**Architecture:** 采集器按源分模块(统一 fetch 接口)→ 清洗管道(去HTML/正文提取/字段规整)→ 交叉验证去重(多源比对+质量分)→ 写 `jd_pool`;前期用公开数据集填充 `jd_pool` 解锁下游。

**Tech Stack:** Python 3.11, httpx, Playwright, BeautifulSoup, 代理池, APScheduler, SQLAlchemy, pytest

**依赖:** 计划 0(`jd_pool` 表、`get_db`)。可独立于 C/D/E 并行。

## Global Constraints

- 复用计划0:`app.db.mysql.get_db`,`jd_pool`/`signal` 表契约
- 采集:代理池 + 随机延迟 + 断点续爬;不堆多线程高频(反爬)
- 优先级:GitHub/牛客/博客(反爬弱)先爬满,Boss/猎聘/智联量力而行
- **两阶段**:阶段1 公开数据集填充 `jd_pool` 解锁下游;阶段2 真实爬取逐步替换
- `signal` 表(技术热度/社区)为 P1,不阻塞 P0
- 输出统一 `jd_pool` schema,下游只认数据池不认来源
- 网络请求用 mock 单测;真实爬取脚本手动/定时跑;TDD;每任务 commit

---

## 文件结构(本计划创建)

```
backend/app/collect/
  __init__.py
  schema.py         # 采集统一中间结构 RawJD
  cleaner.py        # 清洗:去HTML/正文提取/字段规整
  dedup.py          # 交叉验证去重 + 质量分
  fetchers/
    __init__.py
    base.py         # Fetcher 抽象 + 代理/延迟/断点
    github.py       # GitHub Trending 采集(反爬弱,先做)
    dataset.py      # 阶段1:公开数据集导入
  repository.py     # 写 jd_pool
  pipeline.py       # 编排:fetch→clean→dedup→save
backend/tests/
  test_cleaner.py
  test_dedup.py
  test_dataset_import.py
  test_collect_repo.py
  test_pipeline.py
```

---

## Task 1: 采集中间结构 + 清洗

**Files:**
- Create: `backend/app/collect/__init__.py`
- Create: `backend/app/collect/schema.py`
- Create: `backend/app/collect/cleaner.py`
- Test: `backend/tests/test_cleaner.py`

**Interfaces:**
- Consumes: BeautifulSoup
- Produces:
  - `RawJD`(dataclass:`source, job_title, raw_html, duties, experience`)
  - `clean(raw: RawJD) -> dict`——输出 jd_pool 行 dict(去HTML、正文提取、字段规整、status='cleaned')

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_cleaner.py
from app.collect.schema import RawJD
from app.collect.cleaner import clean

def test_clean_strips_html_and_shapes_row():
    raw = RawJD(source="github", job_title="  AI Engineer ",
                raw_html="<p>负责<b>RAG</b>系统开发</p>", duties="", experience="3-5年")
    row = clean(raw)
    assert row["source"] == "github"
    assert row["job_title"] == "AI Engineer"        # 去首尾空格
    assert "<p>" not in row["raw_text"] and "RAG" in row["raw_text"]  # 去标签保文本
    assert row["experience"] == "3-5年"
    assert row["status"] == "cleaned"
```

- [ ] **Step 2: 运行验证失败**

Run: `cd backend && pytest tests/test_cleaner.py -v`
Expected: FAIL,`ModuleNotFoundError: No module named 'app.collect.schema'`

- [ ] **Step 3: 实现 schema.py 与 cleaner.py**

```python
# backend/app/collect/schema.py
from dataclasses import dataclass

@dataclass
class RawJD:
    source: str
    job_title: str
    raw_html: str
    duties: str = ""
    experience: str = ""
```

```python
# backend/app/collect/cleaner.py
from datetime import datetime
from bs4 import BeautifulSoup
from app.collect.schema import RawJD

def _strip_html(html: str) -> str:
    return BeautifulSoup(html or "", "html.parser").get_text(separator=" ").strip()

def clean(raw: RawJD) -> dict:
    return {
        "source": raw.source,
        "job_title": raw.job_title.strip(),
        "raw_text": _strip_html(raw.raw_html),
        "duties": _strip_html(raw.duties),
        "experience": raw.experience.strip(),
        "crawled_at": datetime.utcnow(),
        "status": "cleaned",
    }
```

在 `backend/requirements.txt` 追加:
```
beautifulsoup4==4.12.3
playwright==1.47.0
apscheduler==3.10.4
```

- [ ] **Step 4: 运行验证通过**

Run: `cd backend && pytest tests/test_cleaner.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/collect/__init__.py backend/app/collect/schema.py backend/app/collect/cleaner.py backend/tests/test_cleaner.py backend/requirements.txt
git commit -m "feat(A): raw jd schema and html cleaner"
```

---

## Task 2: 交叉验证去重 + 质量分

**Files:**
- Create: `backend/app/collect/dedup.py`
- Test: `backend/tests/test_dedup.py`

**Interfaces:**
- Consumes: 无(纯函数)
- Produces:
  - `text_signature(text: str) -> str`——归一化签名(用于分组)
  - `assign_dup_groups(rows: list[dict]) -> list[dict]`——为每行填 `dup_group`;同签名同组
  - `quality_score(row: dict, group_size: int) -> float`——多源出现↑质量;正文过短↓质量

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_dedup.py
from app.collect.dedup import assign_dup_groups, quality_score

def test_same_content_grouped():
    rows = [
        {"raw_text": "负责 RAG 系统开发 熟悉 Python"},
        {"raw_text": "负责RAG系统开发,熟悉Python"},   # 标点/空格差异,应同组
        {"raw_text": "完全不同的后端岗位 Java Spring"},
    ]
    out = assign_dup_groups(rows)
    assert out[0]["dup_group"] == out[1]["dup_group"]
    assert out[2]["dup_group"] != out[0]["dup_group"]

def test_quality_score_multi_source_higher():
    long_row = {"raw_text": "x" * 200}
    short_row = {"raw_text": "太短"}
    assert quality_score(long_row, group_size=3) > quality_score(long_row, group_size=1)
    assert quality_score(short_row, group_size=1) < quality_score(long_row, group_size=1)
```

- [ ] **Step 2: 运行验证失败**

Run: `cd backend && pytest tests/test_dedup.py -v`
Expected: FAIL,`ModuleNotFoundError: No module named 'app.collect.dedup'`

- [ ] **Step 3: 实现 dedup.py**

```python
# backend/app/collect/dedup.py
import hashlib, re

def text_signature(text: str) -> str:
    norm = re.sub(r"[\s,。,.、;;]+", "", text or "").lower()
    return hashlib.md5(norm.encode()).hexdigest()[:16]

def assign_dup_groups(rows: list[dict]) -> list[dict]:
    for r in rows:
        r["dup_group"] = text_signature(r.get("raw_text", ""))
    return rows

def quality_score(row: dict, group_size: int) -> float:
    text = row.get("raw_text", "")
    length_score = min(len(text) / 200, 1.0)      # 正文越长质量越高(封顶)
    multi_source = min(group_size / 3, 1.0)         # 多源交叉验证加成
    return round(0.6 * length_score + 0.4 * multi_source, 2)
```

- [ ] **Step 4: 运行验证通过**

Run: `cd backend && pytest tests/test_dedup.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/collect/dedup.py backend/tests/test_dedup.py
git commit -m "feat(A): cross-validation dedup and quality score"
```

---

## Task 3: 阶段1 公开数据集导入(解锁下游)

**Files:**
- Create: `backend/app/collect/fetchers/__init__.py`
- Create: `backend/app/collect/fetchers/dataset.py`
- Test: `backend/tests/test_dataset_import.py`

**Interfaces:**
- Consumes: `RawJD`
- Produces: `load_dataset(path: str) -> list[RawJD]`——读 JSONL 公开数据集(每行 `{job_title, description, experience}`)转 RawJD

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_dataset_import.py
import json
from app.collect.fetchers.dataset import load_dataset
from app.collect.schema import RawJD

def test_load_dataset_jsonl(tmp_path):
    f = tmp_path / "jd.jsonl"
    f.write_text(
        json.dumps({"job_title": "AI工程师", "description": "负责LLM应用", "experience": "3-5年"}) + "\n" +
        json.dumps({"job_title": "后端工程师", "description": "Java开发", "experience": "1-3年"}) + "\n",
        encoding="utf-8")
    rows = load_dataset(str(f))
    assert len(rows) == 2
    assert isinstance(rows[0], RawJD)
    assert rows[0].job_title == "AI工程师" and rows[0].source == "dataset"
```

- [ ] **Step 2: 运行验证失败**

Run: `cd backend && pytest tests/test_dataset_import.py -v`
Expected: FAIL,`ModuleNotFoundError: No module named 'app.collect.fetchers.dataset'`

- [ ] **Step 3: 实现 dataset.py**

```python
# backend/app/collect/fetchers/dataset.py
import json
from app.collect.schema import RawJD

def load_dataset(path: str) -> list[RawJD]:
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            rows.append(RawJD(
                source="dataset",
                job_title=d.get("job_title", ""),
                raw_html=d.get("description", ""),
                experience=d.get("experience", "")))
    return rows
```

创建空 `backend/app/collect/fetchers/__init__.py`。

- [ ] **Step 4: 运行验证通过**

Run: `cd backend && pytest tests/test_dataset_import.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/collect/fetchers/ backend/tests/test_dataset_import.py
git commit -m "feat(A): stage-1 public dataset importer"
```

---

## Task 4: jd_pool 仓储

**Files:**
- Create: `backend/app/collect/repository.py`
- Test: `backend/tests/test_collect_repo.py`

**Interfaces:**
- Consumes: `app.db.mysql.get_db`
- Produces: `save_rows(db, rows: list[dict]) -> int`——批量写 jd_pool,返回写入条数;`build_insert_params(row) -> dict`(纯函数便于单测)

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_collect_repo.py
from datetime import datetime
from app.collect.repository import build_insert_params

def test_build_insert_params_maps_fields():
    row = {"source": "github", "job_title": "AI", "raw_text": "x", "duties": "",
           "experience": "3-5年", "quality": 0.8, "dup_group": "abc",
           "crawled_at": datetime(2026, 7, 20), "status": "cleaned"}
    p = build_insert_params(row)
    assert p["source"] == "github" and p["quality"] == 0.8 and p["dup_group"] == "abc"
    assert p["status"] == "cleaned"
```

- [ ] **Step 2: 运行验证失败**

Run: `cd backend && pytest tests/test_collect_repo.py -v`
Expected: FAIL,`ModuleNotFoundError: No module named 'app.collect.repository'`

- [ ] **Step 3: 实现 repository.py**

```python
# backend/app/collect/repository.py
from sqlalchemy import text

def build_insert_params(row: dict) -> dict:
    return {
        "source": row.get("source", ""),
        "job_title": row.get("job_title", ""),
        "raw_text": row.get("raw_text", ""),
        "duties": row.get("duties", ""),
        "experience": row.get("experience", ""),
        "quality": row.get("quality", 0.0),
        "dup_group": row.get("dup_group", ""),
        "crawled_at": row.get("crawled_at"),
        "status": row.get("status", "cleaned"),
    }

def save_rows(db, rows: list[dict]) -> int:
    stmt = text(
        "INSERT INTO jd_pool (source, job_title, raw_text, duties, experience, "
        "quality, dup_group, crawled_at, status) VALUES "
        "(:source, :job_title, :raw_text, :duties, :experience, "
        ":quality, :dup_group, :crawled_at, :status)")
    for row in rows:
        db.execute(stmt, build_insert_params(row))
    db.commit()
    return len(rows)
```

- [ ] **Step 4: 运行验证通过**

Run: `cd backend && pytest tests/test_collect_repo.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/collect/repository.py backend/tests/test_collect_repo.py
git commit -m "feat(A): jd_pool repository"
```

---

## Task 5: 采集管道编排 + GitHub 采集器骨架

**Files:**
- Create: `backend/app/collect/fetchers/base.py`
- Create: `backend/app/collect/fetchers/github.py`
- Create: `backend/app/collect/pipeline.py`
- Test: `backend/tests/test_pipeline.py`

**Interfaces:**
- Consumes: cleaner, dedup, repository, RawJD
- Produces:
  - `class Fetcher`(抽象:`fetch() -> list[RawJD]`)
  - `run_pipeline(db, raws: list[RawJD]) -> dict`——clean→dedup→quality→save,返回统计

- [ ] **Step 1: 写失败测试(mock db)**

```python
# backend/tests/test_pipeline.py
from app.collect.pipeline import run_pipeline
from app.collect.schema import RawJD

class FakeDB:
    def __init__(self): self.saved = []
    def execute(self, stmt, params=None):
        if params: self.saved.append(params)
    def commit(self): pass

def test_pipeline_cleans_dedups_saves():
    db = FakeDB()
    raws = [
        RawJD(source="github", job_title="AI工程师", raw_html="<p>负责 RAG 开发 熟悉 Python 的候选人</p>", experience="3-5年"),
        RawJD(source="dataset", job_title="AI工程师", raw_html="负责RAG开发,熟悉Python的候选人", experience="3-5年"),
    ]
    stats = run_pipeline(db, raws)
    assert stats["saved"] == 2
    # 同内容不同源 → 同 dup_group → 质量分获多源加成
    assert db.saved[0]["dup_group"] == db.saved[1]["dup_group"]
    assert db.saved[0]["quality"] > 0
```

- [ ] **Step 2: 运行验证失败**

Run: `cd backend && pytest tests/test_pipeline.py -v`
Expected: FAIL,`ModuleNotFoundError: No module named 'app.collect.pipeline'`

- [ ] **Step 3: 实现 base.py / github.py / pipeline.py**

```python
# backend/app/collect/fetchers/base.py
from abc import ABC, abstractmethod
from app.collect.schema import RawJD

class Fetcher(ABC):
    """采集器抽象。实现类负责代理池/随机延迟/断点续爬。"""
    @abstractmethod
    def fetch(self) -> list[RawJD]:
        ...
```

```python
# backend/app/collect/fetchers/github.py
import httpx
from app.collect.fetchers.base import Fetcher
from app.collect.schema import RawJD

class GithubTrendingFetcher(Fetcher):
    """GitHub Trending 采集(反爬弱,优先)。真实实现按需补充解析逻辑。"""
    def __init__(self, client: httpx.Client | None = None):
        self.client = client or httpx.Client(timeout=10)

    def fetch(self) -> list[RawJD]:
        # 骨架:真实爬取时解析 trending 页面的技术栈,产出 RawJD。
        # 单测不覆盖网络;集成时手动运行。
        return []
```

```python
# backend/app/collect/pipeline.py
from app.collect.cleaner import clean
from app.collect.dedup import assign_dup_groups, quality_score
from app.collect.repository import save_rows

def run_pipeline(db, raws) -> dict:
    rows = [clean(r) for r in raws]
    rows = assign_dup_groups(rows)
    group_sizes: dict[str, int] = {}
    for r in rows:
        group_sizes[r["dup_group"]] = group_sizes.get(r["dup_group"], 0) + 1
    for r in rows:
        r["quality"] = quality_score(r, group_sizes[r["dup_group"]])
    saved = save_rows(db, rows)
    return {"saved": saved, "groups": len(group_sizes)}
```

- [ ] **Step 4: 运行验证通过**

Run: `cd backend && pytest tests/test_pipeline.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/collect/fetchers/base.py backend/app/collect/fetchers/github.py backend/app/collect/pipeline.py backend/tests/test_pipeline.py
git commit -m "feat(A): collection pipeline and github fetcher skeleton"
```

---

## Task 6: 阶段1 落库集成(解锁下游的关键里程碑)

**Files:**
- Test: `backend/tests/test_collect_integration.py`

**Interfaces:**
- Consumes: `load_dataset`, `run_pipeline`, `get_db`

- [ ] **Step 1: 写集成测试(真库)**

```python
# backend/tests/test_collect_integration.py
import json
import pytest
from sqlalchemy import text
from app.db.mysql import get_db
from app.collect.fetchers.dataset import load_dataset
from app.collect.pipeline import run_pipeline

pytestmark = pytest.mark.integration

def test_dataset_to_jd_pool(tmp_path):
    f = tmp_path / "seed.jsonl"
    f.write_text(json.dumps(
        {"job_title": "AI应用工程师", "description": "负责 RAG 与 LLM 应用开发", "experience": "3-5年"}) + "\n",
        encoding="utf-8")
    db = next(get_db())
    db.execute(text("DELETE FROM jd_pool WHERE source='dataset'"))
    db.commit()
    raws = load_dataset(str(f))
    stats = run_pipeline(db, raws)
    assert stats["saved"] == 1
    cnt = db.execute(text(
        "SELECT COUNT(*) FROM jd_pool WHERE source='dataset' AND status='cleaned'")).scalar()
    assert cnt == 1
```

- [ ] **Step 2: 起库运行**

Run: `docker-compose up -d --wait && cd backend && pytest tests/test_collect_integration.py -v -m integration`
Expected: PASS——数据集成功进 `jd_pool`,下游(C)可开始抽取

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_collect_integration.py
git commit -m "test(A): stage-1 dataset to jd_pool integration"
```

---

## 自审说明
- 覆盖 spec:多源采集(GitHub骨架+数据集)✓ 清洗✓ 交叉验证去重+质量分✓ 两阶段(数据集解锁)✓ jd_pool契约✓
- 类型一致:`jd_pool` 字段与计划0 DDL 一致;下游 C 读 `status='cleaned'` 与本计划写入一致
- 真实爬虫(Boss/猎聘等)实现细节在 github.py/base.py 骨架上按源扩展,反爬对抗为运行期工程,不阻塞代码结构
- `signal` 表(P1)在闭环稳定后补充技术热度/社区采集,本计划先交付 P0 JD 采集

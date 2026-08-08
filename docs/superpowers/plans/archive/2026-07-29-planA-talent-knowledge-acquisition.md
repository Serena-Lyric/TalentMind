# Talent Knowledge Acquisition — 数据获取模块扩展 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在已完成的 JD 采集代码（`RawJD`/`cleaner.py`/`dedup.py`/`repository.py::save_rows`/`jd_pool`）基础上，并列新增人才侧原始数据采集链路（`RawTalent`/`talent_cleaner.py`/`repository.py::save_talent_rows`/`talent_raw`），并让 `pipeline.run_pipeline` 按 `Fetcher.fetch()` 返回的元素类型自动路由到对应处理链。

**本计划替代**：`docs/superpowers/plans/2026-07-20-planA-data-collection.md` 的整体范围定义（该计划仅覆盖 JD 采集）。已完成的 JD 侧代码全部保留、不推翻，本计划只做并列扩展。

**Architecture:** `Fetcher` 抽象不变（`fetch() -> list[RawJD | RawTalent]`），新增数据源只需实现一个 `Fetcher` 子类返回其中一种类型；`run_pipeline` 在入口处按 `isinstance` 把混合列表拆成 JD 组和 Talent 组，JD 组走现有 `clean → enrich_skills → dedup → quality → save_rows` 不变，Talent 组走新增 `clean_talent → dedup(复用) → quality(复用) → save_talent_rows`；两组统计合并到同一个 stats dict 返回，`stats["saved"]` 保持含义为总保存行数以兼容现有调用方（`import_csv.py`）。

**Tech Stack:** Python 3.11, SQLAlchemy(text), pytest, MySQL(JSON 列存 `skills_hint`)

**依赖设计文档:** `docs/superpowers/specs/2026-07-29-talent-knowledge-acquisition-workflow-design.md`（已经用户审阅确认，第 7 节字段级契约是本计划的直接依据）

## Global Constraints

- 不改动已完成的 JD 侧代码签名：`RawJD`、`fetchers/base.py::Fetcher`、`cleaner.py::clean`、`dedup.py`（`text_signature`/`assign_dup_groups`/`quality_score`）、`repository.py::save_rows`/`build_insert_params`、`fetchers/dataset.py` 均保持不变，仅新增并列内容
- 不改动 v2 架构已冻结的 6 张表（`jd_pool`/`signal`/`skill_dict`/`job_skill`/`emerging_job`/`resume`）；`talent_raw` 是新增表，遵循"加表自由，改/删须全队通知"规则
- `talent_raw` 字段结构与 `jd_pool` 对齐（`quality`/`dup_group`/`crawled_at`/`status` 语义一致），复用 `dedup.py` 通用函数，不为人才侧另写去重/质量逻辑
- `Fetcher.fetch()` 返回类型本身是路由依据，不新增 `kind` 字符串字段
- Python 3.11；测试框架 pytest；先写失败测试（TDD）；每个任务结束 commit，message 用 `feat:`/`test:` 前缀并带 `(A)` 标记
- 集成测试标记 `pytest.mark.integration`，需要 `docker-compose up -d --wait` 起库后运行；已在 `backend/pytest.ini` 注册该 marker，无需重复注册
- 批量落库沿用 1000 条/批 commit 一次的模式（对齐 `save_rows` 现状）
- `identity_hint` 写入前截断到 128 字符（对齐 `job_title` 截断到 128 字符的现有先例，`backend/app/collect/repository.py:14`）

---

## 文件结构（本计划新增/修改）

```
backend/app/collect/
  schema.py                 # 修改：新增 RawTalent（RawJD 不变）
  talent_cleaner.py          # 新建：clean_talent(raw: RawTalent) -> dict
  repository.py               # 修改：新增 build_talent_insert_params / save_talent_rows
  pipeline.py                  # 修改：run_pipeline 按类型分流
  contracts/ddl.sql             # 修改：追加 talent_raw 表定义
backend/tests/
  test_talent_schema.py        # 新建
  test_talent_cleaner.py        # 新建
  test_talent_repo.py            # 新建
  test_ddl_integration.py         # 修改：追加 talent_raw 校验
  test_pipeline.py                 # 修改：追加路由测试
  test_talent_pipeline_integration.py  # 新建：端到端集成测试
```

---

## Task 1: `RawTalent` 数据结构

**Files:**
- Modify: `backend/app/collect/schema.py`
- Test: `backend/tests/test_talent_schema.py`

**Interfaces:**
- Consumes: 无（纯 dataclass，与现有 `RawJD` 并列）
- Produces: `RawTalent`（dataclass：`source: str, raw_text: str, identity_hint: str = "", skills_hint: list[str] | None = None, experience_hint: str = ""`）—— 供 Task 2 的 `clean_talent` 和后续 Fetcher 实现消费

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_talent_schema.py
from app.collect.schema import RawJD, RawTalent


def test_rawtalent_minimal_construction():
    t = RawTalent(source="github", raw_text="Python developer, 5 repos")
    assert t.source == "github"
    assert t.raw_text == "Python developer, 5 repos"
    assert t.identity_hint == ""
    assert t.skills_hint is None
    assert t.experience_hint == ""


def test_rawtalent_full_construction():
    t = RawTalent(
        source="resume_dataset",
        raw_text="5 years backend experience",
        identity_hint="user_123",
        skills_hint=["Python", "Django"],
        experience_hint="5 years backend",
    )
    assert t.identity_hint == "user_123"
    assert t.skills_hint == ["Python", "Django"]
    assert t.experience_hint == "5 years backend"


def test_rawjd_unaffected_by_rawtalent_addition():
    # 回归防护：RawJD 字段不受本次修改影响
    jd = RawJD(source="dataset", job_title="AI Engineer", raw_html="desc")
    assert jd.source == "dataset"
    assert jd.job_id == ""
    assert jd.raw_skills is None
```

- [ ] **Step 2: 运行验证失败**

Run: `cd backend && pytest tests/test_talent_schema.py -v`
Expected: FAIL，`ImportError: cannot import name 'RawTalent' from 'app.collect.schema'`

- [ ] **Step 3: 实现 RawTalent**

在 `backend/app/collect/schema.py` 中，`RawJD` dataclass 定义之后追加（文件其余内容不变）：

```python
@dataclass
class RawTalent:
    source: str
    raw_text: str
    identity_hint: str = ""
    skills_hint: list[str] | None = None
    experience_hint: str = ""
```

- [ ] **Step 4: 运行验证通过**

Run: `cd backend && pytest tests/test_talent_schema.py -v`
Expected: PASS（3 passed）

- [ ] **Step 5: Commit**

```bash
git add backend/app/collect/schema.py backend/tests/test_talent_schema.py
git commit -m "feat(A): add RawTalent dataclass alongside RawJD"
```

---

## Task 2: 人才侧清洗 `talent_cleaner.py`

**Files:**
- Create: `backend/app/collect/talent_cleaner.py`
- Test: `backend/tests/test_talent_cleaner.py`

**Interfaces:**
- Consumes: `RawTalent`（Task 1 产出）
- Produces: `clean_talent(raw: RawTalent) -> dict`——输出字段覆盖 `source, identity_hint, raw_text, skills_hint, experience_hint, crawled_at, status`（`status` 固定为 `"cleaned"`），供 Task 4 的 `run_pipeline` 路由消费

设计约束（来自 spec 第 7.3 节）：不做 JD 式的职责段落提取（`_extract_duties`/`_extract_experience` 是岗位专用逻辑，不适用于简历/GitHub 文本），只做通用文本规整——去首尾空白、把 `None` 的 `skills_hint` 规整为空列表。

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_talent_cleaner.py
from app.collect.schema import RawTalent
from app.collect.talent_cleaner import clean_talent


def test_clean_talent_produces_talent_raw_row():
    raw = RawTalent(
        source="github",
        raw_text="  Python developer with 5 repos  ",
        identity_hint="  octocat  ",
        skills_hint=["Python", "Go"],
        experience_hint="  5 years  ",
    )
    row = clean_talent(raw)
    assert row["source"] == "github"
    assert row["identity_hint"] == "octocat"
    assert row["raw_text"] == "Python developer with 5 repos"
    assert row["skills_hint"] == ["Python", "Go"]
    assert row["experience_hint"] == "5 years"
    assert row["status"] == "cleaned"
    assert row["crawled_at"] is not None


def test_clean_talent_defaults_none_skills_hint_to_empty_list():
    raw = RawTalent(source="resume_dataset", raw_text="text")
    row = clean_talent(raw)
    assert row["skills_hint"] == []
    assert row["identity_hint"] == ""
    assert row["experience_hint"] == ""


def test_clean_talent_strips_whitespace_only_raw_text():
    raw = RawTalent(source="github", raw_text="   \n  ")
    row = clean_talent(raw)
    assert row["raw_text"] == ""
```

- [ ] **Step 2: 运行验证失败**

Run: `cd backend && pytest tests/test_talent_cleaner.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'app.collect.talent_cleaner'`

- [ ] **Step 3: 实现 talent_cleaner.py**

```python
# backend/app/collect/talent_cleaner.py
from datetime import datetime, timezone
from app.collect.schema import RawTalent


def clean_talent(raw: RawTalent) -> dict:
    """人才侧清洗：仅做通用文本规整，不做 JD 式职责段落提取。

    _extract_duties/_extract_experience (cleaner.py) 是岗位专用逻辑，
    识别 "Responsibilities:" 等岗位JD段落标题，不适用于简历/GitHub文本。
    """
    return {
        "source": raw.source,
        "identity_hint": raw.identity_hint.strip(),
        "raw_text": (raw.raw_text or "").strip(),
        "skills_hint": raw.skills_hint or [],
        "experience_hint": raw.experience_hint.strip(),
        "crawled_at": datetime.now(timezone.utc),
        "status": "cleaned",
    }
```

- [ ] **Step 4: 运行验证通过**

Run: `cd backend && pytest tests/test_talent_cleaner.py -v`
Expected: PASS（3 passed）

- [ ] **Step 5: Commit**

```bash
git add backend/app/collect/talent_cleaner.py backend/tests/test_talent_cleaner.py
git commit -m "feat(A): add clean_talent for talent-side raw text normalization"
```

---

## Task 3: `talent_raw` 表契约 + `save_talent_rows` 仓储

**Files:**
- Modify: `backend/app/contracts/ddl.sql`
- Modify: `backend/app/collect/repository.py`
- Modify: `backend/tests/test_ddl_integration.py`
- Test: `backend/tests/test_talent_repo.py`

**Interfaces:**
- Consumes: `clean_talent` 输出的行 dict（Task 2 产出，字段：`source, identity_hint, raw_text, skills_hint, experience_hint, crawled_at, status`）
- Produces:
  - `build_talent_insert_params(row: dict) -> dict`——纯函数，`skills_hint` 序列化为 JSON 字符串（MySQL JSON 列写入需要字符串）
  - `save_talent_rows(db, rows: list[dict], batch_size: int = 1000) -> int`——批量写 `talent_raw`，签名对齐现有 `save_rows`
  - 供 Task 4 的 `run_pipeline` 消费

- [ ] **Step 1: 在 ddl.sql 追加 talent_raw 表**

在 `backend/app/contracts/ddl.sql` 文件末尾（`resume` 表定义之后）追加：

```sql
CREATE TABLE IF NOT EXISTS talent_raw (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  source VARCHAR(32), identity_hint VARCHAR(128), raw_text TEXT,
  skills_hint JSON, experience_hint TEXT,
  quality FLOAT DEFAULT 0, dup_group VARCHAR(64),
  crawled_at DATETIME, status VARCHAR(16) DEFAULT 'raw',
  INDEX idx_status (status), INDEX idx_source (source)
);
```

- [ ] **Step 2: 应用 DDL**

Run: `docker-compose up -d --wait && docker exec -i $(docker-compose ps -q mysql) mysql -uroot -ptalentmind talentmind < backend/app/contracts/ddl.sql`
Expected: 无报错（`CREATE TABLE IF NOT EXISTS` 对已有表是幂等操作）

- [ ] **Step 3: 扩展 DDL 集成测试校验 talent_raw**

修改 `backend/tests/test_ddl_integration.py`，将 `EXPECTED_TABLES` 一行改为包含 `talent_raw`：

```python
EXPECTED_TABLES = {"jd_pool", "signal", "skill_dict", "job_skill", "emerging_job", "resume", "talent_raw"}
```

并在文件末尾追加一个新测试函数：

```python
def test_talent_raw_has_frozen_columns():
    db = next(get_db())
    try:
        cols = _cols(db, "talent_raw")
        assert {"source", "identity_hint", "raw_text", "skills_hint",
                "experience_hint", "quality", "dup_group", "crawled_at", "status"}.issubset(cols)
    finally:
        db.close()
```

- [ ] **Step 4: 运行 DDL 集成测试验证**

Run: `cd backend && pytest tests/test_ddl_integration.py -v -m integration`
Expected: PASS（4 passed）——`talent_raw` 表和字段均校验通过

- [ ] **Step 5: 写失败测试（repository 纯函数部分，无需数据库）**

```python
# backend/tests/test_talent_repo.py
import json
from datetime import datetime, timezone
from app.collect.repository import build_talent_insert_params, save_talent_rows


def test_build_talent_insert_params_maps_fields():
    row = {
        "source": "github", "identity_hint": "octocat", "raw_text": "Python dev",
        "skills_hint": ["Python", "Go"], "experience_hint": "5 years",
        "quality": 0.7, "dup_group": "abc123",
        "crawled_at": datetime(2026, 7, 29, tzinfo=timezone.utc),
        "status": "cleaned",
    }
    p = build_talent_insert_params(row)
    assert p["source"] == "github"
    assert p["identity_hint"] == "octocat"
    assert p["raw_text"] == "Python dev"
    assert json.loads(p["skills_hint"]) == ["Python", "Go"]
    assert p["experience_hint"] == "5 years"
    assert p["quality"] == 0.7
    assert p["status"] == "cleaned"


def test_build_talent_insert_params_defaults():
    row = {"raw_text": "x"}
    p = build_talent_insert_params(row)
    assert p["source"] == ""
    assert p["identity_hint"] == ""
    assert json.loads(p["skills_hint"]) == []
    assert p["quality"] == 0.0
    assert p["status"] == "cleaned"


def test_build_talent_insert_params_truncates_identity_hint():
    row = {"raw_text": "x", "identity_hint": "a" * 200}
    p = build_talent_insert_params(row)
    assert len(p["identity_hint"]) == 128


class FakeDB:
    def __init__(self):
        self.saved = []
        self.committed = 0

    def execute(self, stmt, params=None):
        if params:
            self.saved.append(params)

    def commit(self):
        self.committed += 1


def test_save_talent_rows_batches_commits():
    db = FakeDB()
    rows = [{"raw_text": f"talent_{i}"} for i in range(1500)]
    count = save_talent_rows(db, rows, batch_size=1000)
    assert count == 1500
    assert len(db.saved) == 1500
    assert db.committed == 2   # 1000 + 500 -> 2 commits


def test_save_empty_talent_rows():
    db = FakeDB()
    count = save_talent_rows(db, [], batch_size=1000)
    assert count == 0
    assert db.committed == 0
```

- [ ] **Step 6: 运行验证失败**

Run: `cd backend && pytest tests/test_talent_repo.py -v`
Expected: FAIL，`ImportError: cannot import name 'build_talent_insert_params' from 'app.collect.repository'`

- [ ] **Step 7: 实现 build_talent_insert_params / save_talent_rows**

先修改 `backend/app/collect/repository.py` 文件顶部的 import 行，把：

```python
from sqlalchemy import text
```

替换为：

```python
import json
from sqlalchemy import text
```

然后在文件末尾追加（现有 `INSERT_STMT`/`build_insert_params`/`save_rows` 均不改动）：

```python
TALENT_INSERT_STMT = text(
    "INSERT INTO talent_raw (source, identity_hint, raw_text, skills_hint, "
    "experience_hint, quality, dup_group, crawled_at, status) VALUES "
    "(:source, :identity_hint, :raw_text, :skills_hint, "
    ":experience_hint, :quality, :dup_group, :crawled_at, :status)"
)


def build_talent_insert_params(row: dict) -> dict:
    return {
        "source": row.get("source", ""),
        "identity_hint": (row.get("identity_hint", "") or "")[:128],
        "raw_text": row.get("raw_text", ""),
        "skills_hint": json.dumps(row.get("skills_hint") or []),
        "experience_hint": row.get("experience_hint", ""),
        "quality": row.get("quality", 0.0),
        "dup_group": row.get("dup_group", ""),
        "crawled_at": row.get("crawled_at"),
        "status": row.get("status", "cleaned"),
    }


def save_talent_rows(db, rows: list[dict], batch_size: int = 1000) -> int:
    """批量写入 talent_raw，每 batch_size 条 commit 一次。结构对齐 save_rows。"""
    if not rows:
        return 0
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]
        for row in batch:
            db.execute(TALENT_INSERT_STMT, build_talent_insert_params(row))
        db.commit()
    return len(rows)
```

- [ ] **Step 8: 运行验证通过**

Run: `cd backend && pytest tests/test_talent_repo.py -v`
Expected: PASS（5 passed）

- [ ] **Step 9: Commit**

```bash
git add backend/app/contracts/ddl.sql backend/app/collect/repository.py backend/tests/test_ddl_integration.py backend/tests/test_talent_repo.py
git commit -m "feat(A): freeze talent_raw table contract and add save_talent_rows"
```

---

## Task 4: Pipeline 按类型分流路由

**Files:**
- Modify: `backend/app/collect/pipeline.py`
- Modify: `backend/tests/test_pipeline.py`

**Interfaces:**
- Consumes: `clean`/`enrich_skills`（现有，不变）、`clean_talent`（Task 2）、`assign_dup_groups`/`quality_score`（现有 `dedup.py`，不变）、`save_rows`（现有）、`save_talent_rows`（Task 3）
- Produces: `run_pipeline(db, raws, job_skill_map=None, skill_map=None) -> dict`——**签名不变**，`raws` 参数现在可传 `RawJD`、`RawTalent` 或两者混合的列表；返回 dict 新增 `jd_saved`/`talent_saved` 键，同时保留原有 `saved`（= `jd_saved + talent_saved`，向后兼容现有调用方 `import_csv.py` 和现有测试）和 `groups`（= 两侧分组数之和）键

关键兼容性要求：现有 `backend/tests/test_pipeline.py` 中 `TestRunPipeline` 两个测试只传纯 `RawJD` 列表，且断言 `stats["saved"] == 2`、`stats["saved"] == 1`——改造后这两个断言必须仍然通过，不能修改这两个已有测试的断言内容。

- [ ] **Step 1: 写失败测试（新增路由测试，不改动现有 TestRunPipeline）**

在 `backend/tests/test_pipeline.py` 顶部 import 区追加 `RawTalent` 导入：

```python
from app.collect.schema import RawJD, RawTalent
```

（原 `from app.collect.schema import RawJD` 这一行替换为上面这行，其余现有 import 不变）

在文件末尾追加新的测试类：

```python
class TestRunPipelineRouting:
    def test_routes_talent_raws_to_talent_saved(self):
        db = FakeDB()
        raws = [
            RawTalent(source="github", raw_text="Python developer with 5 repos"),
            RawTalent(source="resume_dataset", raw_text="Python developer with five repos"),
        ]
        stats = run_pipeline(db, raws)
        assert stats["talent_saved"] == 2
        assert stats["jd_saved"] == 0
        assert stats["saved"] == 2

    def test_routes_mixed_raws_to_both_sides(self):
        db = FakeDB()
        raws = [
            RawJD(source="dataset", job_title="AI Engineer", raw_html="Build AI systems."),
            RawTalent(source="github", raw_text="Python developer with 5 repos"),
        ]
        stats = run_pipeline(db, raws)
        assert stats["jd_saved"] == 1
        assert stats["talent_saved"] == 1
        assert stats["saved"] == 2

    def test_empty_raws_returns_zero_stats(self):
        db = FakeDB()
        stats = run_pipeline(db, [])
        assert stats == {"saved": 0, "jd_saved": 0, "talent_saved": 0, "groups": 0}
```

- [ ] **Step 2: 运行验证失败**

Run: `cd backend && pytest tests/test_pipeline.py -v`
Expected: FAIL——`test_routes_talent_raws_to_talent_saved` 等新测试因 `stats` 缺少 `jd_saved`/`talent_saved` 键报 `KeyError`；已有 `TestRunPipeline`/`TestEnrichSkills` 测试此时仍应 PASS（尚未改动 pipeline.py 实现）

- [ ] **Step 3: 实现 pipeline.py 路由**

用以下完整内容替换 `backend/app/collect/pipeline.py`（`enrich_skills` 函数保持完全不变，只重写 `run_pipeline` 并新增一个私有辅助函数）：

```python
from app.collect.cleaner import clean
from app.collect.talent_cleaner import clean_talent
from app.collect.dedup import assign_dup_groups, quality_score
from app.collect.repository import save_rows, save_talent_rows
from app.collect.schema import RawJD, RawTalent


def enrich_skills(
    rows: list[dict],
    job_skill_map: dict[str, list[str]],
    skill_map: dict[str, str],
    job_id_key: str = "_job_id",
) -> list[dict]:
    """通过 job_id join 技能缩写→技能名，追加到 raw_text 尾部。"""
    for row in rows:
        job_id = row.pop(job_id_key, None)
        if not job_id or job_id not in job_skill_map:
            continue
        abrs = job_skill_map[job_id]
        names = [skill_map[a] for a in abrs if a in skill_map]
        if names:
            skill_text = "\n\nSkills: " + ", ".join(names)
            row["raw_text"] = row.get("raw_text", "") + skill_text
    return rows


def _assign_quality(rows: list[dict]) -> int:
    """按 dup_group 统计分组大小并填充 quality 分数，返回分组数。两侧共用。"""
    group_sizes: dict[str, int] = {}
    for r in rows:
        group_sizes[r["dup_group"]] = group_sizes.get(r["dup_group"], 0) + 1
    for r in rows:
        r["quality"] = quality_score(r, group_sizes[r["dup_group"]])
    return len(group_sizes)


def run_pipeline(
    db,
    raws,
    job_skill_map: dict[str, list[str]] | None = None,
    skill_map: dict[str, str] | None = None,
) -> dict:
    """按元素类型分流：RawJD 走岗位链(jd_pool)，RawTalent 走人才链(talent_raw)。
    raws 可混合两种类型；Fetcher.fetch() 的返回类型本身即路由依据。"""
    jd_raws = [r for r in raws if isinstance(r, RawJD)]
    talent_raws = [r for r in raws if isinstance(r, RawTalent)]

    jd_saved = 0
    talent_saved = 0
    total_groups = 0

    if jd_raws:
        rows = []
        for r in jd_raws:
            row = clean(r)
            if r.job_id:
                row["_job_id"] = r.job_id  # 临时传递，enrich 后删除
            rows.append(row)

        if job_skill_map and skill_map:
            rows = enrich_skills(rows, job_skill_map, skill_map)

        rows = assign_dup_groups(rows)
        total_groups += _assign_quality(rows)
        jd_saved = save_rows(db, rows)

    if talent_raws:
        rows = [clean_talent(r) for r in talent_raws]
        rows = assign_dup_groups(rows)
        total_groups += _assign_quality(rows)
        talent_saved = save_talent_rows(db, rows)

    return {
        "saved": jd_saved + talent_saved,
        "jd_saved": jd_saved,
        "talent_saved": talent_saved,
        "groups": total_groups,
    }
```

- [ ] **Step 4: 运行验证通过（全部 pipeline 测试，包括未改动的既有测试）**

Run: `cd backend && pytest tests/test_pipeline.py -v`
Expected: PASS——`TestEnrichSkills`（4 项，未受影响）+ `TestRunPipeline`（2 项，既有断言 `stats["saved"]` 依旧成立）+ `TestRunPipelineRouting`（3 项新增）全部通过

- [ ] **Step 5: 回归验证 import_csv.py 调用方未被破坏**

Run: `cd backend && pytest tests/test_collect_integration.py -v -m integration`（需先 `docker-compose up -d --wait`）
Expected: PASS——该测试通过 `stats['saved']` 判断保存行数，验证 Task 4 的改动未破坏现有 CLI 入口的调用契约

- [ ] **Step 6: Commit**

```bash
git add backend/app/collect/pipeline.py backend/tests/test_pipeline.py
git commit -m "feat(A): route run_pipeline by RawJD/RawTalent type, keep saved/groups backward compatible"
```

---

## Task 5: 端到端集成测试（RawTalent → talent_raw）

**Files:**
- Test: `backend/tests/test_talent_pipeline_integration.py`

**Interfaces:**
- Consumes: `RawTalent`（Task 1）、`run_pipeline`（Task 4）、`app.db.mysql.get_db`（现有）

这是本计划的关键里程碑测试：验证 `RawTalent` 经过真实数据库落库后，`talent_raw` 表中确实产出了预期的清洗后数据，且与 `jd_pool` 的落库互不干扰（混合批次场景）。

- [ ] **Step 1: 写集成测试（真库）**

```python
# backend/tests/test_talent_pipeline_integration.py
import pytest
from sqlalchemy import text
from app.db.mysql import get_db
from app.collect.schema import RawJD, RawTalent
from app.collect.pipeline import run_pipeline

pytestmark = pytest.mark.integration


def test_talent_raw_to_database(tmp_path):
    """端到端: RawTalent → clean_talent → dedup → talent_raw"""
    db = next(get_db())
    try:
        db.execute(text("DELETE FROM talent_raw WHERE source='github'"))
        db.commit()

        raws = [
            RawTalent(
                source="github",
                raw_text="Experienced Python developer with 5 open source repos",
                identity_hint="octocat",
                skills_hint=["Python", "Go"],
                experience_hint="5 years",
            ),
        ]
        stats = run_pipeline(db, raws)
        assert stats["talent_saved"] == 1
        assert stats["jd_saved"] == 0

        row = db.execute(text(
            "SELECT identity_hint, raw_text, skills_hint, status FROM talent_raw "
            "WHERE source='github' AND identity_hint='octocat'"
        )).fetchone()
        assert row is not None
        assert row[0] == "octocat"
        assert "Python developer" in row[1]
        assert row[3] == "cleaned"
    finally:
        db.close()


def test_mixed_batch_saves_to_both_tables_independently():
    """混合批次: RawJD 进 jd_pool, RawTalent 进 talent_raw, 互不干扰"""
    db = next(get_db())
    try:
        db.execute(text("DELETE FROM jd_pool WHERE source='dataset' AND job_title='Mixed Batch JD'"))
        db.execute(text("DELETE FROM talent_raw WHERE source='github' AND identity_hint='mixed_batch_user'"))
        db.commit()

        raws = [
            RawJD(source="dataset", job_title="Mixed Batch JD", raw_html="Build systems."),
            RawTalent(source="github", raw_text="Go developer", identity_hint="mixed_batch_user"),
        ]
        stats = run_pipeline(db, raws)
        assert stats["jd_saved"] == 1
        assert stats["talent_saved"] == 1
        assert stats["saved"] == 2

        jd_count = db.execute(text(
            "SELECT COUNT(*) FROM jd_pool WHERE source='dataset' AND job_title='Mixed Batch JD'"
        )).scalar()
        talent_count = db.execute(text(
            "SELECT COUNT(*) FROM talent_raw WHERE source='github' AND identity_hint='mixed_batch_user'"
        )).scalar()
        assert jd_count == 1
        assert talent_count == 1
    finally:
        db.close()
```

- [ ] **Step 2: 起库运行**

Run: `docker-compose up -d --wait && cd backend && pytest tests/test_talent_pipeline_integration.py -v -m integration`
Expected: PASS（2 passed）——`RawTalent` 数据成功落入 `talent_raw`，且与 `jd_pool` 落库互不干扰

- [ ] **Step 3: 全量回归（确保本计划全部改动未破坏现有测试套件）**

Run: `cd backend && pytest -v -m "not integration"`
Expected: 全部 PASS（含本计划新增的 `test_talent_schema.py`/`test_talent_cleaner.py`/`test_talent_repo.py`/`test_pipeline.py` 新增用例，以及未改动的既有测试套件如 `test_cleaner.py`/`test_dataset_import.py`/`test_collect_repo.py`）

Run: `docker-compose up -d --wait && cd backend && pytest -v -m integration`
Expected: 全部 PASS（含 `test_ddl_integration.py`/`test_collect_integration.py`/`test_talent_pipeline_integration.py`/`test_db_integration.py`）

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_talent_pipeline_integration.py
git commit -m "test(A): end-to-end integration test for talent_raw acquisition path"
```

---

## 自审说明

- **覆盖设计文档 spec 第 7 节字段级契约**：`RawTalent`(7.1)✓ `talent_raw` 表(7.2)✓ `clean_talent`/`save_talent_rows`/`run_pipeline` 路由签名(7.3)✓ 文件组织(7.4)✓
- **不破坏现有代码**：`RawJD`/`Fetcher`/`cleaner.py`/`dedup.py`/`save_rows`/`build_insert_params`/`fetchers/dataset.py` 均未修改签名或行为；`test_pipeline.py` 中既有 `TestRunPipeline` 两个断言（`stats["saved"]`）在 Task 4 后依然成立，`test_collect_integration.py`（既有集成测试）在 Task 4 Step 5 中显式回归验证
- **类型一致性**：`clean_talent` 输出字段与 `talent_raw` DDL 列名一一对应；`build_talent_insert_params` 消费的字段名与 `clean_talent` 产出字段名一致；`run_pipeline` 新增返回键（`jd_saved`/`talent_saved`）与 Task 4/5 测试断言的键名一致
- **范围边界**：本计划仅落地设计文档第 7 节的接口契约（Fetcher/Pipeline/表结构），不实现真实的 GitHub/简历数据源抓取逻辑（`fetchers/github.py` 迁移为产出 `RawTalent` 属于设计文档第 10 节列出的未决问题，不在本计划范围内）
- **测试策略**：纯函数（`clean_talent`/`build_talent_insert_params`/`run_pipeline` 路由逻辑）用 `FakeDB`/mock 覆盖，不依赖真实数据库；表结构和端到端落库用 `pytest.mark.integration` 隔离，需要 `docker-compose up -d --wait`





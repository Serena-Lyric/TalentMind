# Plan A CSV 扩展 — 公开数据集导入与中洗管道 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 扩展 planA Task 1/3/4/5，将 LinkedIn 公开数据集 CSV 导入 `jd_pool`（采样 10 万行），包含中洗管道（信息分离 + 职责提取 + 技能补充）。

**Architecture:** 在 planA 既有 Task 结构上扩展——`load_csv()`逐行读取 CSV → `clean()`中洗分离杂讯/提取职责 → `enrich_skills()` join job_skills + mappings 追加技能名 → `dedup/quality`(不变) → `save_rows()`批量写入 `jd_pool`。

**Tech Stack:** Python 3.11, csv stdlib, re, SQLAlchemy, pytest

**依赖:** 设计文档 `docs/superpowers/specs/2026-07-23-csv-import-cleaning-design.md`；planA 原始计划 `docs/superpowers/plans/2026-07-20-planA-data-collection.md`。

## Global Constraints

- 复用 plan0:`app.db.mysql.get_db`、`jd_pool` 表契约（不改 DDL）
- **采样 10 万行**作为默认值；`--limit 0` 可切全量
- 中洗深度(B)：正则分离杂讯行 + 职责段落识别 + 经验提取（不用 LLM）
- `job_id` 仅用于 enrich_skills 阶段 join，不写入 `jd_pool`
- 技能名追加到 `raw_text` 尾部，不新增 `jd_pool` 列
- TDD：每任务先写失败测试 → 验证失败 → 实现 → 验证通过 → commit
- 本计划是 planA 的扩展，Task 2 (dedup) 和 Task 6 (集成测试) 不变，不在本计划中重复

---

## 文件结构（本计划创建/修改）

```
backend/app/collect/
  __init__.py              ← planA Task 1 创建，本计划不改
  schema.py                ← 修改：RawJD 新增 job_id, raw_skills
  cleaner.py               ← 重写：中洗逻辑替代去 HTML
  dedup.py                 ← planA Task 2，不改
  fetchers/
    __init__.py            ← planA Task 3 创建
    base.py                ← planA Task 5 创建，不改
    github.py              ← planA Task 5 创建，不改
    dataset.py             ← 重写：CSV 加载器替代 JSONL
  repository.py            ← 修改：批量 INSERT 替代逐行
  pipeline.py              ← 修改：流程中插入 enrich_skills
  import_csv.py            ← 新增：CLI 入口

backend/tests/
  test_cleaner.py          ← 重写：含真实 CSV 样本的测试用例
  test_dataset_import.py   ← 重写：CSV 替代 JSONL 测试
  test_collect_repo.py     ← 微调：验证批量写入
  test_pipeline.py         ← 扩展：验证技能补充
```

---

## Task 1: 扩展 RawJD schema

**Files:**
- Create: `backend/app/collect/__init__.py`
- Create: `backend/app/collect/schema.py`
- Test: 无独立测试（RawJD 是纯数据结构，由 Task 2/3 的测试间接覆盖）

**Interfaces:**
- Consumes: 无
- Produces: `RawJD` dataclass——新增 `job_id: str = ""`、`raw_skills: list[str] | None = None`

> **与 planA 差异**: planA Task 1 的 RawJD 仅有 5 个字段。本任务在 planA 基础上扩展至 7 个字段。

- [ ] **Step 1: 创建 `__init__.py` + `schema.py`**

```python
# backend/app/collect/__init__.py
# 空文件
```

```python
# backend/app/collect/schema.py
from dataclasses import dataclass, field

@dataclass
class RawJD:
    source: str
    job_title: str
    raw_html: str              # CSV 中为 description 原文
    duties: str = ""
    experience: str = ""
    job_id: str = ""           # 新增：用于 join job_skills，不写入 jd_pool
    raw_skills: list[str] | None = None  # 新增：技能名列表
```

- [ ] **Step 2: 验证模块可导入**

Run: `cd backend && python -c "from app.collect.schema import RawJD; r = RawJD(source='test', job_title='x', raw_html='<p>hi</p>', job_id='123'); print(r.job_id)"`
Expected: `123`

- [ ] **Step 3: Commit**

```bash
git add backend/app/collect/__init__.py backend/app/collect/schema.py
git commit -m "feat(A-csv): extend RawJD schema with job_id and raw_skills"
```

---

## Task 2: 中洗 cleaner（替换 planA 去 HTML 逻辑）

**Files:**
- Create: `backend/app/collect/cleaner.py`
- Test: `backend/tests/test_cleaner.py`

**Interfaces:**
- Consumes: `RawJD`, `re`
- Produces:
  - `_strip_noise(text: str) -> str`——剥离杂讯行 + 修复粘连前缀
  - `_extract_duties(text: str) -> str`——识别职责段落
  - `_extract_experience(text: str, fallback: str) -> str`——经验提取（列优先，正则回退）
  - `clean(raw: RawJD) -> dict`——输出 jd_pool 行 dict

> **与 planA 差异**: planA 的 `clean()` 用 BeautifulSoup 去 HTML 标签。本任务替换为正则中洗，BeautifulSoup 仍然保留在 requirements.txt 中以供阶段 2 真实爬取使用。

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_cleaner.py
import pytest
from app.collect.schema import RawJD
from app.collect.cleaner import clean, _strip_noise, _extract_duties, _extract_experience


class TestStripNoise:
    def test_removes_pay_line(self):
        text = "Leading real estate firm\nPay: $18-20/hour\nGreat culture"
        result = _strip_noise(text)
        assert "Pay:" not in result
        assert "Leading real estate firm" in result
        assert "Great culture" in result

    def test_removes_benefits_line(self):
        text = "Cool startup\nBenefits:Paid time off\nFun team"
        result = _strip_noise(text)
        assert "Benefits:" not in result
        assert "Cool startup" in result

    def test_removes_schedule_line(self):
        text = "Exciting role\nSchedule:8 hour shift\nApply now"
        result = _strip_noise(text)
        assert "Schedule:" not in result

    def test_removes_location_line(self):
        text = "Remote friendly\nWork Location: In person\nJoin us"
        result = _strip_noise(text)
        assert "Work Location:" not in result

    def test_removes_job_type_line(self):
        text = "Great job\nJob Type: Full-time\nApply"
        result = _strip_noise(text)
        assert "Job Type:" not in result

    def test_removes_salary_amount_line(self):
        text = "Awesome role\n$65,000 - $85,000 per year\nJoin us"
        result = _strip_noise(text)
        assert "$65,000" not in result

    def test_fixes_fused_prefix(self):
        text = "Job descriptionA leading real estate firm is seeking..."
        result = _strip_noise(text)
        assert result.startswith("A leading")
        assert "Job description" not in result

    def test_fixes_job_summary_fused(self):
        text = "Job SummaryWe are looking for a skilled engineer..."
        result = _strip_noise(text)
        assert result.startswith("We are looking")

    def test_preserves_normal_text(self):
        text = "We are looking for a Python developer with 5 years of experience."
        result = _strip_noise(text)
        assert result == text


class TestExtractDuties:
    def test_extracts_responsibilities_section(self):
        text = "About us\nWe are a company.\nResponsibilities:\n- Build APIs\n- Review code\n\nQualifications:\nBS degree"
        result = _extract_duties(text)
        assert "Build APIs" in result
        assert "Review code" in result
        assert "BS degree" not in result   # qualifications 后的不应包含

    def test_extracts_what_you_will_do(self):
        text = "Overview\nWhat you'll do:\nDesign systems\nWrite tests\n\nRequirements:\nPython"
        result = _extract_duties(text)
        assert "Design systems" in result
        assert "Python" not in result

    def test_extracts_essential_functions(self):
        text = "Intro\nEssential Functions:\n- Task A\n- Task B\n\nEducation:"
        result = _extract_duties(text)
        assert "Task A" in result
        assert "Education:" not in result

    def test_returns_empty_when_no_duties_header(self):
        text = "Just a plain job description without any section headers."
        result = _extract_duties(text)
        assert result == ""


class TestExtractExperience:
    def test_uses_fallback_when_provided(self):
        result = _extract_experience("some text", "Entry level")
        assert result == "Entry level"

    def test_extracts_from_text_when_no_fallback(self):
        text = "Overview\nExperience: 3-5 years in software development\nSkills: Python"
        result = _extract_experience(text, "")
        assert "3-5 years" in result

    def test_returns_empty_when_nothing_found(self):
        result = _extract_experience("Just a job description.", "")
        assert result == ""


class TestClean:
    def test_clean_produces_jd_pool_row(self):
        raw = RawJD(
            source="dataset",
            job_title="  AI Engineer ",
            raw_html=(
                "Job descriptionWe are seeking an AI Engineer.\n"
                "Responsibilities:\n- Build RAG systems\n- Deploy models\n"
                "Pay: $50/hour\nBenefits:Full coverage\n"
                "Experience: 3-5 years\nWork Location: Remote"
            ),
            duties="",
            experience="",
        )
        row = clean(raw)
        assert row["source"] == "dataset"
        assert row["job_title"] == "AI Engineer"
        assert "Pay:" not in row["raw_text"]
        assert "Benefits:" not in row["raw_text"]
        assert "Build RAG systems" in row["duties"]
        assert "3-5 years" in row["experience"]
        assert row["status"] == "cleaned"
        assert row["crawled_at"] is not None
```

- [ ] **Step 2: 运行验证失败**

Run: `cd backend && pytest tests/test_cleaner.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'app.collect.cleaner'`

- [ ] **Step 3: 实现 cleaner.py**

```python
# backend/app/collect/cleaner.py
import re
from datetime import datetime, timezone
from app.collect.schema import RawJD

# ── 杂讯剥离 ────────────────────────────────────────────

NOISE_LINE_PATTERNS = [
    r"^(Pay|Salary|Compensation|Wage)\s*:",
    r"^\$[\d,.\s]+(.+?(hour|year|month|week|annum))",
    r"^(Expected\s+)?[Hh]ours?\s*:",
    r"^(Benefits?|Perks)\s*:",
    r"^Schedule\s*:",
    r"^(Work\s+)?[Ll]ocation\s*:",
    r"^Job\s+[Tt]ype\s*:",
    r"^\$[\d,.]+\s*[-–to]+\s*\$?[\d,.]+",
    r"^https?://\S+$",
]

FUSED_PREFIXES = [
    "Job description",
    "Job Description",
    "Job Summary",
    "Job summary",
    "About the job",
    "About this job",
]


def _fix_fused_prefix(text: str) -> str:
    """修复粘连前缀：'Job descriptionA leading...' → 'A leading...'"""
    for prefix in FUSED_PREFIXES:
        if text.startswith(prefix) and len(text) > len(prefix):
            next_char = text[len(prefix)]
            if next_char.isalpha() or (next_char.isascii() and not next_char.isspace()):
                text = text[len(prefix):]
                break
    return text


def _is_noise_line(line: str) -> bool:
    line = line.strip()
    if not line:
        return False
    for pat in NOISE_LINE_PATTERNS:
        if re.match(pat, line):
            return True
    return False


def _strip_noise(text: str) -> str:
    """剥离薪资/福利/工时/地点等杂讯行，修复粘连前缀。"""
    text = _fix_fused_prefix(text or "")
    lines = text.split("\n")
    kept = [ln for ln in lines if not _is_noise_line(ln)]
    return "\n".join(kept).strip()


# ── 职责提取 ────────────────────────────────────────────

DUTY_HEADER_PATTERN = re.compile(
    r"(?im)^(?:Key\s+)?Responsibilities?:?\s*$|"
    r"^Essential\s+Functions?:?\s*$|"
    r"^(?:Primary\s+)?Duties?:?\s*$|"
    r"^What\s+You'?ll\s+Do:?\s*$|"
    r"^Role\s*:?\s*$"
)

# 职责段结束标志：下一个标题行（全大写或常见标题）
SECTION_BOUNDARY_PATTERN = re.compile(
    r"(?im)^(?:Qualifications?|Requirements?|Education|Experience|Skills?|"
    r"About\s+(?:Us|the\s+Company)|Benefits?|Compensation|"
    r"We\s+(?:Are|Offer|Value)|How\s+to\s+Apply|"
    r"Equal\s+Opportunity|Our\s+Company)\s*:?"
)


def _extract_duties(text: str) -> str:
    """识别职责段落，截取至下一个标题或末尾。"""
    match = DUTY_HEADER_PATTERN.search(text or "")
    if not match:
        return ""
    start = match.end()
    remainder = text[start:]
    boundary = SECTION_BOUNDARY_PATTERN.search(remainder)
    if boundary:
        remainder = remainder[:boundary.start()]
    return remainder.strip()


# ── 经验提取 ────────────────────────────────────────────

EXPERIENCE_LINE_RE = re.compile(r"(?im)^Experience\s*:\s*(.+)$")


def _extract_experience(text: str, fallback: str) -> str:
    """列优先，空时正则回退。"""
    if fallback and fallback.strip():
        return fallback.strip()
    match = EXPERIENCE_LINE_RE.search(text or "")
    if match:
        return match.group(1).strip()
    return ""


# ── clean() 主函数 ─────────────────────────────────────

def clean(raw: RawJD) -> dict:
    text = raw.raw_html or ""
    return {
        "source": raw.source,
        "job_title": raw.job_title.strip(),
        "raw_text": _strip_noise(text),
        "duties": _extract_duties(text),
        "experience": _extract_experience(text, raw.experience),
        "crawled_at": datetime.now(timezone.utc),
        "status": "cleaned",
    }
```

- [ ] **Step 4: 运行验证通过**

Run: `cd backend && pytest tests/test_cleaner.py -v`
Expected: PASS（14 passed）

- [ ] **Step 5: Commit**

```bash
git add backend/app/collect/cleaner.py backend/tests/test_cleaner.py
git commit -m "feat(A-csv): medium-wash cleaner with noise stripping, duty and experience extraction"
```

---

## Task 3: CSV 数据集加载器（替换 planA JSONL loader）

**Files:**
- Create: `backend/app/collect/fetchers/__init__.py`
- Create: `backend/app/collect/fetchers/dataset.py`
- Test: `backend/tests/test_dataset_import.py`

**Interfaces:**
- Consumes: `RawJD`, `csv`
- Produces:
  - `load_csv_posting(path: str, limit: int = 100000) -> list[RawJD]`——读 postings.csv，采样 limit 行
  - `load_skill_map(skills_csv: str) -> dict[str, str]`——skill_abr → skill_name
  - `load_job_skills(job_skills_csv: str) -> dict[str, list[str]]`——job_id → [skill_abr, ...]

> **与 planA 差异**: planA Task 3 的 `load_dataset()` 读 JSONL。本任务用 `load_csv_posting()` 替代，读 CSV 并产出 RawJD（含 `job_id`、`raw_html`=description 原文）。

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_dataset_import.py
import csv
from app.collect.fetchers.dataset import load_csv_posting, load_skill_map, load_job_skills
from app.collect.schema import RawJD


class TestLoadCsvPosting:
    def test_loads_rows_as_rawjd(self, tmp_path):
        f = tmp_path / "postings.csv"
        f.write_text(
            "job_id,title,description,formatted_experience_level\n"
            "123,AI Engineer,We need an AI engineer.,Mid-Senior level\n"
            "456,Backend Dev,Build APIs.,\n",
            encoding="utf-8",
        )
        rows = load_csv_posting(str(f), limit=0)
        assert len(rows) == 2
        assert isinstance(rows[0], RawJD)
        assert rows[0].job_title == "AI Engineer"
        assert rows[0].source == "dataset"
        assert rows[0].raw_html == "We need an AI engineer."
        assert rows[0].experience == "Mid-Senior level"
        assert rows[0].job_id == "123"

    def test_respects_limit(self, tmp_path):
        f = tmp_path / "postings.csv"
        lines = ["job_id,title,description,formatted_experience_level\n"]
        for i in range(20):
            lines.append(f"{i},Job {i},Description {i},\n")
        f.write_text("".join(lines), encoding="utf-8")
        rows = load_csv_posting(str(f), limit=5)
        assert len(rows) == 5

    def test_skips_empty_title(self, tmp_path):
        f = tmp_path / "postings.csv"
        f.write_text(
            "job_id,title,description,formatted_experience_level\n"
            "1,,Empty title,\n"
            "2,Valid Job,Has description,\n",
            encoding="utf-8",
        )
        rows = load_csv_posting(str(f), limit=0)
        assert len(rows) == 1
        assert rows[0].job_title == "Valid Job"

    def test_handles_multiline_description(self, tmp_path):
        f = tmp_path / "postings.csv"
        f.write_text(
            'job_id,title,description,formatted_experience_level\n'
            '1,Engineer,"Line 1\nLine 2\nLine 3",Entry level\n',
            encoding="utf-8",
        )
        rows = load_csv_posting(str(f), limit=0)
        assert len(rows) == 1
        assert "Line 1" in rows[0].raw_html
        assert "Line 3" in rows[0].raw_html


class TestLoadSkillMap:
    def test_loads_abr_to_name(self, tmp_path):
        f = tmp_path / "skills.csv"
        f.write_text("skill_abr,skill_name\nPRJM,Project Management\nENG,Engineering\n", encoding="utf-8")
        m = load_skill_map(str(f))
        assert m == {"PRJM": "Project Management", "ENG": "Engineering"}


class TestLoadJobSkills:
    def test_loads_job_to_skill_list(self, tmp_path):
        f = tmp_path / "job_skills.csv"
        f.write_text("job_id,skill_abr\n100,PRJM\n100,ENG\n200,PRJM\n", encoding="utf-8")
        m = load_job_skills(str(f))
        assert m == {"100": ["PRJM", "ENG"], "200": ["PRJM"]}
```

- [ ] **Step 2: 运行验证失败**

Run: `cd backend && pytest tests/test_dataset_import.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'app.collect.fetchers.dataset'`

- [ ] **Step 3: 实现 dataset.py**

```python
# backend/app/collect/fetchers/dataset.py
import csv
from app.collect.schema import RawJD


def load_csv_posting(path: str, limit: int = 100000) -> list[RawJD]:
    """读取 postings.csv，逐行产出 RawJD。limit=0 表示全量。"""
    rows: list[RawJD] = []
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            title = (row.get("title") or "").strip()
            if not title:
                continue
            rows.append(RawJD(
                source="dataset",
                job_title=title,
                raw_html=row.get("description") or "",
                experience=(row.get("formatted_experience_level") or "").strip(),
                job_id=(row.get("job_id") or "").strip(),
            ))
            if limit > 0 and len(rows) >= limit:
                break
    return rows


def load_skill_map(skills_csv: str) -> dict[str, str]:
    """加载 skill_abr → skill_name 映射。"""
    mapping: dict[str, str] = {}
    with open(skills_csv, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            abr = (row.get("skill_abr") or "").strip()
            name = (row.get("skill_name") or "").strip()
            if abr and name:
                mapping[abr] = name
    return mapping


def load_job_skills(job_skills_csv: str) -> dict[str, list[str]]:
    """加载 job_id → [skill_abr, ...] 映射。"""
    mapping: dict[str, list[str]] = {}
    with open(job_skills_csv, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            job_id = (row.get("job_id") or "").strip()
            abr = (row.get("skill_abr") or "").strip()
            if job_id and abr:
                mapping.setdefault(job_id, []).append(abr)
    return mapping
```

- [ ] **Step 4: 运行验证通过**

Run: `cd backend && pytest tests/test_dataset_import.py -v`
Expected: PASS（6 passed）

- [ ] **Step 5: Commit**

```bash
git add backend/app/collect/fetchers/__init__.py backend/app/collect/fetchers/dataset.py backend/tests/test_dataset_import.py
git commit -m "feat(A-csv): csv dataset loader replacing jsonl, with skill mapping loaders"
```

---

## Task 4: 仓储批量写入（微调 planA save_rows）

**Files:**
- Create: `backend/app/collect/repository.py`
- Test: `backend/tests/test_collect_repo.py`

**Interfaces:**
- Consumes: `app.db.mysql.get_db`
- Produces: `build_insert_params(row: dict) -> dict`(不变)；`save_rows(db, rows: list[dict], batch_size: int = 1000) -> int`——批量 INSERT，返回写入条数

> **与 planA 差异**: planA Task 4 逐行 `db.execute()` + 单次 `db.commit()`。本任务改为每 1000 条一批 `db.execute()` + `db.commit()`，适应 10 万行场景。

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_collect_repo.py
from datetime import datetime, timezone
from app.collect.repository import build_insert_params, save_rows


def test_build_insert_params_maps_fields():
    row = {
        "source": "dataset", "job_title": "AI Engineer", "raw_text": "Build AI systems",
        "duties": "Design and implement", "experience": "3-5年",
        "quality": 0.8, "dup_group": "abc123",
        "crawled_at": datetime(2026, 7, 24, tzinfo=timezone.utc),
        "status": "cleaned",
    }
    p = build_insert_params(row)
    assert p["source"] == "dataset"
    assert p["job_title"] == "AI Engineer"
    assert p["raw_text"] == "Build AI systems"
    assert p["duties"] == "Design and implement"
    assert p["experience"] == "3-5年"
    assert p["quality"] == 0.8
    assert p["dup_group"] == "abc123"
    assert p["status"] == "cleaned"

def test_build_insert_params_defaults():
    row = {"raw_text": "x"}
    p = build_insert_params(row)
    assert p["source"] == ""
    assert p["quality"] == 0.0
    assert p["status"] == "cleaned"


class FakeDB:
    def __init__(self):
        self.saved = []
        self.committed = 0

    def execute(self, stmt, params=None):
        if params:
            self.saved.append(params)

    def commit(self):
        self.committed += 1


def test_save_rows_batches_commits():
    db = FakeDB()
    rows = [{"raw_text": f"jd_{i}"} for i in range(2500)]
    count = save_rows(db, rows, batch_size=1000)
    assert count == 2500
    assert len(db.saved) == 2500
    assert db.committed == 3   # 1000 + 1000 + 500 → 3 次 commit


def test_save_empty_rows():
    db = FakeDB()
    count = save_rows(db, [], batch_size=1000)
    assert count == 0
    assert db.committed == 0
```

- [ ] **Step 2: 运行验证失败**

Run: `cd backend && pytest tests/test_collect_repo.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'app.collect.repository'`

- [ ] **Step 3: 实现 repository.py**

```python
# backend/app/collect/repository.py
from sqlalchemy import text

INSERT_STMT = text(
    "INSERT INTO jd_pool (source, job_title, raw_text, duties, experience, "
    "quality, dup_group, crawled_at, status) VALUES "
    "(:source, :job_title, :raw_text, :duties, :experience, "
    ":quality, :dup_group, :crawled_at, :status)"
)


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


def save_rows(db, rows: list[dict], batch_size: int = 1000) -> int:
    """批量写入 jd_pool，每 batch_size 条 commit 一次。"""
    if not rows:
        return 0
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]
        for row in batch:
            db.execute(INSERT_STMT, build_insert_params(row))
        db.commit()
    return len(rows)
```

- [ ] **Step 4: 运行验证通过**

Run: `cd backend && pytest tests/test_collect_repo.py -v`
Expected: PASS（4 passed）

- [ ] **Step 5: Commit**

```bash
git add backend/app/collect/repository.py backend/tests/test_collect_repo.py
git commit -m "feat(A-csv): batch insert repository with configurable batch size"
```

---

## Task 5: 管道扩展（插入 enrich_skills）

**Files:**
- Create: `backend/app/collect/pipeline.py`
- Create: `backend/app/collect/fetchers/base.py`
- Create: `backend/app/collect/fetchers/github.py`
- Test: `backend/tests/test_pipeline.py`

**Interfaces:**
- Consumes: `cleaner`, `dedup`, `repository`, `RawJD`
- Produces:
  - `enrich_skills(rows: list[dict], job_skill_map: dict[str, list[str]], skill_map: dict[str, str], job_id_key: str = "_job_id") -> list[dict]`——通过 job_id join 技能，追加到 raw_text
  - `run_pipeline(db, raws, job_skill_map=None, skill_map=None) -> dict`——clean→enrich_skills→dedup→quality→save

> **与 planA 差异**: planA Task 5 的 `run_pipeline` 不含 `enrich_skills` 步骤，不接受 `job_skill_map`/`skill_map`。本任务扩展签名并在流程中插入技能补充步骤。`enrich_skills` 使用 `_job_id` 临时键传递 job_id（由 clean 阶段写入 row dict），完成后删除该键。

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_pipeline.py
from app.collect.pipeline import run_pipeline, enrich_skills
from app.collect.schema import RawJD


class FakeDB:
    def __init__(self):
        self.saved = []
        self.committed = 0

    def execute(self, stmt, params=None):
        if params:
            self.saved.append(params)

    def commit(self):
        self.committed += 1


class TestEnrichSkills:
    def test_appends_skill_names_to_raw_text(self):
        rows = [
            {"raw_text": "Build AI systems.", "_job_id": "100"},
            {"raw_text": "Manage projects.", "_job_id": "200"},
        ]
        job_skill_map = {"100": ["ENG", "PRJM"], "200": ["MGMT"]}
        skill_map = {"ENG": "Engineering", "PRJM": "Project Management", "MGMT": "Management"}
        enriched = enrich_skills(rows, job_skill_map, skill_map)
        assert "Engineering" in enriched[0]["raw_text"]
        assert "Project Management" in enriched[0]["raw_text"]
        assert "Management" in enriched[1]["raw_text"]

    def test_removes_job_id_key_after_enrich(self):
        rows = [{"raw_text": "x", "_job_id": "100"}]
        job_skill_map = {"100": ["ENG"]}
        skill_map = {"ENG": "Engineering"}
        enriched = enrich_skills(rows, job_skill_map, skill_map)
        assert "_job_id" not in enriched[0]

    def test_skips_when_job_id_not_found(self):
        rows = [{"raw_text": "x", "_job_id": "999"}]
        enriched = enrich_skills(rows, {}, {})
        assert enriched[0]["raw_text"] == "x"

    def test_skips_when_no_job_id_key(self):
        rows = [{"raw_text": "x"}]
        enriched = enrich_skills(rows, {}, {})
        assert enriched[0]["raw_text"] == "x"


class TestRunPipeline:
    def test_pipeline_cleans_dedups_saves(self):
        db = FakeDB()
        raws = [
            RawJD(source="github", job_title="AI工程师",
                  raw_html="<p>负责 RAG 开发 熟悉 Python 的候选人</p>", experience="3-5年"),
            RawJD(source="dataset", job_title="AI工程师",
                  raw_html="负责RAG开发,熟悉Python的候选人", experience="3-5年"),
        ]
        stats = run_pipeline(db, raws)
        assert stats["saved"] == 2
        assert db.saved[0]["dup_group"] == db.saved[1]["dup_group"]
        assert db.saved[0]["quality"] > 0

    def test_pipeline_with_skill_enrichment(self):
        db = FakeDB()
        raws = [
            RawJD(source="dataset", job_title="AI Engineer",
                  raw_html="Build AI systems.", job_id="100"),
        ]
        job_skill_map = {"100": ["ENG"]}
        skill_map = {"ENG": "Engineering"}
        stats = run_pipeline(db, raws, job_skill_map=job_skill_map, skill_map=skill_map)
        assert stats["saved"] == 1
        assert "Engineering" in db.saved[0]["raw_text"]
```

- [ ] **Step 2: 运行验证失败**

Run: `cd backend && pytest tests/test_pipeline.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'app.collect.pipeline'`

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
        return []
```

```python
# backend/app/collect/pipeline.py
from app.collect.cleaner import clean
from app.collect.dedup import assign_dup_groups, quality_score
from app.collect.repository import save_rows


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


def run_pipeline(
    db,
    raws,
    job_skill_map: dict[str, list[str]] | None = None,
    skill_map: dict[str, str] | None = None,
) -> dict:
    rows = []
    for r in raws:
        row = clean(r)
        if r.job_id:
            row["_job_id"] = r.job_id  # 临时传递，enrich 后删除
        rows.append(row)

    if job_skill_map and skill_map:
        rows = enrich_skills(rows, job_skill_map, skill_map)

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
Expected: PASS（4 passed）

- [ ] **Step 5: Commit**

```bash
git add backend/app/collect/fetchers/base.py backend/app/collect/fetchers/github.py backend/app/collect/pipeline.py backend/tests/test_pipeline.py
git commit -m "feat(A-csv): pipeline with skill enrichment step"
```

---

## Task 6: CLI 入口（import_csv.py）

**Files:**
- Create: `backend/app/collect/import_csv.py`

**Interfaces:**
- Consumes: `load_csv_posting`, `load_job_skills`, `load_skill_map`, `run_pipeline`, `get_db`
- Produces: `python -m app.collect.import_csv --csv ... --job-skills ... --skills-map ...` CLI

> **用途**: C 拿到 CSV 文件后，一行命令灌入 jd_pool。默认采样 10 万行。

- [ ] **Step 1: 实现 import_csv.py（无独立测试，由 Task 7 集成测试覆盖）**

```python
# backend/app/collect/import_csv.py
"""CLI 入口：将 LinkedIn 公开数据集 CSV 导入 jd_pool。

用法:
  python -m app.collect.import_csv \
      --csv data/archive/postings.csv \
      --job-skills data/archive/jobs/job_skills.csv \
      --skills-map data/archive/mappings/skills.csv \
      --limit 100000
"""
import argparse
import sys
import time
from app.db.mysql import get_db
from app.collect.fetchers.dataset import load_csv_posting, load_job_skills, load_skill_map
from app.collect.pipeline import run_pipeline


def main():
    parser = argparse.ArgumentParser(description="导入 LinkedIn CSV 数据集到 jd_pool")
    parser.add_argument("--csv", required=True, help="postings.csv 路径")
    parser.add_argument("--job-skills", help="job_skills.csv 路径（可选，用于技能补充）")
    parser.add_argument("--skills-map", help="skills.csv 路径（可选，用于技能名映射）")
    parser.add_argument("--limit", type=int, default=100000,
                        help="导入行数上限，0=全量（默认 100000）")
    args = parser.parse_args()

    t0 = time.time()

    # 1. 加载技能映射（可选）
    job_skill_map = {}
    skill_map = {}
    if args.job_skills and args.skills_map:
        print(f"Loading skill mappings...")
        skill_map = load_skill_map(args.skills_map)
        job_skill_map = load_job_skills(args.job_skills)
        print(f"  {len(skill_map)} skill types, {len(job_skill_map)} jobs with skills")

    # 2. 加载 CSV
    print(f"Loading CSV from {args.csv} (limit={args.limit or 'all'})...")
    raws = load_csv_posting(args.csv, limit=args.limit)
    print(f"  {len(raws)} rows loaded")

    # 3. 跑管道
    print("Running pipeline (clean → enrich → dedup → save)...")
    db = next(get_db())
    try:
        stats = run_pipeline(
            db, raws,
            job_skill_map=job_skill_map if job_skill_map else None,
            skill_map=skill_map if skill_map else None,
        )
        elapsed = time.time() - t0
        print(f"Done. {stats['saved']} rows saved, {stats['groups']} dup groups, "
              f"{elapsed:.1f}s elapsed")
    finally:
        db.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 验证模块可执行**

Run: `cd backend && python -m app.collect.import_csv --help`
Expected: 显示 argparse 帮助信息

- [ ] **Step 3: Commit**

```bash
git add backend/app/collect/import_csv.py
git commit -m "feat(A-csv): cli entry point for csv to jd_pool import"
```

---

## Task 7: 集成验证（CSV → jd_pool 端到端）

**Files:**
- Create: `backend/tests/test_collect_integration.py`

**Interfaces:**
- Consumes: `load_csv_posting`, `run_pipeline`, `get_db`

> **与 planA 差异**: planA Task 6 的测试用 JSONL 文件。本任务用真实 CSV 格式的临时文件。

- [ ] **Step 1: 写集成测试**

```python
# backend/tests/test_collect_integration.py
import csv
import pytest
from sqlalchemy import text
from app.db.mysql import get_db
from app.collect.fetchers.dataset import load_csv_posting, load_skill_map, load_job_skills
from app.collect.pipeline import run_pipeline

pytestmark = pytest.mark.integration


def test_csv_to_jd_pool_via_pipeline(tmp_path):
    """端到端：CSV → RawJD → clean → dedup → jd_pool"""
    # 准备 CSV
    postings_csv = tmp_path / "postings.csv"
    with open(postings_csv, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["job_id", "title", "description", "formatted_experience_level"])
        w.writerow(["1", "AI应用工程师", "Job description负责 RAG 与 LLM 应用开发", "3-5年"])
        w.writerow(["2", "后端工程师", "We need a backend developer.", "Entry level"])

    # 准备 skills
    skills_csv = tmp_path / "skills.csv"
    with open(skills_csv, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["skill_abr", "skill_name"])
        w.writerow(["ENG", "Engineering"])
        w.writerow(["PRJM", "Project Management"])

    # 准备 job_skills
    job_skills_csv = tmp_path / "job_skills.csv"
    with open(job_skills_csv, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["job_id", "skill_abr"])
        w.writerow(["1", "ENG"])
        w.writerow(["1", "PRJM"])

    db = next(get_db())
    try:
        # 清理旧数据
        db.execute(text("DELETE FROM jd_pool WHERE source='dataset'"))
        db.commit()

        # 加载
        raws = load_csv_posting(str(postings_csv), limit=0)
        assert len(raws) == 2

        skill_map = load_skill_map(str(skills_csv))
        job_skill_map = load_job_skills(str(job_skills_csv))

        # 管道
        stats = run_pipeline(db, raws, job_skill_map=job_skill_map, skill_map=skill_map)
        assert stats["saved"] == 2

        # 验证 jd_pool
        cnt = db.execute(text(
            "SELECT COUNT(*) FROM jd_pool WHERE source='dataset' AND status='cleaned'"
        )).scalar()
        assert cnt == 2

        # 验证技能补充生效
        text_with_skills = db.execute(text(
            "SELECT raw_text FROM jd_pool WHERE job_title='AI应用工程师'"
        )).scalar()
        assert "Engineering" in text_with_skills
        assert "Project Management" in text_with_skills

        # 验证清洗：粘连前缀已修复
        assert "Job description" not in text_with_skills
        assert "负责 RAG" in text_with_skills
    finally:
        db.close()
```

- [ ] **Step 2: 起库运行**

Run: `docker-compose up -d --wait && cd backend && pytest tests/test_collect_integration.py -v -m integration`
Expected: PASS——2 条 CSV 数据经过完整管道进入 `jd_pool`，技能已补充，前缀已修复

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_collect_integration.py
git commit -m "test(A-csv): csv to jd_pool end-to-end integration test"
```

---

## Task 8: 全量测试与采样冒烟

**Files:**
- 无新增（验证任务）

- [ ] **Step 1: 跑全部单元测试（排除集成）**

Run: `cd backend && pytest -v -m "not integration"`
Expected: 全部 PASS（含 plan0 存量 + 本计划新增的 cleaner/dataset/repo/pipeline）

- [ ] **Step 2: 起库跑集成测试**

Run: `docker-compose up -d --wait && cd backend && pytest -v -m integration`
Expected: 全部 PASS（含 plan0 存量 + 本计划 csv integration）

- [ ] **Step 3: 真实 CSV 采样冒烟**

如果 CSV 文件已就位：
```bash
cd backend && python -m app.collect.import_csv \
    --csv ../docs/originalfile/archive/postings.csv \
    --job-skills ../docs/originalfile/archive/jobs/job_skills.csv \
    --skills-map ../docs/originalfile/archive/mappings/skills.csv \
    --limit 1000
```
Expected: `Done. 1000 rows saved, ...`

- [ ] **Step 4: Commit（标记 CSV 扩展完成）**

```bash
git add -A
git commit -m "chore(A-csv): csv import pipeline complete, all tests green"
```

---

## 自审

- **覆盖设计文档**: schema 扩展 ✓ 中洗 logic ✓ CSV loader ✓ 批量 insert ✓ enrich_skills ✓ CLI ✓ 集成测试 ✓
- **与 planA 关系**: Task 2 (dedup) 不变 ✓；Task 1/3/4/5 均有明确差异标注 ✓；Task 6 改写为 CSV 版本 ✓
- **无 TBD**: 所有函数有完整实现代码，所有测试有具体断言
- **类型一致**: RawJD 新字段通过默认值保持向后兼容；`run_pipeline` 新增可选参数不破坏 planA 原有调用
- **契约不变**: jd_pool 列无增删改，C 的查询 `WHERE status='cleaned'` 完全兼容

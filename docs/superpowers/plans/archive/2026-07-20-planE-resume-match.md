# 计划 E — 简历解析 + 人岗匹配 + 系统整合 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现简历解析(PDF/DOCX 必做,图片走阈值决策)、人岗匹配(加权+向量,B主线)、差距分析与岗位路径推荐,并负责端到端 demo 闭环整合。

**Architecture:** 简历文件 → 文本提取(PyMuPDF/docx,复杂排版走多模态兜底)→ LLM 约束抽取技能(复用C的抽取思路)→ 归一到 skill_dict → 与 job_skill 权重做加权匹配 + embedding 相似度 → 差距/路径。

**Tech Stack:** Python 3.11, PyMuPDF, python-docx, OpenAI(计划0 client), numpy, FastAPI, pytest

**依赖:** 计划 0(契约+llm+normalizer);计划 C(job_skill 权重、skill_dict)。job_skill 可用 Mock 先行。

## Global Constraints

- 复用计划0:`llm.{extract_json,extract_json_with_image,embed}`, `normalizer.*`, `get_db`, `ok`
- 简历技能归一到 `skill_dict.canonical`(与C同一词典,保证匹配对齐)
- **必做**:PDF(文本层/复杂排版分流)+ DOCX;图片格式走"统计分布→阈值决策"闸门,不预先投入(DR-5 同源)
- **不做细粒度能力等级匹配(DR-1)**
- **路径推荐不输出"预计X个月"等无依据数字(DR-2)**
- 不支持格式:返回明确 BizError,前端提示上传 PDF/DOCX
- TDD;文件解析用小样本 fixture;LLM mock;每任务 commit

---

## 文件结构(本计划创建)

```
backend/app/resume/
  __init__.py
  parser.py        # 文件 → 文本(PDF/DOCX + 多模态兜底判定)
  extractor.py     # 文本 → 归一技能(复用C约束抽取)
  matcher.py       # 人岗匹配:加权 + 向量 + 差距
  pathfinder.py    # 岗位路径推荐(无编造数字)
  router.py        # /resume/analyze /match
backend/tests/
  test_resume_parser.py
  test_resume_extractor.py
  test_matcher.py
  test_pathfinder.py
  test_resume_router.py
```

---

## Task 1: 简历文件解析(格式分流 + 多模态兜底判定)

**Files:**
- Create: `backend/app/resume/__init__.py`
- Create: `backend/app/resume/parser.py`
- Test: `backend/tests/test_resume_parser.py`

**Interfaces:**
- Consumes: PyMuPDF(fitz), python-docx
- Produces:
  - `detect_format(filename: str) -> str`——返回 `pdf|docx|image|unsupported`
  - `extract_text(content: bytes, fmt: str) -> str`——提取文本
  - `needs_vision_fallback(text: str) -> bool`——文本过短/疑似乱序 → 需多模态兜底

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_resume_parser.py
import pytest
from app.resume.parser import detect_format, needs_vision_fallback

def test_detect_format():
    assert detect_format("resume.pdf") == "pdf"
    assert detect_format("cv.DOCX") == "docx"
    assert detect_format("scan.png") == "image"
    assert detect_format("a.txt") == "unsupported"

def test_needs_vision_fallback_on_short_text():
    assert needs_vision_fallback("") is True
    assert needs_vision_fallback("张三 15年 xx") is True     # 过短
    assert needs_vision_fallback("张三 " * 50) is False       # 足够长
```

- [ ] **Step 2: 运行验证失败**

Run: `cd backend && pytest tests/test_resume_parser.py -v`
Expected: FAIL,`ModuleNotFoundError: No module named 'app.resume.parser'`

- [ ] **Step 3: 实现 parser.py**

```python
# backend/app/resume/parser.py
import io
from app.response import BizError

def detect_format(filename: str) -> str:
    low = filename.lower()
    if low.endswith(".pdf"): return "pdf"
    if low.endswith(".docx"): return "docx"
    if low.endswith((".png", ".jpg", ".jpeg")): return "image"
    return "unsupported"

def needs_vision_fallback(text: str) -> bool:
    # 文本层缺失或过短(复杂排版/扫描件)→ 走多模态
    return len(text.strip()) < 80

def extract_text(content: bytes, fmt: str) -> str:
    if fmt == "pdf":
        import fitz
        doc = fitz.open(stream=content, filetype="pdf")
        return "\n".join(page.get_text() for page in doc)
    if fmt == "docx":
        import docx
        d = docx.Document(io.BytesIO(content))
        return "\n".join(p.text for p in d.paragraphs)
    if fmt == "image":
        return ""   # 图片无文本层,直接走多模态
    raise BizError(4100, "不支持的简历格式,请上传 PDF 或 DOCX")
```

在 `backend/requirements.txt` 追加:
```
PyMuPDF==1.24.10
python-docx==1.1.2
```

- [ ] **Step 4: 运行验证通过**

Run: `cd backend && pytest tests/test_resume_parser.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/resume/__init__.py backend/app/resume/parser.py backend/tests/test_resume_parser.py backend/requirements.txt
git commit -m "feat(E): resume file parser with format detection and vision fallback flag"
```

---

## Task 2: 简历技能抽取(归一,复用约束抽取)

**Files:**
- Create: `backend/app/resume/extractor.py`
- Test: `backend/tests/test_resume_extractor.py`

**Interfaces:**
- Consumes: `llm.extract_json`, `llm.extract_json_with_image`, `normalizer.normalize`
- Produces:
  - `extract_resume_skills(text: str, alias_map, skill_id_map) -> list[SkillItem]`
  - `extract_resume_skills_from_image(image_b64: str, alias_map, skill_id_map) -> list[SkillItem]`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_resume_extractor.py
from unittest.mock import patch
from app.resume import extractor

ALIAS = {"python": "Python", "docker": "Docker", "k8s": "Kubernetes"}
SKILL_ID = {"Python": 1, "Docker": 2, "Kubernetes": 3}

def test_extract_normalizes_resume_skills():
    fake = {"skills": [{"name": "python"}, {"name": "docker"}, {"name": "COBOL"}]}
    with patch.object(extractor.llm, "extract_json", return_value=fake):
        skills = extractor.extract_resume_skills("...", ALIAS, SKILL_ID)
    names = {s.name for s in skills}
    assert names == {"Python", "Docker"}   # COBOL 未命中词典被丢弃
```

- [ ] **Step 2: 运行验证失败**

Run: `cd backend && pytest tests/test_resume_extractor.py -v`
Expected: FAIL,`ModuleNotFoundError: No module named 'app.resume.extractor'`

- [ ] **Step 3: 实现 extractor.py**

```python
# backend/app/resume/extractor.py
from app.llm import client as llm
from app.skills.normalizer import normalize
from app.models.schemas import SkillItem

_SCHEMA = '{"skills": [{"name": str}], "experience": [{"company": str, "years": str}]}'

def _to_skill_items(raw: dict, alias_map, skill_id_map) -> list[SkillItem]:
    items = []
    for s in raw.get("skills", []):
        canon = normalize(s.get("name", ""), alias_map)
        if not canon or canon not in skill_id_map:
            continue
        items.append(SkillItem(skill_id=skill_id_map[canon], name=canon))
    return items

def extract_resume_skills(text: str, alias_map, skill_id_map) -> list[SkillItem]:
    candidates = list(skill_id_map.keys())
    prompt = (f"从简历中抽取候选人掌握的技能,只能从候选表选择: {candidates}\n简历:\n{text}")
    raw = llm.extract_json(prompt, _SCHEMA)
    return _to_skill_items(raw, alias_map, skill_id_map)

def extract_resume_skills_from_image(image_b64: str, alias_map, skill_id_map) -> list[SkillItem]:
    candidates = list(skill_id_map.keys())
    prompt = f"识别这张简历图片中候选人掌握的技能,只能从候选表选择: {candidates}"
    raw = llm.extract_json_with_image(prompt, image_b64)
    return _to_skill_items(raw, alias_map, skill_id_map)
```

- [ ] **Step 4: 运行验证通过**

Run: `cd backend && pytest tests/test_resume_extractor.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/resume/extractor.py backend/tests/test_resume_extractor.py
git commit -m "feat(E): resume skill extraction with normalization and vision"
```

---

## Task 3: 人岗匹配算法(加权 + 差距)

**Files:**
- Create: `backend/app/resume/matcher.py`
- Test: `backend/tests/test_matcher.py`

**Interfaces:**
- Consumes: 无外部(纯计算)
- Produces:
  - `compute_match(candidate_skills: list[str], job_skills: list[dict]) -> dict`——`job_skills` 为 `[{"name","weight"}]`;返回 `{score:int, matched:[str], missing:[str]}`;score = 命中技能权重和 / 总权重 * 100

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_matcher.py
from app.resume.matcher import compute_match

JOB = [{"name": "Python", "weight": 0.2}, {"name": "LLM", "weight": 0.3},
       {"name": "RAG", "weight": 0.2}, {"name": "Docker", "weight": 0.1},
       {"name": "Linux", "weight": 0.1}, {"name": "数学", "weight": 0.1}]

def test_partial_match_score():
    out = compute_match(["Python", "Docker"], JOB)
    # 命中权重 0.2+0.1=0.3,总权重1.0 → 30
    assert out["score"] == 30
    assert set(out["matched"]) == {"Python", "Docker"}
    assert "RAG" in out["missing"] and "LLM" in out["missing"]

def test_full_match():
    out = compute_match(["Python", "LLM", "RAG", "Docker", "Linux", "数学"], JOB)
    assert out["score"] == 100
    assert out["missing"] == []

def test_empty_candidate():
    out = compute_match([], JOB)
    assert out["score"] == 0
```

- [ ] **Step 2: 运行验证失败**

Run: `cd backend && pytest tests/test_matcher.py -v`
Expected: FAIL,`ModuleNotFoundError: No module named 'app.resume.matcher'`

- [ ] **Step 3: 实现 matcher.py**

```python
# backend/app/resume/matcher.py
def compute_match(candidate_skills: list[str], job_skills: list[dict]) -> dict:
    cand = set(candidate_skills)
    total_w = sum(s.get("weight", 0) for s in job_skills) or 1.0
    matched, missing, hit_w = [], [], 0.0
    for s in job_skills:
        if s["name"] in cand:
            matched.append(s["name"])
            hit_w += s.get("weight", 0)
        else:
            missing.append(s["name"])
    score = round(hit_w / total_w * 100)
    return {"score": score, "matched": matched, "missing": missing}
```

- [ ] **Step 4: 运行验证通过**

Run: `cd backend && pytest tests/test_matcher.py -v`
Expected: PASS(3 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/app/resume/matcher.py backend/tests/test_matcher.py
git commit -m "feat(E): weighted person-job matching with gap"
```

---

## Task 4: 岗位路径推荐(无编造数字)

**Files:**
- Create: `backend/app/resume/pathfinder.py`
- Test: `backend/tests/test_pathfinder.py`

**Interfaces:**
- Consumes: 无
- Produces: `build_path(current_job: str, target_job: str, missing_skills: list[str]) -> list[dict]`——返回 `[{"from","to","gap":[str]}]`,不含任何时间估算数字(DR-2)

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_pathfinder.py
from app.resume.pathfinder import build_path

def test_path_has_gap_no_time_estimate():
    path = build_path("后端工程师", "AI应用工程师", ["LLM", "RAG", "Agent"])
    assert path == [{"from": "后端工程师", "to": "AI应用工程师", "gap": ["LLM", "RAG", "Agent"]}]
    # 断言无任何时间字段(DR-2)
    assert all("months" not in step and "duration" not in step and "预计" not in str(step) for step in path)

def test_path_no_current_job():
    path = build_path(None, "AI应用工程师", ["RAG"])
    assert path[0]["from"] is None and path[0]["to"] == "AI应用工程师"
```

- [ ] **Step 2: 运行验证失败**

Run: `cd backend && pytest tests/test_pathfinder.py -v`
Expected: FAIL,`ModuleNotFoundError: No module named 'app.resume.pathfinder'`

- [ ] **Step 3: 实现 pathfinder.py**

```python
# backend/app/resume/pathfinder.py
def build_path(current_job, target_job: str, missing_skills: list[str]) -> list[dict]:
    """给出从当前岗位到目标岗位的技能差距路径。
    刻意不输出学习时长等无数据支撑的估算(DR-2)。"""
    return [{"from": current_job, "to": target_job, "gap": list(missing_skills)}]
```

- [ ] **Step 4: 运行验证通过**

Run: `cd backend && pytest tests/test_pathfinder.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/resume/pathfinder.py backend/tests/test_pathfinder.py
git commit -m "feat(E): job path recommendation without fabricated durations"
```

---

## Task 5: 简历/匹配路由(/resume/analyze, /match)

**Files:**
- Create: `backend/app/resume/router.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_resume_router.py`

**Interfaces:**
- Consumes: parser, extractor, matcher, pathfinder, `get_db`, `ok`, `MatchResult`
- Produces: `router`;`POST /resume/analyze`(multipart);`POST /match`(resume_id, job_id?)

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_resume_router.py
import io
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app
from app.models.schemas import SkillItem

client = TestClient(app)

def test_analyze_rejects_unsupported_format():
    r = client.post("/resume/analyze",
                    files={"file": ("bad.txt", io.BytesIO(b"hi"), "text/plain")})
    assert r.status_code == 200
    assert r.json()["code"] == 4100   # BizError 不支持格式

def test_analyze_pdf_returns_skills():
    with patch("app.resume.router.extract_text", return_value="张三 " * 60), \
         patch("app.resume.router._load_maps", return_value=({}, {})), \
         patch("app.resume.router.extract_resume_skills",
               return_value=[SkillItem(skill_id=1, name="Python")]), \
         patch("app.resume.router._store_resume", return_value=99):
        r = client.post("/resume/analyze",
                        files={"file": ("cv.pdf", io.BytesIO(b"%PDF-1.4 fake"), "application/pdf")})
    body = r.json()
    assert body["code"] == 0
    assert body["data"]["resume_id"] == 99
    assert body["data"]["skills"][0]["name"] == "Python"
```

- [ ] **Step 2: 运行验证失败**

Run: `cd backend && pytest tests/test_resume_router.py -v`
Expected: FAIL,`ModuleNotFoundError: No module named 'app.resume.router'`

- [ ] **Step 3: 实现 router.py**

```python
# backend/app/resume/router.py
import base64, json
from datetime import datetime
from fastapi import APIRouter, Depends, UploadFile, File
from sqlalchemy import text
from app.db.mysql import get_db
from app.response import ok, BizError
from app.resume.parser import detect_format, extract_text, needs_vision_fallback
from app.resume.extractor import extract_resume_skills, extract_resume_skills_from_image
from app.resume.matcher import compute_match
from app.resume.pathfinder import build_path

router = APIRouter(tags=["resume"])

def _load_maps(db):
    from app.extraction.repository import load_alias_and_id_maps
    return load_alias_and_id_maps(db)

def _store_resume(db, fmt: str, skills: list) -> int:
    res = db.execute(text(
        "INSERT INTO resume (raw_format, skills, experience, parsed_at) "
        "VALUES (:f, :s, :e, :t)"),
        {"f": fmt, "s": json.dumps([sk.model_dump() for sk in skills], ensure_ascii=False),
         "e": json.dumps([]), "t": datetime.utcnow()})
    db.commit()
    return res.lastrowid

@router.post("/resume/analyze")
async def analyze(file: UploadFile = File(...), db=Depends(get_db)):
    fmt = detect_format(file.filename)
    if fmt == "unsupported":
        raise BizError(4100, "不支持的简历格式,请上传 PDF 或 DOCX")
    content = await file.read()
    alias_map, skill_id_map = _load_maps(db)
    text_ = extract_text(content, fmt)
    if fmt == "image" or needs_vision_fallback(text_):
        b64 = base64.b64encode(content).decode()
        skills = extract_resume_skills_from_image(b64, alias_map, skill_id_map)
    else:
        skills = extract_resume_skills(text_, alias_map, skill_id_map)
    rid = _store_resume(db, fmt, skills)
    return ok({"resume_id": rid, "raw_format": fmt,
               "skills": [s.model_dump() for s in skills], "experience": []})

@router.post("/match")
def match(resume_id: int, job_id: int | None = None, db=Depends(get_db)):
    row = db.execute(text("SELECT skills FROM resume WHERE id=:id"), {"id": resume_id}).fetchone()
    if not row:
        raise BizError(4101, "简历不存在")
    cand = [s["name"] for s in json.loads(row[0])]
    # 取目标岗位:指定 job_id 则取之,否则遍历所有岗位取最高分
    jobs = db.execute(text("SELECT id, job_name, skills FROM job_skill")).fetchall()
    if job_id is not None:
        jobs = [j for j in jobs if j[0] == job_id]
    best = None
    for jid, jname, jskills in jobs:
        js = [{"name": s["name"], "weight": s.get("weight", 0)} for s in json.loads(jskills)]
        m = compute_match(cand, js)
        if best is None or m["score"] > best["score"]:
            best = {**m, "target_job": jname}
    if best is None:
        raise BizError(4102, "无可匹配岗位")
    path = build_path(None, best["target_job"], best["missing"])
    return ok({"target_job": best["target_job"], "score": best["score"],
               "matched": best["matched"], "missing": best["missing"], "path": path})
```

- [ ] **Step 4: 挂载 + 验证通过**

在 `main.py` 添加:
```python
from app.resume.router import router as resume_router
app.include_router(resume_router)
```
Run: `cd backend && pytest tests/test_resume_router.py -v`
Expected: PASS(2 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/app/resume/router.py backend/app/main.py backend/tests/test_resume_router.py
git commit -m "feat(E): resume analyze and match endpoints"
```

---

## Task 6: 端到端整合冒烟(E 系统整合责任)

**Files:**
- Test: `backend/tests/test_e2e_smoke.py`

**Interfaces:**
- Consumes: 全链路(需计划0+C+E 就绪 + docker + 种子数据)

- [ ] **Step 1: 写 e2e 冒烟测试(mock LLM,真库)**

```python
# backend/tests/test_e2e_smoke.py
import io, json
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app
from app.db.mysql import get_db
from sqlalchemy import text

pytestmark = pytest.mark.integration
client = TestClient(app)

def _prep_job_and_skills():
    db = next(get_db())
    from app.extraction.skill_seed import seed_skills, DEFAULT_SEED
    seed_skills(db, DEFAULT_SEED)
    db.execute(text("DELETE FROM job_skill"))
    db.execute(text(
        "INSERT INTO job_skill (jd_id, job_name, level, skills, duties, extracted_at) "
        "VALUES (1,'AI应用工程师','高级',:s,'',NOW())"),
        {"s": json.dumps([{"skill_id":1,"name":"Python","weight":0.5},
                          {"skill_id":5,"name":"RAG","weight":0.5}])})
    db.commit()

def test_upload_then_match():
    _prep_job_and_skills()
    from app.models.schemas import SkillItem
    with patch("app.resume.router.extract_text", return_value="张三 "*60), \
         patch("app.resume.router.extract_resume_skills",
               return_value=[SkillItem(skill_id=1, name="Python")]):
        r1 = client.post("/resume/analyze",
                         files={"file": ("cv.pdf", io.BytesIO(b"%PDF fake"), "application/pdf")})
    rid = r1.json()["data"]["resume_id"]
    r2 = client.post(f"/match?resume_id={rid}")
    body = r2.json()
    assert body["code"] == 0
    assert body["data"]["target_job"] == "AI应用工程师"
    assert body["data"]["score"] == 50           # 命中 Python(0.5)/总1.0
    assert "RAG" in body["data"]["missing"]
    assert body["data"]["path"][0]["gap"] == ["RAG"]
```

- [ ] **Step 2: 起库运行**

Run: `docker-compose up -d --wait && cd backend && pytest tests/test_e2e_smoke.py -v -m integration`
Expected: PASS——上传简历→匹配→出分数+缺失+路径,闭环打通

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_e2e_smoke.py
git commit -m "test(E): end-to-end smoke upload-to-match closed loop"
```

---

## 自审说明
- 覆盖 spec:PDF/DOCX解析+多模态兜底✓ 阈值决策(needs_vision_fallback)✓ 加权匹配✓ 差距✓ 路径推荐(无数字DR-2)✓ 舍弃等级匹配(DR-1)✓ 端到端整合✓
- 类型一致:`SkillItem/MatchResult` 来自计划0;`_load_maps` 复用计划C `load_alias_and_id_maps`
- 与C共用 skill_dict 保证归一对齐;job_skill 权重字段结构与C `save_job_skill` 一致
- 图片格式阈值决策:先实现兜底路径(image→多模态),实际占比统计在测试阶段做,占比低则不额外优化

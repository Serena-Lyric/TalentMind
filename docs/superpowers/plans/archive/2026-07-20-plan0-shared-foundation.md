# 计划 0 — 共享地基 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 搭建全队共享地基——docker 环境、FastAPI 骨架、三库连接、冻结的数据契约、skill_dict 归一、LLM 客户端封装,解锁 A~E 五人并行开发。

**Architecture:** FastAPI 单体后端,统一 `{code,message,data}` 响应与异常中间件;MySQL(SQLAlchemy)+Neo4j(driver)+Redis 三库连接注入;Pydantic 模型 + SQL DDL 作为跨人冻结契约;LLM 客户端封装文本/多模态/embedding 三接口 + 重试。

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.x, neo4j-driver, redis-py, Pydantic v2, pytest, OpenAI SDK, docker-compose

## Global Constraints

- Python 版本:3.11(所有 `python_requires >= 3.11`)
- 前端:Vue3 + TypeScript(本计划不涉及,契约供 B 消费)
- LLM:OpenAI `gpt-4o`(文本+多模态)、`text-embedding-3-small`(向量)
- **OpenAI 访问**:base_url 走环境变量 `OPENAI_BASE_URL`(默认官方,可指向代理/中转),不硬编码
- **API Key 与所有密钥**:仅经 `.env` + Pydantic Settings 读取,禁止进代码库;`.env` 必须在 `.gitignore`
- 统一响应格式:`{"code": int, "message": str, "data": any}`,`code=0` 表示成功
- 技能名一律归一到 `skill_dict.canonical`
- 测试框架:pytest;每个任务 TDD,先写失败测试
- 提交:每个任务末尾 commit,message 用 `feat:`/`test:`/`chore:` 前缀

---

## 文件结构(本计划创建/锁定)

```
backend/
  app/
    __init__.py
    main.py                 # FastAPI 实例 + 路由挂载 + 中间件注册
    config.py               # Pydantic Settings(读 .env)
    response.py             # 统一响应包裹 + 业务异常类
    middleware.py           # 全局异常中间件
    db/
      __init__.py
      mysql.py              # SQLAlchemy engine/session 依赖
      neo4j.py              # Neo4j driver 依赖
      redis.py              # Redis 客户端依赖
    models/
      __init__.py
      schemas.py            # 冻结的 Pydantic 契约模型
    contracts/
      ddl.sql               # 冻结的 MySQL 表 DDL
    skills/
      __init__.py
      normalizer.py         # skill_dict 归一函数(全队共用)
    llm/
      __init__.py
      client.py             # LLM 三接口封装 + 重试
  tests/
    test_response.py
    test_middleware.py
    test_config.py
    test_normalizer.py
    test_llm_client.py
  requirements.txt
  .env.example
  .gitignore
docker-compose.yml          # MySQL + Neo4j + Redis
```

**责任边界**:本计划只锁定契约与地基,不实现业务逻辑(抽取/图谱/匹配分别属计划 C/D/E)。

---

## Task 1: 项目脚手架与 docker-compose 环境

**Files:**
- Create: `docker-compose.yml`
- Create: `backend/requirements.txt`
- Create: `backend/.env.example`
- Create: `backend/.gitignore`
- Create: `backend/app/__init__.py`

**Interfaces:**
- Consumes: 无(首个任务)
- Produces: 三库服务(MySQL:3306 / Neo4j:7687,7474 / Redis:6379)、Python 依赖清单

- [ ] **Step 1: 写 docker-compose.yml**

```yaml
services:
  mysql:
    image: mysql:8.0
    environment:
      MYSQL_ROOT_PASSWORD: talentmind
      MYSQL_DATABASE: talentmind
    ports: ["3306:3306"]
    volumes: ["mysql_data:/var/lib/mysql"]
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost", "-uroot", "-ptalentmind"]
      interval: 5s
      timeout: 5s
      retries: 20
      start_period: 30s
  neo4j:
    image: neo4j:5-community
    environment:
      NEO4J_AUTH: neo4j/talentmind
    ports: ["7474:7474", "7687:7687"]
    volumes: ["neo4j_data:/data"]
    healthcheck:
      test: ["CMD-SHELL", "wget -qO- http://localhost:7474 || exit 1"]
      interval: 5s
      timeout: 5s
      retries: 20
      start_period: 30s
  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 10
volumes:
  mysql_data:
  neo4j_data:
```

> **healthcheck 说明**:后续任务凡需连库的验证步骤,先用 `docker-compose up -d --wait`(等待所有服务 healthy 再返回),避免服务未就绪导致验证失败。`--wait` 需要 docker-compose v2.17+。

- [ ] **Step 2: 写 requirements.txt**

```
fastapi==0.115.0
uvicorn[standard]==0.30.6
sqlalchemy==2.0.35
pymysql==1.1.1
neo4j==5.24.0
redis==5.0.8
pydantic==2.9.2
pydantic-settings==2.5.2
openai==1.51.0
pytest==8.3.3
httpx==0.27.2
```

- [ ] **Step 3: 写 .env.example 与 .gitignore**

`.env.example`:
```
MYSQL_URL=mysql+pymysql://root:talentmind@localhost:3306/talentmind
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=talentmind
REDIS_URL=redis://localhost:6379/0
OPENAI_API_KEY=sk-replace-me
OPENAI_BASE_URL=https://api.openai.com/v1
```

`.gitignore`:
```
.env
__pycache__/
*.pyc
.pytest_cache/
```

- [ ] **Step 4: 启动并等待三库就绪**

Run: `docker-compose up -d --wait && docker-compose ps`
Expected: 命令在三库全部 healthy 后返回;`ps` 显示 mysql / neo4j / redis 三个服务 Status 均为 `Up (healthy)`

- [ ] **Step 5: Commit**

```bash
git add docker-compose.yml backend/requirements.txt backend/.env.example backend/.gitignore backend/app/__init__.py
git commit -m "chore: scaffold project with docker-compose and deps"
```

---

## Task 2: 配置管理(Pydantic Settings)

**Files:**
- Create: `backend/app/config.py`
- Test: `backend/tests/test_config.py`

**Interfaces:**
- Consumes: `.env` 环境变量
- Produces: `get_settings() -> Settings`,字段 `mysql_url, neo4j_uri, neo4j_user, neo4j_password, redis_url, openai_api_key, openai_base_url`(均 str)

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_config.py
import os
from app.config import get_settings

def test_settings_reads_env(monkeypatch):
    monkeypatch.setenv("MYSQL_URL", "mysql+pymysql://u:p@h:3306/db")
    monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
    monkeypatch.setenv("NEO4J_USER", "neo4j")
    monkeypatch.setenv("NEO4J_PASSWORD", "pw")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    get_settings.cache_clear()
    s = get_settings()
    assert s.mysql_url.startswith("mysql+pymysql://")
    assert s.openai_api_key == "sk-test"
```

- [ ] **Step 2: 运行验证失败**

Run: `cd backend && pytest tests/test_config.py -v`
Expected: FAIL,`ModuleNotFoundError: No module named 'app.config'`

- [ ] **Step 3: 实现 config.py**

```python
# backend/app/config.py
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    mysql_url: str
    neo4j_uri: str
    neo4j_user: str
    neo4j_password: str
    redis_url: str
    openai_api_key: str
    openai_base_url: str = "https://api.openai.com/v1"

@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 4: 运行验证通过**

Run: `cd backend && pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/config.py backend/tests/test_config.py
git commit -m "feat: add pydantic settings config"
```

---

## Task 3: 统一响应与业务异常

**Files:**
- Create: `backend/app/response.py`
- Test: `backend/tests/test_response.py`

**Interfaces:**
- Consumes: 无
- Produces: `ok(data=None, message="ok") -> dict`;`fail(code, message) -> dict`;`class BizError(Exception)` 带 `.code:int` `.message:str`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_response.py
from app.response import ok, fail, BizError

def test_ok_wraps_data():
    assert ok({"x": 1}) == {"code": 0, "message": "ok", "data": {"x": 1}}

def test_fail_shape():
    assert fail(1001, "bad") == {"code": 1001, "message": "bad", "data": None}

def test_bizerror_carries_code():
    e = BizError(2001, "not found")
    assert e.code == 2001 and e.message == "not found"
```

- [ ] **Step 2: 运行验证失败**

Run: `cd backend && pytest tests/test_response.py -v`
Expected: FAIL,`ModuleNotFoundError: No module named 'app.response'`

- [ ] **Step 3: 实现 response.py**

```python
# backend/app/response.py
from typing import Any

def ok(data: Any = None, message: str = "ok") -> dict:
    return {"code": 0, "message": message, "data": data}

def fail(code: int, message: str) -> dict:
    return {"code": code, "message": message, "data": None}

class BizError(Exception):
    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(message)
```

- [ ] **Step 4: 运行验证通过**

Run: `cd backend && pytest tests/test_response.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/response.py backend/tests/test_response.py
git commit -m "feat: add unified response and BizError"
```

---

## Task 4: 全局异常中间件 + FastAPI 骨架

**Files:**
- Create: `backend/app/middleware.py`
- Create: `backend/app/main.py`
- Test: `backend/tests/test_middleware.py`

**Interfaces:**
- Consumes: `app.response.fail`, `app.response.BizError`
- Produces: `register_exception_handlers(app)`;`app` FastAPI 实例(供 A~E 挂 router);`GET /health` 返回 `{"code":0,...}`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_middleware.py
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["code"] == 0

def test_bizerror_handled():
    r = client.get("/_test_bizerror")
    assert r.status_code == 200
    assert r.json() == {"code": 4001, "message": "boom", "data": None}

def test_unhandled_exception_wrapped():
    r = client.get("/_test_crash")
    assert r.status_code == 200
    assert r.json()["code"] != 0
    assert r.json()["data"] is None

def test_unhandled_exception_logs_error(caplog):
    with caplog.at_level("ERROR", logger="talentmind"):
        client.get("/_test_crash")
    assert any("Unhandled exception" in rec.message for rec in caplog.records)
```

- [ ] **Step 2: 运行验证失败**

Run: `cd backend && pytest tests/test_middleware.py -v`
Expected: FAIL,`ModuleNotFoundError: No module named 'app.main'`

- [ ] **Step 3: 实现 middleware.py**

> **团队约定(全队认可)**:所有业务响应统一 HTTP 200,错误经 body 里的 `code != 0` 表达,而非 HTTP 4xx/5xx。理由:前端只需解析统一 `{code,message,data}`,不必在 HTTP 状态码和业务码两套体系间切换;契约单一、联调简单。真正的传输层错误(网络断、超时)仍由前端 axios 层感知。此约定写入 `middleware.py` 顶部注释,作为全队规范。

```python
# backend/app/middleware.py
# 【全队约定】业务响应一律 HTTP 200,错误经 body.code 表达(code=0 成功,非0失败)。
import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from app.response import fail, BizError

logger = logging.getLogger("talentmind")

def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(BizError)
    async def _biz(request: Request, exc: BizError):
        # 业务异常为预期内错误,warning 级别记录,便于排查但不刷 error 噪声
        logger.warning("BizError code=%s msg=%s path=%s", exc.code, exc.message, request.url.path)
        return JSONResponse(status_code=200, content=fail(exc.code, exc.message))

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        # 未预期异常必须带堆栈落 error 日志,否则 HTTP200 会掩盖真实故障
        logger.error("Unhandled exception at %s", request.url.path, exc_info=exc)
        return JSONResponse(status_code=200, content=fail(5000, "internal error"))
```

- [ ] **Step 4: 实现 main.py(含测试用触发路由)**

```python
# backend/app/main.py
from fastapi import FastAPI
from app.response import ok, BizError
from app.middleware import register_exception_handlers

app = FastAPI(title="TalentMind")
register_exception_handlers(app)

@app.get("/health")
async def health():
    return ok({"status": "up"})

@app.get("/_test_bizerror")
async def _test_bizerror():
    raise BizError(4001, "boom")

@app.get("/_test_crash")
async def _test_crash():
    raise RuntimeError("unexpected")

# 各人 router 挂载点(计划 A~E 在此 include_router)
```

- [ ] **Step 5: 运行验证通过**

Run: `cd backend && pytest tests/test_middleware.py -v`
Expected: PASS(4 passed)

- [ ] **Step 6: Commit**

```bash
git add backend/app/middleware.py backend/app/main.py backend/tests/test_middleware.py
git commit -m "feat: add exception middleware and FastAPI skeleton"
```

---

## Task 5: 三库连接依赖

**Files:**
- Create: `backend/app/db/__init__.py`
- Create: `backend/app/db/mysql.py`
- Create: `backend/app/db/neo4j.py`
- Create: `backend/app/db/redis.py`
- Test: `backend/tests/test_db_integration.py`

**Interfaces:**
- Consumes: `app.config.get_settings`
- Produces: `get_db()`(SQLAlchemy Session 生成器,FastAPI Depends 用);`get_neo4j()`(Neo4j Driver);`get_redis()`(Redis 客户端)

- [ ] **Step 1: 实现 mysql.py**

```python
# backend/app/db/mysql.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.config import get_settings

class Base(DeclarativeBase):
    pass

_engine = create_engine(get_settings().mysql_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=_engine, autoflush=False)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 2: 实现 neo4j.py 与 redis.py**

```python
# backend/app/db/neo4j.py
from neo4j import GraphDatabase
from app.config import get_settings

_s = get_settings()
_driver = GraphDatabase.driver(_s.neo4j_uri, auth=(_s.neo4j_user, _s.neo4j_password))

def get_neo4j():
    return _driver
```

```python
# backend/app/db/redis.py
import redis
from app.config import get_settings

_pool = redis.ConnectionPool.from_url(get_settings().redis_url)

def get_redis():
    return redis.Redis(connection_pool=_pool)
```

创建空 `backend/app/db/__init__.py`。

- [ ] **Step 3: 写三库集成测试(标记 integration,需 docker 起库)**

```python
# backend/tests/test_db_integration.py
import pytest
from sqlalchemy import text
from app.db.mysql import get_db
from app.db.neo4j import get_neo4j
from app.db.redis import get_redis

pytestmark = pytest.mark.integration

def test_mysql_roundtrip():
    db = next(get_db())
    try:
        assert db.execute(text("SELECT 1")).scalar() == 1
    finally:
        db.close()

def test_neo4j_roundtrip():
    driver = get_neo4j()
    with driver.session() as s:
        assert s.run("RETURN 1 AS n").single()["n"] == 1

def test_redis_roundtrip():
    r = get_redis()
    r.set("tm:ping", "pong")
    assert r.get("tm:ping") == b"pong"
    r.delete("tm:ping")
```

在 `backend/pytest.ini` 注册 marker(避免 unknown marker 警告),创建:
```ini
[pytest]
markers =
    integration: 需要 docker 起库的集成测试
```

- [ ] **Step 4: 起库并运行集成测试**

Run: `docker-compose up -d --wait && cd backend && pytest tests/test_db_integration.py -v -m integration`
Expected: PASS(3 passed)——三库读写往返均成功

- [ ] **Step 5: Commit**

```bash
git add backend/app/db/ backend/tests/test_db_integration.py backend/pytest.ini
git commit -m "feat: add db dependencies with integration tests"
```

---

## Task 6: 冻结 MySQL 表契约(DDL)

**Files:**
- Create: `backend/app/contracts/ddl.sql`
- Test: `backend/tests/test_ddl_integration.py`

**Interfaces:**
- Consumes: `app.db.mysql.get_db`
- Produces: 6 张冻结表 `jd_pool, signal, skill_dict, job_skill, emerging_job, resume`(供 A/C/E 消费,字段来自 spec 第 7 节)

- [ ] **Step 1: 写 ddl.sql**

```sql
-- backend/app/contracts/ddl.sql  【契约冻结:改/删字段须全队通知,加字段自由】
CREATE TABLE IF NOT EXISTS jd_pool (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  source VARCHAR(32), job_title VARCHAR(128), raw_text TEXT,
  duties TEXT, experience VARCHAR(32), quality FLOAT DEFAULT 0,
  dup_group VARCHAR(64), crawled_at DATETIME, status VARCHAR(16) DEFAULT 'raw',
  INDEX idx_status (status), INDEX idx_source (source)
);
CREATE TABLE IF NOT EXISTS signal (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  skill_or_job VARCHAR(128), signal_type VARCHAR(16),
  metric VARCHAR(16), value FLOAT, captured_at DATETIME,
  INDEX idx_soj (skill_or_job)
);
CREATE TABLE IF NOT EXISTS skill_dict (
  id INT PRIMARY KEY AUTO_INCREMENT,
  canonical VARCHAR(64) UNIQUE, aliases JSON, category VARCHAR(32),
  INDEX idx_canonical (canonical)
);
CREATE TABLE IF NOT EXISTS job_skill (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  jd_id BIGINT, job_name VARCHAR(128), level VARCHAR(16),
  skills JSON, duties TEXT, extracted_at DATETIME,
  INDEX idx_jobname (job_name)
);
CREATE TABLE IF NOT EXISTS emerging_job (
  id INT PRIMARY KEY AUTO_INCREMENT,
  job_name VARCHAR(128), definition TEXT, core_skills JSON,
  first_seen DATETIME, evolution JSON
);
CREATE TABLE IF NOT EXISTS resume (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  raw_format VARCHAR(8), skills JSON, experience JSON, parsed_at DATETIME
);
```

- [ ] **Step 2: 应用 DDL**

Run: `docker-compose up -d --wait && docker exec -i $(docker-compose ps -q mysql) mysql -uroot -ptalentmind talentmind < backend/app/contracts/ddl.sql`
Expected: 无报错

- [ ] **Step 3: 写 DDL 集成测试(自动化校验表与关键字段)**

```python
# backend/tests/test_ddl_integration.py
import pytest
from sqlalchemy import text
from app.db.mysql import get_db

pytestmark = pytest.mark.integration

EXPECTED_TABLES = {"jd_pool", "signal", "skill_dict", "job_skill", "emerging_job", "resume"}

def _cols(db, table):
    rows = db.execute(text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema='talentmind' AND table_name=:t"), {"t": table})
    return {r[0] for r in rows}

def test_all_tables_created():
    db = next(get_db())
    try:
        rows = db.execute(text("SHOW TABLES")).fetchall()
        tables = {r[0] for r in rows}
        assert EXPECTED_TABLES.issubset(tables)
    finally:
        db.close()

def test_job_skill_has_frozen_columns():
    db = next(get_db())
    try:
        cols = _cols(db, "job_skill")
        assert {"jd_id", "job_name", "level", "skills", "duties", "extracted_at"}.issubset(cols)
    finally:
        db.close()

def test_skill_dict_canonical_unique():
    db = next(get_db())
    try:
        rows = db.execute(text("SHOW INDEX FROM skill_dict WHERE Column_name='canonical'"))
        assert rows.fetchone() is not None   # canonical 有索引/唯一约束
    finally:
        db.close()
```

- [ ] **Step 4: 运行 DDL 集成测试**

Run: `cd backend && pytest tests/test_ddl_integration.py -v -m integration`
Expected: PASS(3 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/app/contracts/ddl.sql backend/tests/test_ddl_integration.py
git commit -m "feat: freeze mysql table contracts with integration tests"
```

---

## Task 7: 冻结 Pydantic 契约模型

**Files:**
- Create: `backend/app/models/__init__.py`
- Create: `backend/app/models/schemas.py`
- Test: `backend/tests/test_schemas.py`

**Interfaces:**
- Consumes: 无
- Produces: 冻结模型 `SkillItem, JobSkillOut, EmergingJobOut, ResumeOut, MatchResult, GraphNode, GraphEdge, GraphView`(供 A~E 与前端共用的响应契约)

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_schemas.py
from app.models.schemas import SkillItem, MatchResult

def test_skillitem_has_confidence_evidence():
    s = SkillItem(skill_id=1, name="RAG", weight=0.3, confidence=0.9, evidence="JD第3段")
    assert s.name == "RAG" and s.confidence == 0.9

def test_matchresult_shape():
    m = MatchResult(target_job="AI应用工程师", score=82,
                    matched=["Python"], missing=["RAG"],
                    path=[{"from": "后端工程师", "to": "AI应用工程师", "gap": ["RAG"]}])
    assert m.score == 82 and m.missing == ["RAG"]
```

- [ ] **Step 2: 运行验证失败**

Run: `cd backend && pytest tests/test_schemas.py -v`
Expected: FAIL,`ModuleNotFoundError: No module named 'app.models.schemas'`

- [ ] **Step 3: 实现 schemas.py**

```python
# backend/app/models/schemas.py  【契约冻结:加字段自由,改/删须全队通知】
from pydantic import BaseModel
from typing import Optional

class SkillItem(BaseModel):
    skill_id: int
    name: str
    weight: float = 0.0
    confidence: Optional[float] = None   # 无数据支撑时省略
    evidence: Optional[str] = None

class JobSkillOut(BaseModel):
    job_name: str
    level: str
    skills: list[SkillItem]
    duties: str = ""

class EmergingJobOut(BaseModel):
    job_name: str
    definition: str
    core_skills: list[str]
    evolution: dict           # {stage: str, growth_rate?: float}

class ResumeOut(BaseModel):
    resume_id: int
    raw_format: str
    skills: list[SkillItem]
    experience: list[dict]

class MatchResult(BaseModel):
    target_job: str
    score: int
    matched: list[str]
    missing: list[str]
    path: list[dict] = []     # 岗位路径推荐;不含"预计X个月"等无依据数字

class GraphNode(BaseModel):
    id: str
    label: str
    type: str                 # Domain/JobFamily/Job/Skill

class GraphEdge(BaseModel):
    source: str
    target: str
    rel: str                  # REQUIRES/RELATED_TO/BELONGS_TO/PART_OF
    weight: Optional[float] = None

class GraphView(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
```

创建空 `backend/app/models/__init__.py`。

- [ ] **Step 4: 运行验证通过**

Run: `cd backend && pytest tests/test_schemas.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/
git commit -m "feat: freeze pydantic contract schemas"
```

---

## Task 8: skill_dict 归一函数(全队地基)

**Files:**
- Create: `backend/app/skills/__init__.py`
- Create: `backend/app/skills/normalizer.py`
- Test: `backend/tests/test_normalizer.py`

**Interfaces:**
- Consumes: 无(词典以 dict 传入,便于测试;运行期由调用方从 `skill_dict` 表加载)
- Produces: `normalize(raw: str, alias_map: dict[str,str]) -> str | None`——把原始技能名归一到 canonical;未命中返回 None

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_normalizer.py
from app.skills.normalizer import normalize, build_alias_map

DICT = [
    {"canonical": "Kubernetes", "aliases": ["K8s", "k8s"]},
    {"canonical": "Python", "aliases": []},
]

def test_alias_maps_to_canonical():
    m = build_alias_map(DICT)
    assert normalize("k8s", m) == "Kubernetes"
    assert normalize("K8S", m) == "Kubernetes"   # 大小写不敏感

def test_canonical_itself():
    m = build_alias_map(DICT)
    assert normalize("Python", m) == "Python"

def test_unknown_returns_none():
    m = build_alias_map(DICT)
    assert normalize("COBOL", m) is None
```

- [ ] **Step 2: 运行验证失败**

Run: `cd backend && pytest tests/test_normalizer.py -v`
Expected: FAIL,`ModuleNotFoundError: No module named 'app.skills.normalizer'`

- [ ] **Step 3: 实现 normalizer.py**

```python
# backend/app/skills/normalizer.py
def build_alias_map(skill_dict: list[dict]) -> dict[str, str]:
    """把 [{canonical, aliases[]}] 展平成 {小写别名/标准名: canonical}。"""
    m: dict[str, str] = {}
    for row in skill_dict:
        canon = row["canonical"]
        m[canon.lower()] = canon
        for a in row.get("aliases") or []:
            m[a.lower()] = canon
    return m

def normalize(raw: str, alias_map: dict[str, str]) -> str | None:
    if not raw:
        return None
    return alias_map.get(raw.strip().lower())
```

- [ ] **Step 4: 运行验证通过**

Run: `cd backend && pytest tests/test_normalizer.py -v`
Expected: PASS(3 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/app/skills/ backend/tests/test_normalizer.py
git commit -m "feat: add skill_dict normalizer"
```

---

## Task 9: LLM 客户端封装(文本/多模态/embedding + 重试)

**Files:**
- Create: `backend/app/llm/__init__.py`
- Create: `backend/app/llm/client.py`
- Test: `backend/tests/test_llm_client.py`

**Interfaces:**
- Consumes: `app.config.get_settings`
- Produces:
  - `extract_json(prompt: str, schema_hint: str, retries: int = 3) -> dict`——文本抽取,强制 JSON,失败重试
  - `extract_json_with_image(prompt: str, image_b64: str, retries: int = 3) -> dict`——多模态抽取
  - `embed(texts: list[str]) -> list[list[float]]`——向量
  - 供 C(抽取/聚类)、E(简历解析/匹配)复用

- [ ] **Step 1: 写失败测试(mock OpenAI,不真调网络)**

```python
# backend/tests/test_llm_client.py
import json
from unittest.mock import MagicMock, patch
from app.llm import client as llm

def test_extract_json_parses_valid(monkeypatch):
    fake = MagicMock()
    fake.choices = [MagicMock(message=MagicMock(content='{"job":"AI工程师"}'))]
    with patch.object(llm, "_chat", return_value=fake):
        out = llm.extract_json("抽取岗位", '{"job": str}')
        assert out == {"job": "AI工程师"}

def test_extract_json_retries_on_bad_then_succeeds():
    bad = MagicMock(choices=[MagicMock(message=MagicMock(content="not json"))])
    good = MagicMock(choices=[MagicMock(message=MagicMock(content='{"ok":1}'))])
    with patch.object(llm, "_chat", side_effect=[bad, good]):
        out = llm.extract_json("x", "{}", retries=3)
        assert out == {"ok": 1}

def test_embed_returns_vectors():
    resp = MagicMock(data=[MagicMock(embedding=[0.1, 0.2]), MagicMock(embedding=[0.3, 0.4])])
    with patch.object(llm, "_embed_once", return_value=resp):
        out = llm.embed(["a", "b"])
        assert out == [[0.1, 0.2], [0.3, 0.4]]

def test_embed_retries_then_succeeds():
    good = MagicMock(data=[MagicMock(embedding=[0.5])])
    with patch.object(llm, "_embed_once", side_effect=[RuntimeError("429"), good]):
        out = llm.embed(["a"], retries=3)
        assert out == [[0.5]]

def test_embed_raises_after_exhausting_retries():
    with patch.object(llm, "_embed_once", side_effect=RuntimeError("down")):
        try:
            llm.embed(["a"], retries=2)
            assert False, "should have raised"
        except ValueError as e:
            assert "embedding 失败" in str(e)
```

- [ ] **Step 2: 运行验证失败**

Run: `cd backend && pytest tests/test_llm_client.py -v`
Expected: FAIL,`ModuleNotFoundError: No module named 'app.llm.client'`

- [ ] **Step 3: 实现 client.py**

```python
# backend/app/llm/client.py
import json
from openai import OpenAI
from app.config import get_settings

_s = get_settings()
_client = OpenAI(api_key=_s.openai_api_key, base_url=_s.openai_base_url)
MODEL = "gpt-4o"
EMBED_MODEL = "text-embedding-3-small"

def _chat(messages: list[dict]):
    return _client.chat.completions.create(
        model=MODEL, messages=messages,
        response_format={"type": "json_object"},
    )

def _parse(resp) -> dict:
    return json.loads(resp.choices[0].message.content)

def extract_json(prompt: str, schema_hint: str, retries: int = 3) -> dict:
    msg = [{"role": "user", "content": f"{prompt}\n严格按此结构返回JSON: {schema_hint}"}]
    last = None
    for _ in range(retries):
        try:
            return _parse(_chat(msg))
        except (json.JSONDecodeError, Exception) as e:
            last = e
    raise ValueError(f"LLM 抽取失败(重试{retries}次): {last}")

def extract_json_with_image(prompt: str, image_b64: str, retries: int = 3) -> dict:
    content = [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
    ]
    msg = [{"role": "user", "content": content}]
    last = None
    for _ in range(retries):
        try:
            return _parse(_chat(msg))
        except Exception as e:
            last = e
    raise ValueError(f"LLM 多模态抽取失败(重试{retries}次): {last}")

def _embed_once(texts: list[str]):
    return _client.embeddings.create(model=EMBED_MODEL, input=texts)

def embed(texts: list[str], retries: int = 3) -> list[list[float]]:
    last = None
    for _ in range(retries):
        try:
            resp = _embed_once(texts)
            return [d.embedding for d in resp.data]
        except Exception as e:   # 网络/限流/超时,退避重试
            last = e
    raise ValueError(f"LLM embedding 失败(重试{retries}次): {last}")
```

创建空 `backend/app/llm/__init__.py`。

- [ ] **Step 4: 运行验证通过**

Run: `cd backend && pytest tests/test_llm_client.py -v`
Expected: PASS(5 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/app/llm/ backend/tests/test_llm_client.py
git commit -m "feat: add llm client with text/vision/embed and retry"
```

---

## Task 10: 全量测试与骨架冒烟

**Files:**
- 无新增(验证任务)

**Interfaces:**
- Consumes: 前 9 个任务全部产出
- Produces: 绿色测试套件 + 可启动的后端骨架(A~E 并行的起点)

- [ ] **Step 1: 跑全部单元测试(排除集成)**

Run: `cd backend && pytest -v -m "not integration"`
Expected: 全部 PASS(config/response/middleware×4/schemas/normalizer/llm_client×5)

- [ ] **Step 2: 起库跑集成测试**

Run: `docker-compose up -d --wait && cd backend && pytest -v -m integration`
Expected: 全部 PASS(db_integration×3 + ddl_integration×3)

- [ ] **Step 3: 启动后端冒烟**

Run: `cd backend && uvicorn app.main:app --port 8000 &` 然后 `curl localhost:8000/health`
Expected: `{"code":0,"message":"ok","data":{"status":"up"}}`

- [ ] **Step 4: Commit(标记地基完成)**

```bash
git add -A
git commit -m "chore: shared foundation complete, contracts frozen"
```

---

## 契约冻结公告(第 0 天结束时全队确认)

本计划完成即代表以下契约冻结,A~E 可并行开工:
- **MySQL 表**:`ddl.sql` 6 张表
- **Pydantic 响应模型**:`schemas.py`
- **API 响应格式**:`{code,message,data}`
- **技能归一**:`normalize()` 全队统一调用
- **LLM 接口**:`extract_json` / `extract_json_with_image` / `embed`

规则:**加字段自由,改/删字段或改 API 响应结构必须全队通知**。无数据阶段各人用 Mock 填充,互不阻塞。

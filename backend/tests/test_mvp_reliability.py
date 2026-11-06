"""Reliability regressions using synthetic uploads and database doubles only."""
import asyncio
import csv
import io
import json
import threading
import time
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI, UploadFile

from app.response import BizError
from app.routers import mvp


@pytest.fixture(autouse=True)
def no_database(monkeypatch):
    monkeypatch.setattr(mvp, "SessionLocal", lambda: pytest.fail("unexpected database connection"))


def upload(data, name="jobs.csv"):
    return UploadFile(filename=name, file=io.BytesIO(data))


def test_slow_upload_keeps_health_responsive_and_session_on_worker(monkeypatch):
    entered = threading.Event()
    stages = []
    real_parse = mvp.parse_resume
    real_match = mvp.quick_match_weighted

    def parse(content):
        stages.append(("parse", threading.get_ident()))
        return real_parse(content)

    def match(*args):
        stages.append(("match", threading.get_ident()))
        return real_match(*args)

    def extract(*args):
        stages.append(("extract", threading.get_ident()))
        entered.set()
        time.sleep(0.25)
        return "技能：Python"

    class Session:
        def __init__(self):
            stages.append(("create", threading.get_ident()))
        def execute(self, *args):
            stages.append(("query", threading.get_ident()))
            return self
        def mappings(self):
            return self
        def all(self):
            return [{"id": 1, "job_name": "合成岗位", "required_skills": '["Python"]'}]
        def close(self):
            stages.append(("close", threading.get_ident()))

    monkeypatch.setattr(mvp, "_extract_file_text", extract)
    monkeypatch.setattr(mvp, "parse_resume", parse)
    monkeypatch.setattr(mvp, "quick_match_weighted", match)
    monkeypatch.setattr(mvp, "SessionLocal", Session)
    app = FastAPI()
    app.include_router(mvp.router)

    @app.get("/health")
    async def health():
        return {"status": "up"}

    async def exercise():
        event_loop_thread = threading.get_ident()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            pending = asyncio.create_task(client.post("/resume/upload", files={"file": ("resume.txt", b"synthetic")}))
            while not entered.is_set():
                if pending.done():
                    response = await pending
                    pytest.fail(f"upload never reached extraction: {response.status_code} {response.text}")
                await asyncio.sleep(0.001)
            response = await client.get("/health")
            responsive = not pending.done()
            result = await pending
        assert response.json() == {"status": "up"}
        assert result.status_code == 200
        assert responsive, "synchronous parsing blocked the lightweight endpoint"
        assert len({thread for _, thread in stages}) == 1
        assert stages[0][1] != event_loop_thread
        assert [name for name, _ in stages] == ["extract", "parse", "create", "query", "close", "match"]

    asyncio.run(exercise())


def test_exported_csv_roundtrips_chinese_lists_and_empty_fields(monkeypatch):
    row = {"job_name": "数据工程师", "core_duties": "分析数据，编写报告\n维护服务", "required_skills": json.dumps(["Python", "沟通", "A | B"]), "bonus_skills": "[]", "source": '["boss", "猎聘"]', "collected_at": "2026-11-07 01:02:03", "updated_at": None}
    class Session:
        def execute(self, *args): return self
        def mappings(self): return self
        def all(self): return [row]
        def close(self): pass
    monkeypatch.setattr(mvp, "SessionLocal", Session)
    saved = []
    monkeypatch.setattr(mvp, "create_job", lambda payload: saved.append(payload))
    exported = mvp.export_jobs()
    result = asyncio.run(mvp.import_jobs(upload(exported.body)))
    assert result["data"]["imported"] == 1
    assert saved[0].job_name == "数据工程师"
    assert saved[0].core_duties == row["core_duties"]
    assert saved[0].required_skills == ["Python", "沟通", "A | B"]
    assert saved[0].bonus_skills == []
    assert saved[0].source == ["boss", "猎聘"]
    assert saved[0].collected_at == "2026-11-07 01:02:03"
    assert saved[0].updated_at == ""


@pytest.mark.parametrize("skills", ["Python;沟通", "Python | 沟通", '["Python", "沟通"]'])
def test_csv_accepts_legacy_and_json_skill_lists(monkeypatch, skills):
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["title", "required_skills", "bonus_skills", "source"])
    writer.writerow(["测试岗位", skills, "", "boss | hn"])
    saved = []
    monkeypatch.setattr(mvp, "create_job", lambda payload: saved.append(payload))
    asyncio.run(mvp.import_jobs(upload(buf.getvalue().encode("utf-8-sig"))))
    assert saved[0].required_skills == ["Python", "沟通"]
    assert saved[0].bonus_skills == []
    assert saved[0].source == ["boss", "hn"]


@pytest.mark.parametrize("bad", [{"job_name": ""}, {"job_name": "later", "required_skills": [1]}, {"job_name": "later", "quality": "bad"}, {"job_name": "later", "collected_at": "bad"}])
def test_entire_import_is_validated_before_first_insert(monkeypatch, bad):
    saved = []
    monkeypatch.setattr(mvp, "create_job", lambda payload: saved.append(payload))
    with pytest.raises(BizError):
        asyncio.run(mvp.import_jobs(upload(json.dumps([{"job_name": "first"}, bad]).encode(), "jobs.json")))
    assert saved == []


@pytest.mark.parametrize("field,value", [
    ("evolution", '{"weight":1e999}'),
    ("evolution", '{"nested":[{"value":NaN}]}'),
    ("quality", "1e100"),
    ("quality", "-1e100"),
    ("core_duties", json.dumps("a" * 65536)),
    ("core_duties", json.dumps("中" * 21846)),
    ("collected_at", '"0001-01-01"'),
    ("updated_at", '"0999-12-31 23:59:59"'),
    ("collected_at", '"20261107"'),
    ("collected_at", '"2026-W45-6"'),
    ("collected_at", '"2026-11-07T00:00:00Z"'),
], ids=["json-infinity", "json-nan", "float-overflow", "float-underflow-range", "text-ascii-bytes", "text-utf8-bytes", "early-collected", "early-updated", "basic-date", "week-date", "timezone-date"])
def test_later_storage_constraint_violation_cannot_write_first_row(monkeypatch, field, value):
    saved = []
    monkeypatch.setattr(mvp, "create_job", lambda payload: saved.append(payload))
    raw = ('[{"job_name":"first"},{"job_name":"later","' + field + '":' + value + '}]').encode()
    with pytest.raises(BizError):
        asyncio.run(mvp.import_jobs(upload(raw, "jobs.json")))
    assert saved == []


@pytest.mark.parametrize("date,expected", [("1000-01-01", "1000-01-01 00:00:00"), ("2026-11-07T01:02:03", "2026-11-07 01:02:03"), ("9999-12-31 23:59:59", "9999-12-31 23:59:59")])
def test_import_accepts_storage_boundaries_and_normalizes_datetime(monkeypatch, date, expected):
    saved = []
    monkeypatch.setattr(mvp, "create_job", lambda payload: saved.append(payload))
    item = {"job_name": "valid", "core_duties": "中" * 21845, "quality": 3.4028234663852886e38, "collected_at": date, "evolution": {"nested": [1, 2.5, None]}}
    asyncio.run(mvp.import_jobs(upload(json.dumps([item]).encode(), "jobs.json")))
    assert len(saved) == 1
    assert len(saved[0].core_duties.encode("utf-8")) == 65535
    assert saved[0].collected_at == expected


@pytest.mark.parametrize("last_row", ['later,"[1]",0', 'later,"[invalid",0', 'later,Python,bad', ',Python,0', 'later,Python,0,unexpected'])
def test_csv_bad_later_row_cannot_commit_first_row(monkeypatch, last_row):
    saved = []
    monkeypatch.setattr(mvp, "create_job", lambda payload: saved.append(payload))
    raw = f"job_name,required_skills,quality\nfirst,Python,0\n{last_row}\n".encode("utf-8-sig")
    with pytest.raises(BizError):
        asyncio.run(mvp.import_jobs(upload(raw)))
    assert saved == []


def test_import_sessions_are_created_used_and_closed_in_worker(monkeypatch):
    stages = []
    class Session:
        def __init__(self): stages.append(("create", threading.get_ident()))
        def execute(self, statement, params):
            stages.append(("insert", threading.get_ident()))
            return SimpleNamespace(lastrowid=1)
        def commit(self): stages.append(("commit", threading.get_ident()))
        def rollback(self): pytest.fail("unexpected rollback")
        def close(self): stages.append(("close", threading.get_ident()))
    monkeypatch.setattr(mvp, "SessionLocal", Session)
    async def exercise():
        loop_thread = threading.get_ident()
        result = await mvp.import_jobs(upload(b"job_name\nfirst\nsecond\n"))
        assert result["data"] == {"imported": 2}
        assert len({thread for _, thread in stages}) == 1
        assert stages[0][1] != loop_thread
        assert [name for name, _ in stages] == ["create", "insert", "commit", "close"] * 2
    asyncio.run(exercise())


@pytest.mark.parametrize("commit_fails", [False, True])
def test_insert_id_comes_from_result_and_commit_precedes_response(monkeypatch, commit_fails):
    events = []
    class Session:
        def execute(self, statement, params=None):
            events.append("insert" if str(statement).startswith("INSERT") else "extra query")
            return SimpleNamespace(lastrowid=718, scalar=lambda: 999)
        def commit(self):
            events.append("commit")
            if commit_fails: raise RuntimeError("commit failed")
        def rollback(self): events.append("rollback")
        def close(self): events.append("close")
    monkeypatch.setattr(mvp, "SessionLocal", Session)
    if commit_fails:
        with pytest.raises(RuntimeError, match="commit failed"):
            mvp.create_job(mvp.JobPayload(job_name="合成岗位"))
        assert events == ["insert", "commit", "rollback", "close"]
    else:
        assert mvp.create_job(mvp.JobPayload(job_name="合成岗位"))["data"]["id"] == "718"
        assert events == ["insert", "commit", "close"]


def test_create_edit_export_import_with_isolated_sqlite(monkeypatch):
    """Real SQL/HTTP path; all fixtures are removed by exact identity in finally."""
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from app.middleware import register_exception_handlers

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    assert engine.url.database is None
    fixture_name = "fixture-pr71-csv-中文工程师"
    sentinel_name = "fixture-pr71-untouched-sentinel"
    with engine.begin() as connection:
        connection.execute(text("""CREATE TABLE job_definition (
            id INTEGER PRIMARY KEY AUTOINCREMENT, job_name TEXT, core_duties TEXT,
            required_skills TEXT, bonus_skills TEXT, scenarios TEXT, source TEXT,
            quality FLOAT, is_emerging INTEGER, evolution TEXT,
            collected_at TEXT, updated_at TEXT)"""))
        connection.execute(text("INSERT INTO job_definition (job_name) VALUES (:name)"), {"name": sentinel_name})
    monkeypatch.setattr(mvp, "SessionLocal", sessionmaker(bind=engine))
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(mvp.router, prefix="/api")
    try:
        with TestClient(app) as client:
            payload = {"job_name": fixture_name, "core_duties": "分析数据\n维护服务", "required_skills": ["Python", "沟通"], "bonus_skills": [], "source": ["boss", "hn"], "collected_at": "2026-11-07 01:02:03"}
            created = client.post("/api/jobs", json=payload).json()
            inserted_id = int(created["data"]["id"])
            with engine.connect() as connection:
                stored = connection.execute(text("SELECT * FROM job_definition WHERE id=:id"), {"id": inserted_id}).mappings().one()
                assert stored["job_name"] == fixture_name
                assert json.loads(stored["required_skills"]) == ["Python", "沟通"]
            payload["required_skills"] = ["Python", "SQL"]
            payload["bonus_skills"] = ["沟通", "A | B"]
            edited = client.put(f"/api/jobs/{inserted_id}", json=payload).json()
            assert edited["data"]["success"] is True
            # The sentinel is deliberately excluded from the import, not deleted or rewritten.
            exported = client.get("/api/jobs/export").content.decode("utf-8-sig")
            rows = list(csv.DictReader(io.StringIO(exported)))
            exported_row = next(row for row in rows if row["job_name"] == fixture_name)
            buf = io.StringIO()
            writer = csv.DictWriter(buf, fieldnames=list(exported_row))
            writer.writeheader()
            writer.writerow(exported_row)
            imported = client.post("/api/jobs/import", files={"file": ("export.csv", buf.getvalue().encode("utf-8-sig"))}).json()
            assert imported["data"] == {"imported": 1}
            with engine.connect() as connection:
                copies = connection.execute(text("SELECT * FROM job_definition WHERE job_name=:name ORDER BY id"), {"name": fixture_name}).mappings().all()
                assert len(copies) == 2
                assert copies[0]["id"] == inserted_id
                assert copies[1]["id"] != inserted_id
                for copy in copies:
                    assert copy["core_duties"] == "分析数据\n维护服务"
                    assert json.loads(copy["required_skills"]) == ["Python", "SQL"]
                    assert json.loads(copy["bonus_skills"]) == ["沟通", "A | B"]
                    assert json.loads(copy["source"]) == ["boss", "hn"]
                    assert copy["updated_at"] is None
            malformed = f"job_name,quality\n{fixture_name},0\n{fixture_name},invalid\n"
            rejected = client.post("/api/jobs/import", files={"file": ("invalid.csv", malformed.encode("utf-8-sig"))}).json()
            assert rejected["code"] != 0
            with engine.connect() as connection:
                assert connection.execute(text("SELECT COUNT(*) FROM job_definition WHERE job_name=:name"), {"name": fixture_name}).scalar_one() == 2
    finally:
        try:
            with engine.begin() as connection:
                connection.execute(text("DELETE FROM job_definition WHERE job_name=:name"), {"name": fixture_name})
                assert connection.execute(text("SELECT COUNT(*) FROM job_definition WHERE job_name=:name"), {"name": fixture_name}).scalar_one() == 0
                assert connection.execute(text("SELECT COUNT(*) FROM job_definition WHERE job_name=:name"), {"name": sentinel_name}).scalar_one() == 1
                connection.execute(text("DELETE FROM job_definition WHERE job_name=:name"), {"name": sentinel_name})
                assert connection.execute(text("SELECT COUNT(*) FROM job_definition")).scalar_one() == 0
        finally:
            engine.dispose()

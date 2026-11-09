"""Retained resume/resource and profile-audit regressions; no real database."""
import asyncio
import csv
import io
import json
import threading
import time

import httpx
import pytest
from fastapi import FastAPI
from app.routers import mvp


def test_export_preserves_chinese_lists_delimiters_and_empty_fields(monkeypatch):
    row = {'job_name': '数据工程师', 'core_duties': '分析数据，编写报告\n维护服务',
           'required_skills': json.dumps(['Python', '沟通', 'A | B']),
           'bonus_skills': '[]', 'source': '["boss", "猎聘"]',
           'collected_at': '2026-11-07 01:02:03', 'updated_at': None}
    class Session:
        def execute(self, *args): return self
        def mappings(self): return self
        def all(self): return [row]
        def close(self): pass
    monkeypatch.setattr(mvp, 'SessionLocal', Session)
    result = mvp.export_jobs()
    saved = list(csv.DictReader(io.StringIO(result.body.decode('utf-8-sig'))))
    assert len(saved) == 1
    assert saved[0]['job_name'] == row['job_name']
    assert saved[0]['core_duties'] == row['core_duties']
    assert json.loads(saved[0]['required_skills']) == ['Python', '沟通', 'A | B']
    assert json.loads(saved[0]['source']) == ['boss', '猎聘']
    assert saved[0]['updated_at'] == ''

@pytest.fixture(autouse=True)
def no_database(monkeypatch):
    monkeypatch.setattr(mvp, "SessionLocal", lambda: pytest.fail("unexpected database connection"))



def test_job_detail_never_falls_back_to_same_number_raw_pool_id(monkeypatch):
    statements = []

    class Session:
        def execute(self, statement, params):
            statements.append((str(statement), params))
            self._rows = []
            return self

        def mappings(self):
            return self

        def first(self):
            return self._rows[0] if self._rows else None

        def close(self):
            pass

    monkeypatch.setattr(mvp, "SessionLocal", Session)
    with pytest.raises(mvp.BizError) as error:
        mvp.job_detail(7)
    assert error.value.code == 4041
    assert len(statements) == 1
    assert "FROM job_definition" in statements[0][0]
    assert all("jd_pool" not in statement for statement, _ in statements)


def test_job_detail_returns_only_the_requested_profile_identity(monkeypatch):
    row = {
        "id": 7, "job_name": "合成画像", "name_en": "Synthetic Profile",
        "job_name_zh": "合成画像", "m2_job_id": "m2-7", "category": "fixture",
        "category_review": "fixture", "required_skills": '["Python"]',
        "bonus_skills": '["SQL"]', "core_duties": "负责合成服务\n维护合成接口",
        "scenarios": "[]", "source": '["boss"]', "quality": 1.0,
        "is_emerging": 0, "evolution": "{}", "source_jd_count": 1,
        "collected_at": "2026-11-09T00:00:00", "updated_at": "2026-11-09T00:00:00",
    }

    class Session:
        def execute(self, *args, **kwargs):
            return self

        def mappings(self):
            return self

        def first(self):
            return row

        def close(self):
            pass

    monkeypatch.setattr(mvp, "SessionLocal", Session)
    result = mvp.job_detail(7)["data"]
    assert result["id"] == "7"
    assert result["job_name"] == "合成画像"
    assert result["object_type"] == "job_profile"
    assert result["responsibilities"] == ["负责合成服务", "维护合成接口"]
    assert "raw_text" not in result



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



@pytest.mark.parametrize('edit_case', ['noop', 'version_chain'])
def test_profile_audit_uses_persisted_values_for_noop_and_version_chain(monkeypatch, edit_case):
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    engine = create_engine('sqlite://', poolclass=StaticPool)
    assert engine.url.database is None
    name = 'fixture-issue73-audit-' + edit_case
    with engine.begin() as db:
        db.execute(text('''CREATE TABLE job_definition (
            id INTEGER PRIMARY KEY AUTOINCREMENT, job_name TEXT, core_duties TEXT,
            required_skills TEXT, bonus_skills TEXT, scenarios TEXT, source TEXT,
            quality FLOAT, is_emerging INTEGER, evolution TEXT,
            collected_at TEXT, updated_at TEXT)'''))
        db.execute(text('''CREATE TABLE job_change_log (id INTEGER PRIMARY KEY, job_id INTEGER,
            change_type TEXT, detail TEXT, source TEXT, reason TEXT, created_at TEXT, object_type TEXT)'''))
    monkeypatch.setattr(mvp, 'SessionLocal', sessionmaker(bind=engine))
    ident = None
    try:
        payload = mvp.JobPayload(job_name=name, required_skills=['Python'])
        with engine.begin() as db:
            result = db.execute(text('''INSERT INTO job_definition
                (job_name, core_duties, required_skills, bonus_skills, scenarios, source,
                 quality, is_emerging, evolution, collected_at, updated_at)
                VALUES (:name, '', '["Python"]', '[]', '[]', '[]', 0, 0, '{}', NULL, NULL)'''), {'name': name})
            ident = result.lastrowid
        payload.bonus_skills = ['Git']
        payload.collected_at = '2026-11-07T01:02:03'
        mvp.update_job(ident, payload)
        if edit_case == 'version_chain':
            payload.required_skills = ['Python', 'Docker']
            payload.is_emerging = True
        mvp.update_job(ident, payload)
        with engine.connect() as db:
            logs = [json.loads(row[0]) for row in db.execute(text('SELECT detail FROM job_change_log WHERE job_id=:id ORDER BY id'), {'id': ident})]
        if edit_case == 'noop':
            assert len(logs) == 1
        else:
            assert len(logs) == 2
            assert logs[1]['before'] == logs[0]['after']
            assert logs[1]['before_version'] == logs[0]['after_version']
    finally:
        with engine.begin() as db:
            if ident is not None:
                db.execute(text('DELETE FROM job_change_log WHERE job_id=:id'), {'id': ident})
                db.execute(text('DELETE FROM job_definition WHERE id=:id AND job_name=:name'), {'id':ident, 'name':name})
            assert db.execute(text('SELECT count(*) FROM job_change_log')).scalar_one() == 0
            assert db.execute(text('SELECT count(*) FROM job_definition')).scalar_one() == 0
        engine.dispose()

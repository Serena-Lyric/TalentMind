"""MVP 集成测试：exchange 导入（MySQL/Neo4j）+ 统一 API 冒烟（阶段 6）。"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.main import app
from app.db.mysql import SessionLocal
from app.integration.import_exchange import import_all
from app.integration.import_graph import import_graph

pytestmark = pytest.mark.integration

client = TestClient(app)


def test_import_exchange_idempotent():
    first = import_all()
    second = import_all()
    assert first["skill_dict"] > 0
    assert first["job_definition"] > 0
    assert first["job_skill"] > 0
    # 幂等：重复导入不增加行数
    db = SessionLocal()
    try:
        n1 = db.execute(text("SELECT COUNT(*) FROM job_definition")).scalar()
        n2 = db.execute(text("SELECT COUNT(*) FROM job_skill")).scalar()
        n3 = db.execute(text("SELECT COUNT(*) FROM skill_dict")).scalar()
    finally:
        db.close()
    assert n1 == first["job_definition"]
    assert n2 == first["job_skill"]
    assert n3 == first["skill_dict"]
    assert second == first


def test_import_graph_idempotent():
    first = import_graph()
    second = import_graph()
    assert first["nodes"] > 0
    assert first["edges"] > 0
    assert second == first


def test_mvp_jobs_api():
    resp = client.get("/api/jobs", params={"page": 1, "page_size": 10})
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["total"] > 0
    item = body["data"]["list"][0]
    assert item["title"]
    assert isinstance(item["skills"], list)


def test_mvp_graph_api():
    resp = client.get("/api/graph/data")
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["stats"]["totalNodes"] > 0
    kinds = {n["kind"] for n in body["data"]["nodes"]}
    assert kinds <= {"job", "skill"}


def test_mvp_resume_upload():
    resume = "姓名：张三\n技能：Python、Django、MySQL、Redis"
    resp = client.post("/api/resume/upload", data={"content": resume})
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["profile"]["skills"]
    assert "score" in body["data"]["matchResult"]
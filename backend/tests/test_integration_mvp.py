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

# ==================== MVP 补全接口（dashboard + jobs CRUD + import/export） ====================

def test_mvp_dashboard_overview():
    resp = client.get("/api/dashboard/overview")
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["totalJobs"] > 0


def test_mvp_dashboard_skill_distribution():
    resp = client.get("/api/dashboard/skill-distribution")
    body = resp.json()
    assert body["code"] == 0
    assert isinstance(body["data"], list)


def test_mvp_jobs_crud():
    resp = client.post("/api/jobs", json={
        "job_name": "MVP测试岗位", "required_skills": ["python"], "quality": 0.5,
    })
    assert resp.json()["code"] == 0
    new_id = resp.json()["data"]["id"]

    resp = client.get(f"/api/jobs/{new_id}")
    assert resp.json()["code"] == 0
    assert resp.json()["data"]["title"] == "MVP测试岗位"

    resp = client.put(f"/api/jobs/{new_id}", json={
        "job_name": "MVP测试岗位改", "required_skills": ["python", "docker"],
    })
    assert resp.json()["code"] == 0

    resp = client.delete(f"/api/jobs/{new_id}")
    assert resp.json()["code"] == 0
    resp = client.get(f"/api/jobs/{new_id}")
    assert resp.json()["code"] == 4041


def test_mvp_jobs_import_export():
    import io
    resp = client.post(
        "/api/jobs/import",
        files={"file": ("jobs.json", io.BytesIO(
            '[{"job_name": "导入岗位A", "required_skills": ["python"]}]'.encode("utf-8")
        ), "application/json")},
    )
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["imported"] == 1

    resp = client.get("/api/jobs/export")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert "job_name" in resp.text

    # 清理导入数据，避免影响幂等断言
    db = SessionLocal()
    try:
        db.execute(text("DELETE FROM job_definition WHERE job_name = '导入岗位A'"))
        db.commit()
    finally:
        db.close()


def test_mvp_graph_skill_radar():
    resp = client.get("/api/graph/skill-radar", params={"node_name": "Python"})
    assert resp.json()["code"] == 0

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
    new_id = None
    try:
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
    finally:
        # 测试数据清理规范（D37）：无论成败都删除本次创建的岗位
        if new_id is not None:
            db = SessionLocal()
            try:
                db.execute(text("DELETE FROM job_definition WHERE id = :i"), {"i": new_id})
                db.commit()
            finally:
                db.close()

def test_mvp_jobs_import_export():
    import io
    try:
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
    finally:
        # 测试数据清理规范（D37）：无论成败都删除导入的岗位
        db = SessionLocal()
        try:
            db.execute(text("DELETE FROM job_definition WHERE job_name = '导入岗位A'"))
            db.commit()
        finally:
            db.close()

def test_mvp_graph_skill_radar():
    resp = client.get("/api/graph/skill-radar", params={"node_name": "Python"})
    assert resp.json()["code"] == 0


def test_import_change_logs_job_name_resolution(tmp_path):
    """job_change_log.json 的 job_id 为 job_name（M2 differ 产出），导入时应解析为
    job_definition.id；object_type 列不存在于 DDL，不得再写入（曾潜伏于空日志）。
    测试数据清理规范（D37）：用唯一 reason 标记，finally 中按标记精确清理。
    """
    import json as _json
    from app.integration.import_exchange import import_change_logs
    from app.db.mysql import SessionLocal

    MARKER = "pytest-marker-change-log-resolution"

    db = SessionLocal()
    try:
        job = db.execute(
            text("SELECT id, job_name FROM job_definition ORDER BY id LIMIT 1")
        ).first()
    finally:
        db.close()
    assert job, "需要至少一条 job_definition"

    log_file = tmp_path / "job_change_log.json"
    log_file.write_text(_json.dumps([
        {
            "job_id": job[1],  # job_name 字符串
            "change_type": "added",
            "object_type": "skill",  # M2 会输出该字段，导入层应忽略（DDL 无此列）
            "skill_name": "python",
            "detail": {"old_value": None, "new_value": {"confidence": 0.8}},
            "source": ["linkedin"],
            "reason": MARKER,
            "created_at": "2026-08-14T10:00:00",
        },
        {"job_id": "不存在的岗位名", "change_type": "added", "skill_name": "x"},
    ], ensure_ascii=False), encoding="utf-8")

    try:
        n = import_change_logs(path=log_file)
        assert n == 1

        db = SessionLocal()
        try:
            row = db.execute(
                text("SELECT job_id, change_type, skill_name FROM job_change_log")
            ).first()
        finally:
            db.close()
        assert row is not None
        assert row[0] == job[0]
        assert row[1] == "added"
        assert row[2] == "python"
    finally:
        # 无论成败都按唯一标记清理，保持 job_change_log 为空（与线上状态一致）
        db = SessionLocal()
        try:
            db.execute(text("DELETE FROM job_change_log WHERE reason = :m"), {"m": MARKER})
            db.commit()
        finally:
            db.close()

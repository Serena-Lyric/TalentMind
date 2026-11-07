"""MVP 集成测试：exchange 导入（MySQL/Neo4j）+ 统一 API 冒烟（阶段 6）。"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.main import app
from app.db.mysql import SessionLocal
from app.integration.import_exchange import import_all
from app.integration.import_graph import import_graph
from app.integration.m2_package import DEFAULT_PACKAGE_DIR

pytestmark = pytest.mark.integration

skip_if_no_legacy = pytest.mark.skipif(
    not DEFAULT_PACKAGE_DIR.exists(),
    reason="原 M2 回包(input/岗位数据-新一代与现有)仅存于开发仓库，不随提交物提供",
)


client = TestClient(app)


@skip_if_no_legacy
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


def test_mvp_resume_upload():
    resume = "姓名：张三\n技能：Python、Django、MySQL、Redis"
    target = client.get("/api/learning/jobs").json()["data"][0]
    resp = client.post("/api/resume/upload", data={"content": resume, "target_job_id": target["value"]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["profile"]["skills"]
    assert "score" in body["data"]["matchResult"]
    assert body["data"]["matchResult"]["target_job_id"] == target["value"]
    assert 0 < len(body["data"]["recommendedJobs"]) <= 3

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
                text("SELECT job_id, change_type, skill_name FROM job_change_log WHERE reason = :m"), {"m": MARKER}
            ).first()
        finally:
            db.close()
        assert row is not None
        assert row[0] == job[0]
        assert row[1] == "added"
        assert row[2] == "python"
    finally:
        # 无论成败都按唯一标记清理，不影响 M2 生产变更日志
        db = SessionLocal()
        try:
            db.execute(text("DELETE FROM job_change_log WHERE reason = :m"), {"m": MARKER})
            db.commit()
        finally:
            db.close()

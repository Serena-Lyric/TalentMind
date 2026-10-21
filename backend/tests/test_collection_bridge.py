import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.collect import bridge, control


def list_capture(*, count: int = 1) -> dict:
    return {
        "schema_version": "m1-browser-bridge-v1",
        "kind": "list",
        "page_url": "https://www.zhipin.com/web/geek/jobs?city=101010100&query=Java&page=1",
        "items": [
            {
                "url": f"https://www.zhipin.com/job_detail/job-{index}.html",
                "title": f"Java 后端工程师 {index}",
                "company": "示例科技",
                "salary": "20-30K",
                "location": "北京",
                "tags": ["Java", "Spring Boot"],
            }
            for index in range(count)
        ],
        "detail": None,
    }


def detail_capture(**changes) -> dict:
    payload = {
        "schema_version": "m1-browser-bridge-v1",
        "kind": "detail",
        "page_url": "https://www.zhipin.com/job_detail/job-0.html",
        "items": [],
        "detail": {
            "url": "https://www.zhipin.com/job_detail/job-0.html",
            "title": "Java 后端工程师 0",
            "company": "示例科技",
            "salary": "20-30K",
            "location": "北京",
            "experience": "3-5年",
            "degree": "本科",
            "description": "负责 Java 服务端开发\n熟悉 Spring Boot 和 MySQL",
            "company_info": "示例科技专注企业服务",
            "description_truncated": False,
            "challenge_detected": False,
        },
    }
    for key, value in changes.items():
        if key in payload:
            payload[key] = value
        else:
            payload["detail"][key] = value
    return payload


@pytest.fixture
def private_state(tmp_path, monkeypatch):
    state = tmp_path / "collection"
    monkeypatch.setattr(control, "_STATE_DIR", state)
    monkeypatch.setattr(control, "_STATE_PATH", state / "control-state.json")
    monkeypatch.setattr(bridge, "_STATE_DIR", state)
    monkeypatch.setattr(bridge, "_SESSIONS_DIR", state / "bridge")
    return state


def test_session_lifecycle_persists_history_events_and_counts(private_state):
    created = bridge.create_session(
        {"keyword": "Java", "city_name": "北京", "city_code": "101010100", "pages": 1, "max_jobs": 5, "detail_limit": 5}
    )
    run_id = created["run_id"]

    bridge.append_capture(run_id, list_capture(count=2))
    current = bridge.get_session(run_id)
    assert current["status"] == "waiting_for_capture"
    assert current["listed"] == 2
    assert current["detail_attempted"] == 0

    finished = bridge.finish_session(run_id)
    assert finished["status"] == "completed"
    assert finished["finished_at"]

    history = control.get_history(page_size=20)["items"]
    assert history[0]["run_id"] == run_id
    assert history[0]["mode"] == "bridge"

    results = control.get_results(run_id)
    assert {item["job_title"] for item in results} == {"Java 后端工程师 0", "Java 后端工程师 1"}

    event_file = private_state / f"{run_id}.events.jsonl"
    assert event_file.exists()
    assert json.loads(event_file.read_text(encoding="utf-8").splitlines()[0])["event"] == "listed"

    with pytest.raises(ValueError, match="已结束"):
        bridge.append_capture(run_id, list_capture())


def test_duplicate_capture_digest_is_idempotent(private_state):
    run_id = bridge.create_session(
        {"keyword": "Java", "city_name": "北京", "city_code": "101010100"}
    )["run_id"]
    payload = list_capture(count=1)

    first = bridge.append_capture(run_id, payload)
    second = bridge.append_capture(run_id, payload)

    assert second["duplicate"] is True
    assert second["result"] == first["result"]
    current = bridge.get_session(run_id)
    assert current["listed"] == 1
    assert len(current["captures"]) == 1


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'bridge.sqlite'}")
    with engine.begin() as connection:
        connection.execute(text(
            "CREATE TABLE jd_pool ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, source TEXT NOT NULL, source_detail TEXT NOT NULL, "
            "job_title TEXT NOT NULL, raw_text TEXT NOT NULL, duties TEXT, experience TEXT, "
            "quality REAL, dup_group TEXT, crawled_at TEXT, status TEXT)"
        ))
    SessionLocal = sessionmaker(bind=engine)

    def provider():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    monkeypatch.setattr(bridge, "_get_db", provider)
    return engine


def test_list_capture_never_inserts_but_valid_detail_inserts_once(private_state, isolated_db):
    run_id = bridge.create_session(
        {"keyword": "Java", "city_name": "北京", "city_code": "101010100"}
    )["run_id"]

    bridge.append_capture(run_id, list_capture(count=1))
    with isolated_db.connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM jd_pool")).scalar_one() == 0

    inserted = bridge.append_capture(run_id, detail_capture())
    assert inserted["result"]["outcome"] == "inserted"
    assert inserted["result"]["jd_pool_id"]

    current = bridge.get_session(run_id)
    assert current["listed"] == 1
    assert current["detail_attempted"] == 1
    assert current["detail_obtained"] == 1
    assert current["content_eligible"] == 1
    assert current["identity_verified"] == 1
    assert current["complete"] == 1
    assert current["inserted"] == 1

    with isolated_db.connect() as connection:
        row = connection.execute(text(
            "SELECT id, source, source_detail, job_title, raw_text FROM jd_pool"
        )).mappings().one()
        assert row["source"] == "boss"
        assert row["source_detail"] == "https://www.zhipin.com/job_detail/job-0.html"
        assert "Spring Boot" in row["raw_text"]

    repeated = bridge.append_capture(run_id, detail_capture(description="负责 Java 服务端开发\n掌握 MySQL"))
    assert repeated["result"]["outcome"] == "skipped"
    assert repeated["result"]["jd_pool_id"] == inserted["result"]["jd_pool_id"]
    assert bridge.get_session(run_id)["inserted"] == 1
    with isolated_db.connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM jd_pool")).scalar_one() == 1

    results = control.get_results(run_id)
    assert len(results) == 1
    assert results[0]["identity_status"] == "verified"
    assert results[0]["content_eligible"] is True
    assert results[0]["outcome"] == "skipped"


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"challenge_detected": True}, "security_verification"),
        ({"description_truncated": True}, "truncated_description"),
        ({"description": ""}, "empty_detail"),
        ({"title": "另一个岗位"}, "title_mismatch"),
    ],
)
def test_invalid_detail_is_rejected_without_write(private_state, isolated_db, change, reason):
    run_id = bridge.create_session(
        {"keyword": "Java", "city_name": "北京", "city_code": "101010100"}
    )["run_id"]
    bridge.append_capture(run_id, list_capture(count=1))

    result = bridge.append_capture(run_id, detail_capture(**change))

    assert result["result"]["outcome"] == "rejected"
    assert result["result"]["reason"] == reason
    with isolated_db.connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM jd_pool")).scalar_one() == 0
    current = bridge.get_session(run_id)
    assert current["inserted"] == 0
    assert current["rejected"] == 1


def test_sixth_detail_url_is_rejected_at_session_limit(private_state, isolated_db):
    run_id = bridge.create_session(
        {"keyword": "Java", "city_name": "北京", "city_code": "101010100", "detail_limit": 5}
    )["run_id"]
    bridge.append_capture(run_id, list_capture(count=5))

    for index in range(5):
        payload = detail_capture(
            url=f"https://www.zhipin.com/job_detail/job-{index}.html",
            title=f"Java 后端工程师 {index}",
        )
        payload["page_url"] = payload["detail"]["url"]
        bridge.append_capture(run_id, payload)

    sixth = detail_capture(url="https://www.zhipin.com/job_detail/job-5.html", title="Java 后端工程师 5")
    sixth["page_url"] = sixth["detail"]["url"]
    result = bridge.append_capture(run_id, sixth)

    assert result["result"]["outcome"] == "rejected"
    assert result["result"]["reason"] == "bridge_session_limit_reached"
    assert bridge.get_session(run_id)["detail_attempted"] == 5

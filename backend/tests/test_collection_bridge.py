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
    monkeypatch.setattr(control, '_PROCESS', None)
    monkeypatch.setattr(control, '_STARTING_RUN', None)
    monkeypatch.setattr(control, '_RESERVATION', None)
    try:
        yield state
    finally:
        for path in state.rglob('*'):
            if path.is_file():
                path.unlink()
        assert not any(path.is_file() for path in state.rglob('*'))


def test_only_one_bridge_session_can_be_active(private_state):
    payload = {'keyword': 'Java', 'city_name': '北京', 'city_code': '101010100'}
    first = bridge.create_session(payload)['run_id']
    with pytest.raises(RuntimeError, match='桥接'):
        bridge.create_session(payload)
    bridge.finish_session(first)
    assert bridge.create_session(payload)['run_id'] != first


def test_creating_bridge_session_does_not_query_database_or_browser(private_state, monkeypatch):
    calls = []
    monkeypatch.setattr(control, 'get_database_stats', lambda: calls.append('database') or {
        'database_total': 0, 'database_boss_total': 0, 'database_new_count': 0,
    })
    monkeypatch.setattr(control, '_ensure_browser', lambda *a: calls.append('browser') or {})
    bridge.create_session({'keyword': 'Java', 'city_name': '北京', 'city_code': '101010100'})
    assert calls == []


def test_extension_blocked_capture_stops_session_without_database(private_state, monkeypatch):
    monkeypatch.setattr(bridge, '_get_db', lambda: pytest.fail('blocked capture must not reach database'))
    run_id = bridge.create_session({'keyword': 'Java', 'city_name': '北京', 'city_code': '101010100'})['run_id']
    result = bridge.append_capture(run_id, {
        'schema_version': 'm1-browser-bridge-v1', 'kind': 'blocked',
        'page_url': 'https://www.zhipin.com/web/passport/zp/security.html',
        'blocked_reason': 'security_verification',
    })
    assert result['session']['status'] == 'stopped'
    assert result['session']['finished_at']
    assert result['session']['stop_reason'] == 'security_verification'
    assert result['session']['detail_attempted'] == 0
    with pytest.raises(ValueError, match='已结束'):
        bridge.append_capture(run_id, list_capture())


@pytest.mark.parametrize('action', ['start', 'reserve'])
def test_active_bridge_blocks_single_and_batch_control_entries(private_state, monkeypatch, action):
    bridge.create_session({'keyword': 'Java', 'city_name': '北京', 'city_code': '101010100'})
    class Thread:
        def __init__(self, **kwargs): pass
        def start(self): pass
    monkeypatch.setattr(control.threading, 'Thread', Thread)
    with pytest.raises(RuntimeError, match='桥接'):
        control.start_task({}) if action == 'start' else control._reserve_tasks()


@pytest.mark.parametrize('query', ['city=101010100&query=Java&page=2',
                                  'city=101020100&query=Java&page=1',
                                  'city=101010100&query=Python&page=1'])
def test_list_capture_must_match_single_page_session_target(private_state, query):
    run_id = bridge.create_session({'keyword': 'Java', 'city_name': '北京', 'city_code': '101010100'})['run_id']
    payload = list_capture()
    payload['page_url'] = 'https://www.zhipin.com/web/geek/jobs?' + query
    with pytest.raises(ValueError, match='bridge_search_target_mismatch'):
        bridge.append_capture(run_id, payload)
    assert bridge.get_session(run_id)['listed'] == 0


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
    path = tmp_path / 'bridge.sqlite'
    engine = create_engine(f"sqlite:///{path}")
    with engine.begin() as connection:
        connection.execute(text(
            "CREATE TABLE jd_pool ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, source TEXT NOT NULL, source_detail TEXT NOT NULL, "
            "job_title TEXT NOT NULL, raw_text TEXT NOT NULL, duties TEXT, experience TEXT, "
            "quality REAL, dup_group TEXT, crawled_at TEXT, status TEXT, "
            "identity_status TEXT DEFAULT 'unknown', content_eligible BOOLEAN, identity_evidence TEXT)"
        ))
    SessionLocal = sessionmaker(bind=engine)

    def provider():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    monkeypatch.setattr(bridge, "_get_db", provider)
    try:
        yield engine
    finally:
        engine.dispose()
        path.unlink(missing_ok=True)
        assert not path.exists()


def test_missing_identity_schema_never_silently_drops_evidence(private_state, isolated_db):
    with isolated_db.begin() as db:
        for column in ('identity_status', 'content_eligible', 'identity_evidence'):
            db.exec_driver_sql(f'ALTER TABLE jd_pool DROP COLUMN {column}')
    run_id = bridge.create_session({'keyword': 'Java', 'city_name': '北京', 'city_code': '101010100'})['run_id']
    bridge.append_capture(run_id, list_capture())
    result = bridge.append_capture(run_id, detail_capture())
    assert result['result'] == {'outcome': 'failed', 'reason': 'identity_schema_migration_required'}
    assert result['session']['finished_at']
    assert result['session']['status'] == 'error'
    with isolated_db.connect() as db:
        assert db.execute(text('SELECT COUNT(*) FROM jd_pool')).scalar_one() == 0


@pytest.mark.parametrize('capture_list_first', [True, False])
def test_only_details_in_session_list_can_persist(private_state, isolated_db, capture_list_first):
    run_id = bridge.create_session({'keyword': 'Java', 'city_name': '北京', 'city_code': '101010100'})['run_id']
    if capture_list_first:
        bridge.append_capture(run_id, list_capture())
    other = detail_capture(url='https://www.zhipin.com/job_detail/outside.html')
    other['page_url'] = other['detail']['url']
    result = bridge.append_capture(run_id, other)
    assert result['result'] == {'outcome': 'rejected', 'reason': 'detail_not_in_session_list'}
    with isolated_db.connect() as db:
        assert db.execute(text('SELECT COUNT(*) FROM jd_pool')).scalar_one() == 0


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


def test_control_api_pairing_list_detail_and_verification_stop(private_state, isolated_db, monkeypatch):
    import asyncio
    import httpx
    from app.main import app
    from app.collect import bridge_access

    monkeypatch.setattr(bridge_access, '_TOKEN_PATH', private_state / 'synthetic-bridge.token')
    monkeypatch.setenv('TALENTMIND_LOCAL_RAW', '1')
    async def scenario():
        transport = httpx.ASGITransport(app=app, client=('127.0.0.1', 40001))
        async with httpx.AsyncClient(transport=transport, base_url='http://127.0.0.1:18000') as client:
            management = {'Origin': 'http://127.0.0.1:18080'}
            pairing = (await client.get('/api/collection/bridge/pairing', headers=management)).json()
            assert pairing['code'] == 0
            extension = {'Origin': bridge_access.EXTENSION_ORIGIN,
                         bridge_access.TOKEN_HEADER: pairing['data']['token']}
            created = (await client.post('/api/collection/bridge/sessions', headers=management, json={
                'keyword': 'Java', 'city_name': '北京', 'city_code': '101010100',
                'pages': 1, 'max_jobs': 2, 'detail_limit': 2,
            })).json()
            run_id = created['data']['run_id']
            base = f'/api/collection/bridge/sessions/{run_id}'
            listed = await client.post(base + '/captures', headers=extension, json=list_capture(count=2))
            assert listed.json()['data']['session']['listed'] == 2
            detail = await client.post(base + '/captures', headers=extension, json=detail_capture())
            assert detail.json()['data']['result']['outcome'] == 'inserted'
            blocked = await client.post(base + '/captures', headers=extension, json={
                'schema_version': 'm1-browser-bridge-v1', 'kind': 'blocked',
                'page_url': 'https://www.zhipin.com/web/passport/zp/security.html',
                'blocked_reason': 'security_verification',
            })
            assert blocked.json()['data']['session']['status'] == 'stopped'
            rows = (await client.get('/api/collection/results', params={'run_id': run_id}, headers=management)).json()
            assert rows['data'][0]['outcome'] == 'inserted'
            assert len(rows['data']) == 2
            after = (await client.post(base + '/captures', headers=extension, json=detail_capture())).json()
            assert after['code'] != 0
    asyncio.run(scenario())
    with isolated_db.connect() as connection:
        assert connection.execute(text('SELECT COUNT(*) FROM jd_pool')).scalar_one() == 1


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

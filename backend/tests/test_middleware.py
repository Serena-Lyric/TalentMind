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

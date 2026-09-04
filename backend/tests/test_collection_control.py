from datetime import datetime

from app.collect import control


def test_log_line_updates_task(tmp_path, monkeypatch):
    state_path = tmp_path / "control-state.json"
    monkeypatch.setattr(control, "_STATE_DIR", tmp_path)
    monkeypatch.setattr(control, "_STATE_PATH", state_path)
    monkeypatch.setattr(control, "_PROCESS", None)
    state = control._default_state()
    state["current_task"] = control._empty_task("boss-test", state["config"])
    control._save_state(state)

    control._parse_log_line("boss-test", "BOSS 第 2 轮开始: 北京/Python; pages=1")
    updated = control._load_state()["current_task"]

    assert updated["status"] == "running"
    assert updated["current_round"] == 2
    assert updated["current_city"] == "北京"
    assert updated["current_keyword"] == "Python"


def test_get_status_defaults_to_idle_without_task(tmp_path, monkeypatch):
    monkeypatch.setattr(control, "_STATE_DIR", tmp_path)
    monkeypatch.setattr(control, "_STATE_PATH", tmp_path / "control-state.json")
    monkeypatch.setattr(control, "_PROCESS", None)
    monkeypatch.setattr(control, "get_database_stats", lambda: {"database_total": 0, "database_boss_total": 0, "database_new_count": 0})

    status = control.get_status()

    assert status["status"] == "idle"
    assert status["run_id"] is None

def test_prepare_browser_auto_start_uses_single_round(tmp_path, monkeypatch):
    state_path = tmp_path / "control-state.json"
    monkeypatch.setattr(control, "_STATE_DIR", tmp_path)
    monkeypatch.setattr(control, "_STATE_PATH", state_path)
    config = {**control._DEFAULT_CONFIG, "mode": "continuous", "rounds": 9}
    monkeypatch.setattr(control, "get_config", lambda: config)
    monkeypatch.setattr(control, "_ensure_browser", lambda endpoint, user_data_dir: {
        "endpoint": endpoint, "reachable": True, "boss_page_count": 1, "login_required": False,
    })
    calls = []
    monkeypatch.setattr(control, "start_task", lambda payload: calls.append(payload) or {"run_id": "boss-test"})

    result = control.prepare_browser(auto_start=True)

    assert result["status"] == "started"
    assert calls == [{"mode": "once", "rounds": 0}]



class _FakeRecentSession:
    """仅支撑 get_recent_raw 的只读 execute().mappings().all() 链。"""

    def __init__(self, rows):
        self._rows = rows

    def execute(self, *args, **kwargs):
        return self

    def mappings(self):
        return self

    def all(self):
        return self._rows

    def close(self):
        pass


def test_get_recent_raw_returns_latest_rows(tmp_path, monkeypatch):
    import app.db.mysql as db_mysql
    rows = [
        {"id": 2, "source": "zhaopin", "job_title": "后端工程师", "quality": 0.73,
         "crawled_at": datetime(2026, 8, 28, 21, 6, 45), "body": "岗位职责：" + "长" * 400},
        {"id": 1, "source": "boss", "job_title": "EDC产品经理", "quality": 0.16,
         "crawled_at": datetime(2026, 8, 28, 21, 13, 18), "body": ""},
    ]
    monkeypatch.setattr(db_mysql, "SessionLocal", lambda: _FakeRecentSession(rows))

    result = control.get_recent_raw(limit=10)

    assert len(result) == 2
    assert result[0]["job_title"] == "后端工程师"
    assert result[0]["content"].endswith("…")
    assert result[1]["content"] == ""
    assert result[1]["crawled_at"] == "2026-08-28T21:13:18"
    assert "body" not in result[0]

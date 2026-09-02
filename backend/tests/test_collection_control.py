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

from app.collect import control


def test_legacy_utf8_log_is_parsed(tmp_path):
    log = tmp_path / "zhaopin_collect_loop.out.log"
    log.write_text("[2026-09-02 10:00:00] zhaopin 第 1 轮开始: 北京/Python; pages=1\n[2026-09-02 10:01:00] zhaopin 第 1 轮完成: {'platform': 'zhaopin', 'listed': 12, 'details': 8, 'new': 2, 'skipped': 10}\n", encoding="utf-8")
    summary = control._summarize_log(log)
    assert summary["platform"] == "zhaopin"
    assert summary["current_round"] == 1
    assert summary["listed"] == 12
    assert summary["details"] == 8
    assert summary["new"] == 2
    assert summary["log_status"] == "parsed"


def test_log_lines_keep_history_tail(tmp_path, monkeypatch):
    state_path = tmp_path / "control-state.json"
    monkeypatch.setattr(control, "_STATE_DIR", tmp_path)
    monkeypatch.setattr(control, "_STATE_PATH", state_path)
    state = control._default_state()
    state["current_task"] = control._empty_task("liepin-test", state["config"])
    control._save_state(state)
    control._parse_log_line("liepin-test", "[2026-09-02 10:00:00] liepin 第 1 轮开始: 杭州/Java; pages=1")
    control._parse_log_line("liepin-test", "[2026-09-02 10:01:00] liepin 第 1 轮完成: {'listed': 3, 'details': 2, 'new': 1, 'skipped': 2}")
    task = control._load_state()["current_task"]
    assert task["new"] == 1
    assert task["raw_log_tail"]

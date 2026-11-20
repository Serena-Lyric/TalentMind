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

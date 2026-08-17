"""D42 多源交叉验证：纯函数单测（不联网不写库）。"""
from app.collect.cross_validate import normalize_title, hn_segments, _is_match


def test_normalize_title():
    assert normalize_title("  Senior Backend Engineer (Python) ") == "senior backend engineer python"
    assert normalize_title("PostHog | Full-Time | REMOTE") == "posthog full time remote"


def test_hn_segments_requires_two_words():
    segs = hn_segments("PostHog | Full-Time | Technical CSMs, Technical AEs | REMOTE")
    # 单段（Full-Time/REMOTE/PostHog）被过滤；多词段保留
    assert "posthog" not in segs
    assert any("technical csms" in s for s in segs)
    assert all(" " in s for s in segs)


def test_is_match():
    assert _is_match("software engineer", "senior software engineer")      # 双向包含 + 长度比
    assert _is_match("devops engineer", "devops engineer")
    assert not _is_match("engineer", "licensed healthcare insurance agent work from home")  # 单段/长度悬殊
    assert not _is_match("sales", "full stack engineer")                    # 泛词不匹配
    assert not _is_match("", "software engineer")
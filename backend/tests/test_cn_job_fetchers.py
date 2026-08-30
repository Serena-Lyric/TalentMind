from app.collect.fetchers.job_sites import (
    SITES,
    build_detail_extract_js,
    build_search_extract_js,
    deduplicate_jobs,
    normalize_job,
    normalize_url,
)
from app.collect.cn_collect_loop import QueryTarget, build_targets


def test_normalize_url_strips_tracking_query():
    spec = SITES["zhaopin"]
    assert normalize_url(spec, "/job/abc.html?sid=1") == "https://www.zhaopin.com/job/abc.html"
    assert normalize_url(spec, "/sou/?kw=Python") == ""


def test_liepin_normalizes_detail_url():
    spec = SITES["liepin"]
    assert normalize_url(spec, "https://www.liepin.com/job/123456/") == "https://www.liepin.com/job/123456"


def test_dedup_keeps_tags_from_richer_record():
    spec = SITES["zhaopin"]
    jobs = deduplicate_jobs(spec, [
        {"url": "/job/abc", "title": "Python 工程师"},
        {"url": "/job/abc?x=1", "title": "Python 工程师", "tags": ["本科"]},
    ])
    assert len(jobs) == 1
    assert jobs[0]["tags"] == ["本科"]


def test_normalize_job_returns_platform_source_and_raw_text():
    spec = SITES["liepin"]
    raw = normalize_job(spec, {
        "url": "/job/abc",
        "title": "数据工程师",
        "company": "示例公司",
        "tags": ["3-5年", "本科", "Python"],
    }, {"description": "负责数据平台建设", "company_info": "软件服务公司"})
    assert raw is not None
    assert raw.source == "liepin"
    assert raw.experience == ""
    assert "负责数据平台建设" in raw.raw_html
    assert raw.source_detail.endswith("/job/abc")


def test_build_targets_stable_order():
    assert build_targets(["Python", "Java"], [("北京", "530"), ("上海", "538")]) == [
        QueryTarget("Python", "北京", "530"),
        QueryTarget("Python", "上海", "538"),
        QueryTarget("Java", "北京", "530"),
        QueryTarget("Java", "上海", "538"),
    ]


def test_zhaopin_dom_identity_is_stable_and_kept_over_detail_url():
    spec = SITES["zhaopin"]
    assert normalize_url(spec, "dom://zhaopin/cfca7fe7") == "dom://zhaopin/cfca7fe7"
    raw = normalize_job(
        spec,
        {"url": "dom://zhaopin/cfca7fe7", "title": "Python 工程师"},
        {"url": "https://www.zhaopin.com/job/real-detail", "description": "负责平台开发"},
    )
    assert raw is not None
    assert raw.source_detail == "dom://zhaopin/cfca7fe7"


def test_dom_extract_scripts_include_current_site_selectors_without_extra_quotes():
    zhaopin_js = build_search_extract_js(SITES["zhaopin"])
    liepin_js = build_search_extract_js(SITES["liepin"])
    assert 'const cards = ".job-card' in zhaopin_js
    assert "dom://zhaopin/" in zhaopin_js
    assert "const titleRequired = false" in zhaopin_js
    assert "const titleRequired = true" in liepin_js
    assert 'const cards = ".job-list-item' in liepin_js
    assert "[class*='job-card']" in liepin_js
    for script in (zhaopin_js, liepin_js, build_detail_extract_js(SITES["zhaopin"]), build_detail_extract_js(SITES["liepin"])):
        assert "querySelectorAll(''" not in script
        assert "const cards = '" not in script

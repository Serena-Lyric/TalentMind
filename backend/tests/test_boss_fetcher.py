"""BOSS 采集纯函数测试，不联网、不启动浏览器、不写数据库。"""
from app.collect.fetchers.boss import deduplicate_jobs, normalize_boss_job, normalize_url


def test_normalize_url_removes_tracking_query():
    assert normalize_url("/job_detail/abc.html?ka=header-job-detail") == "https://www.zhipin.com/job_detail/abc.html"
    assert normalize_url("/job_detail/") == ""


def test_deduplicate_jobs_keeps_detail_rich_record():
    jobs = deduplicate_jobs([
        {"url": "/job_detail/abc.html", "title": "Python 工程师"},
        {"url": "https://www.zhipin.com/job_detail/abc.html?sid=1", "title": "Python 工程师", "tags": ["本科"]},
    ])
    assert len(jobs) == 1
    assert jobs[0]["tags"] == ["本科"]


def test_normalize_boss_job_keeps_merged_detail_fields():
    raw = normalize_boss_job({
        "url": "/job_detail/merged.html",
        "title": "Python 工程师",
        "description": "负责后端服务开发",
        "company_info": "示例公司简介",
    })
    assert raw is not None
    assert "负责后端服务开发" in raw.raw_html
    assert "示例公司简介" in raw.raw_html


def test_normalize_boss_job_to_rawjd():
    raw = normalize_boss_job({
        "url": "/job_detail/abc.html",
        "title": "Python 后端工程师",
        "company": "示例公司",
        "salary": "20-30K",
        "location": "北京·海淀",
        "tags": ["3-5年", "本科", "Python"],
    }, {
        "description": "负责后端服务开发",
        "company_info": "软件服务公司",
    })
    assert raw is not None
    assert raw.source == "boss"
    assert raw.job_title == "Python 后端工程师"
    assert raw.experience == "3-5年"
    assert "负责后端服务开发" in raw.raw_html
    assert raw.source_detail.endswith("/job_detail/abc.html")

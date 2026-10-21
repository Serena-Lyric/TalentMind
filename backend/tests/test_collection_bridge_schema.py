import pytest
from pydantic import ValidationError

from app.collect.bridge_schema import validate_capture


def valid_list() -> dict:
    return {
        "schema_version": "m1-browser-bridge-v1",
        "kind": "list",
        "page_url": "https://www.zhipin.com/web/geek/jobs?city=101010100&query=Java&page=1",
        "items": [
            {
                "url": "https://www.zhipin.com/job_detail/abc123.html",
                "title": "Java 后端工程师",
                "company": "示例科技",
                "salary": "20-30K",
                "location": "北京",
                "tags": ["Java", "Spring Boot"],
            }
        ],
        "detail": None,
    }


def valid_detail() -> dict:
    return {
        "schema_version": "m1-browser-bridge-v1",
        "kind": "detail",
        "page_url": "https://www.zhipin.com/job_detail/abc123.html",
        "items": [],
        "detail": {
            "url": "https://www.zhipin.com/job_detail/abc123.html",
            "title": "Java 后端工程师",
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


def test_valid_list_and_detail_are_bounded_text_captures():
    listed = validate_capture(valid_list())
    detail = validate_capture(valid_detail())

    assert listed.kind == "list"
    assert len(listed.items) == 1
    assert detail.kind == "detail"
    assert detail.detail is not None
    assert "Spring Boot" in detail.detail.description


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("url", "https://evil.example/job_detail/abc"),
        ("url", "javascript:alert(1)"),
    ],
)
def test_detail_rejects_foreign_or_non_http_url(field, value):
    payload = valid_detail()
    payload["detail"][field] = value

    with pytest.raises((ValidationError, ValueError)):
        validate_capture(payload)


def test_capture_rejects_credentials_html_or_wrong_kind_shape():
    credential = valid_list()
    credential["cookie"] = "session=secret"
    with pytest.raises((ValidationError, ValueError)):
        validate_capture(credential)

    html = valid_detail()
    html["detail"]["html"] = "<main>private markup</main>"
    with pytest.raises((ValidationError, ValueError)):
        validate_capture(html)

    wrong_shape = valid_list()
    wrong_shape["kind"] = "detail"
    with pytest.raises((ValidationError, ValueError)):
        validate_capture(wrong_shape)


def test_list_capture_has_five_item_hard_limit():
    payload = valid_list()
    item = payload["items"][0]
    payload["items"] = [{**item, "url": f"https://www.zhipin.com/job_detail/{index}.html"} for index in range(6)]

    with pytest.raises((ValidationError, ValueError)):
        validate_capture(payload)


def test_detail_page_url_must_match_the_captured_job_url():
    payload = valid_detail()
    payload["page_url"] = "https://www.zhipin.com/web/geek/jobs?query=Java"

    with pytest.raises((ValidationError, ValueError)):
        validate_capture(payload)


def test_detail_rejects_overlarge_or_tag_markup_body():
    payload = valid_detail()
    payload["detail"]["description"] = "<div>not plain visible text</div>"

    with pytest.raises((ValidationError, ValueError)):
        validate_capture(payload)

    payload = valid_detail()
    payload["detail"]["description"] = "岗位" * 60_000

    with pytest.raises((ValidationError, ValueError)):
        validate_capture(payload)

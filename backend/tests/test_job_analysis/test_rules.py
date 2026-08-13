"""测试硬规则预筛。"""
from app.job_analysis.models import JdRecord, RejectedItem
from app.job_analysis.rules import apply_rules, _is_readable_char, _info_density


def make_record(
    id=1, source="test", job_title="Test Job", raw_text="Test content",
    duties="Some duties", experience="3 years", quality=0.5,
    dup_group="", crawled_at="2026-01-01", status="cleaned",
):
    return JdRecord(
        id=id, source=source, job_title=job_title, raw_text=raw_text,
        duties=duties, experience=experience, quality=quality,
        dup_group=dup_group, crawled_at=crawled_at, status=status,
    )


def test_is_readable_char_cjk():
    assert _is_readable_char("中")
    assert _is_readable_char("文")
    assert _is_readable_char("！")
    assert _is_readable_char(" ")


def test_is_readable_char_ascii():
    assert _is_readable_char("a")
    assert _is_readable_char("Z")
    assert _is_readable_char("1")
    assert _is_readable_char(".")


def test_is_readable_char_garbled():
    # 私用区字符
    assert not _is_readable_char("")


def test_apply_rules_empty_fields():
    r1 = make_record(id=1, raw_text="", duties="")
    r2 = make_record(id=2, raw_text="content", duties="")
    passed, rejected = apply_rules([r1, r2])
    assert len(passed) == 1
    assert passed[0].id == 2
    assert len(rejected) == 1
    assert rejected[0].rule_id == "empty_fields"


def test_apply_rules_garbled():
    # 全是乱码字符
    garbled_text = "" * 100
    r1 = make_record(id=1, raw_text=garbled_text)
    r2 = make_record(id=2, raw_text="正常的中文JD内容，包含AI、大模型等技术要求")
    passed, rejected = apply_rules([r1, r2])
    assert len(passed) == 1
    assert passed[0].id == 2
    assert len(rejected) == 1
    assert rejected[0].rule_id == "garbled"


def test_apply_rules_short_text_skip_garbled():
    # 短文本即使可读比例低也 pass
    short_text = "" * 10  # 少于 garbled_min_length (30)
    r = make_record(id=1, raw_text=short_text)
    passed, rejected = apply_rules([r])
    assert len(passed) == 1


def test_apply_rules_duplicate_group():
    r1 = make_record(id=1, dup_group="g1", quality=0.8,
                     raw_text="short")
    r2 = make_record(id=2, dup_group="g1", quality=0.5,
                     raw_text="much longer text with more content")
    passed, rejected = apply_rules([r1, r2])
    assert len(passed) == 1
    # quality 高的保留
    assert passed[0].id == 1
    assert len(rejected) == 1
    assert rejected[0].rule_id == "duplicate"
    assert rejected[0].kept_jd_id == 1


def test_apply_rules_duplicate_same_quality():
    # quality 相同时保留信息密度高的
    r1 = make_record(id=1, dup_group="g1", quality=0.5,
                     raw_text="short")
    r2 = make_record(id=2, dup_group="g1", quality=0.5,
                     raw_text="much longer text with more content and details")
    passed, rejected = apply_rules([r1, r2])
    assert len(passed) == 1
    assert passed[0].id == 2  # 更长文本


def test_apply_rules_no_dup_group():
    r1 = make_record(id=1, dup_group="")
    r2 = make_record(id=2, dup_group="")
    passed, rejected = apply_rules([r1, r2])
    assert len(passed) == 2


def test_info_density():
    r1 = make_record(raw_text="hello world", duties="test")
    r2 = make_record(raw_text="hello world<br/>more text", duties="")
    assert _info_density(r2) > _info_density(r1)

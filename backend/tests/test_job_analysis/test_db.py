"""测试 SQL 解析器。"""
import pytest
from pathlib import Path
from app.job_analysis.db import parse_jd_pool, parse_records_by_ids, _unescape_sql, _split_sql_values
from app.job_analysis.models import JdRecord

DATA_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "job_analysis"


def test_unescape_sql():
    assert _unescape_sql("hello\\'world") == "hello'world"
    assert _unescape_sql("line1\\nline2") == "line1\nline2"
    assert _unescape_sql("tab\\there") == "tab\there"
    assert _unescape_sql("back\\\\slash") == "back\\slash"


def test_split_sql_values_simple():
    fields = _split_sql_values("1020,'dataset','AI Engineer','text','duties','exp',0.31,'grp','2026-07-24','cleaned'")
    assert len(fields) == 10
    assert fields[0] == "1020"
    assert fields[1] == "dataset"
    assert fields[2] == "AI Engineer"
    assert fields[6] == "0.31"
    assert fields[9] == "cleaned"


def test_split_sql_values_empty():
    fields = _split_sql_values("1,'src','title','','','',0.5,'','',''")
    assert len(fields) == 10
    assert fields[3] == ""
    assert fields[4] == ""


def test_split_sql_values_with_commas_in_text():
    fields = _split_sql_values("1,'src','title','text, with, commas','duties','exp',0.5,'grp','2026-01-01','ok'")
    assert len(fields) == 10
    assert fields[3] == "text, with, commas"


def test_split_sql_values_with_escaped_quotes():
    fields = _split_sql_values("1,'src','it''s a title','text','','',0.5,'','',''")
    assert fields[2] == "it's a title"


def test_parse_jd_pool():
    sql_path = DATA_DIR / "seed_jd_pool.sql"
    if not sql_path.exists():
        pytest.skip("seed_jd_pool.sql not found")
    records = parse_jd_pool(str(sql_path))
    assert len(records) > 0
    assert all(isinstance(r, JdRecord) for r in records)
    assert all(r.id > 0 for r in records)
    assert all(r.status for r in records)


def test_parse_records_by_ids():
    sql_path = DATA_DIR / "seed_jd_pool.sql"
    if not sql_path.exists():
        pytest.skip("seed_jd_pool.sql not found")
    all_records = parse_jd_pool(str(sql_path))
    if len(all_records) >= 3:
        target_ids = {all_records[0].id, all_records[2].id}
        subset = parse_records_by_ids(str(sql_path), target_ids)
        assert len(subset) == 2
        assert {r.id for r in subset} == target_ids

"""Retained SQL value decoding used by read-only source exports."""
from app.integration.sql_values import split_sql_values as _split_sql_values


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

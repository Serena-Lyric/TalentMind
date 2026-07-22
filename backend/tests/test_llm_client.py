import json
from unittest.mock import MagicMock, patch
from app.llm import client as llm

def test_extract_json_parses_valid(monkeypatch):
    fake = MagicMock()
    fake.choices = [MagicMock(message=MagicMock(content='{"job":"AI工程师"}'))]
    with patch.object(llm, "_chat", return_value=fake):
        out = llm.extract_json("抽取岗位", '{"job": str}')
        assert out == {"job": "AI工程师"}

def test_extract_json_retries_on_bad_then_succeeds():
    bad = MagicMock(choices=[MagicMock(message=MagicMock(content="not json"))])
    good = MagicMock(choices=[MagicMock(message=MagicMock(content='{"ok":1}'))])
    with patch.object(llm, "_chat", side_effect=[bad, good]):
        out = llm.extract_json("x", "{}", retries=3)
        assert out == {"ok": 1}

def test_embed_returns_vectors():
    resp = MagicMock(data=[MagicMock(embedding=[0.1, 0.2]), MagicMock(embedding=[0.3, 0.4])])
    with patch.object(llm, "_embed_once", return_value=resp):
        out = llm.embed(["a", "b"])
        assert out == [[0.1, 0.2], [0.3, 0.4]]

def test_embed_retries_then_succeeds():
    good = MagicMock(data=[MagicMock(embedding=[0.5])])
    with patch.object(llm, "_embed_once", side_effect=[RuntimeError("429"), good]):
        out = llm.embed(["a"], retries=3)
        assert out == [[0.5]]

def test_embed_raises_after_exhausting_retries():
    with patch.object(llm, "_embed_once", side_effect=RuntimeError("down")):
        try:
            llm.embed(["a"], retries=2)
            assert False, "should have raised"
        except ValueError as e:
            assert "embedding 失败" in str(e)

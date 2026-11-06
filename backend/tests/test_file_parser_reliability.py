"""Legacy local-file parser regressions; independent of the web upload path."""

import subprocess
import sys
from io import BytesIO
from types import SimpleNamespace

import pytest

from app.matching.file_parser import DOCParser, DOCXParser, ResumeFileParser
from app.matching import file_parser


def test_clean_text_consumes_merged_line_once_and_keeps_following_lines():
    parser = ResumeFileParser.__new__(ResumeFileParser)
    source = "  技能  \n\nPython SQL and distributed data processing\n经历\n尾行"

    assert parser._clean_text(source) == (
        "技能 Python SQL and distributed data processing\n经历\n尾行"
    )


def test_missing_docx_dependency_raises_import_error(monkeypatch):
    monkeypatch.setitem(sys.modules, "docx", None)
    parser = DOCXParser()

    with pytest.raises(ImportError, match="python-docx"):
        parser.parse("unused.docx")


@pytest.mark.parametrize("antiword_available", [True, False])
def test_failed_textract_uses_existing_fallback_order(
    monkeypatch, antiword_available
):
    def fail_process(_):
        raise RuntimeError("synthetic conversion failure")

    monkeypatch.setitem(sys.modules, "textract", SimpleNamespace(process=fail_process))
    monkeypatch.setattr(DOCParser, "_check_antiword", lambda self: antiword_available)
    monkeypatch.setattr(
        subprocess, "run", lambda *args, **kwargs: SimpleNamespace(stdout="antiword text")
    )
    monkeypatch.setitem(
        sys.modules, "mammoth",
        SimpleNamespace(convert_to_text=lambda stream: SimpleNamespace(value="mammoth text")),
    )
    monkeypatch.setattr(
        file_parser, "open", lambda *args: BytesIO(b"synthetic local fixture"), raising=False
    )

    assert DOCParser().parse("synthetic.doc") == (
        "antiword text" if antiword_available else "mammoth text"
    )


def test_successful_textract_still_takes_priority(monkeypatch):
    monkeypatch.setitem(
        sys.modules, "textract", SimpleNamespace(process=lambda _: b"textract text")
    )
    monkeypatch.setattr(DOCParser, "_check_antiword", lambda self: True)

    assert DOCParser().parse("unused.doc") == "textract text"

"""Web upload format contract: synthetic bytes only, database access forbidden."""
import io
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from docx import Document
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.middleware import register_exception_handlers
from app.routers import mvp


def text_pdf(text=b"Python Docker"):
    """One-page standard PDF fixture without an optional generator dependency."""
    stream = b"BT /F1 12 Tf 40 80 Td (" + text + b") Tj ET"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 120] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    data = b"%PDF-1.4\n"
    offsets = [0]
    for number, obj in enumerate(objects, 1):
        offsets.append(len(data))
        data += f"{number} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(data)
    data += b"xref\n0 6\n0000000000 65535 f \n"
    data += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets[1:])
    return data + f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()


@pytest.fixture
def client(monkeypatch):
    def forbidden():
        pytest.fail("format test must not query a database")
    monkeypatch.setattr(mvp, "SessionLocal", forbidden)
    app = FastAPI()
    app.include_router(mvp.router, prefix="/api")
    register_exception_handlers(app)
    with TestClient(app) as connection:
        yield connection


def test_web_extracts_pdf_docx_and_bom_txt():
    assert mvp._extract_file_text("synthetic.pdf", text_pdf()).strip() == "Python Docker"
    document = Document()
    document.add_paragraph("姓名：格式测试")
    document.add_paragraph("技能：Python、Docker")
    output = io.BytesIO()
    document.save(output)
    assert "技能：Python、Docker" in mvp._extract_file_text("synthetic.docx", output.getvalue())
    assert mvp._extract_file_text("synthetic.txt", "姓名：格式测试\n技能：Python".encode("utf-8-sig")) == "姓名：格式测试\n技能：Python"


@pytest.mark.parametrize("name,body,expected", [
    ("old.doc", b"\xd0\xcf\x11\xe0", "旧版 DOC"),
    ("bad.pdf", b"not a PDF", "文件解析失败"),
    ("bad.docx", b"not a ZIP", "文件解析失败"),
    ("bad.txt", b"\xff\x00", "文件解析失败"),
    ("empty.pdf", text_pdf(b""), "未提取到简历文字"),
    ("empty.txt", b"", "未提取到简历文字"),
    ("big.txt", b"a" * (10 * 1024 * 1024 + 1), "10MB"),
], ids=["legacy-doc", "invalid-pdf", "invalid-docx", "binary-txt", "empty-pdf", "empty-txt", "oversize"])
def test_upload_rejects_invalid_formats_before_database(client, name, body, expected):
    result = client.post("/api/resume/upload", files={"file": (name, body)}).json()
    assert result["code"] != 0
    assert expected in result["message"]


def test_docx_expansion_limit_before_document_parser(client):
    output = io.BytesIO()
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", b"a" * (40 * 1024 * 1024 + 1))
    assert len(output.getvalue()) < 10 * 1024 * 1024
    with pytest.raises(ValueError, match="解压内容过大"):
        mvp._extract_file_text("expanded.docx", output.getvalue())
    result = client.post("/api/resume/upload", files={"file": ("expanded.docx", output.getvalue())}).json()
    assert result["code"] != 0
    assert "文件解析失败" in result["message"]

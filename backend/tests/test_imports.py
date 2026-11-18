"""Uploading files as new documents."""

import io
import zipfile
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter

from app.config import get_settings
from app.services import importers
from app.services.importers import LEGACY_DOC_MESSAGE, SUPPORTED_EXTENSIONS, UNSUPPORTED_MESSAGE

IMPORT_URL = "/api/documents/import"
FIXTURES = Path(__file__).parent / "fixtures"


def upload(client: TestClient, filename: str, data: bytes) -> httpx.Response:
    """POST a file to the import endpoint."""
    return client.post(IMPORT_URL, files={"file": (filename, data)})


def test_import_info_lists_supported_types_and_limit(alice: TestClient, anon: TestClient) -> None:
    response = alice.get(f"{IMPORT_URL}/info")

    assert response.status_code == 200
    assert response.json() == {"extensions": list(SUPPORTED_EXTENSIONS), "max_mb": 5}
    assert anon.get(f"{IMPORT_URL}/info").status_code == 401


def test_import_markdown_creates_document_with_heading_and_list(alice: TestClient) -> None:
    response = upload(alice, "Meeting notes.md", b"# Agenda\n\n- budget\n- hiring\n")

    assert response.status_code == 201
    doc = response.json()
    assert doc["title"] == "Meeting notes"
    assert doc["role"] == "owner"
    assert "<h1>Agenda</h1>" in doc["content_html"]
    assert "<li>budget</li>" in doc["content_html"]
    assert alice.get(f"/api/documents/{doc['id']}").json()["content_html"] == doc["content_html"]


def test_import_rejects_unsupported_type(alice: TestClient) -> None:
    response = upload(alice, "budget.xlsx", b"PK\x03\x04 fake spreadsheet")

    assert response.status_code == 415
    assert response.json() == {"detail": UNSUPPORTED_MESSAGE}
    for ext in SUPPORTED_EXTENSIONS:
        assert ext in UNSUPPORTED_MESSAGE
    assert alice.get("/api/documents").json()["owned"] == []


def test_import_rejects_legacy_doc_with_helpful_message(alice: TestClient) -> None:
    response = upload(alice, "old report.doc", b"\xd0\xcf\x11\xe0 legacy word binary")

    assert response.status_code == 415
    assert response.json() == {"detail": LEGACY_DOC_MESSAGE}
    assert "save as .docx" in LEGACY_DOC_MESSAGE


def test_import_rejects_empty_file(alice: TestClient) -> None:
    response = upload(alice, "empty.txt", b"")

    assert response.status_code == 400
    assert alice.get("/api/documents").json()["owned"] == []


def test_import_rejects_file_over_size_limit(alice: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "max_upload_mb", 1)

    response = upload(alice, "big.txt", b"a" * (1024 * 1024 + 1))

    assert response.status_code == 413
    assert response.json() == {"detail": "File is larger than 1 MB"}
    assert alice.get("/api/documents").json()["owned"] == []


def test_import_docx(alice: TestClient) -> None:
    docx = pytest.importorskip("docx")  # test-only dependency (requirements-dev.txt)
    document = docx.Document()
    document.add_heading("Launch plan", level=1)
    paragraph = document.add_paragraph()
    paragraph.add_run("Ship it").bold = True
    document.add_paragraph("first step", style="List Bullet")
    buffer = io.BytesIO()
    document.save(buffer)

    response = upload(alice, "launch.docx", buffer.getvalue())

    assert response.status_code == 201
    html = response.json()["content_html"]
    assert response.json()["title"] == "launch"
    assert "<h1>Launch plan</h1>" in html
    assert "<strong>Ship it</strong>" in html
    assert "<li>first step</li>" in html


def test_import_html_uses_title_tag_and_keeps_formatting(alice: TestClient) -> None:
    page = (
        "<!doctype html><html><head><title>Team &amp; Goals</title>"
        "<style>p { color: red }</style></head>"
        "<body><h2>Goals</h2><p>Ship <em>fast</em></p><ul><li>one</li></ul></body></html>"
    )

    response = upload(alice, "export.html", page.encode())

    assert response.status_code == 201
    doc = response.json()
    assert doc["title"] == "Team & Goals"
    assert doc["content_html"] == "<h2>Goals</h2><p>Ship <em>fast</em></p><ul><li>one</li></ul>"


def test_import_html_is_sanitized(alice: TestClient) -> None:
    page = '<p onclick="steal()">Hi</p><script>alert("xss")</script><a href="javascript:x()">bad</a>'

    html = upload(alice, "page.htm", page.encode()).json()["content_html"]

    assert "<script" not in html and "alert" not in html
    assert "onclick" not in html and "javascript:" not in html
    assert html.startswith("<p>Hi</p>")


def test_import_rtf_as_plain_text(alice: TestClient) -> None:
    rtf = r"{\rtf1\ansi{\fonttbl\f0 Arial;}\f0\b Bold title\b0\par\par Second paragraph\par}"

    response = upload(alice, "memo.rtf", rtf.encode())

    assert response.status_code == 201
    html = response.json()["content_html"]
    assert "Bold title" in html and "Second paragraph" in html
    assert "<strong>" not in html  # formatting is intentionally not preserved
    assert "\\rtf" not in html


def test_import_odt_keeps_headings_bold_and_lists(alice: TestClient) -> None:
    odf_doc = pytest.importorskip("odf.opendocument")  # test-only dependency (requirements-dev.txt)
    from odf.style import Style, TextProperties
    from odf.text import H, List, ListItem, P, Span

    document = odf_doc.OpenDocumentText()
    bold = Style(name="Bold", family="text")
    bold.addElement(TextProperties(fontweight="bold"))
    document.automaticstyles.addElement(bold)
    document.text.addElement(H(outlinelevel=1, text="Roadmap"))
    document.text.addElement(H(outlinelevel=5, text="Deep heading"))
    paragraph = P(text="Plan: ")
    paragraph.addElement(Span(stylename=bold, text="ship it"))
    document.text.addElement(paragraph)
    items = List()
    item = ListItem()
    item.addElement(P(text="first step"))
    items.addElement(item)
    document.text.addElement(items)
    buffer = io.BytesIO()
    document.save(buffer)

    response = upload(alice, "roadmap.odt", buffer.getvalue())

    assert response.status_code == 201
    assert response.json()["content_html"] == (
        "<h1>Roadmap</h1><h3>Deep heading</h3><p>Plan: <strong>ship it</strong></p>"
        "<ul><li><p>first step</p></li></ul>"
    )


def test_import_pdf_extracts_text(alice: TestClient) -> None:
    response = upload(alice, "report.pdf", (FIXTURES / "sample.pdf").read_bytes())

    assert response.status_code == 201
    assert response.json()["title"] == "report"
    html = response.json()["content_html"]
    assert "Quarterly report" in html and "Revenue grew in every region." in html


def test_import_pdf_without_text_is_rejected(alice: TestClient) -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    buffer = io.BytesIO()
    writer.write(buffer)

    response = upload(alice, "scan.pdf", buffer.getvalue())

    assert response.status_code == 400
    assert response.json() == {"detail": "This PDF has no selectable text (scanned PDFs aren't supported)"}


@pytest.mark.parametrize("filename", ["bomb.docx", "bomb.odt"])
def test_import_rejects_zip_that_expands_too_far(
    alice: TestClient, monkeypatch: pytest.MonkeyPatch, filename: str
) -> None:
    monkeypatch.setattr(importers, "MAX_UNZIPPED_BYTES", 1024)  # same check, small numbers
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("content.xml", "0" * 4096)  # 4 KB of zeros compresses to a few dozen bytes

    response = upload(alice, filename, archive.getvalue())

    assert response.status_code == 400
    assert response.json() == {"detail": importers.TOO_BIG_UNZIPPED}
    assert alice.get("/api/documents").json()["owned"] == []

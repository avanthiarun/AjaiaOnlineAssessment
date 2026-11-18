"""Uploading files as new documents."""

import io

import httpx
import pytest
from fastapi.testclient import TestClient

IMPORT_URL = "/api/documents/import"


def upload(client: TestClient, filename: str, data: bytes) -> httpx.Response:
    """POST a file to the import endpoint."""
    return client.post(IMPORT_URL, files={"file": (filename, data)})


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
    response = upload(alice, "report.pdf", b"%PDF-1.7 fake")

    assert response.status_code == 415
    assert response.json() == {"detail": "Supported files are .txt, .md and .docx"}
    assert alice.get("/api/documents").json()["owned"] == []


def test_import_rejects_empty_file(alice: TestClient) -> None:
    response = upload(alice, "empty.txt", b"")

    assert response.status_code == 400
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

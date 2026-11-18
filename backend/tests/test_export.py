"""Downloading documents as Markdown or a standalone HTML page."""

from fastapi.testclient import TestClient

from tests.helpers import create_doc, share

CONTENT = "<h1>Plan</h1><p><strong>Bold</strong> move</p><ul><li>one</li></ul>"


def test_markdown_export_downloads_converted_content(alice: TestClient) -> None:
    doc = create_doc(alice, title="Q3 plan")
    alice.patch(f"/api/documents/{doc['id']}", json={"content_html": CONTENT})

    response = alice.get(f"/api/documents/{doc['id']}/export?format=md")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    assert response.headers["content-disposition"] == 'attachment; filename="Q3 plan.md"'
    assert "# Plan" in response.text
    assert "**Bold** move" in response.text
    assert "* one" in response.text


def test_html_export_is_a_standalone_page_with_escaped_title(alice: TestClient) -> None:
    doc = create_doc(alice, title="Q&A <draft>")
    alice.patch(f"/api/documents/{doc['id']}", json={"content_html": CONTENT})

    response = alice.get(f"/api/documents/{doc['id']}/export?format=html")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert response.headers["content-disposition"] == 'attachment; filename="QA draft.html"'
    page = response.text
    assert page.startswith("<!doctype html>\n")
    assert '<meta charset="utf-8">' in page
    assert "<title>Q&amp;A &lt;draft&gt;</title>" in page
    assert f"<body>\n{CONTENT}\n</body>" in page


def test_export_is_allowed_for_viewers_and_hidden_from_unshared_users(
    alice: TestClient, bob: TestClient, carol: TestClient
) -> None:
    doc = create_doc(alice, title="Private")
    share(alice, doc["id"], "carol@ajaia.test", "viewer")

    for fmt in ("md", "html"):
        assert carol.get(f"/api/documents/{doc['id']}/export?format={fmt}").status_code == 200
        response = bob.get(f"/api/documents/{doc['id']}/export?format={fmt}")
        assert response.status_code == 404
        assert response.json() == {"detail": "Document not found"}

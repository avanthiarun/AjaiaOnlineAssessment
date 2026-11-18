"""Document create/edit/reopen and HTML sanitizing."""

from fastapi.testclient import TestClient

from tests.helpers import create_doc


def test_create_rename_edit_and_reopen_document(alice: TestClient) -> None:
    doc = create_doc(alice)
    assert doc["title"] == "Untitled document"
    assert doc["role"] == "owner"

    content = "<h2>Plan</h2><p><strong>Bold</strong> <em>it</em> <u>under</u></p><ul><li>one</li></ul>"
    response = alice.patch(
        f"/api/documents/{doc['id']}", json={"title": "  Q3 plan  ", "content_html": content}
    )
    assert response.status_code == 200

    reopened = alice.get(f"/api/documents/{doc['id']}").json()
    assert reopened["title"] == "Q3 plan"
    assert reopened["content_html"] == content
    assert reopened["updated_at"] > doc["updated_at"]
    assert [d["title"] for d in alice.get("/api/documents").json()["owned"]] == ["Q3 plan"]


def test_html_is_sanitized(alice: TestClient) -> None:
    doc = create_doc(alice)
    dirty = (
        '<h2 onclick="steal()">Title</h2>'
        "<script>alert('xss')</script>"
        '<p><strong onmouseover="x()">Safe</strong><img src=x onerror="alert(1)"></p>'
    )

    html = alice.patch(f"/api/documents/{doc['id']}", json={"content_html": dirty}).json()["content_html"]

    assert html == "<h2>Title</h2><p><strong>Safe</strong></p>"

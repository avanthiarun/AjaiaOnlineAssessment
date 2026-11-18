"""Version history: throttled snapshots, preview, restore and permissions."""

from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update

from app.db import SessionLocal, utc_now
from app.models import DocumentVersion
from app.services import documents as service
from tests.helpers import create_doc, share


def save(client: TestClient, doc_id: str, html: str) -> dict[str, Any]:
    """Save content (asserts it succeeded)."""
    response = client.patch(f"/api/documents/{doc_id}", json={"content_html": html})
    assert response.status_code == 200, response.text
    return response.json()


def versions(client: TestClient, doc_id: str) -> list[dict[str, Any]]:
    """The history list (asserts it succeeded)."""
    response = client.get(f"/api/documents/{doc_id}/versions")
    assert response.status_code == 200, response.text
    return response.json()


def content_of(client: TestClient, doc_id: str, version_id: str) -> str:
    """One version's content."""
    return client.get(f"/api/documents/{doc_id}/versions/{version_id}").json()["content_html"]


def age_snapshots(minutes: int) -> None:
    """Pretend every snapshot was taken `minutes` ago."""
    with SessionLocal() as db:
        db.execute(update(DocumentVersion).values(created_at=utc_now() - timedelta(minutes=minutes)))
        db.commit()


def test_quick_saves_make_one_snapshot_of_the_previous_content(alice: TestClient, bob: TestClient) -> None:
    doc = create_doc(alice)
    share(alice, doc["id"], "bob@ajaia.test", "editor")

    save(bob, doc["id"], "<p>A</p>")  # previous content was empty: nothing to keep
    save(alice, doc["id"], "<p>B</p>")  # snapshots A, written by Bob
    save(alice, doc["id"], "<p>C</p>")  # within 5 minutes of that snapshot: skipped

    history = versions(alice, doc["id"])
    assert [v["created_by"] for v in history] == ["Bob"]
    assert content_of(alice, doc["id"], history[0]["id"]) == "<p>A</p>"

    age_snapshots(minutes=6)
    save(alice, doc["id"], "<p>D</p>")  # throttle window passed: snapshots C
    history = versions(alice, doc["id"])
    assert [content_of(alice, doc["id"], v["id"]) for v in history] == ["<p>C</p>", "<p>A</p>"]


def test_restore_replaces_content_and_can_itself_be_undone(alice: TestClient) -> None:
    doc = create_doc(alice, title="Plan")
    save(alice, doc["id"], "<p>first draft</p>")
    save(alice, doc["id"], "<p>second draft</p>")
    first = versions(alice, doc["id"])[0]

    restored = alice.post(f"/api/documents/{doc['id']}/versions/{first['id']}/restore")

    assert restored.status_code == 200
    assert restored.json()["content_html"] == "<p>first draft</p>"
    assert restored.json()["version"] == 4  # 1 -> 2 -> 3 by saves, 4 by the restore
    assert restored.json()["title"] == "Plan"
    undo = versions(alice, doc["id"])[0]  # the restore snapshotted what it replaced
    assert content_of(alice, doc["id"], undo["id"]) == "<p>second draft</p>"
    alice.post(f"/api/documents/{doc['id']}/versions/{undo['id']}/restore")
    assert alice.get(f"/api/documents/{doc['id']}").json()["content_html"] == "<p>second draft</p>"


def test_only_the_newest_versions_are_kept(alice: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(service, "MAX_VERSIONS", 2)
    doc = create_doc(alice)
    for text in ("one", "two", "three", "four"):
        age_snapshots(minutes=6)
        save(alice, doc["id"], f"<p>{text}</p>")

    history = versions(alice, doc["id"])
    assert [content_of(alice, doc["id"], v["id"]) for v in history] == ["<p>three</p>", "<p>two</p>"]


def test_viewer_can_browse_but_not_restore_and_strangers_get_404(
    alice: TestClient, bob: TestClient, carol: TestClient
) -> None:
    doc = create_doc(alice)
    other = create_doc(alice)
    share(alice, doc["id"], "carol@ajaia.test", "viewer")
    save(alice, doc["id"], "<p>old</p>")
    save(alice, doc["id"], "<p>new</p>")
    version_id = versions(alice, doc["id"])[0]["id"]
    base = f"/api/documents/{doc['id']}/versions"

    assert len(versions(carol, doc["id"])) == 1
    assert content_of(carol, doc["id"], version_id) == "<p>old</p>"
    assert carol.post(f"{base}/{version_id}/restore").status_code == 403

    for response in (bob.get(base), bob.get(f"{base}/{version_id}"), bob.post(f"{base}/{version_id}/restore")):
        assert response.status_code == 404
        assert response.json() == {"detail": "Document not found"}
    wrong_doc = alice.get(f"/api/documents/{other['id']}/versions/{version_id}")
    assert wrong_doc.status_code == 404
    assert wrong_doc.json() == {"detail": "Version not found"}

"""Presence heartbeats: who else has a document open."""

from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import update

from app.db import SessionLocal, utc_now
from app.models import DocumentPresence, User
from tests.helpers import create_doc, share


def beat(client: TestClient, doc_id: str, editing: bool = False) -> dict:
    """Send a heartbeat and return the JSON (asserts it succeeded)."""
    response = client.post(f"/api/documents/{doc_id}/presence", json={"editing": editing})
    assert response.status_code == 200, response.text
    return response.json()


def test_two_users_heartbeating_see_each_other(alice: TestClient, bob: TestClient) -> None:
    doc = create_doc(alice, title="Live")
    share(alice, doc["id"], "bob@ajaia.test", "editor")

    assert beat(alice, doc["id"])["viewers"] == []  # nobody else yet, and never yourself
    from_bob = beat(bob, doc["id"], editing=True)
    from_alice = beat(alice, doc["id"])

    assert [(v["name"], v["role"], v["is_editing"]) for v in from_bob["viewers"]] == [("Alice", "owner", False)]
    assert [(v["name"], v["role"], v["is_editing"]) for v in from_alice["viewers"]] == [("Bob", "editor", True)]
    assert from_alice["version"] == 1


def test_heartbeat_reports_the_latest_version(alice: TestClient, bob: TestClient) -> None:
    doc = create_doc(alice)
    share(alice, doc["id"], "bob@ajaia.test", "editor")
    bob.patch(f"/api/documents/{doc['id']}", json={"content_html": "<p>new</p>", "base_version": 1})

    assert beat(alice, doc["id"])["version"] == 2


def test_heartbeats_older_than_30_seconds_are_excluded(alice: TestClient, bob: TestClient) -> None:
    doc = create_doc(alice)
    share(alice, doc["id"], "bob@ajaia.test", "viewer")
    beat(bob, doc["id"])
    with SessionLocal() as db:
        bob_id = db.query(User.id).filter_by(email="bob@ajaia.test").scalar()
        db.execute(
            update(DocumentPresence)
            .where(DocumentPresence.user_id == bob_id)
            .values(last_seen_at=utc_now() - timedelta(seconds=31))
        )
        db.commit()

    assert beat(alice, doc["id"])["viewers"] == []


def test_revoked_user_disappears_and_unshared_user_gets_404(
    alice: TestClient, bob: TestClient, carol: TestClient
) -> None:
    doc = create_doc(alice)
    share(alice, doc["id"], "bob@ajaia.test", "viewer")
    beat(bob, doc["id"])
    bob.delete(f"/api/documents/{doc['id']}/shares/me")

    assert beat(alice, doc["id"])["viewers"] == []
    for outsider in (bob, carol):
        response = outsider.post(f"/api/documents/{doc['id']}/presence", json={"editing": False})
        assert response.status_code == 404
        assert response.json() == {"detail": "Document not found"}

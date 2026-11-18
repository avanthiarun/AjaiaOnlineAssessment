"""Access control: owners, editors, viewers and strangers."""

from fastapi.testclient import TestClient

from tests.helpers import create_doc, share


def test_unshared_user_gets_404(alice: TestClient, bob: TestClient) -> None:
    doc = create_doc(alice, title="Private")
    url = f"/api/documents/{doc['id']}"

    for response in (bob.get(url), bob.patch(url, json={"title": "x"}), bob.delete(url)):
        assert response.status_code == 404
        assert response.json() == {"detail": "Document not found"}
    assert bob.get("/api/documents").json() == {"owned": [], "shared": []}


def test_viewer_can_read_but_not_edit(alice: TestClient, carol: TestClient) -> None:
    doc = create_doc(alice, title="Read only")
    share(alice, doc["id"], "carol@ajaia.test", "viewer")

    assert carol.get(f"/api/documents/{doc['id']}").json()["role"] == "viewer"
    response = carol.patch(f"/api/documents/{doc['id']}", json={"content_html": "<p>hacked</p>"})
    assert response.status_code == 403
    assert alice.get(f"/api/documents/{doc['id']}").json()["content_html"] == ""


def test_editor_can_edit_but_not_share(alice: TestClient, bob: TestClient) -> None:
    doc = create_doc(alice)
    share(alice, doc["id"], "bob@ajaia.test", "editor")

    edit = bob.patch(f"/api/documents/{doc['id']}", json={"content_html": "<p>by bob</p>"})
    assert edit.status_code == 200
    reshare = bob.post(
        f"/api/documents/{doc['id']}/shares", json={"email": "carol@ajaia.test", "role": "viewer"}
    )
    assert reshare.status_code == 403
    assert bob.delete(f"/api/documents/{doc['id']}").status_code == 403


def test_owner_can_share_and_doc_appears_under_shared_for_recipient(
    alice: TestClient, bob: TestClient
) -> None:
    doc = create_doc(alice, title="Team notes")

    first = alice.post(
        f"/api/documents/{doc['id']}/shares", json={"email": " BOB@ajaia.test ", "role": "viewer"}
    )
    upgrade = alice.post(
        f"/api/documents/{doc['id']}/shares", json={"email": "bob@ajaia.test", "role": "editor"}
    )
    assert (first.status_code, upgrade.status_code) == (201, 200)

    listing = bob.get("/api/documents").json()
    assert listing["owned"] == []
    assert [(d["title"], d["role"], d["owner"]["email"]) for d in listing["shared"]] == [
        ("Team notes", "editor", "alice@ajaia.test")
    ]
    assert alice.get("/api/documents").json()["shared"] == []


def test_revoke_removes_access(alice: TestClient, bob: TestClient) -> None:
    doc = create_doc(alice)
    share(alice, doc["id"], "bob@ajaia.test", "editor")
    bob_id = bob.get("/api/auth/me").json()["id"]

    assert alice.delete(f"/api/documents/{doc['id']}/shares/{bob_id}").status_code == 204

    assert bob.get(f"/api/documents/{doc['id']}").status_code == 404
    assert bob.get("/api/documents").json()["shared"] == []


def test_shared_user_can_leave_but_owner_cannot(alice: TestClient, bob: TestClient) -> None:
    doc = create_doc(alice, title="Team doc")
    share(alice, doc["id"], "bob@ajaia.test", "editor")

    assert bob.delete(f"/api/documents/{doc['id']}/shares/me").status_code == 204

    assert bob.get(f"/api/documents/{doc['id']}").status_code == 404
    assert bob.get("/api/documents").json()["shared"] == []
    owner_leave = alice.delete(f"/api/documents/{doc['id']}/shares/me")
    assert owner_leave.status_code == 400
    assert owner_leave.json() == {"detail": "Owners cannot leave their own document"}
    assert alice.get(f"/api/documents/{doc['id']}").status_code == 200

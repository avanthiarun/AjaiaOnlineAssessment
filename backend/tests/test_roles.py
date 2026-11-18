"""The commenter role over HTTP, and transferring ownership."""

from fastapi.testclient import TestClient

from tests.helpers import create_doc, share


def test_commenter_can_read_but_not_edit(alice: TestClient, bob: TestClient) -> None:
    doc = create_doc(alice, title="Draft")
    share(alice, doc["id"], "bob@ajaia.test", "commenter")

    assert bob.get(f"/api/documents/{doc['id']}").json()["role"] == "commenter"
    assert [d["role"] for d in bob.get("/api/documents").json()["shared"]] == ["commenter"]
    assert bob.patch(f"/api/documents/{doc['id']}", json={"content_html": "<p>x</p>"}).status_code == 403
    assert alice.get(f"/api/documents/{doc['id']}/shares").json()["shares"][0]["role"] == "commenter"


def test_transfer_makes_the_target_owner_and_the_old_owner_an_editor(alice: TestClient, bob: TestClient) -> None:
    doc = create_doc(alice, title="Handover")
    share(alice, doc["id"], "bob@ajaia.test", "viewer")

    response = alice.post(f"/api/documents/{doc['id']}/transfer", json={"email": " BOB@ajaia.test "})

    assert response.status_code == 200
    assert response.json()["role"] == "editor"
    assert response.json()["owner"]["email"] == "bob@ajaia.test"
    access = bob.get(f"/api/documents/{doc['id']}/shares").json()
    assert access["owner"]["email"] == "bob@ajaia.test"
    assert [(s["user"]["email"], s["role"]) for s in access["shares"]] == [("alice@ajaia.test", "editor")]
    assert [d["title"] for d in bob.get("/api/documents").json()["owned"]] == ["Handover"]
    assert [(d["title"], d["role"]) for d in alice.get("/api/documents").json()["shared"]] == [("Handover", "editor")]
    # The new roles are enforced: alice can still edit but no longer share or delete.
    assert alice.patch(f"/api/documents/{doc['id']}", json={"content_html": "<p>ok</p>"}).status_code == 200
    assert alice.delete(f"/api/documents/{doc['id']}").status_code == 403
    assert bob.delete(f"/api/documents/{doc['id']}").status_code == 204


def test_transfer_is_refused_without_changing_anything(
    alice: TestClient, bob: TestClient, carol: TestClient
) -> None:
    doc = create_doc(alice)
    share(alice, doc["id"], "bob@ajaia.test", "editor")
    url = f"/api/documents/{doc['id']}/transfer"

    cases = [
        (alice, "carol@ajaia.test", 400, "Share the document with them before making them the owner"),
        (alice, "alice@ajaia.test", 400, "You already own this document"),
        (alice, "nobody@ajaia.test", 404, "No user with that email"),
        (bob, "bob@ajaia.test", 403, "You do not have permission to transfer this document"),
        (carol, "carol@ajaia.test", 404, "Document not found"),
    ]
    for client, email, code, detail in cases:
        response = client.post(url, json={"email": email})
        assert (response.status_code, response.json()["detail"]) == (code, detail), email

    access = alice.get(f"/api/documents/{doc['id']}/shares").json()
    assert access["owner"]["email"] == "alice@ajaia.test"
    assert [(s["user"]["email"], s["role"]) for s in access["shares"]] == [("bob@ajaia.test", "editor")]

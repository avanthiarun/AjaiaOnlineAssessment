"""Comments over HTTP: who may create, resolve and delete; validation; bodies are plain text."""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.helpers import create_doc, share


def comment(client: TestClient, doc_id: str, body: str = "Looks good", quote: str = "") -> dict[str, Any]:
    """Post a comment (asserts it was created)."""
    response = client.post(f"/api/documents/{doc_id}/comments", json={"body": body, "quote": quote})
    assert response.status_code == 201, response.text
    return response.json()


def url(doc_id: str, comment_id: str = "") -> str:
    return f"/api/documents/{doc_id}/comments" + (f"/{comment_id}" if comment_id else "")


@pytest.mark.parametrize(("role", "code"), [("editor", 201), ("commenter", 201), ("viewer", 403)])
def test_who_can_comment(alice: TestClient, bob: TestClient, carol: TestClient, role: str, code: int) -> None:
    doc = create_doc(alice)
    share(alice, doc["id"], "bob@ajaia.test", role)

    assert bob.post(url(doc["id"]), json={"body": "hi"}).status_code == code
    assert alice.post(url(doc["id"]), json={"body": "owner too"}).status_code == 201
    assert carol.post(url(doc["id"]), json={"body": "stranger"}).status_code == 404
    assert carol.get(url(doc["id"])).status_code == 404


def test_comment_keeps_quote_author_and_lists_oldest_first(alice: TestClient, bob: TestClient) -> None:
    doc = create_doc(alice)
    share(alice, doc["id"], "bob@ajaia.test", "commenter")

    first = comment(bob, doc["id"], body="  Why this number?  ", quote="  revenue grew 40%  ")
    comment(alice, doc["id"], body="Source is the Q3 report")

    assert (first["author"]["email"], first["quote"], first["body"], first["resolved"]) == (
        "bob@ajaia.test", "revenue grew 40%", "Why this number?", False
    )
    assert [c["body"] for c in alice.get(url(doc["id"])).json()] == ["Why this number?", "Source is the Q3 report"]


def test_editors_resolve_any_comment_and_others_only_their_own(
    alice: TestClient, bob: TestClient, carol: TestClient
) -> None:
    doc = create_doc(alice)
    share(alice, doc["id"], "bob@ajaia.test", "commenter")
    share(alice, doc["id"], "carol@ajaia.test", "commenter")
    by_bob = comment(bob, doc["id"])
    resolve = {"resolved": True}

    assert carol.patch(url(doc["id"], by_bob["id"]), json=resolve).status_code == 403  # commenter, not author
    assert bob.patch(url(doc["id"], by_bob["id"]), json=resolve).json()["resolved"] is True  # author
    share(alice, doc["id"], "carol@ajaia.test", "editor")
    assert carol.patch(url(doc["id"], by_bob["id"]), json={"resolved": False}).json()["resolved"] is False  # editor
    assert alice.patch(url(doc["id"], by_bob["id"]), json=resolve).status_code == 200  # owner


def test_only_the_author_or_owner_can_delete(alice: TestClient, bob: TestClient, carol: TestClient) -> None:
    doc = create_doc(alice)
    share(alice, doc["id"], "bob@ajaia.test", "commenter")
    share(alice, doc["id"], "carol@ajaia.test", "editor")
    first, second = comment(bob, doc["id"]), comment(bob, doc["id"])

    assert carol.delete(url(doc["id"], first["id"])).status_code == 403  # editors can't delete others'
    assert bob.delete(url(doc["id"], first["id"])).status_code == 204  # author
    assert alice.delete(url(doc["id"], second["id"])).status_code == 204  # owner
    assert alice.get(url(doc["id"])).json() == []


def test_permission_flags_tell_the_ui_what_each_user_may_do(alice: TestClient, bob: TestClient) -> None:
    doc = create_doc(alice)
    share(alice, doc["id"], "bob@ajaia.test", "commenter")
    comment(alice, doc["id"], body="by alice")
    comment(bob, doc["id"], body="by bob")

    flags = {c["body"]: (c["can_resolve"], c["can_delete"]) for c in bob.get(url(doc["id"])).json()}
    assert flags == {"by alice": (False, False), "by bob": (True, True)}


def test_comment_ids_are_scoped_to_their_document(alice: TestClient) -> None:
    doc, other = create_doc(alice), create_doc(alice)
    note = comment(alice, doc["id"])

    response = alice.delete(url(other["id"], note["id"]))
    assert (response.status_code, response.json()) == (404, {"detail": "Comment not found"})


@pytest.mark.parametrize(
    "payload",
    [{"body": ""}, {"body": "   "}, {"body": "x" * 2001}, {"body": "ok", "quote": "q" * 501}, {}],
    ids=["empty", "blank", "body-too-long", "quote-too-long", "missing"],
)
def test_invalid_comments_are_rejected(alice: TestClient, payload: dict[str, str]) -> None:
    doc = create_doc(alice)

    assert alice.post(url(doc["id"]), json=payload).status_code == 422
    assert alice.get(url(doc["id"])).json() == []


def test_longest_allowed_body_is_accepted(alice: TestClient) -> None:
    doc = create_doc(alice)

    assert comment(alice, doc["id"], body="x" * 2000, quote="q" * 500)["body"] == "x" * 2000


def test_html_in_a_comment_is_stored_and_returned_as_plain_text(alice: TestClient) -> None:
    doc = create_doc(alice)
    html = '<img src=x onerror="alert(1)"><b>bold?</b> & <script>alert(2)</script>'

    created = comment(alice, doc["id"], body=html, quote="<i>quoted</i>")

    listed = alice.get(url(doc["id"])).json()[0]
    assert created["body"] == listed["body"] == html  # not sanitized, not rendered: React escapes it
    assert listed["quote"] == "<i>quoted</i>"

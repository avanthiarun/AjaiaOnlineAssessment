"""Optimistic concurrency: stale content saves get 409 instead of silently overwriting."""

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text

from app.db import add_missing_columns
from tests.helpers import create_doc, share

CONFLICT = "This document was changed by someone else."


def test_stale_save_gets_409_and_fresh_or_unversioned_saves_succeed(alice: TestClient, bob: TestClient) -> None:
    doc = create_doc(alice, title="Shared plan")
    share(alice, doc["id"], "bob@ajaia.test", "editor")
    url = f"/api/documents/{doc['id']}"
    alice_view = alice.get(url).json()
    bob_view = bob.get(url).json()
    assert alice_view["version"] == bob_view["version"] == 1

    bob_save = bob.patch(url, json={"content_html": "<p>Bob's text</p>", "base_version": 1})
    assert bob_save.status_code == 200
    assert bob_save.json()["version"] == 2

    stale = alice.patch(url, json={"content_html": "<p>Alice's text</p>", "base_version": 1})
    assert stale.status_code == 409
    assert stale.json() == {"detail": CONFLICT, "current_version": 2}
    assert alice.get(url).json()["content_html"] == "<p>Bob's text</p>"  # nothing was overwritten

    fresh = alice.patch(url, json={"content_html": "<p>Alice, merged</p>", "base_version": 2})
    assert fresh.status_code == 200
    assert fresh.json()["version"] == 3

    unversioned = bob.patch(url, json={"content_html": "<p>Old client</p>"})
    assert unversioned.status_code == 200
    assert unversioned.json()["version"] == 4
    assert unversioned.json()["content_html"] == "<p>Old client</p>"


def test_title_rename_needs_no_version_and_does_not_bump_it(alice: TestClient) -> None:
    doc = create_doc(alice)
    url = f"/api/documents/{doc['id']}"

    renamed = alice.patch(url, json={"title": "Renamed"})
    save = alice.patch(url, json={"content_html": "<p>still fine</p>", "base_version": 1})

    assert renamed.status_code == 200 and renamed.json()["version"] == 1
    assert save.status_code == 200 and save.json()["version"] == 2
    assert alice.get("/api/documents").json()["owned"][0]["version"] == 2


def test_add_missing_columns_is_idempotent(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{(tmp_path / 'old.db').as_posix()}")
    with engine.begin() as conn:  # a documents table from before the version column existed
        conn.execute(text("CREATE TABLE documents (id VARCHAR(36) PRIMARY KEY, title VARCHAR(200))"))
        conn.execute(text("INSERT INTO documents (id, title) VALUES ('d1', 'Old doc')"))

    add_missing_columns(engine)
    add_missing_columns(engine)

    columns = [c["name"] for c in inspect(engine).get_columns("documents")]
    assert columns.count("version") == 1
    with engine.connect() as conn:
        assert conn.execute(text("SELECT version FROM documents WHERE id = 'd1'")).scalar_one() == 1
    engine.dispose()
